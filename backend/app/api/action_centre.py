from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..services.action_centre_service import ActionCentreService, ActionCentreServiceError
from ..services.breeze_gateway import BreezeGateway, get_gateway

action_centre_bp = Blueprint("action-centre", __name__)


def _gateway() -> BreezeGateway:
    return get_gateway(
        current_app.extensions,
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
    )


def _service() -> ActionCentreService:
    return ActionCentreService(
        database_url=current_app.config.get("DATABASE_URL"),
        gateway=_gateway(),
    )


@action_centre_bp.get("/action-centre")
def get_action_centre() -> tuple[object, int]:
    try:
        payload = _service().get_actions(status=request.args.get("status"))
    except ActionCentreServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200


@action_centre_bp.post("/action-centre/<int:action_id>/approve")
def approve_action(action_id: int) -> tuple[object, int]:
    try:
        payload = _service().approve_action(action_id)
    except ActionCentreServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200


@action_centre_bp.post("/action-centre/<int:action_id>/reject")
def reject_action(action_id: int) -> tuple[object, int]:
    try:
        payload = _service().reject_action(action_id)
    except ActionCentreServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200
