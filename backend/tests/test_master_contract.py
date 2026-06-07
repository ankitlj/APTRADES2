from pathlib import Path
from unittest.mock import patch

from app.db import create_session_factory
from app.models import Instrument
from app.services.master_contract_service import MasterContractService, SourcePayload


CSV_HEADER = "SC,SN,EC,SM,SG,TK,LS,CD,NS,TS,ISIN,SR,SI\n"
CSV_ROWS = [
    "RELIND,RELIANCE INDUSTRIES,NSE,RELIND,EQUITY,2885,1,RELIND,RELIANCE,0.1,INE002A01018,EQ,\n",
    "ADAPOR,ADANI PORT AND SPECIAL ECONO,NSE,ADAPOR,EQUITY,15083,1,ADAPOR,ADANIPORTS,0.1,INE742F01042,EQ,\n",
    "CNXBAN,NIFTY BANK,NSE,CNXBAN,EQUITY,NIFTY BANK,1,CNXBAN,BANK NIFTY,0,,0,\n",
    "RELIND,RELIANCE INDUSTRIES,NFO,RELIND~F:30-Mar-2026,DERIVATIVE,52023,500,FUT-RELIND-30-Mar-2026,RELIANCE,10,,,\n",
]


def _write_csv(path: Path) -> None:
    path.write_text(CSV_HEADER + "".join(CSV_ROWS), encoding="utf-8")


def test_master_contract_status_not_configured():
    service = MasterContractService(database_url=None, stock_script_csv_path=None, security_master_url="http://example.com")

    payload = service.get_status()

    assert payload["status"] == "not_configured"
    assert payload["database_configured"] is False


def test_master_contract_resolves_repo_relative_stock_script_path():
    service = MasterContractService(
        database_url=None,
        stock_script_csv_path="data/StockScriptNew.csv",
        security_master_url="http://example.com",
    )

    assert service._csv_available() is True


def test_master_contract_maps_security_master_cash_row():
    service = MasterContractService(None, None, "http://example.com")

    mapped = service._security_master_row_to_stock_script_row(
        {
            "Token": "2885",
            "ShortName": "RELIND",
            "Series": "EQ",
            "CompanyName": "RELIANCE INDUSTRIES",
            "Lotsize": "1",
            "ticksize": "0.1",
            "ISINCode": "INE002A01018",
            "ExchangeCode": "RELIANCE",
        },
        "NSE",
    )

    assert mapped is not None
    assert mapped["SC"] == "RELIND"
    assert mapped["EC"] == "NSE"
    assert mapped["NS"] == "RELIANCE"
    assert mapped["__source_name"] == "security_master"


def test_master_contract_maps_security_master_future_row():
    service = MasterContractService(None, None, "http://example.com")

    mapped = service._security_master_row_to_stock_script_row(
        {
            "Token": "62873",
            "InstrumentName": "FUTSTK",
            "ShortName": "WAAENE",
            "Series": "FUTURE",
            "ExpiryDate": "30-Jun-2026",
            "StrikePrice": "0",
            "OptionType": "XX",
            "LotSize": "500",
            "TickSize": "0.05",
            "CompanyName": "WAAREE ENERGIES LIMITED",
        },
        "NFO",
    )

    assert mapped is not None
    assert mapped["EC"] == "NFO"
    assert mapped["SM"] == "WAAENE~F:30-Jun-2026"
    assert mapped["SG"] == "DERIVATIVE"


def test_master_contract_import_uses_csv_when_security_master_is_unavailable(tmp_path):
    csv_path = tmp_path / "StockScriptNew.csv"
    db_path = tmp_path / "master_contract.sqlite"
    _write_csv(csv_path)
    service = MasterContractService(
        database_url=f"sqlite:///{db_path}",
        stock_script_csv_path=str(csv_path),
        security_master_url="http://example.com/securitymaster.zip",
    )

    with patch.object(
        service,
        "_load_security_master_rows",
        return_value=SourcePayload(
            name="security_master",
            rows=[],
            digest_source=None,
            warnings=["SecurityMaster download failed: timeout"],
        ),
    ):
        payload = service.import_master_contract()

    assert payload["status"] == "ok"
    assert payload["row_count"] == 6
    assert payload["alias_count"] >= 4
    assert "SecurityMaster download failed: timeout" in payload["warnings"]

    status = service.get_status()
    assert status["instrument_count"] == 6
    assert status["alias_count"] >= 4
    assert status["latest_run"]["status"] == "success"
    assert status["verified_aliases"][0]["broker_symbol"] == "RELIND"

    session_factory = create_session_factory(f"sqlite:///{db_path}")
    with session_factory() as session:
        future_contract = session.query(Instrument).filter_by(exchange_code="NFO", broker_symbol="RELIND").one()

    assert future_contract.product_type == "futures"
    assert future_contract.expiry_date.isoformat() == "2026-03-30"


def test_master_contract_import_falls_back_to_seed_rows_when_no_sources_are_available(tmp_path):
    db_path = tmp_path / "master_contract.sqlite"
    service = MasterContractService(
        database_url=f"sqlite:///{db_path}",
        stock_script_csv_path=str(tmp_path / "missing.csv"),
        security_master_url="http://example.com/securitymaster.zip",
    )

    with patch.object(
        service,
        "_load_security_master_rows",
        return_value=SourcePayload(
            name="security_master",
            rows=[],
            digest_source=None,
            warnings=["SecurityMaster download failed: timeout"],
        ),
    ):
        payload = service.import_master_contract()

    assert payload["status"] == "ok"
    assert payload["row_count"] == 5
    assert payload["alias_count"] >= 5
    assert any("fallback seeded aliases" in warning.lower() for warning in payload["warnings"])


def test_master_contract_status_endpoint_returns_not_configured(client):
    response = client.get("/api/master-contract/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "not_configured"


def test_master_contract_import_endpoint_requires_database(client):
    response = client.post("/api/master-contract/import")

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "DATABASE_URL is not configured" in payload["error"]
