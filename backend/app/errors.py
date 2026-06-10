from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


def error_payload(code: Any, message: str) -> dict[str, Any]:
    """Single structured error shape used across every /api/* failure."""
    return {"status": "error", "error": {"code": code, "message": message}}


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def _handle_http_exception(error: HTTPException):
        message = error.description or error.name or "Request failed."
        response = jsonify(error_payload(error.code, message))
        response.status_code = error.code or 500
        return response

    @app.errorhandler(Exception)
    def _handle_unexpected(error: Exception):
        # Never leak internals to clients; the full trace is logged server-side.
        app.logger.exception("Unhandled application error: %s", error)
        response = jsonify(error_payload(500, "Internal server error."))
        response.status_code = 500
        return response
