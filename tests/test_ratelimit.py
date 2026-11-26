from fastapi.testclient import TestClient

from server.main import create_phone_app
from server.ratelimit import RateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_bucket_allows_burst_then_refills():
    clock = FakeClock()
    limiter = RateLimiter(burst=3, per_second=1, clock=clock)
    assert [limiter.allow() for _ in range(4)] == [True, True, True, False]
    assert limiter.retry_after() == 1
    clock.now = 1.0
    assert limiter.allow() is True
    assert limiter.allow() is False


def test_api_returns_429_with_retry_after(settings, tokens):
    limiter = RateLimiter(burst=2, per_second=0.5, clock=FakeClock())
    client = TestClient(create_phone_app(settings, tokens, limiter))
    codes = [client.get("/api/health").status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    response = client.get("/api/ping")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "2"


def test_page_and_assets_are_not_rate_limited(settings, tokens):
    limiter = RateLimiter(burst=1, per_second=0, clock=FakeClock())
    client = TestClient(create_phone_app(settings, tokens, limiter))
    client.get("/api/health")
    assert all(client.get("/").status_code == 200 for _ in range(5))
