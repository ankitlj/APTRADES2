from datetime import date, timedelta
from unittest.mock import patch

from app import create_app
from app.db import create_session_factory, ensure_tables
from app.models import Instrument


def _seed_nifty_options(database_url: str) -> date:
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
        strikes = [23200, 23300, 23400]
        options = [
            Instrument(
                exchange_code="NFO",
                broker_symbol="NIFTY",
                contract_code=f"NIFTY~O:{expiry.strftime('%d-%b-%Y').upper()}:{right}:{strike}",
                display_symbol="NIFTY",
                name=f"NIFTY {'CE' if right == 'call' else 'PE'} {strike}",
                instrument_group="DERIVATIVE",
                product_type="options",
                token=str(9000 + idx),
                lot_size=50,
                tick_size="0.05",
                expiry_date=expiry,
                option_right=right,
                strike_price=str(strike),
                source="security_master",
                is_active=True,
            )
            for idx, (right, strike) in enumerate(
                [(side, s) for s in strikes for side in ("call", "put")]
            )
        ]
        session.add_all([nifty_cash, *options])
        session.commit()
    return expiry


def _client_with_db(database_url: str):
    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=database_url)
    return app.test_client()


# CE OI: 23200=150000, 23300=95000, 23400=50000
# PE OI: 23200=80000,  23300=200000, 23400=60000
# Total: 23200=230000, 23300=295000, 23400=110000
# Sorted by total: 23300, 23200, 23400
def _mock_chain_quotes(instrument):
    ce_oi_map = {"23200": 150000, "23300": 95000, "23400": 50000}
    pe_oi_map = {"23200": 80000, "23300": 200000, "23400": 60000}
    ce_ltp_map = {"23200": 145.5, "23300": 92.8, "23400": 55.0}
    pe_ltp_map = {"23200": 118.2, "23300": 165.4, "23400": 90.0}
    if instrument.right == "call":
        return [
            {
                "strike_price": s,
                "ltp": ce_ltp_map[s],
                "open_interest": ce_oi_map[s],
                "total_quantity_traded": 10000,
                "spot_price": 23268.8,
                "previous_close": 23451.7,
                "expiry_date": "30-Jun-2026",
            }
            for s in ["23200", "23300", "23400"]
        ]
    return [
        {
            "strike_price": s,
            "ltp": pe_ltp_map[s],
            "open_interest": pe_oi_map[s],
            "total_quantity_traded": 10000,
            "spot_price": 23268.8,
            "previous_close": 23451.7,
            "expiry_date": "30-Jun-2026",
        }
        for s in ["23200", "23300", "23400"]
    ]


def test_oi_tracker_missing_params_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'oi.sqlite'}"
    with _client_with_db(database_url) as client:
        response = client.get("/api/oi/tracker")
    assert response.status_code == 400
    assert "required" in response.get_json()["error"]


def test_oi_profile_missing_params_returns_400(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'oi.sqlite'}"
    with _client_with_db(database_url) as client:
        response = client.get("/api/oi/profile")
    assert response.status_code == 400
    assert "required" in response.get_json()["error"]


def test_oi_tracker_rows_sorted_by_total_oi_descending(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'oi_tracker.sqlite'}"
    expiry = _seed_nifty_options(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes",
        side_effect=_mock_chain_quotes,
    ):
        response = client.get(f"/api/oi/tracker?underlying=NIFTY&expiry={expiry.isoformat()}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["underlying"] == "NIFTY"
    rows = payload["rows"]
    assert len(rows) == 3
    for i in range(len(rows) - 1):
        assert rows[i]["total_oi"] >= rows[i + 1]["total_oi"]
    assert rows[0]["strike_price"] == 23300.0
    assert payload["max_ce_oi_strike"] == 23200.0
    assert payload["max_pe_oi_strike"] == 23300.0


def test_oi_profile_rows_sorted_by_strike_ascending(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'oi_profile.sqlite'}"
    expiry = _seed_nifty_options(database_url)

    with _client_with_db(database_url) as client, patch(
        "app.services.breeze_gateway.BreezeGateway.get_option_chain_quotes",
        side_effect=_mock_chain_quotes,
    ):
        response = client.get(f"/api/oi/profile?underlying=NIFTY&expiry={expiry.isoformat()}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    rows = payload["rows"]
    assert len(rows) == 3
    for i in range(len(rows) - 1):
        assert rows[i]["strike_price"] <= rows[i + 1]["strike_price"]
    assert rows[0]["strike_price"] == 23200.0
    assert rows[0]["ce_oi"] == 150000.0
    assert rows[0]["pe_oi"] == 80000.0
    assert rows[2]["strike_price"] == 23400.0
