from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, jsonify, request

from ..services.breeze_gateway import BreezeGateway, get_gateway
from ..services.option_chain_service import (
    OptionChainRequest,
    OptionChainService,
    OptionChainServiceError,
    OptionExpiryRequest,
)

options_bp = Blueprint("options", __name__)


def _gateway() -> BreezeGateway:
    return get_gateway(
        current_app.extensions,
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
    )


def _option_chain_service() -> OptionChainService:
    return OptionChainService(
        database_url=current_app.config.get("DATABASE_URL"),
        redis_url=current_app.config.get("REDIS_URL"),
        gateway=_gateway(),
    )


@options_bp.get("/options/expiries")
def get_option_expiries() -> tuple[object, int]:
    underlying = str(request.args.get("underlying", "")).strip()
    exchange_code = str(request.args.get("exchange", "NFO")).strip().upper()
    if not underlying:
        return jsonify({"status": "error", "error": "underlying is required."}), 400

    try:
        payload = _option_chain_service().get_expiries(
            OptionExpiryRequest(
                underlying=underlying,
                exchange_code=exchange_code,
            )
        )
    except OptionChainServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400

    return jsonify(payload), 200


@options_bp.get("/option-chain")
def get_option_chain() -> tuple[object, int]:
    underlying = str(request.args.get("underlying", "")).strip()
    expiry_text = str(request.args.get("expiry", "")).strip()
    exchange_code = str(request.args.get("exchange", "NFO")).strip().upper()
    strike_count = int(request.args.get("strike_count", "12"))

    if not underlying or not expiry_text:
        return jsonify({"status": "error", "error": "underlying and expiry are required."}), 400

    try:
        expiry_date = date.fromisoformat(expiry_text)
        payload = _option_chain_service().get_option_chain(
            OptionChainRequest(
                underlying=underlying,
                expiry_date=expiry_date,
                exchange_code=exchange_code,
                strike_count=strike_count,
            )
        )
    except (OptionChainServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400

    return jsonify(payload), 200
