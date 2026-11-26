def test_health_returns_ok(phone_client):
    response = phone_client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
