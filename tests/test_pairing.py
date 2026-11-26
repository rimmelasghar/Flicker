from dataclasses import replace

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
    assert "viewBox" in response.text
    assert "https://192.168.1.50:8443/" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_pair_page_rejects_foreign_host_header(settings, tokens):
    client = TestClient(create_pair_app(settings, tokens), base_url="http://evil.example:8080")
    assert client.get("/pair").status_code == 400


@pytest.fixture
def folder_client(settings, tokens):
    (settings.inbox_dir / "Photos").mkdir()
    (settings.inbox_dir / "Work").mkdir()
    labelled = replace(settings, inbox_label="C:/Users/me/Desktop")
    return TestClient(create_pair_app(labelled, tokens), base_url="http://localhost:8080")


def test_folder_listing(folder_client):
    body = folder_client.get("/api/folders").json()
    assert body == {
        "path": "",
        "display": "C:/Users/me/Desktop",
        "folders": ["Photos", "Work"],
        "selected": "",
    }


def test_select_and_create_folder(folder_client, settings):
    created = folder_client.post("/api/folders", json={"parent": "Photos", "name": "Flick"})
    assert created.json() == {"path": "Photos/Flick"}
    chosen = folder_client.put("/api/save-folder", json={"path": "Photos/Flick"})
    assert chosen.json() == {"path": "Photos/Flick", "display": "C:/Users/me/Desktop/Photos/Flick"}
    assert folder_client.get("/api/save-folder").json()["path"] == "Photos/Flick"


def test_folder_api_refuses_escape(folder_client):
    assert folder_client.get("/api/folders", params={"path": "../.."}).status_code == 400
    assert folder_client.put("/api/save-folder", json={"path": ".."}).status_code == 400


def test_folder_changes_refuse_cross_site(folder_client):
    evil = {"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"}
    assert (
        folder_client.put("/api/save-folder", json={"path": "Work"}, headers=evil).status_code
        == 403
    )
    response = folder_client.post("/api/folders", json={"name": "x"}, headers=evil)
    assert response.status_code == 403


def test_rotate_changes_token(pair_client, tokens):
    old = tokens.current
    response = pair_client.post("/api/token/rotate")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert tokens.current != old


def test_rotate_refuses_cross_site_post(pair_client, tokens):
    old = tokens.current
    response = pair_client.post(
        "/api/token/rotate",
        headers={"Origin": "https://evil.example", "Sec-Fetch-Site": "cross-site"},
    )
    assert response.status_code == 403
    assert tokens.current == old


def test_rotate_allows_same_origin_fetch(pair_client):
    response = pair_client.post(
        "/api/token/rotate",
        headers={"Origin": "http://localhost:8080", "Sec-Fetch-Site": "same-origin"},
    )
    assert response.status_code == 200
