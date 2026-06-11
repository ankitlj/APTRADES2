from unittest.mock import Mock, patch

import pytest

from app import db
from app.db import create_db_engine, create_session_factory, ensure_tables
from app.models import Instrument
from app.services import symbol_resolver
from app.services.breeze_gateway import BreezeGateway, BreezeInstrument, get_gateway
from app.services.symbol_resolver import SymbolResolver, SymbolResolverError


def _seed_cash(database_url: str) -> None:
    ensure_tables(database_url)
    session_factory = create_session_factory(database_url)
    with session_factory() as session:
        session.add(
            Instrument(
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
                source="stock_script_csv",
                is_active=True,
            )
        )
        session.commit()


# ----- db.py engine + table caching -----------------------------------------


def test_engine_is_reused_for_same_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'reuse.sqlite'}"
    assert create_db_engine(url) is create_db_engine(url)


def test_different_urls_get_different_engines(tmp_path):
    url_a = f"sqlite:///{tmp_path / 'a.sqlite'}"
    url_b = f"sqlite:///{tmp_path / 'b.sqlite'}"
    assert create_db_engine(url_a) is not create_db_engine(url_b)


def test_session_factory_is_reused_for_same_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'reuse.sqlite'}"
    assert create_session_factory(url) is create_session_factory(url)


def test_ensure_tables_is_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'idem.sqlite'}"
    ensure_tables(url)

    with patch("app.models.Base.metadata.create_all") as create_all:
        ensure_tables(url)

    create_all.assert_not_called()
    assert db.normalize_database_url(url) in db._prepared_urls


# ----- symbol resolution TTL cache ------------------------------------------


def test_resolution_cache_returns_cached_after_db_changes(tmp_path):
    url = f"sqlite:///{tmp_path / 'res.sqlite'}"
    _seed_cash(url)
    resolver = SymbolResolver(url)

    first = resolver.resolve("SBIN", "NSE")
    assert first.token == "3045"

    # Remove the row; a cache hit must still return the prior resolution.
    session_factory = create_session_factory(url)
    with session_factory() as session:
        session.query(Instrument).delete()
        session.commit()

    cached = resolver.resolve("SBIN", "NSE")
    assert cached.token == "3045"


def test_resolution_cache_expires_after_ttl(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'res.sqlite'}"
    _seed_cash(url)
    resolver = SymbolResolver(url)

    clock = {"now": 1000.0}
    monkeypatch.setattr(symbol_resolver.time, "monotonic", lambda: clock["now"])

    assert resolver.resolve("SBIN", "NSE").token == "3045"

    session_factory = create_session_factory(url)
    with session_factory() as session:
        session.query(Instrument).delete()
        session.commit()

    # Advance past the TTL so the stale entry is dropped and the DB is re-queried.
    clock["now"] += symbol_resolver._RESOLUTION_TTL_SECONDS + 1
    with pytest.raises(SymbolResolverError):
        resolver.resolve("SBIN", "NSE")


# ----- shared Breeze gateway -------------------------------------------------


def test_get_gateway_reuses_instance_for_same_credentials():
    extensions: dict = {}
    first = get_gateway(extensions, "app", "secret", "token")
    second = get_gateway(extensions, "app", "secret", "token")
    assert first is second


def test_get_gateway_rebuilds_on_token_change():
    extensions: dict = {}
    first = get_gateway(extensions, "app", "secret", "token-old")
    second = get_gateway(extensions, "app", "secret", "token-new")
    assert first is not second


def test_gateway_refreshes_session_token_on_auth_error():
    gateway = BreezeGateway(app_key="app", secret_key="secret", session_token="api-session")
    instrument = BreezeInstrument("SBIN", "STABAN", "NSE", "cash")

    customer_one = Mock(status_code=200)
    customer_one.raise_for_status.return_value = None
    customer_one.json.return_value = {"Success": {"session_token": "cust-1"}}

    quote_unauthorized = Mock(status_code=401)

    customer_two = Mock(status_code=200)
    customer_two.raise_for_status.return_value = None
    customer_two.json.return_value = {"Success": {"session_token": "cust-2"}}

    quote_ok = Mock(status_code=200)
    quote_ok.raise_for_status.return_value = None
    quote_ok.json.return_value = {"Success": [{"ltp": 812.5}]}

    with patch(
        "app.services.breeze_gateway.requests.request",
        side_effect=[customer_one, quote_unauthorized, customer_two, quote_ok],
    ) as request_mock:
        result = gateway.get_quote(instrument)

    assert result[0]["ltp"] == 812.5
    assert request_mock.call_count == 4
    # The retry used the freshly re-exchanged customer session token.
    assert request_mock.call_args.kwargs["headers"]["X-SessionToken"] == "cust-2"
