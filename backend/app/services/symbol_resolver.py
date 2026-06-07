from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

from sqlalchemy import Select, func, or_, select

from ..db import create_session_factory, ensure_tables
from ..models import Instrument, InstrumentAlias


class SymbolResolverError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedInstrument:
    display_symbol: str
    broker_symbol: str
    exchange_code: str
    product_type: str
    token: str | None
    contract_code: str
    expiry_date: date | None = None
    right: str = "others"
    strike_price: str = "0"
    lot_size: int | None = None
    tick_size: str | None = None
    source: str | None = None
    resolution_source: str = "broker_symbol"


class SymbolResolver:
    def __init__(self, database_url: str | None):
        self.database_url = database_url

    def resolve(
        self,
        symbol: str,
        exchange_code: str,
        *,
        product_type: str | None = None,
        expiry_date: date | None = None,
        right: str | None = None,
        strike_price: str | None = None,
    ) -> ResolvedInstrument:
        if not self.database_url:
            raise SymbolResolverError("DATABASE_URL is not configured.")

        cleaned_symbol = symbol.strip().upper()
        if not cleaned_symbol:
            raise SymbolResolverError("symbol is required.")

        resolved_exchange = exchange_code.strip().upper()
        resolved_product_type = (product_type or self._default_product_type(resolved_exchange)).strip().lower()
        normalized_alias = self._normalize_alias(cleaned_symbol)

        ensure_tables(self.database_url)
        session_factory = create_session_factory(self.database_url)
        with session_factory() as session:
            if resolved_exchange in {"NSE", "BSE"}:
                instrument = self._resolve_cash_instrument(session, cleaned_symbol, normalized_alias, resolved_exchange)
                return self._to_resolved_instrument(instrument, resolution_source="alias")

            base_symbol = self._resolve_base_broker_symbol(session, cleaned_symbol, normalized_alias)
            instrument = self._resolve_derivative_instrument(
                session,
                base_symbol,
                resolved_exchange,
                resolved_product_type,
                expiry_date=expiry_date,
                right=right,
                strike_price=strike_price,
            )
            resolution_source = "alias" if base_symbol != cleaned_symbol else "broker_symbol"
            return self._to_resolved_instrument(instrument, resolution_source=resolution_source)

    @staticmethod
    def _default_product_type(exchange_code: str) -> str:
        if exchange_code in {"NFO", "BFO"}:
            return "futures"
        return "cash"

    def _resolve_cash_instrument(
        self,
        session,
        symbol: str,
        normalized_alias: str,
        exchange_code: str,
    ) -> Instrument:
        statement = (
            select(Instrument)
            .outerjoin(InstrumentAlias, InstrumentAlias.instrument_id == Instrument.id)
            .where(
                Instrument.exchange_code == exchange_code,
                Instrument.product_type == "cash",
                Instrument.is_active.is_(True),
                or_(
                    func.upper(Instrument.broker_symbol) == symbol,
                    func.upper(Instrument.contract_code) == symbol,
                    func.upper(Instrument.display_symbol) == symbol,
                    (
                        (InstrumentAlias.alias_scope == exchange_code)
                        & (InstrumentAlias.normalized_alias == normalized_alias)
                    ),
                ),
            )
            .order_by(Instrument.updated_at.desc())
        )
        instrument = session.scalars(statement).first()
        if not instrument:
            raise SymbolResolverError(f"Unable to resolve cash symbol '{symbol}' for exchange {exchange_code}.")
        return instrument

    def _resolve_base_broker_symbol(self, session, symbol: str, normalized_alias: str) -> str:
        cash_statement = (
            select(Instrument)
            .outerjoin(InstrumentAlias, InstrumentAlias.instrument_id == Instrument.id)
            .where(
                Instrument.exchange_code.in_(["NSE", "BSE"]),
                Instrument.product_type == "cash",
                Instrument.is_active.is_(True),
                or_(
                    func.upper(Instrument.broker_symbol) == symbol,
                    func.upper(Instrument.contract_code) == symbol,
                    func.upper(Instrument.display_symbol) == symbol,
                    InstrumentAlias.normalized_alias == normalized_alias,
                ),
            )
            .order_by(
                Instrument.exchange_code == "NSE",
                Instrument.updated_at.desc(),
            )
        )
        matched_cash = session.scalars(cash_statement).first()
        if matched_cash:
            return matched_cash.broker_symbol.upper()
        return symbol

    def _resolve_derivative_instrument(
        self,
        session,
        base_symbol: str,
        exchange_code: str,
        product_type: str,
        *,
        expiry_date: date | None,
        right: str | None,
        strike_price: str | None,
    ) -> Instrument:
        statement: Select[tuple[Instrument]] = select(Instrument).where(
            Instrument.exchange_code == exchange_code,
            Instrument.product_type == product_type,
            Instrument.broker_symbol == base_symbol,
            Instrument.is_active.is_(True),
        )

        if expiry_date is not None:
            statement = statement.where(Instrument.expiry_date == expiry_date)
        elif product_type == "futures":
            statement = statement.order_by(
                Instrument.expiry_date.is_(None),
                Instrument.expiry_date.asc(),
                Instrument.updated_at.desc(),
            )

        if product_type == "options":
            expected_right = (right or "others").lower()
            expected_strike = strike_price or "0"
            statement = statement.where(
                Instrument.option_right == expected_right,
                Instrument.strike_price == expected_strike,
            ).order_by(
                Instrument.expiry_date.is_(None),
                Instrument.expiry_date.asc(),
                Instrument.updated_at.desc(),
            )

        instrument = session.scalars(statement).first()
        if not instrument:
            raise SymbolResolverError(
                f"Unable to resolve {product_type} contract for '{base_symbol}' on exchange {exchange_code}."
            )
        return instrument

    @staticmethod
    def _to_resolved_instrument(instrument: Instrument, *, resolution_source: str) -> ResolvedInstrument:
        return ResolvedInstrument(
            display_symbol=instrument.display_symbol or instrument.broker_symbol,
            broker_symbol=instrument.broker_symbol,
            exchange_code=instrument.exchange_code,
            product_type=instrument.product_type or "cash",
            token=instrument.token,
            contract_code=instrument.contract_code,
            expiry_date=instrument.expiry_date,
            right=instrument.option_right or "others",
            strike_price=instrument.strike_price or "0",
            lot_size=instrument.lot_size,
            tick_size=instrument.tick_size,
            source=instrument.source,
            resolution_source=resolution_source,
        )

    @staticmethod
    def _normalize_alias(alias: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", alias.upper())
