from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from ..db import create_session_factory, ensure_tables
from ..models import PendingAction
from .breeze_gateway import BreezeGateway
from .logs_service import LogsService
from .orders_service import OrderQuery, OrdersService

_TRACKED_EXCHANGES = ("NFO", "NSE", "BFO", "BSE")
_OPEN_STATUSES = {"open", "ordered", "pending", "partially_executed"}


class ActionCentreServiceError(Exception):
    pass


class ActionCentreService:
    def __init__(self, *, database_url: str | None, gateway: BreezeGateway):
        self.database_url = database_url
        self.gateway = gateway
        self.logs = LogsService(database_url)

    def get_actions(self, *, status: str | None = None) -> dict[str, Any]:
        session_factory = self._session_factory()
        synced = self._sync_open_orders()

        with session_factory() as session:
            query = select(PendingAction).order_by(PendingAction.requested_at.desc(), PendingAction.id.desc())
            normalized_status = (status or "pending").strip().lower()
            if normalized_status != "all":
                query = query.where(PendingAction.status == normalized_status)
            rows = session.scalars(query).all()

            counts = dict(
                session.execute(
                    select(PendingAction.status, func.count(PendingAction.id)).group_by(PendingAction.status)
                ).all()
            )

        self.logs.safe_record_app_event(
            level="info",
            source="action-centre",
            event_type="sync",
            message=f"Action Centre synchronized {synced} pending broker actions.",
            context={"synced": synced, "filter_status": normalized_status},
        )
        return {
            "status": "ok",
            "filter_status": normalized_status,
            "stats": {
                "pending": int(counts.get("pending", 0)),
                "approved": int(counts.get("approved", 0)),
                "rejected": int(counts.get("rejected", 0)),
                "all": sum(int(value) for value in counts.values()),
            },
            "actions": [self._serialize_action(row) for row in rows],
        }

    def approve_action(self, action_id: int) -> dict[str, Any]:
        session_factory = self._session_factory()
        with session_factory() as session:
            action = session.get(PendingAction, action_id)
            if not action:
                raise ActionCentreServiceError("Action row was not found.")
            if action.status != "pending":
                raise ActionCentreServiceError(f"Only pending rows can be approved. Current status: {action.status}.")

            result = self.gateway.cancel_order(exchange_code=action.exchange_code, order_id=action.order_id)
            action.status = "approved"
            action.reviewed_at = datetime.now(timezone.utc)
            action.resolution_note = "Cancel request submitted to Breeze."
            action.broker_result_json = json.dumps(result, default=str)
            session.commit()
            payload = self._serialize_action(action)

        self.logs.safe_record_app_event(
            level="info",
            source="action-centre",
            event_type="approve",
            message=f"Approved action {action_id} for order {payload['order_id']}.",
            context={"action_id": action_id, "order_id": payload["order_id"], "result": result},
        )
        return {"status": "ok", "action": payload}

    def reject_action(self, action_id: int) -> dict[str, Any]:
        session_factory = self._session_factory()
        with session_factory() as session:
            action = session.get(PendingAction, action_id)
            if not action:
                raise ActionCentreServiceError("Action row was not found.")
            if action.status != "pending":
                raise ActionCentreServiceError(f"Only pending rows can be rejected. Current status: {action.status}.")

            action.status = "rejected"
            action.reviewed_at = datetime.now(timezone.utc)
            action.resolution_note = "User rejected the pending broker action."
            session.commit()
            payload = self._serialize_action(action)

        self.logs.safe_record_app_event(
            level="warning",
            source="action-centre",
            event_type="reject",
            message=f"Rejected action {action_id} for order {payload['order_id']}.",
            context={"action_id": action_id, "order_id": payload["order_id"]},
        )
        return {"status": "ok", "action": payload}

    def _sync_open_orders(self) -> int:
        orders_service = OrdersService(self.gateway)
        seen = 0
        session_factory = self._session_factory()
        with session_factory() as session:
            for exchange_code in _TRACKED_EXCHANGES:
                try:
                    payload = orders_service.get_orders(
                        OrderQuery(
                            exchange_code=exchange_code,
                            from_date=datetime.now(timezone.utc) - timedelta(days=2),
                            to_date=datetime.now(timezone.utc),
                        ),
                        gateway_timeout=8,
                        gateway_attempts=1,
                    )
                except Exception as error:
                    self.logs.safe_record_app_event(
                        level="warning",
                        source="action-centre",
                        event_type="sync_error",
                        message=f"Unable to sync orders for {exchange_code}.",
                        context={"exchange_code": exchange_code, "error": str(error)},
                    )
                    continue

                for order in payload.get("orders", []):
                    if order.get("status_normalized") not in _OPEN_STATUSES:
                        continue
                    order_id = str(order.get("order_id") or "").strip()
                    if not order_id:
                        continue
                    existing = session.scalars(
                        select(PendingAction).where(
                            PendingAction.action_type == "cancel_order",
                            PendingAction.order_id == order_id,
                        )
                    ).first()
                    if existing:
                        continue

                    session.add(
                        PendingAction(
                            action_type="cancel_order",
                            status="pending",
                            title=f"Cancel broker order for {order.get('symbol') or order.get('broker_symbol') or order_id}",
                            symbol=str(order.get("symbol") or order.get("broker_symbol") or order_id),
                            broker_symbol=order.get("broker_symbol"),
                            exchange_code=str(order.get("exchange_code") or exchange_code),
                            product_type=order.get("product_type"),
                            order_id=order_id,
                            quantity=self._to_int(order.get("pending_quantity") or order.get("quantity")),
                            request_payload_json=json.dumps(order, default=str),
                            requested_by="system",
                            created_from="breeze_order_sync",
                        )
                    )
                    seen += 1
            session.commit()
        return seen

    def _session_factory(self):
        if not self.database_url:
            raise ActionCentreServiceError("DATABASE_URL is not configured.")
        ensure_tables(self.database_url)
        return create_session_factory(self.database_url)

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _deserialize_json(value: str | None) -> dict[str, Any] | None:
        if not value:
            return None
        try:
            payload = json.loads(value)
        except ValueError:
            return {"raw": value}
        if isinstance(payload, dict):
            return payload
        return {"value": payload}

    def _serialize_action(self, row: PendingAction) -> dict[str, Any]:
        return {
            "id": row.id,
            "action_type": row.action_type,
            "status": row.status,
            "title": row.title,
            "symbol": row.symbol,
            "broker_symbol": row.broker_symbol,
            "exchange_code": row.exchange_code,
            "product_type": row.product_type,
            "order_id": row.order_id,
            "quantity": row.quantity,
            "requested_by": row.requested_by,
            "created_from": row.created_from,
            "requested_at": row.requested_at.isoformat() if row.requested_at else None,
            "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
            "resolution_note": row.resolution_note,
            "request_payload": self._deserialize_json(row.request_payload_json),
            "broker_result": self._deserialize_json(row.broker_result_json),
            "can_approve": row.status == "pending",
            "can_reject": row.status == "pending",
        }
