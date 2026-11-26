import pytest

from server.auth import TOKEN_HEADER

ROUTES = [
    ("get", "/api/ping", {}),
    ("post", "/api/upload", {"files": {"file": ("a.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")}}),
]


def _call(client, method, path, kwargs, headers=None):
    return getattr(client, method)(path, headers=headers or {}, **kwargs)


@pytest.mark.parametrize(("method", "path", "kwargs"), ROUTES)
def test_missing_token_is_rejected(phone_client, method, path, kwargs):
    assert _call(phone_client, method, path, kwargs).status_code == 401


@pytest.mark.parametrize(("method", "path", "kwargs"), ROUTES)
@pytest.mark.parametrize("bad", ["", "wrong", "x" * 43, "tökén"])
def test_wrong_token_is_rejected(phone_client, method, path, kwargs, bad):
    headers = {TOKEN_HEADER: bad.encode("utf-8")}
    assert _call(phone_client, method, path, kwargs, headers).status_code == 401


@pytest.mark.parametrize(("method", "path", "kwargs"), ROUTES)
def test_valid_token_is_accepted(phone_client, tokens, method, path, kwargs):
    headers = {TOKEN_HEADER: tokens.current}
    assert _call(phone_client, method, path, kwargs, headers).status_code == 200


def test_rejected_upload_writes_nothing(phone_client, settings):
    _call(phone_client, *ROUTES[1], headers={TOKEN_HEADER: "wrong"})
    assert list(settings.inbox_dir.iterdir()) == []


def test_token_in_query_string_is_not_accepted(phone_client, tokens):
    assert phone_client.get(f"/api/ping?t={tokens.current}").status_code == 401


def test_health_needs_no_token(phone_client):
    assert phone_client.get("/api/health").status_code == 200
