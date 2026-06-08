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
    assert payload["metrics"][0]["label"] == "NIFTY futures"
    assert payload["metrics"][2]["label"] == "Open positions"
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
    assert any(alert["title"] == "No active positions" for alert in payload["alerts"])


def test_dashboard_chart_endpoint_returns_normalized_points(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'dashboard.sqlite'}"
    _seed_dashboard_data(database_url)

    def _chart_response(instrument, **kwargs):
        assert instrument.stock_code == "NIFTY"
        assert instrument.exchange_code == "NFO"
        assert instrument.product_type == "futures"
        assert instrument.expiry_date.endswith("T06:00:00.000Z")
        assert kwargs["interval"] == "1day"
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
    assert payload["resolved"]["broker_symbol"] == "NIFTY"
    assert len(payload["points"]) == 2
    assert payload["points"][1]["close"] == 23440.0
