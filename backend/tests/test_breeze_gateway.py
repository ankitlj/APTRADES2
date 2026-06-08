from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.services.breeze_gateway import BreezeGateway, BreezeGatewayError, BreezeInstrument


def test_auth_diagnostic_reports_missing_configuration():
    gateway = BreezeGateway(app_key=None, secret_key=None, session_token=None)

    payload = gateway.auth_diagnostic()

    assert payload["status"] == "not_configured"
    assert payload["configured"] is False
    assert payload["missing"] == ["BREEZE_API_KEY", "BREEZE_SECRET_KEY", "BREEZE_SESSION_TOKEN"]


def test_get_customer_details_uses_unsigned_request():
    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="api-session")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {"Success": {"session_token": "customer-session"}}

    with patch("app.services.breeze_gateway.requests.request", return_value=response) as request_mock:
        payload = gateway.get_customer_details()

    assert payload["Success"]["session_token"] == "customer-session"
    _, kwargs = request_mock.call_args
    assert kwargs["headers"] == {"Content-Type": "application/json"}


def test_get_quote_uses_customer_session_token_and_caches_lookup():
    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="api-session")
    instrument = BreezeInstrument("SBIN", "STABAN", "NSE", "cash")
    customer_response = Mock()
    customer_response.raise_for_status.return_value = None
    customer_response.json.return_value = {"Success": {"session_token": "customer-session"}}
    quote_response = Mock()
    quote_response.raise_for_status.return_value = None
    quote_response.json.return_value = {"Success": [{"ltp": 812.5, "previous_close": 805.1}]}

    with patch(
        "app.services.breeze_gateway.requests.request",
        side_effect=[customer_response, quote_response, quote_response],
    ) as request_mock, patch("app.services.breeze_gateway.time.sleep") as sleep_mock:
        first_quote = gateway.get_quote(instrument)
        second_quote = gateway.get_quote(instrument)

    assert first_quote[0]["ltp"] == 812.5
    assert second_quote[0]["previous_close"] == 805.1
    assert request_mock.call_count == 3
    sleep_mock.assert_not_called()
    _, kwargs = request_mock.call_args
    assert kwargs["headers"]["X-AppKey"] == "app-key"
    assert kwargs["headers"]["X-SessionToken"] == "customer-session"
    assert kwargs["headers"]["X-Checksum"].startswith("token ")


def test_run_symbol_diagnostics_returns_clear_errors_when_not_configured():
    gateway = BreezeGateway(app_key=None, secret_key=None, session_token=None)

    payload = gateway.run_symbol_diagnostics()

    assert payload["configured"] is False
    assert payload["status"] == "error"
    assert len(payload["symbols"]) == 5
    assert all(item["status"] == "error" for item in payload["symbols"])
    assert "Missing Breeze configuration" in payload["symbols"][0]["error"]


def test_request_raises_clear_error_after_retries():
    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="api-session")
    response_error = BreezeGatewayError("boom")

    with patch(
        "app.services.breeze_gateway.requests.request",
        side_effect=[ValueError("bad json"), ValueError("bad json"), ValueError("bad json")],
    ), patch("app.services.breeze_gateway.time.sleep") as sleep_mock:
        try:
            gateway._request("GET", "/customerdetails", {}, requires_auth=False)
        except BreezeGatewayError as error:
            response_error = error

    assert "Breeze request failed for /customerdetails" in str(response_error)
    assert sleep_mock.call_count == 2


def test_get_order_list_calls_breeze_order_endpoint():
    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="api-session")
    customer_response = Mock()
    customer_response.raise_for_status.return_value = None
    customer_response.json.return_value = {"Success": {"session_token": "customer-session"}}
    orders_response = Mock()
    orders_response.raise_for_status.return_value = None
    orders_response.json.return_value = {"Success": []}

    with patch(
        "app.services.breeze_gateway.requests.request",
        side_effect=[customer_response, orders_response],
    ) as request_mock:
        gateway.get_order_list(
            exchange_code="NFO",
            from_date=datetime(2026, 6, 8, tzinfo=timezone.utc),
            to_date=datetime(2026, 6, 8, 23, 59, tzinfo=timezone.utc),
        )

    assert request_mock.call_args_list[1].args[1].endswith("/order")


def test_cancel_order_calls_breeze_order_delete_endpoint():
    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="api-session")
    customer_response = Mock()
    customer_response.raise_for_status.return_value = None
    customer_response.json.return_value = {"Success": {"session_token": "customer-session"}}
    cancel_response = Mock()
    cancel_response.raise_for_status.return_value = None
    cancel_response.json.return_value = {"Success": {"message": "ok"}}

    with patch(
        "app.services.breeze_gateway.requests.request",
        side_effect=[customer_response, cancel_response],
    ) as request_mock:
        gateway.cancel_order(exchange_code="NFO", order_id="1001")

    assert request_mock.call_args_list[1].args[0] == "DELETE"
    assert request_mock.call_args_list[1].args[1].endswith("/order")


def test_get_trade_list_calls_breeze_trades_endpoint():
    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="api-session")
    customer_response = Mock()
    customer_response.raise_for_status.return_value = None
    customer_response.json.return_value = {"Success": {"session_token": "customer-session"}}
    trades_response = Mock()
    trades_response.raise_for_status.return_value = None
    trades_response.json.return_value = {"Success": []}

    with patch(
        "app.services.breeze_gateway.requests.request",
        side_effect=[customer_response, trades_response],
    ) as request_mock:
        gateway.get_trade_list(
            exchange_code="NFO",
            from_date=datetime(2026, 6, 8, tzinfo=timezone.utc),
            to_date=datetime(2026, 6, 8, 23, 59, tzinfo=timezone.utc),
        )

    assert request_mock.call_args_list[1].args[1].endswith("/trades")
