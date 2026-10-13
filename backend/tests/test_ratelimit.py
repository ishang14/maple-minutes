from starlette.requests import Request

from app.config import settings
from app.ratelimit import AskLimits, SlidingWindowLimiter, client_ip
from tests.test_api import HITS, FakeLLM, make_client


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_the_limit_then_refuses_with_a_wait_time():
    clock = Clock()
    lim = SlidingWindowLimiter(3, 10, clock)
    assert [lim.hit("a") for _ in range(3)] == [(True, 0)] * 3
    clock.now += 4
    assert lim.hit("a") == (False, 6)  # the oldest hit expires 6 s from now


def test_the_window_slides_so_capacity_returns_gradually():
    clock = Clock()
    lim = SlidingWindowLimiter(2, 10, clock)
    assert lim.hit("a")[0]          # t = 0
    clock.now += 3
    assert lim.hit("a")[0]          # t = 3
    clock.now += 4
    assert not lim.hit("a")[0]      # t = 7: both hits are still inside the 10 s window
    clock.now += 4
    assert lim.hit("a")[0]          # t = 11: the hit at t = 0 has expired, the one at t = 3 has not
    assert not lim.hit("a")[0]      # so only one slot came back


def test_refused_attempts_are_not_counted_and_keys_are_independent():
    clock = Clock()
    lim = SlidingWindowLimiter(1, 10, clock)
    assert lim.hit("a")[0]
    for _ in range(5):
        assert not lim.hit("a")[0]  # hammering must not extend the wait
    clock.now += 10
    assert lim.hit("a")[0]
    assert lim.hit("b")[0]  # another visitor has their own allowance


def test_a_limit_of_zero_turns_the_limiter_off():
    lim = SlidingWindowLimiter(0, 10)
    assert all(lim.hit("a") == (True, 0) for _ in range(100))


def test_idle_visitors_are_forgotten_so_memory_stays_bounded():
    clock = Clock()
    lim = SlidingWindowLimiter(1, 10, clock)
    for i in range(5001):
        lim.hit(f"ip{i}")
    clock.now += 11
    lim.hit("fresh")  # triggers the clean-up
    assert len(lim._hits) < 100


def request_with(headers: dict[str, str], host: str = "9.9.9.9") -> Request:
    return Request({"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
                    "client": (host, 1234)})


def test_client_ip_uses_the_last_forwarded_entry_only_when_the_proxy_is_trusted():
    req = request_with({"X-Forwarded-For": "6.6.6.6, 1.2.3.4"})  # the first entry is what the caller claimed
    assert client_ip(req, trust_proxy=True) == "1.2.3.4"
    assert client_ip(req, trust_proxy=False) == "9.9.9.9"
    assert client_ip(request_with({}), trust_proxy=True) == "9.9.9.9"  # no header: fall back to the socket


def test_ask_limits_per_ip_and_global_have_distinct_messages(monkeypatch):
    monkeypatch.setattr(settings, "ask_limit_per_ip", 2)
    monkeypatch.setattr(settings, "ask_limit_global", 3)
    limits = AskLimits(settings, Clock())
    from fastapi import HTTPException

    def call(host):
        try:
            limits.check(request_with({}, host))
            return None
        except HTTPException as e:
            return e

    assert call("1.1.1.1") is None and call("1.1.1.1") is None
    per_ip = call("1.1.1.1")
    assert per_ip.status_code == 429 and "asked a lot of questions" in per_ip.detail
    assert int(per_ip.headers["Retry-After"]) > 0
    assert call("2.2.2.2") is None  # a different visitor is fine... until everyone together hits the cap
    everyone = call("3.3.3.3")
    assert everyone.status_code == 429 and "quota is used up" in everyone.detail and "searching still works" in everyone.detail


def post_ask(client, **headers):
    return client.post("/ask", json={"query": "carbon pricing"}, headers=headers)


def test_ask_endpoint_returns_429_before_streaming_and_search_is_not_limited(monkeypatch):
    monkeypatch.setattr(settings, "ask_limit_per_ip", 2)
    client, *_ = make_client(HITS, FakeLLM(["ok [1]."]))
    assert post_ask(client).status_code == 200 and post_ask(client).status_code == 200
    blocked = post_ask(client)
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"].isdigit()
    assert "try again in" in blocked.json()["detail"]
    assert not blocked.headers["content-type"].startswith("text/event-stream")  # a plain error, not a stream
    for _ in range(5):  # /search spends no LLM quota
        assert client.post("/search", json={"query": "carbon pricing"}).status_code == 200


def test_the_limit_is_per_visitor_when_behind_a_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "ask_limit_per_ip", 1)
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    client, *_ = make_client(HITS, FakeLLM(["ok [1]."]))
    assert post_ask(client, **{"X-Forwarded-For": "5.5.5.5"}).status_code == 200
    assert post_ask(client, **{"X-Forwarded-For": "5.5.5.5"}).status_code == 429
    assert post_ask(client, **{"X-Forwarded-For": "7.7.7.7"}).status_code == 200  # someone else


def test_a_forwarded_header_is_ignored_when_the_proxy_is_not_trusted(monkeypatch):
    monkeypatch.setattr(settings, "ask_limit_per_ip", 1)
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    client, *_ = make_client(HITS, FakeLLM(["ok [1]."]))
    assert post_ask(client, **{"X-Forwarded-For": "5.5.5.5"}).status_code == 200
    # a caller cannot dodge the limit by inventing a new address
    assert post_ask(client, **{"X-Forwarded-For": "8.8.8.8"}).status_code == 429


def test_limits_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ask_limit_per_ip", 0)
    monkeypatch.setattr(settings, "ask_limit_global", 0)
    client, *_ = make_client(HITS, FakeLLM(["ok [1]."]))
    assert all(post_ask(client).status_code == 200 for _ in range(30))


def test_the_default_limits_are_on_and_sensible():
    assert settings.ask_limit_per_ip > 0 and settings.ask_limit_global >= settings.ask_limit_per_ip
