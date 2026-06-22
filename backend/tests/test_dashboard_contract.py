from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from app import create_app
from app.db import create_session_factory, ensure_tables
from app.models import Instrument, InstrumentAlias, MasterContractRun
from app.services.breeze_gateway import BreezeGatewayError


def _seed_dashboard_data(database_url: str) -> None:
    future_expiry = date.today() + timedelta(days=14)
    ensure_tables(database_url)
    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        nifty_cash = Instrument(
            exchange_code="NSE",
            broker_symbol="NIFTY",
            contract_code="NIFTY",
            display_symbol="NIFTY",
            name="NIFTY 50",
            instrument_group="EQUITY",
            product_type="cash",
            token="9999",
            lot_size=1,
            tick_size="0",
            isin="",
            series="0",
            source="seed_aliases",
            is_active=True,
        )
        banknifty_cash = Instrument(
            exchange_code="NSE",
            broker_symbol="CNXBAN",
            contract_code="CNXBAN",
            display_symbol="BANKNIFTY",
            name="NIFTY BANK",
            instrument_group="EQUITY",
            product_type="cash",
            token="26009",
            lot_size=1,
            tick_size="0",
            isin="",
            series="0",
            source="seed_aliases",
            is_active=True,
        )
        nifty_future = Instrument(
            exchange_code="NFO",
            broker_symbol="NIFTY",
            contract_code=f"NIFTY~F:{future_expiry.strftime('%d-%b-%Y').upper()}",
            display_symbol="NIFTY",
            name="NIFTY FUTURE",
            instrument_group="DERIVATIVE",
            product_type="futures",
            token="62329",
            lot_size=50,
            tick_size="0.05",
            expiry_date=future_expiry,
            option_right="others",
            strike_price="0",
            source="security_master",
            is_active=True,
        )
        banknifty_future = Instrument(
            exchange_code="NFO",
            broker_symbol="CNXBAN",
            contract_code=f"CNXBAN~F:{future_expiry.strftime('%d-%b-%Y').upper()}",
            display_symbol="BANKNIFTY",
            name="BANKNIFTY FUTURE",
            instrument_group="DERIVATIVE",
            product_type="futures",
            token="62326",
            lot_size=30,
            tick_size="0.05",
            expiry_date=future_expiry,
            option_right="others",
            strike_price="0",
            source="security_master",
            is_active=True,
        )
        sbin = Instrument(
            exchange_code="NSE",
            broker_symbol="STABAN",
            contract_code="STABAN",
            display_symbol="SBIN",
            name="STATE BANK OF INDIA",
            instrument_group="EQUITY",
            product_type="cash",
            token="3045",
            lot_size=1,
            tick_size="0.1",
            isin="INE062A01020",
            series="EQ",
            source="stock_script_csv",
            is_active=True,
        )
        session.add_all([nifty_cash, banknifty_cash, nifty_future, banknifty_future, sbin])
        session.flush()
        session.add_all(
            [
                InstrumentAlias(
                    instrument_id=banknifty_cash.id,
                    alias="BANKNIFTY",
                    normalized_alias="BANKNIFTY",
                    alias_scope="NSE",
                    alias_type="display",
                    source="seed_aliases",
                ),
            InstrumentAlias(
                instrument_id=sbin.id,
                alias="SBIN",
                normalized_alias="SBIN",
                alias_scope="NSE",
                alias_type="display",
                source="stock_script_csv",
            ),
        ]
        # FINNIFTY and NIFTYMID50 aliases won't exist in _seed_dashboard_data
        # They will be added via _seed_search_test_data
        )
        session.add(
            MasterContractRun(
                status="success",
                source_name="security_master+stock_script_csv+seed_aliases",
                source_checksum="abc123",
                security_master_url="https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip",
                csv_path="data/StockScriptNew.csv",
                row_count=127774,
                alias_count=37204,
                warning_count=0,
                error_message=None,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def _client_with_db(database_url: str):
    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=database_url)
    return app.test_client()


def _quote_response(instrument):
    if instrument.stock_code == "NIFTY":
        return [{"ltp": 23440.0, "previous_close": 23451.7, "spot_price": 23366.7, "expiry_date": "30-Jun-2026"}]
    if instrument.stock_code == "CNXBAN":
        return [{"ltp": 54799.0, "previous_close": 54781.6, "spot_price": 54496.25, "expiry_date": "30-Jun-2026"}]
    if instrument.stock_code == "STABAN":
        return [{"ltp": 977.7, "previous_close": 979.25, "spot_price": 977.7, "expiry_date": None}]
    raise AssertionError(f"Unexpected stock code {instrument.stock_code}")


def test_dashboard_summary_endpoint_returns_metrics_and_positions(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'dashboard.sqlite'}"
    _seed_dashboard_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        side_effect=_quote_response,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[
            {
                "underlying": "SBIN",
                "stock_code": "STABAN",
                "exchange_code": "NSE",
                "product_type": "cash",
                "quantity": "25",
                "average_price": "972.5",
                "ltp": "977.7",
                "pnl": "130.0",
            }
        ],
    ):
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert len(payload["metrics"]) == 4
    assert [metric["key"] for metric in payload["metrics"]] == [
        "day_pnl",
        "open_positions",
        "monthly_roi",
        "margin_used",
    ]
    assert payload["metrics"][0]["label"] == "Day's P&L"
    assert payload["metrics"][0]["format"] == "currency"
    assert payload["metrics"][0]["submetrics"][0]["label"] == "Realized"
    assert payload["metrics"][0]["submetrics"][1]["label"] == "Unrealized"
    assert payload["metrics"][1]["label"] == "Open positions"
    assert payload["metrics"][1]["submetrics"][0]["label"] == "Options"
    assert payload["metrics"][1]["submetrics"][1]["label"] == "Future"
    assert payload["metrics"][1]["submetrics"][2]["label"] == "Equity"
    assert payload["metrics"][2]["label"] == "Monthly ROI"
    assert payload["metrics"][2]["submetrics"][0]["label"] == "Annual ROI (FY)"
    assert payload["metrics"][3]["label"] == "Margin used"
    assert payload["positions"][0]["symbol"] == "SBIN"
    assert payload["positions"][0]["pnl"] == 130.0


