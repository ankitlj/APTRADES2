from __future__ import annotations

from flask import Flask

from .api.health import health_bp
from .config import load_config


def create_app() -> Flask:
    config = load_config()
    app = Flask(__name__)
    app.config.update(config.as_flask_config())
    app.register_blueprint(health_bp, url_prefix=config.api_prefix)
    return app
