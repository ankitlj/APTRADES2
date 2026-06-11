from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from ..services.breeze_gateway import BreezeGateway, get_gateway
from ..services.orders_service import OrderQuery, OrdersService, OrdersServiceError
from ..services.trades_service import TradeQuery, TradesService, TradesServiceError

orders_bp = Blueprint("orders", __name__)


def _gateway() -> BreezeGateway:
    return get_gateway(
        current_app.extensions,
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
    )


def _orders_service() -> OrdersService:
    return OrdersService(_gateway())


def _trades_service() -> TradesService:
    return TradesService(_gateway())


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned.replace("Z", "+00:00")
    return datetime.fromisoformat(cleaned)


def _order_query_from_args() -> OrderQuery:
    return OrderQuery(
        exchange_code=str(request.args.get("exchange") or request.args.get("exchange_code") or "NFO"),
        from_date=_parse_datetime(request.args.get("from_date")),
        to_date=_parse_datetime(request.args.get("to_date")),
        status=(request.args.get("status") or None),
    )


def _trade_query_from_args() -> TradeQuery:
    return TradeQuery(
        exchange_code=str(request.args.get("exchange") or request.args.get("exchange_code") or "NFO"),
        from_date=_parse_datetime(request.args.get("from_date")),
        to_date=_parse_datetime(request.args.get("to_date")),
        product_type=(request.args.get("product_type") or None),
        action=(request.args.get("action") or None),
        stock_code=(request.args.get("stock_code") or None),
    )


@orders_bp.get("/orders")
def get_orders() -> tuple[object, int]:
    try:
        payload = _orders_service().get_orders(_order_query_from_args())
    except (OrdersServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200


@orders_bp.post("/orders/cancel")
def cancel_order() -> tuple[object, int]:
    body = request.get_json(silent=True) or {}
    exchange_code = str(body.get("exchange") or body.get("exchange_code") or "").strip()
    order_id = str(body.get("order_id") or "").strip()
    try:
        payload = _orders_service().cancel_order(exchange_code=exchange_code, order_id=order_id)
    except OrdersServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200


@orders_bp.post("/orders/cancel-all")
def cancel_all_orders() -> tuple[object, int]:
    body = request.get_json(silent=True) or {}
    try:
        query = OrderQuery(
            exchange_code=str(body.get("exchange") or body.get("exchange_code") or "NFO"),
            from_date=_parse_datetime(body.get("from_date")),
            to_date=_parse_datetime(body.get("to_date")),
            status=(body.get("status") or None),
        )
        payload = _orders_service().cancel_all(query)
    except (OrdersServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200


@orders_bp.get("/trades")
def get_trades() -> tuple[object, int]:
    try:
        payload = _trades_service().get_trades(_trade_query_from_args())
    except (TradesServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200
