from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..services.breeze_gateway import get_gateway
from ..services.positions_service import PositionsService, PositionsServiceError

positions_bp = Blueprint("positions", __name__)


def _positions_service() -> PositionsService:
    gateway = get_gateway(
        current_app.extensions,
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
    )
    return PositionsService(gateway, current_app.config.get("DATABASE_URL"))


@positions_bp.get("/positions")
def get_positions() -> tuple[object, int]:
    try:
        payload = _positions_service().get_positions(gateway_timeout=4, gateway_attempts=1)
    except PositionsServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200
