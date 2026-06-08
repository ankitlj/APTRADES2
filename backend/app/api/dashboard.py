from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..services.breeze_gateway import BreezeGateway
from ..services.dashboard_service import DashboardDependencies, DashboardService, DashboardServiceError

dashboard_bp = Blueprint("dashboard", __name__)


def _dashboard_service() -> DashboardService:
    gateway = BreezeGateway(
        app_key=current_app.config.get("BREEZE_API_KEY"),
        secret_key=current_app.config.get("BREEZE_SECRET_KEY"),
        session_token=current_app.config.get("BREEZE_SESSION_TOKEN"),
    )
    return DashboardService(
        DashboardDependencies(
            database_url=current_app.config.get("DATABASE_URL"),
            stock_script_csv_path=current_app.config.get("STOCK_SCRIPT_CSV_PATH"),
            security_master_url=current_app.config.get("SECURITY_MASTER_URL"),
            security_master_connect_timeout=current_app.config.get("SECURITY_MASTER_CONNECT_TIMEOUT", 20),
            security_master_read_timeout=current_app.config.get("SECURITY_MASTER_READ_TIMEOUT", 30),
            gateway=gateway,
        )
    )


@dashboard_bp.get("/dashboard/summary")
def dashboard_summary() -> tuple[object, int]:
    payload = _dashboard_service().get_summary()
    return jsonify(payload), 200


@dashboard_bp.get("/dashboard/alerts")
def dashboard_alerts() -> tuple[object, int]:
    payload = _dashboard_service().get_alerts()
    return jsonify(payload), 200


@dashboard_bp.get("/dashboard/chart")
def dashboard_chart() -> tuple[object, int]:
    symbol = str(request.args.get("symbol", "NIFTY")).strip() or "NIFTY"
    try:
        payload = _dashboard_service().get_chart(symbol)
    except DashboardServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200
