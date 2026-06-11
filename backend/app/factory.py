from __future__ import annotations

import json
import time

from flask import Flask, g, request
from flask.cli import AppGroup
from flask_cors import CORS

from .api.action_centre import action_centre_bp
from .api.dashboard import dashboard_bp
from .api.debug import debug_bp
from .api.health import health_bp
from .api.logs import logs_bp
from .api.market_data import market_data_bp
from .api.master_contract import master_contract_bp
from .api.oi import oi_bp
from .api.options import options_bp
from .api.orders import orders_bp
from .api.positions import positions_bp
from .api.quotes import quotes_bp
from .api.strategy import strategy_bp
from .config import load_config
from .db import ensure_tables
from .errors import register_error_handlers
from .rate_limit import init_rate_limiting
from .realtime import init_realtime
from .services.master_contract_service import MasterContractImportError, MasterContractService
from .services.logs_service import LogsService


def _register_cli(app: Flask) -> None:
    master_contract_cli = AppGroup("master-contract")

    @master_contract_cli.command("import")
    def import_master_contract_command() -> None:
        service = MasterContractService(
            database_url=app.config.get("DATABASE_URL"),
            stock_script_csv_path=app.config.get("STOCK_SCRIPT_CSV_PATH"),
            security_master_url=app.config.get("SECURITY_MASTER_URL"),
            security_master_connect_timeout=app.config.get("SECURITY_MASTER_CONNECT_TIMEOUT", 20),
            security_master_read_timeout=app.config.get("SECURITY_MASTER_READ_TIMEOUT", 30),
        )
        try:
            payload = service.import_master_contract()
        except MasterContractImportError as error:
            raise SystemExit(str(error)) from error

        print(json.dumps(payload, indent=2))

    app.cli.add_command(master_contract_cli)


def create_app() -> Flask:
    config = load_config()
    app = Flask(__name__)
    app.config.update(config.as_flask_config())
    CORS(
        app,
        resources={r"/api/*": {"origins": config.cors_origins}},
    )
    app.register_blueprint(health_bp, url_prefix=config.api_prefix)
    app.register_blueprint(debug_bp, url_prefix=config.api_prefix)
    app.register_blueprint(master_contract_bp, url_prefix=config.api_prefix)
    app.register_blueprint(oi_bp, url_prefix=config.api_prefix)
    app.register_blueprint(options_bp, url_prefix=config.api_prefix)
    app.register_blueprint(orders_bp, url_prefix=config.api_prefix)
    app.register_blueprint(positions_bp, url_prefix=config.api_prefix)
    app.register_blueprint(quotes_bp, url_prefix=config.api_prefix)
    app.register_blueprint(strategy_bp, url_prefix=config.api_prefix)
    app.register_blueprint(dashboard_bp, url_prefix=config.api_prefix)
    app.register_blueprint(action_centre_bp, url_prefix=config.api_prefix)
    app.register_blueprint(logs_bp, url_prefix=config.api_prefix)
    app.register_blueprint(market_data_bp, url_prefix=config.api_prefix)

    @app.before_request
    def _capture_request_started_at() -> None:
        g.request_started_at = time.perf_counter()

    @app.after_request
    def _record_api_log(response):
        if not request.path.startswith(config.api_prefix):
            return response
        if not app.config.get("DATABASE_URL"):
            return response
        started_at = getattr(g, "request_started_at", None)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2) if started_at else None
        source = request.endpoint.split(".")[0] if request.endpoint else "api"
        LogsService(app.config.get("DATABASE_URL")).safe_record_api_log(
            method=request.method,
            path=request.path,
            status_code=response.status_code,
            source=source,
            message=f"{request.method} {request.path} completed with {response.status_code}",
            context={"elapsed_ms": elapsed_ms, "query_string": request.query_string.decode("utf-8", errors="ignore")},
        )
        return response

    register_error_handlers(app)
    init_rate_limiting(app)
    _register_cli(app)
    init_realtime(app)

    # Phase 18 Tier 1: create tables once at startup so the resolve() hot path no
    # longer pays a schema round-trip. Degraded-safe: if the DB is unreachable at
    # boot, services re-run ensure_tables (idempotent) when it returns.
    database_url = app.config.get("DATABASE_URL")
    if database_url:
        try:
            ensure_tables(database_url)
        except Exception:  # noqa: BLE001 — never block boot on the database
            pass

    return app
