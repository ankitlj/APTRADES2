from __future__ import annotations

from datetime import date
from typing import Any

from flask import Blueprint, current_app, jsonify, request

from ..services.breeze_gateway import BreezeGateway
from ..services.quote_service import QuoteRequest, QuoteService, QuoteServiceError

quotes_bp = Blueprint("quotes", __name__)


def _gateway() -> BreezeGateway:
    return BreezeGateway(
        app_key=current_app.config.get("BREEZE_API_KEY"),
        secret_key=current_app.config.get("BREEZE_SECRET_KEY"),
        session_token=current_app.config.get("BREEZE_SESSION_TOKEN"),
    )


def _quote_service() -> QuoteService:
    return QuoteService(
        database_url=current_app.config.get("DATABASE_URL"),
        gateway=_gateway(),
    )


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def _build_request(payload: dict[str, Any]) -> QuoteRequest:
    symbol = str(payload.get("symbol", "")).strip()
    exchange_code = str(payload.get("exchange") or payload.get("exchange_code") or "").strip()
    if not symbol or not exchange_code:
        raise QuoteServiceError("symbol and exchange are required.")

    return QuoteRequest(
        symbol=symbol,
        exchange_code=exchange_code,
        product_type=(payload.get("product_type") or None),
        expiry_date=_parse_date(payload.get("expiry_date")),
        right=(payload.get("right") or None),
        strike_price=(payload.get("strike_price") or None),
    )


@quotes_bp.get("/quotes")
def get_quote() -> tuple[object, int]:
    try:
        quote_request = _build_request(request.args.to_dict())
        payload = _quote_service().get_quote(quote_request)
    except (QuoteServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400

    return jsonify(payload), 200


@quotes_bp.post("/quotes/batch")
def get_batch_quotes() -> tuple[object, int]:
    body = request.get_json(silent=True) or {}
    raw_items = body.get("symbols")
    if not isinstance(raw_items, list) or not raw_items:
        return jsonify({"status": "error", "error": "symbols must be a non-empty array."}), 400

    try:
        items = [_build_request(item) for item in raw_items if isinstance(item, dict)]
    except (QuoteServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400

    payload = _quote_service().get_batch_quotes(items)
    return jsonify(payload), 200
