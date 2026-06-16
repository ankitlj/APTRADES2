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


def test_diagnosis_token_verify_requires_symbol_and_exchange(client):
    response = client.get("/api/diagnosis/token-verify")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"

    response = client.get("/api/diagnosis/token-verify?symbol=NIFTY")
    assert response.status_code == 400

    response = client.get("/api/diagnosis/token-verify?exchange=NFO")
    assert response.status_code == 400


def test_diagnosis_token_verify_returns_structured_output(client):
    response = client.get("/api/diagnosis/token-verify?symbol=NIFTY&exchange=NFO&product_type=futures")
    payload = response.get_json()
    # Without a configured DATABASE_URL the endpoint returns 400.
    if response.status_code == 400:
        assert payload["status"] == "error"
        return
    assert response.status_code == 200
    assert payload["status"] == "ok"
    diag = payload["diagnosis"]
    assert diag["requested"]["symbol"] == "NIFTY"
    assert diag["requested"]["exchange"] == "NFO"
    assert "verdict" in diag
    assert diag["verdict"] in ("exact_match", "resolved_but_multiple_related_rows", "stale_token_suspected", "missing_match", "candidate_scan_failed")
    # Additional comparison fields must be present
    assert "exact_candidate_count" in diag
    assert "related_candidate_count" in diag
    assert "matching_candidate_ids" in diag
    assert "resolved_token_found_in_candidates" in diag
    assert isinstance(diag["resolved_token_found_in_candidates"], bool)
    assert "verdict_reason" in diag
    assert isinstance(diag["verdict_reason"], str)


def test_diagnosis_token_verify_banknifty(client):
    """BANKNIFTY resolves to an NFO futures contract with a token."""
    response = client.get("/api/diagnosis/token-verify?symbol=BANKNIFTY&exchange=NFO&product_type=futures")
    payload = response.get_json()
    if response.status_code == 400:
        assert payload["status"] == "error"
        return
    assert response.status_code == 200
    assert payload["status"] == "ok"
    diag = payload["diagnosis"]
    assert diag["requested"]["symbol"] == "BANKNIFTY"
    if diag["verdict"] in ("exact_match", "resolved_but_multiple_related_rows"):
        assert diag["resolved"]["token"] is not None


def test_diagnosis_token_verify_verdict_includes_comparison_fields(client):
    """Verdict must include exact/related counts and a reason string regardless of outcome."""
    response = client.get("/api/diagnosis/token-verify?symbol=SOMETHING_UNLIKELY&exchange=NFO&product_type=futures")
    payload = response.get_json()
    if response.status_code == 400:
        assert payload["status"] == "error"
        return
    assert response.status_code == 200
    diag = payload["diagnosis"]
    assert "exact_candidate_count" in diag
    assert "related_candidate_count" in diag
    assert "matching_candidate_ids" in diag
    assert "resolved_token_found_in_candidates" in diag
    assert "verdict_reason" in diag
    # The verdict should be one of the valid values
    assert diag["verdict"] in ("exact_match", "resolved_but_multiple_related_rows", "stale_token_suspected", "missing_match", "candidate_scan_failed")
