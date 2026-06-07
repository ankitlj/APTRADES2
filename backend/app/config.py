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
    vercel_preview_origin: str | None = os.getenv("VERCEL_PREVIEW_ORIGIN")

    @property
    def cors_origins(self) -> list[str]:
        origins: list[str] = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
        for value in (self.frontend_origin, self.vercel_preview_origin):
            if not value:
                continue
            origins.extend(
                origin.strip()
                for origin in value.split(",")
                if origin.strip()
            )
        seen: set[str] = set()
        unique_origins: list[str] = []
        for origin in origins:
            if origin in seen:
                continue
            seen.add(origin)
            unique_origins.append(origin)
        return unique_origins

    def as_flask_config(self) -> dict[str, object]:
        return {
            "ENV": self.env,
            "DEBUG": self.debug,
            "APP_NAME": self.app_name,
            "FRONTEND_ORIGIN": self.frontend_origin,
            "VERCEL_PREVIEW_ORIGIN": self.vercel_preview_origin,
            "CORS_ORIGINS": self.cors_origins,
        }


def load_config() -> AppConfig:
    return AppConfig()
