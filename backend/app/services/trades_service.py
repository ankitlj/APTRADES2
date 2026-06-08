from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .breeze_gateway import BreezeGateway, BreezeGatewayError


class TradesServiceError(Exception):
    pass


@dataclass(frozen=True)
class TradeQuery:
    exchange_code: str = "NFO"
    from_date: datetime | None = None
    to_date: datetime | None = None
    product_type: str | None = None
    action: str | None = None
    stock_code: str | None = None


class TradesService:
    def __init__(self, gateway: BreezeGateway):
        self.gateway = gateway

    def get_trades(self, query: TradeQuery) -> dict[str, Any]:
        exchange_code = (query.exchange_code or "NFO").strip().upper()
        from_date, to_date = self._date_window(query.from_date, query.to_date)

        try:
            raw_trades = self.gateway.get_trade_list(
                from_date=from_date,
                to_date=to_date,
                exchange_code=exchange_code,
                product_type=(query.product_type or "").strip().lower(),
                action=(query.action or "").strip().upper(),
                stock_code=(query.stock_code or "").strip().upper(),
            )
        except BreezeGatewayError as error:
            raise TradesServiceError(str(error)) from error

        trades = [self._normalize_trade(item) for item in raw_trades if isinstance(item, dict)]
        return {
            "status": "ok",
            "exchange_code": exchange_code,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "stats": self._stats(trades),
            "trades": trades,
        }

    @staticmethod
    def _date_window(from_date: datetime | None, to_date: datetime | None) -> tuple[datetime, datetime]:
        to_value = to_date.astimezone(timezone.utc) if to_date else datetime.now(timezone.utc)
        from_value = from_date.astimezone(timezone.utc) if from_date else to_value - timedelta(days=7)
        return from_value, to_value

    @staticmethod
    def _normalize_trade(item: dict[str, Any]) -> dict[str, Any]:
        action = TradesService._text(item.get("action") or item.get("transaction_type")).upper()
        return {
            "trade_id": TradesService._text(item.get("trade_id") or item.get("fill_id")),
            "order_id": TradesService._text(item.get("order_id") or item.get("app_order_id")),
            "symbol": TradesService._text(item.get("stock_code") or item.get("symbol") or "UNKNOWN").upper(),
            "broker_symbol": TradesService._text(item.get("stock_code") or item.get("symbol") or "UNKNOWN").upper(),
            "exchange_code": TradesService._text(item.get("exchange_code")).upper(),
            "product_type": TradesService._text(item.get("product_type") or "cash").lower(),
            "action": action,
            "quantity": TradesService._to_float(item.get("quantity") or item.get("traded_quantity")),
            "price": TradesService._to_float(item.get("price") or item.get("trade_price") or item.get("average_price")),
            "trade_time": TradesService._text(item.get("trade_time") or item.get("trade_date") or item.get("order_datetime")),
        }

    @staticmethod
    def _stats(trades: list[dict[str, Any]]) -> dict[str, int]:
        actions = [trade["action"] for trade in trades]
        return {
            "total": len(trades),
            "buy": sum(1 for action in actions if action == "BUY"),
            "sell": sum(1 for action in actions if action == "SELL"),
        }

    @staticmethod
    def _text(value: Any) -> str:
        return str(value).strip() if value not in (None, "") else ""

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None
