def test_diagnosis_trace_requires_route_param(client):
    response = client.get("/api/diagnosis/trace")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"


def test_diagnosis_trace_health_returns_timing(client):
    response = client.get("/api/diagnosis/trace?route=health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["route"] == "health"
    assert isinstance(payload["elapsed_ms"], (int, float))
    assert isinstance(payload["result"]["service"], str)


def test_diagnosis_trace_readiness_returns_checks(client):
    response = client.get("/api/diagnosis/trace?route=readiness")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "postgres" in payload["result"]
    assert "redis" in payload["result"]


def test_diagnosis_trace_breeze_auth_returns_not_configured(client):
    response = client.get("/api/diagnosis/trace?route=breeze-auth")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["result"]["status"] in ("not_configured", "error")


def test_diagnosis_trace_unknown_route_returns_400(client):
    response = client.get("/api/diagnosis/trace?route=nonexistent")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"


def test_diagnosis_cache_returns_status(client):
    response = client.get("/api/diagnosis/cache")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] in ("online", "not_configured", "offline")


def test_diagnosis_broker_returns_not_configured(client):
    response = client.get("/api/diagnosis/broker")
    assert response.status_code == 200
    payload = response.get_json()
    assert "configured" in payload
    assert payload["configured"] is False


def test_diagnosis_worker_returns_state(client):
    response = client.get("/api/diagnosis/worker")
    assert response.status_code == 200
    payload = response.get_json()
    assert "state" in payload
    assert payload["state"] in ("offline", "connecting", "live", "degraded")


def test_diagnosis_full_runs_all_checks(client):
    response = client.get("/api/diagnosis/full")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "checks" in payload
    assert "api" in payload["checks"]
    assert "worker" in payload


def test_diagnosis_timing_list_empty_on_start(client):
    response = client.get("/api/diagnosis/timing")
    assert response.status_code == 200
    payload = response.get_json()
    assert "records" in payload


def test_diagnosis_timing_clear_works(client):
    response = client.delete("/api/diagnosis/timing")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["cleared"] is True


def test_diagnosis_collects_timing_after_trace(client):
    client.get("/api/diagnosis/trace?route=health")
    response = client.get("/api/diagnosis/timing")
    assert response.status_code == 200
    payload = response.get_json()
    # The trace should have created at least one timing record
    record_names = [r["name"] for r in payload["records"]]
    assert any("trace" in n for n in record_names)
