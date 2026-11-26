from server import __version__
from server.auth import TOKEN_HEADER


def test_health_returns_ok(phone_client):
    response = phone_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_ping_returns_host_and_version(phone_client, tokens):
    response = phone_client.get("/api/ping", headers={TOKEN_HEADER: tokens.current})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "host": "192.168.1.50", "version": __version__}
