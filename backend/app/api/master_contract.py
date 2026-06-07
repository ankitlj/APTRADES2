from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from ..services.master_contract_service import MasterContractImportError, MasterContractService

master_contract_bp = Blueprint("master_contract", __name__)


def _service() -> MasterContractService:
    return MasterContractService(
        database_url=current_app.config.get("DATABASE_URL"),
        stock_script_csv_path=current_app.config.get("STOCK_SCRIPT_CSV_PATH"),
        security_master_url=current_app.config.get("SECURITY_MASTER_URL"),
        security_master_connect_timeout=current_app.config.get("SECURITY_MASTER_CONNECT_TIMEOUT", 20),
        security_master_read_timeout=current_app.config.get("SECURITY_MASTER_READ_TIMEOUT", 30),
    )


@master_contract_bp.get("/master-contract/status")
def master_contract_status() -> tuple[object, int]:
    return jsonify(_service().get_status()), 200


@master_contract_bp.post("/master-contract/import")
def master_contract_import() -> tuple[object, int]:
    service = _service()
    try:
        payload = service.import_master_contract()
    except MasterContractImportError as error:
        return jsonify({"status": "error", "error": str(error), "details": service.get_status()}), 400

    return jsonify(payload), 200
