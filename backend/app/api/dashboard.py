from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..services.breeze_gateway import get_gateway
from ..services.dashboard_service import DashboardDependencies, DashboardService, DashboardServiceError

dashboard_bp = Blueprint("dashboard", __name__)


def _dashboard_service() -> DashboardService:
    gateway = get_gateway(
        current_app.extensions,
        current_app.config.get("BREEZE_API_KEY"),
        current_app.config.get("BREEZE_SECRET_KEY"),
        current_app.config.get("BREEZE_SESSION_TOKEN"),
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


@dashboard_bp.get("/dashboard/search")
def dashboard_search() -> tuple[object, int]:
    q = str(request.args.get("q", "")).strip()
    tab = str(request.args.get("tab", "all")).strip().lower()
    if tab not in ("all", "stocks", "fno"):
        tab = "all"
    payload = _dashboard_service().search_instruments(q, tab=tab)
    return jsonify(payload), 200


@dashboard_bp.get("/dashboard/orderbook")
def dashboard_orderbook() -> tuple[object, int]:
    broker_symbol = str(request.args.get("broker_symbol", "")).strip()
    exchange_code = str(request.args.get("exchange_code", "")).strip()
    product_type = str(request.args.get("product_type", "")).strip()
    expiry_date = str(request.args.get("expiry_date", "")).strip() or None
    right = str(request.args.get("right", "")).strip().lower() or None
    strike_price = str(request.args.get("strike_price", "")).strip() or None

    if not broker_symbol:
        return jsonify({"status": "error", "error": "broker_symbol is required."}), 400
    if not exchange_code:
        return jsonify({"status": "error", "error": "exchange_code is required."}), 400
    if not product_type or product_type.lower() not in ("cash", "futures", "options"):
        return jsonify({"status": "error", "error": "product_type must be 'cash', 'futures', or 'options'."}), 400

    try:
        payload = _dashboard_service().get_orderbook(
            broker_symbol, exchange_code, product_type,
            expiry_date=expiry_date, right=right, strike_price=strike_price,
        )
    except DashboardServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200


@dashboard_bp.get("/dashboard/option-orderbook")
def dashboard_option_orderbook() -> tuple[object, int]:
    underlying = str(request.args.get("underlying", "")).strip()
    exchange = str(request.args.get("exchange", "NFO")).strip() or "NFO"
    expiry = str(request.args.get("expiry", "")).strip()
    strike = str(request.args.get("strike", "")).strip()
    right = str(request.args.get("right", "")).strip().lower()

    if not underlying:
        return jsonify({"status": "error", "error": "underlying is required."}), 400
    if not expiry:
        return jsonify({"status": "error", "error": "expiry is required (ISO date string)."}), 400
    if not strike:
        return jsonify({"status": "error", "error": "strike is required."}), 400
    if not right or right not in ("call", "put"):
        return jsonify({"status": "error", "error": "right must be 'call' or 'put'."}), 400

    try:
        payload = _dashboard_service().get_option_orderbook(underlying, exchange, expiry, strike, right)
    except DashboardServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify(payload), 200
