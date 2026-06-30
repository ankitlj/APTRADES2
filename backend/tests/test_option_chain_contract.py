from datetime import date, timedelta
from unittest.mock import patch

from app import create_app
from app.db import create_session_factory, ensure_tables
from app.models import Instrument, InstrumentAlias


def _seed_option_chain_data(database_url: str) -> None:
    today = date.today()
    expiry = today + timedelta(days=14)
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
            source="seed_aliases",
            is_active=True,
        )
        option_rows = [
            Instrument(
                exchange_code="NFO",
                broker_symbol="NIFTY",
                contract_code=f"NIFTY~O:{expiry.strftime('%d-%b-%Y').upper()}:call:23200",
                display_symbol="NIFTY",
                name="NIFTY CE 23200",
                instrument_group="DERIVATIVE",
                product_type="options",
                token="90001",
                lot_size=50,
                tick_size="0.05",
                expiry_date=expiry,
                option_right="call",
                strike_price="23200",
                source="security_master",
                is_active=True,
            ),
            Instrument(
                exchange_code="NFO",
                broker_symbol="NIFTY",
                contract_code=f"NIFTY~O:{expiry.strftime('%d-%b-%Y').upper()}:put:23200",
                display_symbol="NIFTY",
                name="NIFTY PE 23200",
                instrument_group="DERIVATIVE",
                product_type="options",
                token="90002",
                lot_size=50,
                tick_size="0.05",
                expiry_date=expiry,
                option_right="put",
                strike_price="23200",
                source="security_master",
                is_active=True,
            ),
            Instrument(
                exchange_code="NFO",
                broker_symbol="NIFTY",
                contract_code=f"NIFTY~O:{expiry.strftime('%d-%b-%Y').upper()}:call:23300",
                display_symbol="NIFTY",
                name="NIFTY CE 23300",
                instrument_group="DERIVATIVE",
                product_type="options",
                token="90003",
                lot_size=50,
                tick_size="0.05",
                expiry_date=expiry,
                option_right="call",
                strike_price="23300",
                source="security_master",
                is_active=True,
            ),
            Instrument(
                exchange_code="NFO",
                broker_symbol="NIFTY",
                contract_code=f"NIFTY~O:{expiry.strftime('%d-%b-%Y').upper()}:put:23300",
                display_symbol="NIFTY",
                name="NIFTY PE 23300",
                instrument_group="DERIVATIVE",
                product_type="options",
                token="90004",
                lot_size=50,
                tick_size="0.05",
                expiry_date=expiry,
                option_right="put",
                strike_price="23300",
                source="security_master",
                is_active=True,
            ),
        ]
        session.add_all([nifty_cash, banknifty_cash, *option_rows])
        session.flush()
        session.add(
            InstrumentAlias(
                instrument_id=banknifty_cash.id,
                alias="BANKNIFTY",
                normalized_alias="BANKNIFTY",
                alias_scope="NSE",
                alias_type="display",
                source="seed_aliases",
            )
        )
        session.commit()


def _client_with_db(database_url: str):
    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=database_url)
    return app.test_client()


def _option_chain_response(instrument):
    if instrument.right == "call":
        return [
            {
                "strike_price": "23200",
                "ltp": 145.5,
                "best_bid_price": 145.0,
                "best_offer_price": 146.1,
                "open_interest": 120000,
                "total_quantity_traded": 18000,
                "spot_price": 23268.8,
                "previous_close": 23451.7,
                "expiry_date": "30-Jun-2026",
                "token": "90001",
            },
            {
                "strike_price": "23300",
                "ltp": 92.8,
                "best_bid_price": 92.2,
                "best_offer_price": 93.1,
                "open_interest": 115000,
                "total_quantity_traded": 16000,
                "spot_price": 23268.8,
                "previous_close": 23451.7,
                "expiry_date": "30-Jun-2026",
                "token": "90003",
            },
        ]
    return [
        {
            "strike_price": "23200",
            "ltp": 118.2,
            "best_bid_price": 117.8,
            "best_offer_price": 118.7,
            "open_interest": 95000,
            "total_quantity_traded": 12000,
            "spot_price": 23268.8,
            "previous_close": 23451.7,
            "expiry_date": "30-Jun-2026",
            "token": "90002",
        },
        {
            "strike_price": "23300",
            "ltp": 165.4,
            "best_bid_price": 164.8,
            "best_offer_price": 166.1,
            "open_interest": 132000,
            "total_quantity_traded": 21000,
            "spot_price": 23268.8,
            "previous_close": 23451.7,
            "expiry_date": "30-Jun-2026",
            "token": "90004",
        },
    ]


def test_option_expiries_endpoint_returns_available_expiries(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'option_chain.sqlite'}"
    _seed_option_chain_data(database_url)

    with _client_with_db(database_url) as client:
        response = client.get("/api/options/expiries?underlying=NIFTY")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["underlying"] == "NIFTY"
    assert len(payload["expiries"]) == 1


def test_option_chain_endpoint_returns_normalized_rows(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'option_chain.sqlite'}"
    _seed_option_chain_data(database_url)
    expiry = (date.today() + timedelta(days=14)).isoformat()

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes",
        side_effect=_option_chain_response,
    ):
        response = client.get(f"/api/option-chain?underlying=NIFTY&expiry={expiry}&strike_count=2")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["underlying"] == "NIFTY"
    assert payload["broker_symbol"] == "NIFTY"
    assert payload["atm_strike"] == 23300.0
    assert payload["rows"][0]["ce"]["ltp"] == 145.5
    assert payload["rows"][0]["ce"]["token"] == "90001"
    assert payload["rows"][0]["ce"]["broker_symbol"] == "NIFTY"
    assert payload["rows"][0]["ce"]["expiry_date"] == expiry
    assert payload["rows"][0]["ce"]["strike_price"] == "23200"
    assert payload["rows"][0]["ce"]["right"] == "call"
    assert payload["rows"][0]["pe"]["token"] == "90002"
    assert payload["rows"][0]["pe"]["right"] == "put"
    assert payload["rows"][1]["pe"]["oi"] == 132000.0
    assert payload["pcr"] == round((95000 + 132000) / (120000 + 115000), 4)
