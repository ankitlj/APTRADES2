from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..services.breeze_gateway import BreezeGateway, BreezeGatewayError
from ..services.quote_service import QuoteRequest, QuoteService, QuoteServiceError

debug_bp = Blueprint("debug", __name__)


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


@debug_bp.get("/debug/breeze-auth")
def breeze_auth() -> tuple[object, int]:
    gateway = _gateway()
    try:
        payload = gateway.auth_diagnostic()
    except BreezeGatewayError as error:
        return jsonify({"status": "error", "configured": gateway.is_configured(), "error": str(error)}), 200

    return jsonify(payload), 200


@debug_bp.get("/debug/breeze-test")
def breeze_test() -> tuple[object, int]:
    try:
        payload = _quote_service().get_batch_quotes(
            [
                QuoteRequest(symbol="NIFTY", exchange_code="NFO", product_type="futures"),
                QuoteRequest(symbol="BANKNIFTY", exchange_code="NFO", product_type="futures"),
                QuoteRequest(symbol="RELIANCE", exchange_code="NSE", product_type="cash"),
                QuoteRequest(symbol="ADANIPORTS", exchange_code="NSE", product_type="cash"),
                QuoteRequest(symbol="SBIN", exchange_code="NSE", product_type="cash"),
            ]
        )
        payload = {
            "status": payload["status"],
            "configured": _gateway().is_configured(),
            "symbols": [
                {
                    "symbol": item["symbol"],
                    "broker_symbol": item.get("resolved", {}).get("broker_symbol", item["symbol"]),
                    "status": item["status"],
                    "exchange": item.get("resolved", {}).get("exchange_code", item.get("exchange_code", "")),
                    "product_type": item.get("resolved", {}).get("product_type", item.get("product_type", "")),
                    "quote": item.get("quote"),
                    "error": item.get("error"),
                }
                for item in payload["results"]
            ],
        }
    except (BreezeGatewayError, QuoteServiceError) as error:
        return jsonify({"status": "error", "configured": _gateway().is_configured(), "error": str(error)}), 200

    return jsonify(payload), 200
