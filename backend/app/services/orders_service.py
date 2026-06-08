from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .breeze_gateway import BreezeGateway, BreezeGatewayError


class OrdersServiceError(Exception):
    pass


_OPEN_STATUSES = {
    "open",
    "ordered",
    "pending",
    "partially executed",
    "partiallyexecuted",
    "requested",
    "trigger pending",
    "triggerpending",
    "queued",
    "in process",
    "inprocess",
}
_COMPLETED_STATUSES = {"complete", "completed", "executed", "filled", "traded"}
_REJECTED_STATUSES = {"rejected", "rejection", "failed"}
_CANCELLED_STATUSES = {"cancelled", "canceled", "cancel requested", "cancelrequested"}


@dataclass(frozen=True)
class OrderQuery:
    exchange_code: str = "NFO"
    from_date: datetime | None = None
    to_date: datetime | None = None
    status: str | None = None


class OrdersService:
    def __init__(self, gateway: BreezeGateway):
        self.gateway = gateway

    def get_orders(self, query: OrderQuery) -> dict[str, Any]:
        exchange_code = (query.exchange_code or "NFO").strip().upper()
        from_date, to_date = self._date_window(query.from_date, query.to_date)

        try:
            raw_orders = self.gateway.get_order_list(
                exchange_code=exchange_code,
                from_date=from_date,
                to_date=to_date,
            )
        except BreezeGatewayError as error:
            raise OrdersServiceError(str(error)) from error

        orders = [self._normalize_order(item) for item in raw_orders if isinstance(item, dict)]
        if query.status:
            expected = query.status.strip().lower()
            orders = [order for order in orders if order["status_normalized"] == expected]

        return {
            "status": "ok",
            "exchange_code": exchange_code,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
            "stats": self._stats(orders),
            "orders": orders,
        }

    def cancel_order(self, *, exchange_code: str, order_id: str) -> dict[str, Any]:
        normalized_exchange = exchange_code.strip().upper()
        normalized_order_id = order_id.strip()
        if not normalized_exchange or not normalized_order_id:
            raise OrdersServiceError("exchange_code and order_id are required.")

        try:
            response = self.gateway.cancel_order(exchange_code=normalized_exchange, order_id=normalized_order_id)
        except BreezeGatewayError as error:
            raise OrdersServiceError(str(error)) from error

        return {
            "status": "ok",
            "exchange_code": normalized_exchange,
            "order_id": normalized_order_id,
            "result": response,
        }

    def cancel_all(self, query: OrderQuery) -> dict[str, Any]:
        payload = self.get_orders(query)
        cancellable = [
            order for order in payload["orders"] if order["status_normalized"] in _OPEN_STATUSES and order["order_id"]
        ]

        cancelled: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        for order in cancellable:
            try:
                result = self.cancel_order(
                    exchange_code=payload["exchange_code"],
                    order_id=order["order_id"],
                )
                cancelled.append(
                    {
                        "order_id": order["order_id"],
                        "symbol": order["symbol"],
                        "status": "ok",
                        "result": result["result"],
                    }
                )
            except OrdersServiceError as error:
                errors.append(
                    {
                        "order_id": order["order_id"],
                        "symbol": order["symbol"],
                        "status": "error",
                        "error": str(error),
                    }
                )

        return {
            "status": "ok" if not errors else "partial_success" if cancelled else "error",
            "exchange_code": payload["exchange_code"],
            "requested": len(cancellable),
            "cancelled_count": len(cancelled),
            "error_count": len(errors),
            "cancelled": cancelled,
            "errors": errors,
        }

    @staticmethod
    def _date_window(from_date: datetime | None, to_date: datetime | None) -> tuple[datetime, datetime]:
        to_value = to_date.astimezone(timezone.utc) if to_date else datetime.now(timezone.utc)
        from_value = from_date.astimezone(timezone.utc) if from_date else to_value - timedelta(days=7)
        return from_value, to_value

    @staticmethod
    def _normalize_order(item: dict[str, Any]) -> dict[str, Any]:
        status = OrdersService._text(
            item.get("status")
            or item.get("order_status")
            or item.get("status_description")
        )
        normalized_status = status.lower()
        quantity = OrdersService._to_float(item.get("quantity") or item.get("total_quantity"))
        pending_quantity = OrdersService._to_float(item.get("pending_quantity") or item.get("open_quantity"))
        filled_quantity = OrdersService._to_float(item.get("filled_quantity") or item.get("executed_quantity"))
        return {
            "order_id": OrdersService._text(item.get("order_id") or item.get("app_order_id")),
            "parent_order_id": OrdersService._text(item.get("parent_order_id")),
            "symbol": OrdersService._text(item.get("stock_code") or item.get("symbol") or "UNKNOWN").upper(),
            "broker_symbol": OrdersService._text(item.get("stock_code") or item.get("symbol") or "UNKNOWN").upper(),
            "exchange_code": OrdersService._text(item.get("exchange_code")).upper(),
            "product_type": OrdersService._text(item.get("product_type") or "cash").lower(),
            "action": OrdersService._text(item.get("action")).upper(),
            "status": status,
            "status_normalized": normalized_status,
            "quantity": quantity,
            "pending_quantity": pending_quantity,
            "filled_quantity": filled_quantity if filled_quantity is not None else OrdersService._filled_from_total(quantity, pending_quantity),
            "limit_price": OrdersService._to_float(item.get("limit_price") or item.get("price") or item.get("limit_rate")),
            "trigger_price": OrdersService._to_float(item.get("trigger_price") or item.get("stoploss_price")),
            "average_price": OrdersService._to_float(item.get("average_price") or item.get("average_executed_price")),
            "order_type": OrdersService._text(item.get("order_type") or item.get("variety")),
            "validity": OrdersService._text(item.get("validity")),
            "created_at": OrdersService._text(item.get("order_datetime") or item.get("created_at") or item.get("order_date")),
            "updated_at": OrdersService._text(item.get("updated_at") or item.get("modified_date")),
            "message": OrdersService._text(item.get("message") or item.get("remarks")),
        }

    @staticmethod
    def _stats(orders: list[dict[str, Any]]) -> dict[str, int]:
        statuses = [order["status_normalized"] for order in orders]
        return {
            "total": len(orders),
            "completed": sum(1 for status in statuses if status in _COMPLETED_STATUSES),
            "open": sum(1 for status in statuses if status in _OPEN_STATUSES),
            "rejected": sum(1 for status in statuses if status in _REJECTED_STATUSES),
            "cancelled": sum(1 for status in statuses if status in _CANCELLED_STATUSES),
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

    @staticmethod
    def _filled_from_total(quantity: float | None, pending_quantity: float | None) -> float | None:
        if quantity is None or pending_quantity is None:
            return None
        return quantity - pending_quantity
