def test_unknown_api_route_returns_structured_404(client):
    response = client.get("/api/this-route-does-not-exist")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["error"]["code"] == 404
    assert isinstance(payload["error"]["message"], str)


def test_method_not_allowed_returns_structured_405(client):
    # /api/health only allows GET.
    response = client.post("/api/health")

    assert response.status_code == 405
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["error"]["code"] == 405


def test_rate_limit_headers_present_on_limited_route(client):
    response = client.get("/api/debug/breeze-auth")

    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers


def test_readiness_reports_websocket_and_breeze_state(client):
    response = client.get("/api/health/readiness")

    assert response.status_code == 200
    checks = response.get_json()["checks"]
    assert checks["breeze"] == "not_configured"
    assert checks["websocket"] in {"offline", "connecting", "live", "degraded"}


def test_deployment_reports_master_contract_and_websocket(client):
    response = client.get("/api/health/deployment")

    assert response.status_code == 200
    checks = response.get_json()["checks"]
    assert "master_contract" in checks
    assert "websocket" in checks
