import json

from app import create_app


def _client_with_db(database_url: str):
    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=database_url)
    return app.test_client()


_SAMPLE_LEGS = [
    {"action": "sell", "right": "call", "strike": 23300, "quantity": 1, "premium": 100},
    {"action": "buy", "right": "call", "strike": 23400, "quantity": 1, "premium": 50},
]

_SINGLE_SHORT_CALL = [
    {"action": "sell", "right": "call", "strike": 23300, "quantity": 1, "premium": 100}
]


def test_list_strategies_returns_empty_when_no_strategies(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strat.sqlite'}"
    with _client_with_db(database_url) as client:
        response = client.get("/api/strategies")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["strategies"] == []


def test_create_strategy_returns_created_payload(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strat.sqlite'}"
    body = {
        "name": "Bear Call Spread",
        "underlying": "NIFTY",
        "exchange_code": "NFO",
        "expiry": "2026-06-30",
        "legs": _SAMPLE_LEGS,
    }
    with _client_with_db(database_url) as client:
        response = client.post("/api/strategies", json=body)
    assert response.status_code == 201
    payload = response.get_json()
    assert payload["status"] == "ok"
    strategy = payload["strategy"]
    assert strategy["name"] == "Bear Call Spread"
    assert strategy["underlying"] == "NIFTY"
    assert len(strategy["legs"]) == 2
    assert strategy["net_premium"] == 50.0
    assert "id" in strategy
    assert "created_at" in strategy


def test_create_strategy_missing_name_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strat.sqlite'}"
    body = {"underlying": "NIFTY", "expiry": "2026-06-30", "legs": _SAMPLE_LEGS}
    with _client_with_db(database_url) as client:
        response = client.post("/api/strategies", json=body)
    assert response.status_code == 400
    assert "required" in response.get_json()["error"]


def test_create_strategy_invalid_legs_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strat.sqlite'}"
    body = {
        "name": "Bad Strategy",
        "underlying": "NIFTY",
        "expiry": "2026-06-30",
        "legs": [{"action": "buy", "right": "invalid", "strike": 23300, "quantity": 1, "premium": 50}],
    }
    with _client_with_db(database_url) as client:
        response = client.post("/api/strategies", json=body)
    assert response.status_code == 400
    assert "right" in response.get_json()["error"]


def test_delete_strategy_removes_it(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strat.sqlite'}"
    body = {
        "name": "Temp Strategy",
        "underlying": "BANKNIFTY",
        "exchange_code": "NFO",
        "expiry": "2026-06-30",
        "legs": _SAMPLE_LEGS,
    }
    with _client_with_db(database_url) as client:
        create_response = client.post("/api/strategies", json=body)
        strategy_id = create_response.get_json()["strategy"]["id"]
        delete_response = client.delete(f"/api/strategies/{strategy_id}")
        list_response = client.get("/api/strategies")

    assert delete_response.status_code == 200
    assert delete_response.get_json()["deleted_id"] == strategy_id
    assert list_response.get_json()["strategies"] == []


def test_payoff_preview_returns_curve_and_metrics(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strat.sqlite'}"
    body = {"legs": _SINGLE_SHORT_CALL}
    with _client_with_db(database_url) as client:
        response = client.post("/api/strategies/payoff", json=body)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["net_premium"] == 100.0
    assert len(payload["curve"]) == 50
    assert payload["max_profit"] == 100.0
    assert payload["max_loss"] < 0
    assert len(payload["breakevens"]) >= 1
    assert abs(payload["breakevens"][0] - 23400.0) < 300


def test_payoff_missing_legs_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strat.sqlite'}"
    with _client_with_db(database_url) as client:
        response = client.post("/api/strategies/payoff", json={})
    assert response.status_code == 400
    assert "legs" in response.get_json()["error"]
