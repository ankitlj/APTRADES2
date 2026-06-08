from unittest.mock import patch

from app import create_app


def test_orders_endpoint_returns_normalized_stats():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_order_list",
        return_value=[
            {
                "order_id": "1001",
                "stock_code": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "action": "BUY",
                "status": "Open",
                "quantity": "50",
                "pending_quantity": "50",
                "limit_rate": "23250.0",
                "order_type": "limit",
                "validity": "day",
            },
            {
                "order_id": "1002",
                "stock_code": "SBIN",
                "exchange_code": "NSE",
                "product_type": "cash",
                "action": "SELL",
                "status": "Completed",
                "quantity": "10",
                "pending_quantity": "0",
                "average_price": "978.1",
            },
        ],
    ):
        response = client.get("/api/orders")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["stats"]["total"] == 2
    assert payload["stats"]["open"] == 1
    assert payload["stats"]["completed"] == 1
    assert payload["orders"][0]["status_normalized"] == "open"
    assert payload["orders"][1]["filled_quantity"] == 10.0


def test_cancel_order_endpoint_returns_success_payload():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client, patch(
        "app.services.breeze_gateway.BreezeGateway.cancel_order",
        return_value={"message": "Order cancellation requested"},
    ):
        response = client.post("/api/orders/cancel", json={"exchange_code": "NFO", "order_id": "1001"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["order_id"] == "1001"


def test_cancel_all_endpoint_only_targets_open_orders():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_order_list",
        return_value=[
            {"order_id": "1001", "stock_code": "NIFTY", "exchange_code": "NFO", "status": "Open"},
            {"order_id": "1002", "stock_code": "SBIN", "exchange_code": "NSE", "status": "Completed"},
            {"order_id": "1003", "stock_code": "BANKNIFTY", "exchange_code": "NFO", "status": "Pending"},
        ],
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.cancel_order",
        side_effect=[{"message": "Cancel 1001"}, {"message": "Cancel 1003"}],
    ) as cancel_mock:
        response = client.post("/api/orders/cancel-all", json={"exchange_code": "NFO"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["requested"] == 2
    assert payload["cancelled_count"] == 2
    assert cancel_mock.call_count == 2


def test_trades_endpoint_returns_normalized_stats():
    app = create_app()
    app.config.update(TESTING=True)

    with app.test_client() as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_trade_list",
        return_value=[
            {
                "trade_id": "T1",
                "order_id": "1001",
                "stock_code": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "action": "BUY",
                "quantity": "50",
                "price": "23270.5",
                "trade_time": "2026-06-08T10:10:00",
            },
            {
                "trade_id": "T2",
                "order_id": "1002",
                "stock_code": "SBIN",
                "exchange_code": "NSE",
                "product_type": "cash",
                "action": "SELL",
                "quantity": "10",
                "price": "978.0",
                "trade_time": "2026-06-08T10:12:00",
            },
        ],
    ):
        response = client.get("/api/trades")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["stats"]["total"] == 2
    assert payload["stats"]["buy"] == 1
    assert payload["stats"]["sell"] == 1
    assert payload["trades"][0]["symbol"] == "NIFTY"
