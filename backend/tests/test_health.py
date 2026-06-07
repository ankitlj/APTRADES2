from unittest.mock import patch


def test_health(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "APTRADES v2"


def test_readiness(client):
    with patch("app.api.health.check_database", return_value="not_configured"), patch(
        "app.api.health.check_redis", return_value="not_configured"
    ):
        response = client.get("/api/health/readiness")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["checks"]["api"] == "online"
    assert payload["checks"]["postgres"] == "not_configured"
    assert payload["checks"]["redis"] == "not_configured"


def test_deployment(client):
    with patch("app.api.health.check_database", return_value="offline"), patch(
        "app.api.health.check_redis", return_value="online"
    ):
        response = client.get("/api/health/deployment")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["checks"]["api"] == "online"
    assert payload["checks"]["postgres"] == "offline"
    assert payload["checks"]["redis"] == "online"
