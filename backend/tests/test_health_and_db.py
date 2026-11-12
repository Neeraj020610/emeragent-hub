def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "Emergent Central Hub" in data["service"]


def test_openapi_docs_accessible(client):
    response = client.get("/api/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "Emergent Central Hub"
    assert "/api/v1/auth/login" in spec["paths"]
    assert "/api/v1/accounts" in spec["paths"]
    assert "/api/v1/reports/summary" in spec["paths"]
