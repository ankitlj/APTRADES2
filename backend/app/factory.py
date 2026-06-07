from __future__ import annotations

import json

from flask import Flask
from flask.cli import AppGroup
from flask_cors import CORS

from .api.debug import debug_bp
from .api.health import health_bp
from .api.master_contract import master_contract_bp
from .config import load_config
from .services.master_contract_service import MasterContractImportError, MasterContractService


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
    _register_cli(app)
    return app
