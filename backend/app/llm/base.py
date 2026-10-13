"""LLM provider interface plus the shared HTTP streaming, error handling and retry/fallback."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator

import httpx

Messages = list[dict]  # [{"role": "system" | "user" | "assistant", "content": str}, ...]


class LLMError(Exception):
    """A provider failure with a message that is safe to show to the user."""


class LLMRateLimitError(LLMError):
    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def stream(self, messages: Messages) -> Iterator[str]:
        """Yield the answer as text fragments. Raise LLMError / LLMRateLimitError on failure."""


class HTTPStreamProvider(LLMProvider):
    """Providers that stream over one HTTP request. Subclasses build the request and parse lines."""

    def __init__(self, timeout: float = 60.0, client: httpx.Client | None = None):
        self.timeout = timeout
        self._client = client

    @abstractmethod
    def build_request(self, messages: Messages) -> tuple[str, dict, dict]:
        """Return (url, headers, json_body)."""

    @abstractmethod
    def parse_line(self, line: str) -> str | None:
        """Return the text carried by one streamed line, or None if it carries none."""

    def stream(self, messages: Messages) -> Iterator[str]:
        url, headers, body = self.build_request(messages)
        client = self._client or httpx.Client(timeout=self.timeout)
        try:
            with client.stream("POST", url, headers=headers, json=body) as r:
                if r.status_code != 200:
                    r.read()
                    raise self.error_for(r)
                for line in r.iter_lines():
                    text = self.parse_line(line)
                    if text:
                        yield text
        except httpx.TimeoutException as e:
            raise LLMError(f"{self.name} timed out after {self.timeout:.0f}s.") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Could not reach {self.name}: {e.__class__.__name__}.") from e
        finally:
            if self._client is None:
                client.close()

    def error_for(self, r: httpx.Response) -> LLMError:
        if r.status_code == 429:
            try:
                retry_after = float(r.headers.get("retry-after", ""))
            except ValueError:
                retry_after = None
            return LLMRateLimitError(
                f"{self.name} rate limit reached (free tier). Please try again in a moment.",
                retry_after)
        if r.status_code in (401, 403):
            return LLMError(f"{self.name} rejected the API key. Check the key in the server settings.")
        if r.status_code == 404:
            return LLMError(f"{self.name} could not find the configured model.")
        return LLMError(f"{self.name} returned an error (HTTP {r.status_code}).")


def stream_with_fallback(providers: list[LLMProvider], messages: Messages, max_retries: int = 1,
                         max_wait: float = 5.0,
                         sleep: Callable[[float], None] = time.sleep) -> Iterator[str]:
    """Stream from the first provider that works.

    A rate limit is retried (waiting retry_after, capped at max_wait) up to max_retries times,
    then the next provider is tried. Any failure after text has started streaming is raised as is,
    because switching providers mid-answer would splice two different answers together.
    """
    last: LLMError | None = None
    for provider in providers:
        for attempt in range(max_retries + 1):
            started = False
            try:
                for piece in provider.stream(messages):
                    started = True
                    yield piece
                return
            except LLMRateLimitError as e:
                if started:
                    raise
                last = e
                if attempt < max_retries:
                    sleep(min(e.retry_after or 1.0, max_wait))
            except LLMError as e:
                if started:
                    raise
                last = e
                break  # not a rate limit: retrying the same provider will not help
    raise last or LLMError("No LLM provider is configured.")
