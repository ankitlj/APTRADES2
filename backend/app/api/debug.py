from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..services.breeze_gateway import BreezeGateway, BreezeGatewayError

debug_bp = Blueprint("debug", __name__)


def _gateway() -> BreezeGateway:
    return BreezeGateway(
        app_key=current_app.config.get("BREEZE_API_KEY"),
        secret_key=current_app.config.get("BREEZE_SECRET_KEY"),
        session_token=current_app.config.get("BREEZE_SESSION_TOKEN"),
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
    gateway = _gateway()
    try:
        payload = gateway.run_symbol_diagnostics()
    except BreezeGatewayError as error:
        return jsonify({"status": "error", "configured": gateway.is_configured(), "error": str(error)}), 200

    return jsonify(payload), 200