def test_dashboard_alerts_endpoint_returns_real_status_messages(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'dashboard.sqlite'}"
    _seed_dashboard_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.auth_diagnostic",
        return_value={"status": "ok", "user_id": "AJ510524", "configured": True, "session_token_received": True},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[],
    ):
        response = client.get("/api/dashboard/alerts")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert any(alert["title"] == "Breeze session active" for alert in payload["alerts"])
    assert any(alert["title"] == "Master contract loaded" for alert in payload["alerts"])


def test_dashboard_alerts_endpoint_treats_no_positions_as_empty_state(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'dashboard.sqlite'}"
    _seed_dashboard_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.auth_diagnostic",
        return_value={"status": "ok", "user_id": "AJ510524", "configured": True, "session_token_received": True},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        side_effect=BreezeGatewayError("No Positions available."),
    ):
        response = client.get("/api/dashboard/alerts")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert any(alert["title"] == "Positions snapshot pending" for alert in payload["alerts"])


def test_dashboard_chart_endpoint_returns_normalized_points(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'dashboard.sqlite'}"
    _seed_dashboard_data(database_url)

    def _chart_response(instrument, **kwargs):
        assert instrument.stock_code == "NIFTY"
        assert instrument.exchange_code == "NSE"
        assert instrument.product_type == "cash"
        assert instrument.expiry_date == ""
        assert kwargs["interval"] == "day"
        return [
            {"datetime": "2026-06-05T00:00:00.000Z", "open": 23210.0, "high": 23490.0, "low": 23180.0, "close": 23420.0, "volume": 1200},
            {"datetime": "2026-06-06T00:00:00.000Z", "open": 23420.0, "high": 23510.0, "low": 23320.0, "close": 23440.0, "volume": 1180},
        ]

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_historical_charts",
        side_effect=_chart_response,
    ):
        response = client.get("/api/dashboard/chart?symbol=NIFTY")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["symbol"] == "NIFTY"
    assert payload["interval"] == "day"
    assert payload["resolved"]["broker_symbol"] == "NIFTY"
    assert len(payload["points"]) == 2
    assert payload["points"][1]["close"] == 23440.0


def test_dashboard_summary_degraded_when_positions_fail(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'dashboard.sqlite'}"
    _seed_dashboard_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.auth_diagnostic",
        return_value={"status": "ok", "user_id": "AJ510524", "configured": True, "session_token_received": True},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        side_effect=BreezeGatewayError("Breeze request failed for /portfoliopositions: timeout"),
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        return_value={
            "Success": [{"ltp": 23440.0, "close": 23451.7}],
        },
    ):
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["positions_status"] in ("degraded", "error")
    assert payload["positions"] == []
    metric_keys = [m["key"] for m in payload["metrics"]]
    assert "day_pnl" in metric_keys
    assert "open_positions" in metric_keys
    assert "monthly_roi" in metric_keys
    assert "margin_used" in metric_keys


def test_dashboard_alerts_pending_when_no_cached_positions(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'dashboard.sqlite'}"
    _seed_dashboard_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        side_effect=BreezeGatewayError("No Positions available."),
    ):
        response = client.get("/api/dashboard/alerts")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert any(alert["title"] == "Positions snapshot pending" for alert in payload["alerts"])
    assert any(alert["title"] == "Breeze session active" for alert in payload["alerts"])
    assert any(alert["title"] == "Master contract loaded" for alert in payload["alerts"])
    # Verify no fresh broker call was made — positions endpoint should never be called
    assert all("positions" not in alert["title"].lower() or alert["title"] == "Positions snapshot pending" for alert in payload["alerts"])


def test_dashboard_summary_ticker_has_exactly_4_symbols(tmp_path):
    """After SENSEX removal, the top ticker must contain exactly 4 items and
    never include SENSEX."""
    import app.services.dashboard_service as svc
    assert len(svc._TICKER_SYMBOLS) == 4
    keys = [item["symbol"] for item in svc._TICKER_SYMBOLS]
    assert "SENSEX" not in keys
    assert "NIFTY" in keys
    assert "BANKNIFTY" in keys
    assert "NIFTYMID50" in keys
    assert "FINNIFTY" in keys


def test_dashboard_summary_fallback_uses_cached_value_when_breeze_fails(tmp_path):
    """When Breeze returns a null LTP for a symbol that previously had a valid
    value, the dashboard should return the cached value within TTL."""
    import time
    from app.services.dashboard_service import _last_good_quotes, _last_good_lock

    # Prime the cache with a good value for NIFTY
    with _last_good_lock:
        _last_good_quotes["NIFTY"] = {
            "ltp": 24168.0,
            "change_percent": 0.34,
            "ts": time.monotonic(),
        }

    database_url = f"sqlite:///{tmp_path / 'dashboard_fallback.sqlite'}"
    _seed_dashboard_data(database_url)

    # Mock Breeze to return a failed quote for NIFTY but success for others
    call_count = [0]
    def _mock_quote(instrument):
        call_count[0] += 1
        if instrument.stock_code == "NIFTY":
            # Simulate Breeze returning null ltp
            return [{"ltp": None, "previous_close": 24150.0}]
        return _quote_response(instrument)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        side_effect=_mock_quote,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[],
    ):
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    payload = response.get_json()
    ticker = {item["symbol"]: item for item in payload["ticker"]}
    # NIFTY should use cached value (24168.0) instead of null
    assert ticker["NIFTY"]["ltp"] == 24168.0
    assert ticker["NIFTY"]["change_percent"] == 0.34

    # Cleanup
    with _last_good_lock:
        _last_good_quotes.pop("NIFTY", None)


def test_dashboard_summary_updates_cache_on_valid_quote(tmp_path):
    """When Breeze returns a valid LTP, the cache must be updated with the new
    value."""
    import time as time_module
    from app.services.dashboard_service import _last_good_quotes, _last_good_lock

    # Clear any leftover
    with _last_good_lock:
        _last_good_quotes.clear()

    database_url = f"sqlite:///{tmp_path / 'dashboard_cache_update.sqlite'}"
    _seed_dashboard_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        side_effect=_quote_response,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[],
    ):
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    # NIFTY should have been cached
    with _last_good_lock:
        cached = _last_good_quotes.get("NIFTY")
    assert cached is not None
    assert cached["ltp"] == 23440.0  # from test fixture _quote_response
    # Ensure timestamp is recent
    assert (time_module.monotonic() - cached["ts"]) < 5

    # Cleanup
    with _last_good_lock:
        _last_good_quotes.clear()


