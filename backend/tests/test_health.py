from unittest.mock import patch

from app.db import normalize_database_url


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


def test_normalize_database_url_uses_psycopg_driver():
    url = "postgresql://user:pass@host:5432/dbname"

    assert normalize_database_url(url) == "postgresql+psycopg://user:pass@host:5432/dbname"


def test_breeze_auth_returns_not_configured(client):
    response = client.get("/api/debug/breeze-auth")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "not_configured"
    assert payload["configured"] is False


def test_breeze_test_returns_not_configured_symbols(client):
    response = client.get("/api/debug/breeze-test")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["configured"] is False
    assert payload["status"] == "error"
    assert len(payload["symbols"]) == 5
