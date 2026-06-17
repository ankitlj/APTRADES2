from unittest.mock import patch

from app import create_app
from app.services.breeze_gateway import BreezeGatewayError
from app.services.quote_service import QuoteServiceError


def test_positions_endpoint_returns_not_configured_when_breeze_missing():
    app = create_app()
    app.config.update(TESTING=True, BREEZE_API_KEY=None, BREEZE_SECRET_KEY=None, BREEZE_SESSION_TOKEN=None)

    with app.test_client() as client:
        response = client.get("/api/positions")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "not_configured"
    assert payload["quote_status"] == "not_configured"
    assert payload["close_actions_active"] is False
    assert payload["totals"]["open_positions"] == 0


def test_positions_endpoint_returns_quote_enriched_rows():
    app = create_app()
    app.config.update(
        TESTING=True,
        DATABASE_URL="sqlite:///positions.db",
        BREEZE_API_KEY="app-key",
        BREEZE_SECRET_KEY="secret-key",
        BREEZE_SESSION_TOKEN="session-token",
    )

    with app.test_client() as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[
            {
                "stock_code": "NIFTY",
                "underlying": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "quantity": "50",
                "average_price": "23200",
                "pnl": "0",
                "expiry_date": "30-Jun-2026",
            },
            {
                "stock_code": "STABAN",
                "underlying": "SBIN",
                "exchange_code": "NSE",
                "product_type": "cash",
                "quantity": "-10",
                "average_price": "980",
                "pnl": "0",
            },
        ],
    ), patch(
        "app.services.quote_service.QuoteService.get_quote",
        side_effect=[
            {
                "status": "ok",
                "symbol": "NIFTY",
                "resolved": {
                    "display_symbol": "NIFTY",
                    "broker_symbol": "NIFTY",
                    "exchange_code": "NFO",
                    "product_type": "futures",
                    "token": "62329",
                    "resolution_source": "broker_symbol",
                    "expiry_date": "2026-06-30",
                },
                "quote": {"ltp": 23440, "previous_close": 23451.7},
            },
            {
                "status": "ok",
                "symbol": "SBIN",
                "resolved": {
                    "display_symbol": "SBIN",
                    "broker_symbol": "STABAN",
                    "exchange_code": "NSE",
                    "product_type": "cash",
                    "token": "3045",
                    "resolution_source": "alias",
                    "expiry_date": None,
                },
                "quote": {"ltp": 977.7, "previous_close": 979.25},
            },
        ],
    ):
        response = client.get("/api/positions")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["quote_status"] == "ok"
    assert payload["totals"]["open_positions"] == 2
    assert payload["totals"]["long_positions"] == 1
    assert payload["totals"]["short_positions"] == 1
    assert payload["totals"]["option_positions"] == 0
    assert payload["totals"]["future_positions"] == 1
    assert payload["totals"]["equity_positions"] == 1
    assert payload["totals"]["realized_pnl"] == 0.0
    assert payload["totals"]["unrealized_pnl"] == 12023.0
    assert payload["totals"]["day_pnl"] == 12023.0
    assert payload["positions"][0]["ltp"] == 23440.0
    assert payload["positions"][0]["direction"] == "long"
    assert payload["positions"][0]["token"] == "62329"
    assert payload["positions"][1]["symbol"] == "SBIN"
    assert payload["positions"][1]["resolution_source"] == "alias"
    assert payload["positions"][1]["direction"] == "short"


def test_positions_endpoint_handles_no_positions_as_empty_state():
    app = create_app()
    app.config.update(
        TESTING=True,
        BREEZE_API_KEY="app-key",
        BREEZE_SECRET_KEY="secret-key",
        BREEZE_SESSION_TOKEN="session-token",
    )

    with app.test_client() as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        side_effect=BreezeGatewayError("No Positions available."),
    ):
        response = client.get("/api/positions")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["positions"] == []
    assert payload["totals"]["open_positions"] == 0


def test_positions_endpoint_keeps_rows_when_quote_enrichment_fails():
    app = create_app()
    app.config.update(
        TESTING=True,
        DATABASE_URL="sqlite:///positions.db",
        BREEZE_API_KEY="app-key",
        BREEZE_SECRET_KEY="secret-key",
        BREEZE_SESSION_TOKEN="session-token",
    )

    with app.test_client() as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[
            {
                "stock_code": "RELIND",
                "underlying": "RELIANCE",
                "exchange_code": "NSE",
                "product_type": "cash",
                "quantity": "5",
                "average_price": "1300",
                "ltp": "1291",
                "pnl": "-45",
            }
        ],
    ), patch(
        "app.services.quote_service.QuoteService.get_quote",
        side_effect=QuoteServiceError("quote failed"),
    ):
        response = client.get("/api/positions")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["quote_status"] == "partial"
    assert payload["positions"][0]["ltp"] == 1291.0
    assert payload["positions"][0]["quote_status"] == "error"
    assert payload["positions"][0]["quote_error"] == "quote failed"


def test_get_cached_positions_returns_none_when_no_cache():
    app = create_app()
    app.config.update(
        TESTING=True,
        BREEZE_API_KEY="app-key",
        BREEZE_SECRET_KEY="secret-key",
        BREEZE_SESSION_TOKEN="session-token",
    )

    from app.services.positions_service import PositionsService
    from app.services.breeze_gateway import BreezeGateway

    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="session-token")
    service = PositionsService(gateway, database_url=None)

    with app.app_context():
        cached = service.get_cached_positions()
    assert cached is None


def test_get_cached_positions_returns_data_when_cached():
    app = create_app()
    app.config.update(
        TESTING=True,
        BREEZE_API_KEY="app-key",
        BREEZE_SECRET_KEY="secret-key",
        BREEZE_SESSION_TOKEN="session-token",
    )

    from app.services.positions_service import PositionsService, _POSITIONS_CACHE_KEY, _positions_cache_lock
    from app.services.breeze_gateway import BreezeGateway

    gateway = BreezeGateway(app_key="app-key", secret_key="secret-key", session_token="session-token")
    service = PositionsService(gateway, database_url=None)

    sample = {"status": "ok", "positions": [], "totals": {"open_positions": 0, "long_positions": 0, "short_positions": 0, "total_pnl": 0.0}}
    import time
    with app.app_context():
        with _positions_cache_lock:
            app.config[_POSITIONS_CACHE_KEY] = (time.monotonic(), sample)
        cached = service.get_cached_positions()
    assert cached is not None
    assert cached["status"] == "ok"
    assert cached["totals"]["open_positions"] == 0