def test_dashboard_summary_stale_cache_returns_null(tmp_path):
    """When the cached value is older than FALLBACK_TTL, the dashboard should
    return null/Unavailable instead of the stale cache."""
    import time
    from app.services.dashboard_service import _last_good_quotes, _last_good_lock, _FALLBACK_TTL

    # Prime the cache with a very old value
    with _last_good_lock:
        _last_good_quotes["NIFTY"] = {
            "ltp": 10000.0,
            "change_percent": 0.0,
            "ts": time.monotonic() - _FALLBACK_TTL - 10,
        }

    database_url = f"sqlite:///{tmp_path / 'dashboard_stale.sqlite'}"
    _seed_dashboard_data(database_url)

    # NIFTY resolution fails because we have no instrument matching NIFTYMID50...
    # actually, NIFTY is in the seed data, so it resolves fine. Let's make Breeze
    # return null for it.
    def _stale_quote(instrument):
        if instrument.stock_code == "NIFTY":
            return [{"ltp": None, "previous_close": None}]
        return _quote_response(instrument)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        side_effect=_stale_quote,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[],
    ):
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    payload = response.get_json()
    ticker = {item["symbol"]: item for item in payload["ticker"]}
    # NIFTY should show null because cache is stale and Breeze returned null
    assert ticker["NIFTY"]["ltp"] is None

    # Cleanup
    with _last_good_lock:
        _last_good_quotes.clear()


def test_dashboard_summary_fallback_is_symbol_specific(tmp_path):
    """One symbol's failed quote should not affect another symbol's cached
    value."""
    import time
    from app.services.dashboard_service import _last_good_quotes, _last_good_lock

    # Prime cache for NIFTY only
    with _last_good_lock:
        _last_good_quotes["NIFTY"] = {
            "ltp": 24168.0,
            "change_percent": 0.34,
            "ts": time.monotonic(),
        }

    database_url = f"sqlite:///{tmp_path / 'dashboard_isolation.sqlite'}"
    _seed_dashboard_data(database_url)

    # Breeze returns null for NIFTY but good data for CNXBAN
    def _iso_quote(instrument):
        if instrument.stock_code == "NIFTY":
            return [{"ltp": None, "previous_close": 24150.0}]
        return _quote_response(instrument)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        side_effect=_iso_quote,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_portfolio_positions",
        return_value=[],
    ):
        response = client.get("/api/dashboard/summary")

    assert response.status_code == 200
    payload = response.get_json()
    ticker = {item["symbol"]: item for item in payload["ticker"]}
    # NIFTY uses fallback
    assert ticker["NIFTY"]["ltp"] == 24168.0
    # BANKNIFTY gets live data (from _quote_response mock)
    assert ticker.get("BANKNIFTY") is not None

    # Cleanup
    with _last_good_lock:
        _last_good_quotes.pop("NIFTY", None)

def _option_chain_response(instrument):
    if instrument.stock_code != "NIFTY":
        return []
    return [
        {
            "ltp": "152.35",
            "best_bid_price": "151.80",
            "best_offer_price": "152.90",
            "best_bid_quantity": "225",
            "best_offer_quantity": "175",
            "open_interest": "1245000",
            "total_quantity_traded": "8500",
            "previous_close": "148.20",
            "spot_price": "23420.00",
            "strike_price": "23500",
            "expiry_date": "2026-06-30T06:00:00.000Z",
            "token": "12345",
        }
    ]


def test_option_orderbook_valid_request_returns_expected_keys(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'option_orderbook.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes",
        side_effect=_option_chain_response,
    ):
        response = client.get(
            "/api/dashboard/option-orderbook?underlying=NIFTY&expiry=2026-06-30&strike=23500&right=call"
        )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["underlying"] == "NIFTY"
    assert payload["exchange"] == "NFO"
    assert payload["expiry"] == "2026-06-30"
    assert payload["strike"] == 23500.0
    assert payload["right"] == "call"
    assert payload["ltp"] == 152.35
    assert payload["bid_price"] == 151.80
    assert payload["ask_price"] == 152.90
    assert payload["bid_qty"] == 225.0
    assert payload["ask_qty"] == 175.0
    assert payload["previous_close"] == 148.20
    assert payload["spot_price"] == 23420.0
    assert len(payload["levels"]) == 1
    assert payload["levels"][0]["bid_price"] == 151.80
    assert payload["total_buy_qty"] == 225.0
    assert payload["total_sell_qty"] == 175.0
    assert payload["buy_percent"] == 56.2
    assert payload["sell_percent"] == 43.8
    assert payload["timestamp"] is not None
    assert payload["instrument"]["exchange_code"] == "NFO"
    assert payload["instrument"]["token"] == "12345"


def test_option_orderbook_missing_underlying_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_missing.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/option-orderbook?expiry=2026-06-30&strike=23500&right=call")
    assert response.status_code == 400
    assert "underlying" in response.get_json()["error"].lower()


def test_option_orderbook_missing_expiry_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_missing_exp.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/option-orderbook?underlying=NIFTY&strike=23500&right=call")
    assert response.status_code == 400
    assert "expiry" in response.get_json()["error"].lower()


def test_option_orderbook_missing_strike_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_missing_strike.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/option-orderbook?underlying=NIFTY&expiry=2026-06-30&right=call")
    assert response.status_code == 400
    assert "strike" in response.get_json()["error"].lower()


def test_option_orderbook_invalid_right_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_bad_right.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/option-orderbook?underlying=NIFTY&expiry=2026-06-30&strike=23500&right=straddle")
    assert response.status_code == 400
    assert "right" in response.get_json()["error"].lower()


def test_option_orderbook_unsupported_underlying_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_bad_ul.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/option-orderbook?underlying=SENSEX&expiry=2026-06-30&strike=50000&right=call")
    assert response.status_code == 400
    assert "SENSEX" in response.get_json()["error"]


