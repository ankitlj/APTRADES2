from app import create_app


def _client_with_db(database_url: str):
    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=database_url)
    return app.test_client()


def test_action_centre_sync_and_approve_flow(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'action.sqlite'}"

    def fake_get_order_list(self, *, exchange_code, from_date, to_date):
        if exchange_code != "NFO":
            return []
        return [
            {
                "order_id": "ORD-1",
                "symbol": "NIFTY",
                "broker_symbol": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "status": "Open",
                "quantity": 50,
                "pending_quantity": 50,
                "status_normalized": "open",
            }
        ]

    monkeypatch.setattr("app.services.breeze_gateway.BreezeGateway.get_order_list", fake_get_order_list)
    monkeypatch.setattr(
        "app.services.breeze_gateway.BreezeGateway.cancel_order",
        lambda self, *, exchange_code, order_id: {"message": f"Cancel requested for {order_id}", "exchange_code": exchange_code},
    )

    with _client_with_db(database_url) as client:
        list_response = client.get("/api/action-centre")
        assert list_response.status_code == 200
        list_payload = list_response.get_json()
        assert list_payload["status"] == "ok"
        assert list_payload["stats"]["pending"] == 1
        assert len(list_payload["actions"]) == 1
        action_id = list_payload["actions"][0]["id"]

        approve_response = client.post(f"/api/action-centre/{action_id}/approve")
        assert approve_response.status_code == 200
        approve_payload = approve_response.get_json()
        assert approve_payload["action"]["status"] == "approved"
        assert approve_payload["action"]["broker_result"]["message"] == "Cancel requested for ORD-1"


def test_logs_endpoints_return_backend_rows(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'logs.sqlite'}"

    monkeypatch.setattr("app.services.breeze_gateway.BreezeGateway.get_order_list", lambda *args, **kwargs: [])

    with _client_with_db(database_url) as client:
        action_response = client.get("/api/action-centre")
        assert action_response.status_code == 200

        logs_response = client.get("/api/logs")
        assert logs_response.status_code == 200
        logs_payload = logs_response.get_json()
        assert logs_payload["status"] == "ok"
        assert logs_payload["summary"]["api_count"] >= 1
        assert any(row["kind"] == "api" for row in logs_payload["rows"])

        live_response = client.get("/api/logs/live")
        assert live_response.status_code == 200
        live_payload = live_response.get_json()
        assert live_payload["status"] == "ok"
        assert len(live_payload["lines"]) >= 1
