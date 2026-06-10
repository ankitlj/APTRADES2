from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..services.logs_service import LogsService, LogsServiceError

logs_bp = Blueprint("logs", __name__)


def _service() -> LogsService:
    return LogsService(database_url=current_app.config.get("DATABASE_URL"))


@logs_bp.get("/logs")
def get_logs() -> tuple[object, int]:
    try:
        payload = _service().get_logs(
            level=request.args.get("level"),
            source=request.args.get("source"),
            time_window=request.args.get("time"),
        )
    except LogsServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200


@logs_bp.get("/logs/live")
def get_live_logs() -> tuple[object, int]:
    try:
        payload = _service().get_live()
    except LogsServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200
