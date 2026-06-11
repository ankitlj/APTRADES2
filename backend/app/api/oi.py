from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, jsonify, request

from ..services.breeze_gateway import BreezeGateway, get_gateway
from ..services.oi_service import OIRequest, OIService, OIServiceError

oi_bp = Blueprint("oi", __name__)


def _gateway() -> BreezeGateway:
    return get_gateway(
        current_app.extensions,
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
    )


def _oi_service() -> OIService:
    return OIService(
        database_url=current_app.config.get("DATABASE_URL"),
        redis_url=current_app.config.get("REDIS_URL"),
        gateway=_gateway(),
    )


@oi_bp.get("/oi/tracker")
def get_oi_tracker() -> tuple[object, int]:
    underlying = str(request.args.get("underlying", "")).strip()
    expiry_text = str(request.args.get("expiry", "")).strip()
    exchange_code = str(request.args.get("exchange", "NFO")).strip().upper()

    if not underlying or not expiry_text:
        return jsonify({"status": "error", "error": "underlying and expiry are required."}), 400

    try:
        expiry_date = date.fromisoformat(expiry_text)
        payload = _oi_service().get_tracker(
            OIRequest(underlying=underlying, expiry_date=expiry_date, exchange_code=exchange_code)
        )
    except (OIServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400

    return jsonify(payload), 200


@oi_bp.get("/oi/profile")
def get_oi_profile() -> tuple[object, int]:
    underlying = str(request.args.get("underlying", "")).strip()
    expiry_text = str(request.args.get("expiry", "")).strip()
    exchange_code = str(request.args.get("exchange", "NFO")).strip().upper()

    if not underlying or not expiry_text:
        return jsonify({"status": "error", "error": "underlying and expiry are required."}), 400

    try:
        expiry_date = date.fromisoformat(expiry_text)
        payload = _oi_service().get_profile(
            OIRequest(underlying=underlying, expiry_date=expiry_date, exchange_code=exchange_code)
        )
    except (OIServiceError, ValueError) as error:
        return jsonify({"status": "error", "error": str(error)}), 400

    return jsonify(payload), 200
