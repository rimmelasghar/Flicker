import pytest


def test_root_serves_phone_page_without_token(phone_client):
    response = phone_client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert '<script type="module" src="app.js">' in response.text


@pytest.mark.parametrize(
    ("path", "mime"),
    [
        ("/app.js", "text/javascript"),
        ("/styles.css", "text/css"),
        ("/manifest.json", "application/json"),
        ("/icons/icon-192.png", "image/png"),
        ("/icons/apple-touch-icon.png", "image/png"),
    ],
)
def test_static_assets_have_correct_type(phone_client, path, mime):
    response = phone_client.get(path)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(mime)


def test_api_routes_are_not_shadowed_by_static_files(phone_client):
    assert phone_client.get("/api/ping").status_code == 401
    assert phone_client.get("/api/health").json() == {"ok": True}


def test_static_files_cannot_escape_web_dir(phone_client):
    assert phone_client.get("/../server/auth.py").status_code == 404
