from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from flask import current_app

from .breeze_gateway import BreezeGateway, BreezeGatewayError
from .quote_service import QuoteRequest, QuoteService, QuoteServiceError

# Short TTL cache so parallel dashboard summary + alerts requests share one
# Breeze portfolio positions call instead of making two redundant calls.
# Cache lives on flask.current_app.config (isolated per Flask app instance).
_POSITIONS_CACHE_TTL = 15
_POSITIONS_CACHE_KEY = "_POSITIONS_CACHE"
_positions_cache_lock = threading.Lock()


class PositionsServiceError(Exception):
    pass


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    broker_symbol: str
    exchange_code: str
    product_type: str
    quantity: float
    average_price: float | None
    ltp: float | None
    pnl: float | None
    expiry_date: str | None
    right: str | None
    strike_price: str | None
    segment: str | None
    direction: str
    quote_status: str
    quote_error: str | None
    pnl_percent: float | None
    resolution_source: str | None
    token: str | None


class PositionsService:
    def __init__(self, gateway: BreezeGateway, database_url: str | None):
        self.gateway = gateway
        self.quote_service = QuoteService(database_url, gateway)

    def get_positions(
        self,
        *,
        _force_refresh: bool = False,
        gateway_timeout: int | None = None,
        gateway_attempts: int | None = None,
    ) -> dict[str, Any]:
        if not self.gateway.is_configured():
            return {
                "status": "not_configured",
                "quote_status": "not_configured",
                "close_actions_active": False,
                "positions": [],
                "totals": self._empty_totals(),
            }

        now = time.monotonic()
        if not _force_refresh:
            cache_store = self._get_cache_store()
            if cache_store is not None:
                with _positions_cache_lock:
                    entry = cache_store.get(_POSITIONS_CACHE_KEY)
                if entry is not None and (now - entry[0]) < _POSITIONS_CACHE_TTL:
                    return entry[1]

        try:
            raw_positions = self.gateway.get_portfolio_positions(timeout_override=gateway_timeout, attempts_override=gateway_attempts)
        except BreezeGatewayError as error:
            if "No Positions" in str(error):
                empty = {
                    "status": "ok",
                    "quote_status": "ok",
                    "close_actions_active": False,
                    "positions": [],
                    "totals": self._empty_totals(),
                }
                self._set_cache(empty)
                return empty
            raise PositionsServiceError(str(error)) from error

        normalized = [self._normalize_position(item) for item in raw_positions if isinstance(item, dict)]
        active_positions = [position for position in normalized if position.quantity != 0]
        quote_status = "ok"
        if active_positions and any(position.quote_status != "ok" for position in active_positions):
            quote_status = "partial"
        result = {
            "status": "ok",
            "quote_status": quote_status,
            "close_actions_active": False,
            "positions": [self._serialize_position(position) for position in active_positions],
            "totals": self._totals(active_positions),
        }
        self._set_cache(result)
        return result

    def get_cached_positions(self) -> dict[str, Any] | None:
        cache_store = self._get_cache_store()
        if cache_store is None:
            return None
        with _positions_cache_lock:
            entry = cache_store.get(_POSITIONS_CACHE_KEY)
        if entry is None:
            return None
        if (time.monotonic() - entry[0]) >= _POSITIONS_CACHE_TTL:
            return None
        return entry[1]

    @staticmethod
    def _get_cache_store() -> dict[str, Any] | None:
        try:
            return current_app.config
        except RuntimeError:
            return None

    def _set_cache(self, value: dict[str, Any]) -> None:
        cache_store = self._get_cache_store()
        if cache_store is not None:
            with _positions_cache_lock:
                cache_store[_POSITIONS_CACHE_KEY] = (time.monotonic(), value)

    def _normalize_position(self, item: dict[str, Any]) -> PositionSnapshot:
        product_type = str(item.get("product_type") or "").strip().lower() or "cash"
        quantity = PositionsService._to_float(item.get("quantity")) or 0.0
        symbol = str(item.get("underlying") or item.get("stock_code") or "UNKNOWN").strip().upper()
        broker_symbol = str(item.get("stock_code") or item.get("underlying") or "UNKNOWN").strip().upper()
        exchange_code = str(item.get("exchange_code") or "").strip().upper()
        average_price = PositionsService._to_float(item.get("average_price") or item.get("price"))
        raw_ltp = PositionsService._to_float(item.get("ltp"))
        raw_pnl = PositionsService._to_float(item.get("pnl"))
        expiry_date = str(item.get("expiry_date")).strip() if item.get("expiry_date") else None
        right = str(item.get("right")).strip() if item.get("right") else None
        strike_price = str(item.get("strike_price")).strip() if item.get("strike_price") is not None else None
        segment = str(item.get("segment")).strip().lower() if item.get("segment") else None
        direction = "long" if quantity > 0 else "short"

        ltp = raw_ltp
        pnl = raw_pnl
        pnl_percent = PositionsService._calculate_pnl_percent(raw_pnl, average_price, quantity)
        quote_status = "unknown"
        quote_error = None
        resolution_source = None
        token = None

        try:
            quote_payload = self.quote_service.get_quote(
                QuoteRequest(
                    symbol=broker_symbol,
                    exchange_code=exchange_code,
                    product_type=product_type,
                    expiry_date=self._parse_expiry_date(expiry_date),
                    right=right,
                    strike_price=strike_price,
                )
            )
            quote = quote_payload.get("quote") or {}
            resolved = quote_payload.get("resolved") or {}
            quote_ltp = PositionsService._to_float(quote.get("ltp"))
            if quote_ltp is not None:
                ltp = quote_ltp
            if average_price is not None and ltp is not None:
                pnl = round((ltp - average_price) * quantity, 2)
                pnl_percent = PositionsService._calculate_pnl_percent(pnl, average_price, quantity)
            quote_status = "ok"
            resolution_source = resolved.get("resolution_source")
            token = resolved.get("token")
            symbol = str(resolved.get("display_symbol") or symbol).strip().upper()
            broker_symbol = str(resolved.get("broker_symbol") or broker_symbol).strip().upper()
            exchange_code = str(resolved.get("exchange_code") or exchange_code).strip().upper()
            product_type = str(resolved.get("product_type") or product_type).strip().lower() or product_type
            if resolved.get("expiry_date"):
                expiry_date = str(resolved["expiry_date"])
        except QuoteServiceError as error:
            quote_status = "error"
            quote_error = str(error)

        return PositionSnapshot(
            symbol=symbol,
            broker_symbol=broker_symbol,
            exchange_code=exchange_code,
            product_type=product_type,
            quantity=quantity,
            average_price=average_price,
            ltp=ltp,
            pnl=pnl,
            expiry_date=expiry_date,
            right=right,
            strike_price=strike_price,
            segment=segment,
            direction=direction,
            quote_status=quote_status,
            quote_error=quote_error,
            pnl_percent=pnl_percent,
            resolution_source=resolution_source,
            token=token,
        )

    @staticmethod
    def _serialize_position(position: PositionSnapshot) -> dict[str, Any]:
        return {
            "symbol": position.symbol,
            "broker_symbol": position.broker_symbol,
            "exchange_code": position.exchange_code,
            "product_type": position.product_type,
            "quantity": position.quantity,
            "average_price": position.average_price,
            "ltp": position.ltp,
            "pnl": position.pnl,
            "expiry_date": position.expiry_date,
            "right": position.right,
            "strike_price": position.strike_price,
            "segment": position.segment,
            "direction": position.direction,
            "quote_status": position.quote_status,
            "quote_error": position.quote_error,
            "pnl_percent": position.pnl_percent,
            "resolution_source": position.resolution_source,
            "token": position.token,
        }

    @staticmethod
    def _totals(positions: list[PositionSnapshot]) -> dict[str, Any]:
        unrealized_pnl = round(sum(position.pnl or 0.0 for position in positions), 2)
        return {
            "open_positions": len(positions),
            "long_positions": sum(1 for position in positions if position.quantity > 0),
            "short_positions": sum(1 for position in positions if position.quantity < 0),
            "option_positions": sum(1 for position in positions if PositionsService._position_bucket(position) == "option"),
            "future_positions": sum(1 for position in positions if PositionsService._position_bucket(position) == "future"),
            "equity_positions": sum(1 for position in positions if PositionsService._position_bucket(position) == "equity"),
            "realized_pnl": 0.0,
            "unrealized_pnl": unrealized_pnl,
            "day_pnl": unrealized_pnl,
            "total_pnl": unrealized_pnl,
        }

    @staticmethod
    def _empty_totals() -> dict[str, Any]:
        return {
            "open_positions": 0,
            "long_positions": 0,
            "short_positions": 0,
            "option_positions": 0,
            "future_positions": 0,
            "equity_positions": 0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "day_pnl": 0.0,
            "total_pnl": 0.0,
        }

    @staticmethod
    def _position_bucket(position: PositionSnapshot) -> str:
        product_type = (position.product_type or "").lower()
        right = (position.right or "").lower()
        if product_type in {"options", "option"} or right in {"call", "put"}:
            return "option"
        if product_type in {"futures", "future"} or (position.expiry_date and position.exchange_code in {"NFO", "BFO"}):
            return "future"
        return "equity"

    @staticmethod
    def _parse_expiry_date(value: str | None) -> date | None:
        if not value:
            return None
        cleaned = value.strip()
        for parser in (
            lambda candidate: date.fromisoformat(candidate),
            lambda candidate: datetime.strptime(candidate, "%d-%b-%Y").date(),
            lambda candidate: datetime.strptime(candidate, "%d-%b-%y").date(),
        ):
            try:
                return parser(cleaned)
            except ValueError:
                continue
        return None

    @staticmethod
    def _calculate_pnl_percent(pnl: float | None, average_price: float | None, quantity: float) -> float | None:
        if pnl is None or average_price in (None, 0) or quantity == 0:
            return None
        base_value = abs(quantity) * average_price
        if base_value == 0:
            return None
        return round((pnl / base_value) * 100, 2)

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None
