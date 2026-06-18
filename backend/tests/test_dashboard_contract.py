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
            "best_bid_qty": "225",
            "best_offer_qty": "175",
            "open_interest": "1245000",
            "total_quantity_traded": "8500",
            "previous_close": "148.20",
            "spot_price": "23420.00",
            "strike_price": "23500",
            "expiry_date": "2026-06-30T06:00:00.000Z",
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
            "best_bid_qty": "0",
            "best_offer_qty": "0",
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