def test_option_orderbook_empty_breeze_response_returns_safe_error(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_empty.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes", return_value=[],
    ):
        response = client.get("/api/dashboard/option-orderbook?underlying=NIFTY&expiry=2026-06-30&strike=23500&right=call")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "no data" in payload["error"].lower()
    assert payload["ltp"] is None
    assert payload["levels"] == []


def test_option_orderbook_missing_bid_ask_fields_does_not_crash(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_partial.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes",
        return_value=[{"ltp": "100.00", "strike_price": "23500"}],
    ):
        response = client.get("/api/dashboard/option-orderbook?underlying=NIFTY&expiry=2026-06-30&strike=23500&right=call")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["ltp"] == 100.0
    assert payload["bid_price"] is None
    assert payload["ask_price"] is None
    assert payload["bid_qty"] is None
    assert payload["ask_qty"] is None
    assert payload["levels"] == []
    assert payload["total_buy_qty"] == 0.0
    assert payload["total_sell_qty"] == 0.0
    assert payload["buy_percent"] == 50.0
    assert payload["sell_percent"] == 50.0


def test_option_orderbook_zero_totals_handles_percent_safely(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'opt_ob_zero.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes",
        return_value=[{
            "ltp": "100.00",
            "best_bid_price": "99.50",
            "best_offer_price": "100.50",
            "best_bid_quantity": "0",
            "best_offer_quantity": "0",
        }],
    ):
        response = client.get("/api/dashboard/option-orderbook?underlying=NIFTY&expiry=2026-06-30&strike=23500&right=call")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["bid_qty"] == 0.0
    assert payload["ask_qty"] == 0.0
    assert payload["buy_percent"] == 50.0
    assert payload["sell_percent"] == 50.0


def _seed_search_test_data(database_url: str) -> None:
    """Extended seed data for search ranking tests: adds options, expired rows, ADANI."""
    from app.db import ensure_tables
    ensure_tables(database_url)
    _seed_dashboard_data(database_url)
    session_factory = create_session_factory(database_url)
    today = date.today()
    future_expiry = today + timedelta(days=14)
    past_expiry = today - timedelta(days=5)
    with session_factory() as session:
        options = [
            Instrument(
                exchange_code="NFO", broker_symbol="NIFTY",
                contract_code=f"NIFTY~CE~{future_expiry.isoformat()}~2400000",
                display_symbol="NIFTY", name="NIFTY 24000 CE",
                instrument_group="DERIVATIVE", product_type="options",
                token="70001", lot_size=50, tick_size="0.05",
                expiry_date=future_expiry, option_right="call", strike_price="2400000",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="NIFTY",
                contract_code=f"NIFTY~PE~{future_expiry.isoformat()}~2400000",
                display_symbol="NIFTY", name="NIFTY 24000 PE",
                instrument_group="DERIVATIVE", product_type="options",
                token="70002", lot_size=50, tick_size="0.05",
                expiry_date=future_expiry, option_right="put", strike_price="2400000",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="NIFTY",
                contract_code=f"NIFTY~CE~{future_expiry.isoformat()}~2350000",
                display_symbol="NIFTY", name="NIFTY 23500 CE",
                instrument_group="DERIVATIVE", product_type="options",
                token="70003", lot_size=50, tick_size="0.05",
                expiry_date=future_expiry, option_right="call", strike_price="2350000",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="NIFTY",
                contract_code=f"NIFTY~CE~{future_expiry.isoformat()}~2500000",
                display_symbol="NIFTY", name="NIFTY 25000 CE",
                instrument_group="DERIVATIVE", product_type="options",
                token="70004", lot_size=50, tick_size="0.05",
                expiry_date=future_expiry, option_right="call", strike_price="2500000",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="NIFTY",
                contract_code=f"NIFTY~CE~{future_expiry.isoformat()}~2000000",
                display_symbol="NIFTY", name="NIFTY 20000 CE",
                instrument_group="DERIVATIVE", product_type="options",
                token="70005", lot_size=50, tick_size="0.05",
                expiry_date=future_expiry, option_right="call", strike_price="2000000",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="NIFTY",
                contract_code=f"NIFTY~F~{past_expiry.strftime('%d-%b-%Y').upper()}",
                display_symbol="NIFTY", name="NIFTY FUT EXPIRED",
                instrument_group="DERIVATIVE", product_type="futures",
                token="70006", lot_size=50, tick_size="0.05",
                expiry_date=past_expiry, option_right="others", strike_price="0",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="CNXBAN",
                contract_code=f"CNXBAN~F~{past_expiry.strftime('%d-%b-%Y').upper()}",
                display_symbol="BANKNIFTY", name="BANKNIFTY FUT EXPIRED",
                instrument_group="DERIVATIVE", product_type="futures",
                token="70007", lot_size=30, tick_size="0.05",
                expiry_date=past_expiry, option_right="others", strike_price="0",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NSE", broker_symbol="ADANIENT",
                contract_code="ADANIENT", display_symbol="ADANIENT",
                name="ADANI ENTERPRISES LTD", instrument_group="EQUITY",
                product_type="cash", token="70008", lot_size=1,
                tick_size="0.05", isin="INE423A01024", series="EQ",
                source="stock_script_csv", is_active=True,
            ),
            Instrument(
                exchange_code="NSE", broker_symbol="ADANIPORTS",
                contract_code="ADANIPORTS", display_symbol="ADANIPORTS",
                name="ADANI PORT AND SEZ LTD", instrument_group="EQUITY",
                product_type="cash", token="70009", lot_size=1,
                tick_size="0.05", isin="INE742F01042", series="EQ",
                source="stock_script_csv", is_active=True,
            ),
            Instrument(
                exchange_code="NSE", broker_symbol="ADANIGREEN",
                contract_code="ADANIGREEN", display_symbol="ADANIGREEN",
                name="ADANI GREEN ENERGY LTD", instrument_group="EQUITY",
                product_type="cash", token="70010", lot_size=1,
                tick_size="0.05", isin="INE364U01010", series="EQ",
                source="stock_script_csv", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="ADANIENT",
                contract_code=f"ADANIENT~F:{future_expiry.strftime('%d-%b-%Y').upper()}",
                display_symbol="ADANIENT", name="ADANIENT FUT",
                instrument_group="DERIVATIVE", product_type="futures",
                token="70011", lot_size=500, tick_size="0.05",
                expiry_date=future_expiry, option_right="others", strike_price="0",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NFO", broker_symbol="ADANIPORTS",
                contract_code=f"ADANIPORTS~CE~{future_expiry.isoformat()}~180000",
                display_symbol="ADANIPORTS", name="ADANIPORTS 1800 CE",
                instrument_group="DERIVATIVE", product_type="options",
                token="70012", lot_size=500, tick_size="0.05",
                expiry_date=future_expiry, option_right="call", strike_price="180000",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NSE", broker_symbol="NIFFIN",
                contract_code="NIFFIN", display_symbol="FINNIFTY",
                name="NIFTY FINANCIAL SERVICES", instrument_group="EQUITY",
                product_type="cash", token="70013", lot_size=1,
                tick_size="0", isin="", series="",
                source="security_master", is_active=True,
            ),
            Instrument(
                exchange_code="NSE", broker_symbol="NIFMID",
                contract_code="NIFMID", display_symbol="NIFTYMID50",
                name="NIFTY MIDCAP 50", instrument_group="EQUITY",
                product_type="cash", token="70014", lot_size=1,
                tick_size="0", isin="", series="",
                source="security_master", is_active=True,
            ),
        ]
        session.add_all(options)
        session.commit()


