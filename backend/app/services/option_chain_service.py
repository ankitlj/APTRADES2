from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import Select, func, select

from ..cache import create_redis_client
from ..db import create_session_factory, ensure_tables
from ..models import Instrument
from .breeze_gateway import BreezeGateway, BreezeGatewayError, BreezeInstrument
from .symbol_resolver import SymbolResolver, SymbolResolverError


class OptionChainServiceError(Exception):
    pass


@dataclass(frozen=True)
class OptionExpiryRequest:
    underlying: str
    exchange_code: str = "NFO"


@dataclass(frozen=True)
class OptionChainRequest:
    underlying: str
    expiry_date: date
    exchange_code: str = "NFO"
    strike_count: int = 12


class OptionChainService:
    def __init__(self, database_url: str | None, redis_url: str | None, gateway: BreezeGateway):
        self.database_url = database_url
        self.redis_url = redis_url
        self.gateway = gateway
        self.symbol_resolver = SymbolResolver(database_url)

    def get_expiries(self, request: OptionExpiryRequest) -> dict[str, Any]:
        base_symbol = self._resolve_base_symbol(request.underlying, request.exchange_code)
        expiries = self._list_expiries(base_symbol, request.exchange_code)
        return {
            "status": "ok",
            "underlying": request.underlying.upper(),
            "broker_symbol": base_symbol,
            "exchange_code": request.exchange_code.upper(),
            "expiries": [expiry.isoformat() for expiry in expiries],
        }

    def get_option_chain(self, request: OptionChainRequest) -> dict[str, Any]:
        cache_key = self._cache_key(request)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        base_symbol = self._resolve_base_symbol(request.underlying, request.exchange_code)
        available_expiries = self._list_expiries(base_symbol, request.exchange_code)
        if request.expiry_date not in available_expiries:
            raise OptionChainServiceError(
                f"Expiry {request.expiry_date.isoformat()} is not available for {request.underlying.upper()} on {request.exchange_code.upper()}."
            )

        call_rows = self._load_chain_side(base_symbol, request.exchange_code, request.expiry_date, right="call")
        put_rows = self._load_chain_side(base_symbol, request.exchange_code, request.expiry_date, right="put")

        if not call_rows and not put_rows:
            raise OptionChainServiceError(
                f"No option-chain rows were returned for {request.underlying.upper()} {request.expiry_date.isoformat()}."
            )

        payload = self._normalize_chain_payload(
            request=request,
            broker_symbol=base_symbol,
            call_rows=call_rows,
            put_rows=put_rows,
        )
        self._write_cache(cache_key, payload)
        return payload

    def _resolve_base_symbol(self, underlying: str, exchange_code: str) -> str:
        cash_exchange = "NSE" if exchange_code.upper() == "NFO" else "BSE"
        try:
            resolved = self.symbol_resolver.resolve(underlying, cash_exchange, product_type="cash")
        except SymbolResolverError as error:
            raise OptionChainServiceError(str(error)) from error
        return resolved.broker_symbol

    def _list_expiries(self, broker_symbol: str, exchange_code: str) -> list[date]:
        if not self.database_url:
            raise OptionChainServiceError("DATABASE_URL is not configured.")

        ensure_tables(self.database_url)
        session_factory = create_session_factory(self.database_url)
        statement: Select[tuple[date]] = (
            select(Instrument.expiry_date)
            .where(
                Instrument.exchange_code == exchange_code.upper(),
                Instrument.product_type == "options",
                Instrument.broker_symbol == broker_symbol,
                Instrument.expiry_date.is_not(None),
                Instrument.is_active.is_(True),
                Instrument.expiry_date >= date.today(),
            )
            .group_by(Instrument.expiry_date)
            .order_by(Instrument.expiry_date.asc())
        )
        with session_factory() as session:
            expiries = [value for value in session.scalars(statement).all() if value is not None]

        if not expiries:
            raise OptionChainServiceError(
                f"No option expiries are available for {broker_symbol} on {exchange_code.upper()}. Run master-contract import first."
            )
        return expiries

    def _load_chain_side(
        self,
        broker_symbol: str,
        exchange_code: str,
        expiry_date: date,
        *,
        right: str,
    ) -> list[dict[str, Any]]:
        expiry_value = f"{expiry_date.isoformat()}T06:00:00.000Z"
        instrument = BreezeInstrument(
            display_symbol=broker_symbol,
            stock_code=broker_symbol,
            exchange_code=exchange_code.upper(),
            product_type="options",
            right=right,
            strike_price="0",
            expiry_date=expiry_value,
        )

        try:
            rows = self.gateway.get_option_chain_quotes(instrument)
        except BreezeGatewayError as error:
            raise OptionChainServiceError(str(error)) from error

        if not isinstance(rows, list):
            return []
        return [row for row in rows if isinstance(row, dict)]

    def _normalize_chain_payload(
        self,
        *,
        request: OptionChainRequest,
        broker_symbol: str,
        call_rows: list[dict[str, Any]],
        put_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        combined: dict[str, dict[str, Any]] = {}
        summary_quote = self._summary_quote(call_rows, put_rows)
        underlying_ltp = self._float_value(summary_quote.get("spot_price")) or self._float_value(summary_quote.get("ltp"))
        previous_close = self._float_value(summary_quote.get("previous_close"))

        total_call_oi = 0.0
        total_put_oi = 0.0

        for side, rows in (("ce", call_rows), ("pe", put_rows)):
            for row in rows:
                strike_text = self._strike_text(row)
                if not strike_text:
                    continue
                entry = combined.setdefault(
                    strike_text,
                    {
                        "strike_price": self._float_value(strike_text),
                        "ce": None,
                        "pe": None,
                    },
                )
                normalized = self._normalize_leg(row)
                normalized["broker_symbol"] = broker_symbol
                normalized["expiry_date"] = request.expiry_date.isoformat()
                normalized["strike_price"] = strike_text
                normalized["right"] = "call" if side == "ce" else "put"
                entry[side] = normalized
                if side == "ce":
                    total_call_oi += normalized["oi"] or 0.0
                else:
                    total_put_oi += normalized["oi"] or 0.0

        rows = sorted(
            [row for row in combined.values() if row["strike_price"] is not None],
            key=lambda item: item["strike_price"],
        )
        if not rows:
            raise OptionChainServiceError("Breeze option-chain response did not contain strike prices.")

        atm_strike = self._atm_strike(rows, underlying_ltp)
        visible_rows = self._window_rows(rows, atm_strike, request.strike_count)

        pcr = round(total_put_oi / total_call_oi, 4) if total_call_oi else None
        payload = {
            "status": "ok",
            "underlying": request.underlying.upper(),
            "broker_symbol": broker_symbol,
            "exchange_code": request.exchange_code.upper(),
            "expiry": request.expiry_date.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "underlying_ltp": underlying_ltp,
            "previous_close": previous_close,
            "atm_strike": atm_strike,
            "pcr": pcr,
            "total_call_oi": total_call_oi,
            "total_put_oi": total_put_oi,
            "total_oi": total_call_oi + total_put_oi,
            "rows": visible_rows,
        }
        return payload

    @staticmethod
    def _summary_quote(call_rows: list[dict[str, Any]], put_rows: list[dict[str, Any]]) -> dict[str, Any]:
        for row in call_rows + put_rows:
            if row.get("spot_price") not in (None, "", "0", 0):
                return row
        return (call_rows + put_rows)[0] if (call_rows or put_rows) else {}

    @staticmethod
    def _normalize_leg(row: dict[str, Any]) -> dict[str, Any]:
        token = str(row.get("token") or "").strip() or None
        return {
            "ltp": OptionChainService._float_value(row.get("ltp")),
            "bid": OptionChainService._float_value(row.get("best_bid_price") or row.get("bid_price")),
            "ask": OptionChainService._float_value(row.get("best_offer_price") or row.get("ask_price")),
            "oi": OptionChainService._float_value(
                row.get("open_interest")
                or row.get("oi")
                or row.get("openinterest")
            ),
            "volume": OptionChainService._float_value(
                row.get("total_quantity_traded")
                or row.get("volume")
                or row.get("trade_volume")
            ),
            "token": token,
        }

    @staticmethod
    def _strike_text(row: dict[str, Any]) -> str | None:
        raw = row.get("strike_price") or row.get("strike") or row.get("strikePrice")
        if raw in (None, ""):
            return None
        return str(raw).strip()

    @staticmethod
    def _float_value(value: Any) -> float | None:
        if value in (None, "", "-"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _atm_strike(rows: list[dict[str, Any]], underlying_ltp: float | None) -> float:
        if underlying_ltp is None:
            return rows[len(rows) // 2]["strike_price"]
        return min(rows, key=lambda row: abs((row["strike_price"] or 0.0) - underlying_ltp))["strike_price"]

    @staticmethod
    def _window_rows(rows: list[dict[str, Any]], atm_strike: float, strike_count: int) -> list[dict[str, Any]]:
        if strike_count <= 0 or strike_count >= len(rows):
            return rows

        atm_index = next((index for index, row in enumerate(rows) if row["strike_price"] == atm_strike), len(rows) // 2)
        left = strike_count // 2
        right = strike_count - left
        start = max(atm_index - left, 0)
        end = min(start + strike_count, len(rows))
        if end - start < strike_count:
            start = max(end - strike_count, 0)
        return rows[start:end]

    def _read_cache(self, cache_key: str) -> dict[str, Any] | None:
        if not self.redis_url:
            return None
        try:
            client = create_redis_client(self.redis_url)
            cached = client.get(cache_key)
            client.close()
        except Exception:
            return None
        if not cached:
            return None
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return None

    def _write_cache(self, cache_key: str, payload: dict[str, Any]) -> None:
        if not self.redis_url:
            return
        try:
            client = create_redis_client(self.redis_url)
            client.setex(cache_key, 15, json.dumps(payload))
            client.close()
        except Exception:
            return

    @staticmethod
    def _cache_key(request: OptionChainRequest) -> str:
        return (
            "option-chain:"
            f"{request.exchange_code.upper()}:"
            f"{request.underlying.upper()}:"
            f"{request.expiry_date.isoformat()}:"
            f"{request.strike_count}"
        )
