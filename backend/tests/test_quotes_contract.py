from datetime import date
from unittest.mock import patch

from app import create_app
from app.db import create_session_factory, ensure_tables
from app.models import Instrument, InstrumentAlias


def _seed_quote_data(database_url: str) -> None:
    ensure_tables(database_url)
    session_factory = create_session_factory(database_url)
    with session_factory() as session:
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
        nifty_future = Instrument(
            exchange_code="NFO",
            broker_symbol="NIFTY",
            contract_code="NIFTY~F:25-Jun-2026",
            display_symbol="NIFTY",
            name="NIFTY FUTURE",
            instrument_group="DERIVATIVE",
            product_type="futures",
            token="62001",
            lot_size=50,
            tick_size="0.05",
            expiry_date=date(2026, 6, 25),
            option_right="others",
            strike_price="0",
            source="security_master",
            is_active=True,
        )
        session.add_all([sbin, nifty_cash, nifty_future])
        session.flush()
        session.add_all(
            [
                InstrumentAlias(
                    instrument_id=sbin.id,
                    alias="SBIN",
                    normalized_alias="SBIN",
                    alias_scope="NSE",
                    alias_type="display",
                    source="stock_script_csv",
                ),
                InstrumentAlias(
                    instrument_id=nifty_cash.id,
                    alias="NIFTY",
                    normalized_alias="NIFTY",
                    alias_scope="NSE",
                    alias_type="display",
                    source="seed_aliases",
                ),
            ]
        )
        session.commit()


def _client_with_db(database_url: str):
    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=database_url)
    return app.test_client()


def test_get_quote_endpoint_returns_resolved_quote(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'quotes.sqlite'}"
    _seed_quote_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        return_value=[{"ltp": 977.7, "previous_close": 979.25, "spot_price": None, "expiry_date": None}],
    ):
        response = client.get("/api/quotes?symbol=SBIN&exchange=NSE")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["resolved"]["broker_symbol"] == "STABAN"
    assert payload["quote"]["ltp"] == 977.7


def test_batch_quotes_endpoint_returns_nfo_future_resolution(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'quotes.sqlite'}"
    _seed_quote_data(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_quote",
        return_value=[{"ltp": 23832.85, "previous_close": 23785.4, "spot_price": 23783.7, "expiry_date": "25-Jun-2026"}],
    ):
        response = client.post(
            "/api/quotes/batch",
            json={"symbols": [{"symbol": "NIFTY", "exchange": "NFO", "product_type": "futures"}]},
        )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["results"][0]["resolved"]["broker_symbol"] == "NIFTY"
    assert payload["results"][0]["resolved"]["exchange_code"] == "NFO"
    assert payload["results"][0]["resolved"]["expiry_date"] == "2026-06-25"
