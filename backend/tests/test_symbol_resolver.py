from datetime import date

from app.db import create_session_factory, ensure_tables
from app.models import Instrument, InstrumentAlias
from app.services.symbol_resolver import SymbolResolver


def _seed_symbol_data(database_url: str) -> None:
    ensure_tables(database_url)
    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        relind = Instrument(
            exchange_code="NSE",
            broker_symbol="RELIND",
            contract_code="RELIND",
            display_symbol="RELIANCE",
            name="RELIANCE INDUSTRIES",
            instrument_group="EQUITY",
            product_type="cash",
            token="2885",
            lot_size=1,
            tick_size="0.1",
            isin="INE002A01018",
            series="EQ",
            source="stock_script_csv",
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
        cnxban_cash = Instrument(
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
        cnxban_future = Instrument(
            exchange_code="NFO",
            broker_symbol="CNXBAN",
            contract_code="CNXBAN~F:25-Jun-2026",
            display_symbol="BANKNIFTY",
            name="NIFTY BANK FUTURE",
            instrument_group="DERIVATIVE",
            product_type="futures",
            token="63001",
            lot_size=30,
            tick_size="0.05",
            expiry_date=date(2026, 6, 25),
            option_right="others",
            strike_price="0",
            source="security_master",
            is_active=True,
        )
        session.add_all([relind, sbin, cnxban_cash, cnxban_future])
        session.flush()
        session.add_all(
            [
                InstrumentAlias(
                    instrument_id=relind.id,
                    alias="RELIANCE",
                    normalized_alias="RELIANCE",
                    alias_scope="NSE",
                    alias_type="display",
                    source="stock_script_csv",
                ),
                InstrumentAlias(
                    instrument_id=sbin.id,
                    alias="SBIN",
                    normalized_alias="SBIN",
                    alias_scope="NSE",
                    alias_type="display",
                    source="stock_script_csv",
                ),
                InstrumentAlias(
                    instrument_id=cnxban_cash.id,
                    alias="BANKNIFTY",
                    normalized_alias="BANKNIFTY",
                    alias_scope="NSE",
                    alias_type="display",
                    source="seed_aliases",
                ),
            ]
        )
        session.commit()


def test_symbol_resolver_resolves_cash_alias(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'resolver.sqlite'}"
    _seed_symbol_data(database_url)

    resolved = SymbolResolver(database_url).resolve("SBIN", "NSE")

    assert resolved.display_symbol == "SBIN"
    assert resolved.broker_symbol == "STABAN"
    assert resolved.exchange_code == "NSE"
    assert resolved.product_type == "cash"


def test_symbol_resolver_resolves_banknifty_to_nearest_future(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'resolver.sqlite'}"
    _seed_symbol_data(database_url)

    resolved = SymbolResolver(database_url).resolve("BANKNIFTY", "NFO", product_type="futures")

    assert resolved.display_symbol == "BANKNIFTY"
    assert resolved.broker_symbol == "CNXBAN"
    assert resolved.exchange_code == "NFO"
    assert resolved.product_type == "futures"
    assert resolved.expiry_date == date(2026, 6, 25)