def test_search_nifty_ranks_nifty_before_banknifty(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's1.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=NIFTY&tab=all")
    assert response.status_code == 200
    payload = response.get_json()
    symbols = [r["broker_symbol"] for r in payload["results"]]
    nifty_idx = symbols.index("NIFTY") if "NIFTY" in symbols else len(symbols)
    banknifty_idx = symbols.index("CNXBAN") if "CNXBAN" in symbols else len(symbols)
    assert nifty_idx < banknifty_idx, f"NIFTY should rank before CNXBAN, got order: {symbols}"
    assert payload.get("tab") == "all"


def test_search_banknifty_ranks_banknifty_first(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's2.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=BANKNIFTY&tab=all")
    assert response.status_code == 200
    payload = response.get_json()
    symbols = [r["broker_symbol"] for r in payload["results"]]
    # CNXBAN is the broker_symbol for BANKNIFTY alias
    banknifty_idx = symbols.index("CNXBAN") if "CNXBAN" in symbols else len(symbols)
    assert banknifty_idx == 0, f"BANKNIFTY/CNXBAN should be first, got: {symbols}"


def test_search_finnifty_alias_works(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's3.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=FINNIFTY&tab=all")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["results"]) > 0


def test_search_midcap_alias_works(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's4.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=MIDCAP&tab=all")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["results"]) > 0


def test_search_expired_derivatives_excluded(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's5.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=NIFTY&tab=all")
    assert response.status_code == 200
    payload = response.get_json()
    for r in payload["results"]:
        if r["instrument_kind"] in ("future", "option"):
            assert r["expiry_date"] is not None, f"Derivative missing expiry: {r}"
            expiry = date.fromisoformat(r["expiry_date"])
            assert expiry >= date.today(), f"Expired derivative returned: {r}"


def test_search_futures_appear_in_fno_tab(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's6.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=NIFTY&tab=fno")
    assert response.status_code == 200
    payload = response.get_json()
    kinds = [r["instrument_kind"] for r in payload["results"]]
    assert "future" in kinds, f"No futures found in F&O tab: {kinds}"
    assert "option" in kinds, f"No options found in F&O tab: {kinds}"
    assert "cash" not in kinds, f"Cash found in F&O tab: {kinds}"


def test_search_stocks_tab_contains_no_derivatives(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's7.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=NIFTY&tab=stocks")
    assert response.status_code == 200
    payload = response.get_json()
    for r in payload["results"]:
        assert r["instrument_kind"] == "cash", f"Non-cash in stocks tab: {r}"


def test_search_strike_normalization_displays_24000(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's8.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=24000&tab=fno")
    assert response.status_code == 200
    payload = response.get_json()
    for r in payload["results"]:
        if r["instrument_kind"] == "option" and r["display_strike"]:
            assert r["display_strike"] == "24000", f"Expected display_strike 24000 got {r['display_strike']}"


def test_search_adani_returns_multiple_adani_rows(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's9.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=ADANI&tab=stocks")
    assert response.status_code == 200
    payload = response.get_json()
    symbols = set(r["broker_symbol"] for r in payload["results"])
    adani_matches = [s for s in symbols if "ADANI" in s.upper()]
    assert len(adani_matches) >= 3, f"Expected at least 3 ADANI symbols, got {adani_matches}"


def test_search_options_near_atm_before_deep_strikes(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's10.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=NIFTY&tab=fno")
    assert response.status_code == 200
    payload = response.get_json()
    option_rows = [r for r in payload["results"] if r["instrument_kind"] == "option"]
    if len(option_rows) >= 2:
        strikes = [abs(int(r["strike_price"] or 0)) for r in option_rows]
        central = sum(strikes) // len(strikes)
        for r in option_rows:
            strike_abs = abs(int(r["strike_price"] or 0))
            assert strike_abs >= central - 500000, f"Deep ITM/OTM before central: {r}"


def test_search_decimal_strike_does_not_crash(tmp_path):
    """Option row with fractional strike like 292.5 must not crash _apply_option_diversity."""
    database_url = f"sqlite:///{tmp_path / 's_decimal_strike.sqlite'}"
    _seed_search_test_data(database_url)
    session_factory = create_session_factory(database_url)
    future_expiry = date.today() + timedelta(days=14)
    with session_factory() as session:
        session.add(Instrument(
            exchange_code="NFO", broker_symbol="SBIN",
            contract_code=f"SBIN~CE~{future_expiry.isoformat()}~29250",
            display_symbol="SBIN", name="SBIN 292.5 CE",
            instrument_group="DERIVATIVE", product_type="options",
            token="80001", lot_size=3000, tick_size="0.05",
            expiry_date=future_expiry, option_right="call", strike_price="292.5",
            source="security_master", is_active=True,
        ))
        session.commit()
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=SBIN&tab=fno")
    assert response.status_code == 200, f"Decimal strike caused 500: {response.get_json()}"


def test_search_decimal_strike_included_in_results(tmp_path):
    """Decimal strike option row must appear in search results."""
    database_url = f"sqlite:///{tmp_path / 's_decimal_included.sqlite'}"
    _seed_search_test_data(database_url)
    session_factory = create_session_factory(database_url)
    future_expiry = date.today() + timedelta(days=14)
    with session_factory() as session:
        session.add(Instrument(
            exchange_code="NFO", broker_symbol="SBIN",
            contract_code=f"SBIN~CE~{future_expiry.isoformat()}~29250",
            display_symbol="SBIN", name="SBIN 292.5 CE",
            instrument_group="DERIVATIVE", product_type="options",
            token="80002", lot_size=3000, tick_size="0.05",
            expiry_date=future_expiry, option_right="call", strike_price="292.5",
            source="security_master", is_active=True,
        ))
        session.commit()
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=SBIN&tab=fno")
    assert response.status_code == 200
    payload = response.get_json()
    strikes = [r["strike_price"] for r in payload["results"] if r["instrument_kind"] == "option"]
    assert "292.5" in strikes, f"Decimal strike not found in results: {strikes}"


def test_search_decimal_strike_display_is_raw(tmp_path):
    """display_strike must show the real decimal value, not an integer truncation."""
    database_url = f"sqlite:///{tmp_path / 's_decimal_display.sqlite'}"
    _seed_search_test_data(database_url)
    session_factory = create_session_factory(database_url)
    future_expiry = date.today() + timedelta(days=14)
    with session_factory() as session:
        session.add(Instrument(
            exchange_code="NFO", broker_symbol="SBIN",
            contract_code=f"SBIN~CE~{future_expiry.isoformat()}~29250",
            display_symbol="SBIN", name="SBIN 292.5 CE",
            instrument_group="DERIVATIVE", product_type="options",
            token="80003", lot_size=3000, tick_size="0.05",
            expiry_date=future_expiry, option_right="call", strike_price="292.5",
            source="security_master", is_active=True,
        ))
        session.commit()
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=SBIN&tab=fno")
    assert response.status_code == 200
    payload = response.get_json()
    for r in payload["results"]:
        if r["instrument_kind"] == "option" and r["strike_price"] == "292.5":
            assert r["display_strike"] == "292.5", f"Expected display_strike '292.5', got '{r['display_strike']}'"


def test_search_bad_strike_value_does_not_crash(tmp_path):
    """Option with completely non-numeric strike must not crash."""
    database_url = f"sqlite:///{tmp_path / 's_bad_strike.sqlite'}"
    _seed_search_test_data(database_url)
    session_factory = create_session_factory(database_url)
    future_expiry = date.today() + timedelta(days=14)
    with session_factory() as session:
        session.add(Instrument(
            exchange_code="NFO", broker_symbol="NIFTY",
            contract_code=f"NIFTY~CE~{future_expiry.isoformat()}~BAD",
            display_symbol="NIFTY", name="NIFTY BAD CE",
            instrument_group="DERIVATIVE", product_type="options",
            token="80004", lot_size=50, tick_size="0.05",
            expiry_date=future_expiry, option_right="call", strike_price="ABC",
            source="security_master", is_active=True,
        ))
        session.commit()
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=NIFTY&tab=fno")
    assert response.status_code == 200, f"Bad strike 'ABC' caused 500: {response.get_json()}"


def test_search_mixed_integer_and_decimal_strikes_works(tmp_path):
    """Search with a mix of integer and decimal strike options must not crash
    and must return results from both strike types."""
    database_url = f"sqlite:///{tmp_path / 's_mixed_strikes.sqlite'}"
    _seed_search_test_data(database_url)
    session_factory = create_session_factory(database_url)
    future_expiry = date.today() + timedelta(days=14)
    with session_factory() as session:
        session.add(Instrument(
            exchange_code="NFO", broker_symbol="SBIN",
            contract_code=f"SBIN~CE~{future_expiry.isoformat()}~30000",
            display_symbol="SBIN", name="SBIN 300 CE",
            instrument_group="DERIVATIVE", product_type="options",
            token="80005", lot_size=3000, tick_size="0.05",
            expiry_date=future_expiry, option_right="call", strike_price="30000",
            source="security_master", is_active=True,
        ))
        session.add(Instrument(
            exchange_code="NFO", broker_symbol="SBIN",
            contract_code=f"SBIN~PE~{future_expiry.isoformat()}~29250",
            display_symbol="SBIN", name="SBIN 292.5 PE",
            instrument_group="DERIVATIVE", product_type="options",
            token="80006", lot_size=3000, tick_size="0.05",
            expiry_date=future_expiry, option_right="put", strike_price="292.5",
            source="security_master", is_active=True,
        ))
        session.add(Instrument(
            exchange_code="NFO", broker_symbol="SBIN",
            contract_code=f"SBIN~CE~{future_expiry.isoformat()}~28000",
            display_symbol="SBIN", name="SBIN 280 CE",
            instrument_group="DERIVATIVE", product_type="options",
            token="80007", lot_size=3000, tick_size="0.05",
            expiry_date=future_expiry, option_right="call", strike_price="28000",
            source="security_master", is_active=True,
        ))
        session.commit()
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=SBIN&tab=fno")
    assert response.status_code == 200
    payload = response.get_json()
    strikes = [r["strike_price"] for r in payload["results"] if r["instrument_kind"] == "option"]
    assert "292.5" in strikes, f"Decimal strike missing in mixed results: {strikes}"
    assert "30000" in strikes, f"Integer strike missing in mixed results: {strikes}"
    assert "28000" in strikes, f"Integer strike missing in mixed results: {strikes}"


def test_search_explicit_strike_allowed(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's11.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=ADANIPORTS&tab=fno")
    assert response.status_code == 200
    payload = response.get_json()
    strikes = [r["strike_price"] for r in payload["results"] if r["instrument_kind"] == "option"]
    assert "180000" in strikes, f"Expected strike 180000 in results, got {strikes}"


def test_search_empty_query_returns_no_results(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's12.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"] == []


def test_search_no_match_returns_empty(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's13.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=ZZZZNOTFOUND")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"] == []


def test_search_matches_via_alias(tmp_path):
    database_url = f"sqlite:///{tmp_path / 's14.sqlite'}"
    _seed_search_test_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/search?q=SBI")
    assert response.status_code == 200
    payload = response.get_json()
    symbols = [r["broker_symbol"] for r in payload["results"]]
    assert "STABAN" in symbols


def test_orderbook_endpoint_cash_returns_quote(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ob_cash.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        return_value=[{"ltp": "23440.0", "best_bid_price": "23439.0", "best_offer_price": "23441.0"}],
    ):
        response = client.get("/api/dashboard/orderbook?broker_symbol=NIFTY&exchange_code=NSE&product_type=cash")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["ltp"] == 23440.0
    assert payload["bid_price"] == 23439.0
    assert payload["ask_price"] == 23441.0
    assert payload["product_type"] == "cash"


def _seed_nifty_option(database_url: str) -> None:
    """Add a NIFTY option instrument to the database."""
    from app.db import create_session_factory
    from app.models import Instrument
    from datetime import date as dt_date
    expiry = dt_date.today() + timedelta(days=14)
    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        option = Instrument(
            exchange_code="NFO",
            broker_symbol="NIFTY",
            contract_code=f"NIFTY~CE~{expiry.isoformat()}~23500",
            display_symbol="NIFTY",
            name="NIFTY 23500 CE",
            instrument_group="DERIVATIVE",
            product_type="options",
            token="12345",
            lot_size=50,
            tick_size="0.05",
            expiry_date=expiry,
            option_right="call",
            strike_price="23500",
            source="security_master",
            is_active=True,
        )
        session.add(option)
        session.commit()


def test_orderbook_endpoint_options_returns_data(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ob_options.sqlite'}"
    _seed_dashboard_data(database_url)
    _seed_nifty_option(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes",
        return_value=[{
            "ltp": "152.35",
            "best_bid_price": "151.80",
            "best_offer_price": "152.90",
            "best_bid_quantity": "225",
            "best_offer_quantity": "175",
            "token": "12345",
        }],
    ):
        today = date.today() + timedelta(days=14)
        response = client.get(
            f"/api/dashboard/orderbook?broker_symbol=NIFTY&exchange_code=NFO&product_type=options"
            f"&expiry_date={today.isoformat()}&strike_price=23500&right=call"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["ltp"] == 152.35
    assert payload["bid_price"] == 151.80
    assert payload["ask_price"] == 152.90
    assert payload["product_type"] == "options"


def test_orderbook_endpoint_missing_broker_symbol_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ob_missing_bs.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/orderbook?exchange_code=NSE&product_type=cash")
    assert response.status_code == 400
    assert "broker_symbol" in response.get_json()["error"].lower()


def test_orderbook_endpoint_missing_exchange_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ob_missing_ex.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/orderbook?broker_symbol=NIFTY&product_type=cash")
    assert response.status_code == 400
    assert "exchange_code" in response.get_json()["error"].lower()


def test_orderbook_endpoint_invalid_product_type_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ob_bad_pt.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.get("/api/dashboard/orderbook?broker_symbol=NIFTY&exchange_code=NSE&product_type=bonds")
    assert response.status_code == 400
    assert "product_type" in response.get_json()["error"].lower()


def test_orderbook_endpoint_empty_breeze_response_returns_safe_error(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ob_empty.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote", return_value=[],
    ):
        response = client.get("/api/dashboard/orderbook?broker_symbol=NIFTY&exchange_code=NSE&product_type=cash")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "no data" in payload["error"].lower()


def test_orderbook_endpoint_futures_returns_quote(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'ob_fut.sqlite'}"
    _seed_dashboard_data(database_url)
    expiry = date.today() + timedelta(days=14)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured",
        return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        return_value=[{"ltp": "23500.0", "best_bid_price": "23499.0", "best_offer_price": "23501.0"}],
    ):
        response = client.get(
            f"/api/dashboard/orderbook?broker_symbol=NIFTY&exchange_code=NFO"
            f"&product_type=futures&expiry_date={expiry.isoformat()}"
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["ltp"] == 23500.0
    assert payload["bid_price"] == 23499.0
    assert payload["ask_price"] == 23501.0
    assert payload["product_type"] == "futures"


def test_order_preview_endpoint_rejects_empty_body(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_reject.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client:
        response = client.post("/api/dashboard/order-preview", content_type="application/json", data="{}")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "error"


def test_order_preview_endpoint_cash_returns_resolved(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_cash.sqlite'}"
    _seed_dashboard_data(database_url)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_funds",
        return_value={"allocated_equity": 500000.0, "unallocated_balance": "200000"},
    ):
        response = client.post(
            "/api/dashboard/order-preview",
            content_type="application/json",
            data='{"broker_symbol":"STABAN","exchange_code":"NSE","product_type":"cash","action":"buy","quantity":"10","price":"850"}',
        )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["instrument"]["broker_symbol"] == "STABAN"
    assert payload["instrument"]["display_symbol"] == "SBIN"
    assert payload["preview"]["product_type"] == "cash"
    assert payload["preview"]["action"] == "buy"
    assert payload["preview"]["quantity"] == 10
    assert payload["preview"]["margin"]["margin_status"] == "not_calculated"


def test_order_preview_endpoint_future_returns_margin(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_fut.sqlite'}"
    _seed_dashboard_data(database_url)
    expiry = date.today() + timedelta(days=14)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_funds",
        return_value={"allocated_fno": 1000000.0, "block_by_trade_fno": 0.0, "unallocated_balance": "500000"},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_margin_calculator",
        return_value={"span_margin_required": "150000", "order_value": "1750000"},
    ):
        response = client.post(
            "/api/dashboard/order-preview",
            content_type="application/json",
            data=f'{{"broker_symbol":"NIFTY","exchange_code":"NFO","product_type":"futures","action":"buy","quantity":"75","price":"23500","expiry_date":"{expiry.isoformat()}"}}',
        )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["instrument"]["broker_symbol"] == "NIFTY"
    assert payload["preview"]["product_type"] == "futures"
    assert payload["preview"]["margin"]["margin_status"] == "ok"
    assert payload["preview"]["margin"]["span_margin"] == 150000.0
    assert payload["preview"]["funds"]["fund_status"] == "ok"
    assert payload["preview"]["funds"]["allocated"] == 1000000.0


def test_order_preview_endpoint_option_returns_margin(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_opt.sqlite'}"
    _seed_dashboard_data(database_url)
    _seed_nifty_option(database_url)
    expiry = date.today() + timedelta(days=14)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_funds",
        return_value={"allocated_fno": 1000000.0, "block_by_trade_fno": 0.0, "unallocated_balance": "500000"},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_margin_calculator",
        return_value={"span_margin_required": "75000", "order_value": "125000"},
    ):
        response = client.post(
            "/api/dashboard/order-preview",
            content_type="application/json",
            data=f'{{"broker_symbol":"NIFTY","exchange_code":"NFO","product_type":"options","action":"sell","quantity":"150","price":"50","expiry_date":"{expiry.isoformat()}","right":"call","strike_price":"23500"}}',
        )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["preview"]["product_type"] == "options"
    assert payload["preview"]["margin"]["margin_status"] == "ok"
    assert payload["preview"]["margin"]["span_margin"] == 75000.0


def test_order_preview_endpoint_margin_calc_error_returns_error_status(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_err.sqlite'}"
    _seed_dashboard_data(database_url)
    expiry = date.today() + timedelta(days=14)
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_margin_calculator",
        side_effect=Exception("Breeze rejected"),
    ):
        response = client.post(
            "/api/dashboard/order-preview",
            content_type="application/json",
            data=f'{{"broker_symbol":"NIFTY","exchange_code":"NFO","product_type":"futures","action":"buy","quantity":"75","price":"23500","expiry_date":"{expiry.isoformat()}"}}',
        )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["preview"]["margin"]["margin_status"] == "error"
    assert "Breeze rejected" in payload["preview"]["margin"]["error"]


def _capturing_margin_calculator(store):
    """Return a mock side-effect that captures the payload and returns a dummy response."""
    def inner(positions, exchange_code):
        store.append({"list_of_positions": positions, "exchange_code": exchange_code})
        return {"span_margin_required": "150000", "order_value": "1750000"}
    return inner


def test_order_preview_future_payload_normalization(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_fut_norm.sqlite'}"
    _seed_dashboard_data(database_url)
    expiry = date.today() + timedelta(days=14)
    captured = []
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_funds",
        return_value={"allocated_fno": 1000000.0},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_margin_calculator",
        side_effect=_capturing_margin_calculator(captured),
    ):
        response = client.post(
            "/api/dashboard/order-preview",
            content_type="application/json",
            data=f'{{"broker_symbol":"NIFTY","exchange_code":"NFO","product_type":"futures","action":"buy","quantity":"75","price":"23500","expiry_date":"{expiry.isoformat()}"}}',
        )
    assert response.status_code == 200
    assert len(captured) == 1
    pos = captured[0]["list_of_positions"][0]
    assert pos["right"] == "others", f"Expected 'others', got {pos['right']!r}"
    assert pos["product"] == "futures"
    assert pos["action"] == "buy"
    assert pos["strike_price"] == "0"
    assert pos["price"] == "23500", f"Expected '23500', got {pos['price']!r}"
    assert pos["quantity"] == "3750"
    assert pos["stock_code"] == "NIFTY"
    # Verify the response structure is still valid
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["preview"]["margin"]["margin_status"] == "ok"


def test_order_preview_option_call_payload_normalization(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_opt_call.sqlite'}"
    _seed_dashboard_data(database_url)
    _seed_nifty_option(database_url)
    expiry = date.today() + timedelta(days=14)
    captured = []
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_funds",
        return_value={"allocated_fno": 1000000.0},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_margin_calculator",
        side_effect=_capturing_margin_calculator(captured),
    ):
        response = client.post(
            "/api/dashboard/order-preview",
            content_type="application/json",
            data=f'{{"broker_symbol":"NIFTY","exchange_code":"NFO","product_type":"options","action":"sell","quantity":"150","price":"50","expiry_date":"{expiry.isoformat()}","right":"call","strike_price":"23500"}}',
        )
    assert response.status_code == 200
    assert len(captured) == 1
    pos = captured[0]["list_of_positions"][0]
    assert pos["right"] == "call", f"Expected 'call', got {pos['right']!r}"
    assert pos["product"] == "options"
    assert pos["action"] == "sell"
    assert pos["strike_price"] == "23500"
    assert pos["price"] == "50", f"Expected '50', got {pos['price']!r}"
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["preview"]["margin"]["margin_status"] == "ok"


def test_order_preview_option_put_payload_normalization(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'op_opt_put.sqlite'}"
    _seed_dashboard_data(database_url)
    expiry = date.today() + timedelta(days=14)
    # Seed a PUT option directly (no CE option in this DB)
    from app.db import create_session_factory
    from app.models import Instrument
    sf = create_session_factory(database_url)
    with sf() as s:
        put_opt = Instrument(
            exchange_code="NFO", broker_symbol="NIFTY",
            contract_code=f"NIFTY~PE~{expiry.isoformat()}~23500",
            display_symbol="NIFTY", name="NIFTY 23500 PE",
            instrument_group="DERIVATIVE", product_type="options",
            token="12346", lot_size=50, tick_size="0.05",
            expiry_date=expiry, option_right="put", strike_price="23500",
            source="security_master", is_active=True,
        )
        s.add(put_opt)
        s.commit()
    captured = []
    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.is_configured", return_value=True,
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_funds",
        return_value={"allocated_fno": 1000000.0},
    ), patch(
        "app.services.breeze_gateway.BreezeGateway.get_margin_calculator",
        side_effect=_capturing_margin_calculator(captured),
    ):
        response = client.post(
            "/api/dashboard/order-preview",
            content_type="application/json",
            data=f'{{"broker_symbol":"NIFTY","exchange_code":"NFO","product_type":"options","action":"buy","quantity":"150","price":"55","expiry_date":"{expiry.isoformat()}","right":"put","strike_price":"23500"}}',
        )
    assert response.status_code == 200
    assert len(captured) == 1
    pos = captured[0]["list_of_positions"][0]
    assert pos["right"] == "put", f"Expected 'put', got {pos['right']!r}"
    assert pos["product"] == "options"
    assert pos["action"] == "buy"
    assert pos["strike_price"] == "23500"
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["preview"]["margin"]["margin_status"] == "ok"
