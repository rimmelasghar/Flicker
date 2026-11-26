from fastapi.testclient import TestClient

from server.config import Settings
from server.main import create_phone_app


def test_health_returns_ok(tmp_path):
    settings = Settings(host_ip="127.0.0.1", data_dir=tmp_path / "data", inbox_dir=tmp_path)
    response = TestClient(create_phone_app(settings)).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
