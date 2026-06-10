from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Select, select

from ..db import create_session_factory, ensure_tables
from ..models import ApiLog, AppEventLog


class LogsServiceError(Exception):
    pass


class LogsService:
    def __init__(self, database_url: str | None):
        self.database_url = database_url

    def get_logs(
        self,
        *,
        level: str | None = None,
        source: str | None = None,
        time_window: str | None = None,
        limit: int = 200,
    ) -> dict[str, Any]:
        session_factory = self._session_factory()
        since = self._parse_time_window(time_window)
        with session_factory() as session:
            api_rows = session.scalars(self._apply_api_filters(select(ApiLog), level=level, source=source, since=since)).all()
            app_rows = session.scalars(
                self._apply_app_filters(select(AppEventLog), level=level, source=source, since=since)
            ).all()

        rows = sorted(
            [self._serialize_api_log(row) for row in api_rows] + [self._serialize_app_log(row) for row in app_rows],
            key=lambda item: item["created_at"] or "",
            reverse=True,
        )[:limit]

        return {
            "status": "ok",
            "filters": {
                "level": (level or "").lower() or "all",
                "source": source or "all",
                "time_window": time_window or "24h",
            },
            "summary": {
                "api_count": len(api_rows),
                "app_count": len(app_rows),
                "total_count": len(rows),
            },
            "rows": rows,
        }

    def get_live(self, *, limit: int = 60) -> dict[str, Any]:
        payload = self.get_logs(time_window="24h", limit=limit)
        rows = payload["rows"]
        return {
            "status": "ok",
            "rows": rows,
            "lines": [self._format_live_line(row) for row in rows],
        }

    def record_api_log(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        source: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        session_factory = self._session_factory()
        level = "error" if status_code >= 500 else "warning" if status_code >= 400 else "info"
        with session_factory() as session:
            session.add(
                ApiLog(
                    level=level,
                    source=source,
                    method=method,
                    path=path,
                    status_code=status_code,
                    message=message[:256],
                    context_json=json.dumps(context or {}, default=str),
                )
            )
            session.commit()

    def record_app_event(
        self,
        *,
        level: str,
        source: str,
        event_type: str,
        message: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        session_factory = self._session_factory()
        with session_factory() as session:
            session.add(
                AppEventLog(
                    level=level.lower(),
                    source=source,
                    event_type=event_type,
                    message=message[:256],
                    context_json=json.dumps(context or {}, default=str),
                )
            )
            session.commit()

    def safe_record_api_log(self, **kwargs: Any) -> None:
        try:
            self.record_api_log(**kwargs)
        except Exception:
            return

    def safe_record_app_event(self, **kwargs: Any) -> None:
        try:
            self.record_app_event(**kwargs)
        except Exception:
            return

    def _session_factory(self):
        if not self.database_url:
            raise LogsServiceError("DATABASE_URL is not configured.")
        ensure_tables(self.database_url)
        return create_session_factory(self.database_url)

    @staticmethod
    def _apply_api_filters(query: Select[Any], *, level: str | None, source: str | None, since: datetime | None) -> Select[Any]:
        if level and level.lower() != "all":
            query = query.where(ApiLog.level == level.lower())
        if source and source.lower() != "all":
            query = query.where(ApiLog.source == source.lower())
        if since:
            query = query.where(ApiLog.created_at >= since)
        return query.order_by(ApiLog.created_at.desc())

    @staticmethod
    def _apply_app_filters(query: Select[Any], *, level: str | None, source: str | None, since: datetime | None) -> Select[Any]:
        if level and level.lower() != "all":
            query = query.where(AppEventLog.level == level.lower())
        if source and source.lower() != "all":
            query = query.where(AppEventLog.source == source.lower())
        if since:
            query = query.where(AppEventLog.created_at >= since)
        return query.order_by(AppEventLog.created_at.desc())

    @staticmethod
    def _parse_time_window(value: str | None) -> datetime | None:
        normalized = (value or "24h").strip().lower()
        now = datetime.now(timezone.utc)
        if normalized in {"all", ""}:
            return None
        if normalized == "15m":
            return now - timedelta(minutes=15)
        if normalized == "1h":
            return now - timedelta(hours=1)
        if normalized == "24h":
            return now - timedelta(hours=24)
        if normalized == "7d":
            return now - timedelta(days=7)
        raise LogsServiceError("time_window must be one of all, 15m, 1h, 24h, or 7d.")

    @staticmethod
    def _deserialize_context(value: str | None) -> dict[str, Any] | None:
        if not value:
            return None
        try:
            payload = json.loads(value)
        except ValueError:
            return {"raw": value}
        if isinstance(payload, dict):
            return payload
        return {"value": payload}

    def _serialize_api_log(self, row: ApiLog) -> dict[str, Any]:
        return {
            "id": f"api-{row.id}",
            "kind": "api",
            "level": row.level,
            "source": row.source,
            "message": row.message,
            "method": row.method,
            "path": row.path,
            "status_code": row.status_code,
            "event_type": "request",
            "context": self._deserialize_context(row.context_json),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _serialize_app_log(self, row: AppEventLog) -> dict[str, Any]:
        return {
            "id": f"app-{row.id}",
            "kind": "app",
            "level": row.level,
            "source": row.source,
            "message": row.message,
            "method": None,
            "path": None,
            "status_code": None,
            "event_type": row.event_type,
            "context": self._deserialize_context(row.context_json),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _format_live_line(row: dict[str, Any]) -> str:
        timestamp = row.get("created_at") or "n/a"
        kind = str(row.get("kind") or "app").upper()
        level = str(row.get("level") or "info").upper()
        source = row.get("source") or "system"
        if row.get("kind") == "api":
            return f"[{timestamp}] {level} {kind} {row.get('method')} {row.get('path')} {row.get('status_code')} {row.get('message')}"
        return f"[{timestamp}] {level} {kind} {source} {row.get('event_type')} {row.get('message')}"
