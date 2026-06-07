def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "APTRADES v2"


def test_readiness(client):
    response = client.get("/api/health/readiness")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["checks"]["api"] == "online"
