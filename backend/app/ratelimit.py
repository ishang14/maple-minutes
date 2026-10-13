"""A small in-memory sliding-window rate limiter that protects the free LLM quota behind /ask.

Two limits are applied to every /ask: one per client IP (so one visitor cannot burn the quota) and one
global (so many visitors together cannot). In-memory means the counts live in this process only, which is
right for a single-instance free host; use a shared store (Redis) if the app ever runs on several instances.
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.config import Settings


class SlidingWindowLimiter:
    """Allow at most `limit` hits per key in any window of `window` seconds. limit <= 0 disables it."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit, self.window, self._clock = limit, window, clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, int]:
        """Record an attempt. Returns (allowed, seconds to wait if refused). A refused attempt is not counted."""
        if self.limit <= 0:
            return True, 0
        now = self._clock()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and q[0] <= now - self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(1, math.ceil(q[0] + self.window - now))
            q.append(now)
            if len(self._hits) > 5000:  # forget visitors whose window has fully passed
                self._prune(now)
            return True, 0

    def _prune(self, now: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= now - self.window]:
            del self._hits[k]


def client_ip(request: Request, trust_proxy: bool) -> str:
    """The caller's address. Behind a proxy (Hugging Face, Cloudflare) the real address is in X-Forwarded-For; the
    proxy appends it, so the LAST entry is the one the proxy saw and cannot be spoofed by the caller."""
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"


def _wait_text(seconds: int) -> str:
    return f"{seconds} seconds" if seconds < 90 else f"{math.ceil(seconds / 60)} minutes"


class AskLimits:
    """The per-IP and global limits for /ask, built from settings."""

    def __init__(self, cfg: Settings, clock: Callable[[], float] = time.monotonic):
        self.cfg = cfg
        self.per_ip = SlidingWindowLimiter(cfg.ask_limit_per_ip, cfg.ask_limit_window_seconds, clock)
        self.global_ = SlidingWindowLimiter(cfg.ask_limit_global, cfg.ask_limit_global_window_seconds, clock)

    def check(self, request: Request) -> None:
        """Raise HTTP 429 (with Retry-After) if this /ask is over a limit."""
        ok, wait = self.per_ip.hit(client_ip(request, self.cfg.trust_proxy_headers))
        if not ok:
            raise HTTPException(
                429, headers={"Retry-After": str(wait)},
                detail=f"You have asked a lot of questions in a short time. Please try again in {_wait_text(wait)}.")
        ok, wait = self.global_.hit("*")
        if not ok:
            raise HTTPException(
                429, headers={"Retry-After": str(wait)},
                detail="The free question quota is used up for now. Please try again in "
                       f"{_wait_text(wait)}; searching still works.")
