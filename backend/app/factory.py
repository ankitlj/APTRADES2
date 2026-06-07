from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from .api.health import health_bp
from .config import load_config


def create_app() -> Flask:
    config = load_config()
    app = Flask(__name__)
    app.config.update(config.as_flask_config())
    CORS(
        app,
        resources={r"/api/*": {"origins": config.cors_origins}},
    )
    app.register_blueprint(health_bp, url_prefix=config.api_prefix)
    return app
