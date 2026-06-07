from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(slots=True)
class AppConfig:
    env: str = os.getenv("FLASK_ENV", "development")
    host: str = os.getenv("FLASK_HOST", "127.0.0.1")
    port: int = int(os.getenv("FLASK_PORT", "5000"))
    debug: bool = os.getenv("FLASK_DEBUG", "0") == "1"
    app_name: str = os.getenv("APP_NAME", "APTRADES v2")
    api_prefix: str = "/api"
    database_url: str | None = os.getenv("DATABASE_URL")
    redis_url: str | None = os.getenv("REDIS_URL")
    breeze_api_key: str | None = os.getenv("BREEZE_API_KEY")
    frontend_origin: str | None = os.getenv("FRONTEND_ORIGIN")

    def as_flask_config(self) -> dict[str, object]:
        return {
            "ENV": self.env,
            "DEBUG": self.debug,
            "APP_NAME": self.app_name,
        }


def load_config() -> AppConfig:
    return AppConfig()
