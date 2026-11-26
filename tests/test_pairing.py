import pytest
from fastapi.testclient import TestClient

from server.pairing import create_pair_app, pairing_url


@pytest.fixture
def pair_client(settings, tokens):
    return TestClient(create_pair_app(settings, tokens), base_url="http://localhost:8080")


def test_pairing_url_carries_token_in_fragment(settings, tokens):
    url = pairing_url(settings, tokens.current)
    assert url == f"https://192.168.1.50:8443/#t={tokens.current}"


def test_pair_page_shows_qr_code(pair_client):
    response = pair_client.get("/pair")
    assert response.status_code == 200
    assert "<svg" in response.text
    assert "https://192.168.1.50:8443/" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_pair_page_rejects_foreign_host_header(settings, tokens):
    client = TestClient(create_pair_app(settings, tokens), base_url="http://evil.example:8080")
    assert client.get("/pair").status_code == 400
