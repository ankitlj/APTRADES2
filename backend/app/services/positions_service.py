from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .breeze_gateway import BreezeGateway, BreezeGatewayError


class PositionsServiceError(Exception):
    pass


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    broker_symbol: str
    exchange_code: str
    product_type: str
    quantity: float
    average_price: float | None
    ltp: float | None
    pnl: float | None
    expiry_date: str | None
    right: str | None
    strike_price: str | None
    segment: str | None


class PositionsService:
    def __init__(self, gateway: BreezeGateway):
        self.gateway = gateway

    def get_positions(self) -> dict[str, Any]:
        if not self.gateway.is_configured():
            return {
                "status": "not_configured",
                "positions": [],
                "totals": {
                    "open_positions": 0,
                    "long_positions": 0,
                    "short_positions": 0,
                    "total_pnl": 0.0,
                },
            }

        try:
            raw_positions = self.gateway.get_portfolio_positions()
        except BreezeGatewayError as error:
            if "No Positions" in str(error):
                return {
                    "status": "ok",
                    "positions": [],
                    "totals": {
                        "open_positions": 0,
                        "long_positions": 0,
                        "short_positions": 0,
                        "total_pnl": 0.0,
                    },
                }
            raise PositionsServiceError(str(error)) from error

        normalized = [self._normalize_position(item) for item in raw_positions if isinstance(item, dict)]
        active_positions = [position for position in normalized if position.quantity != 0]
        return {
            "status": "ok",
            "positions": [self._serialize_position(position) for position in active_positions],
            "totals": self._totals(active_positions),
        }

    @staticmethod
    def _normalize_position(item: dict[str, Any]) -> PositionSnapshot:
        product_type = str(item.get("product_type") or "").strip().lower() or "cash"
        quantity = PositionsService._to_float(item.get("quantity")) or 0.0
        return PositionSnapshot(
            symbol=str(item.get("underlying") or item.get("stock_code") or "UNKNOWN").strip().upper(),
            broker_symbol=str(item.get("stock_code") or item.get("underlying") or "UNKNOWN").strip().upper(),
            exchange_code=str(item.get("exchange_code") or "").strip().upper(),
            product_type=product_type,
            quantity=quantity,
            average_price=PositionsService._to_float(item.get("average_price") or item.get("price")),
            ltp=PositionsService._to_float(item.get("ltp")),
            pnl=PositionsService._to_float(item.get("pnl")),
            expiry_date=str(item.get("expiry_date")).strip() if item.get("expiry_date") else None,
            right=str(item.get("right")).strip() if item.get("right") else None,
            strike_price=str(item.get("strike_price")).strip() if item.get("strike_price") is not None else None,
            segment=str(item.get("segment")).strip().lower() if item.get("segment") else None,
        )

    @staticmethod
    def _serialize_position(position: PositionSnapshot) -> dict[str, Any]:
        return {
            "symbol": position.symbol,
            "broker_symbol": position.broker_symbol,
            "exchange_code": position.exchange_code,
            "product_type": position.product_type,
            "quantity": position.quantity,
            "average_price": position.average_price,
            "ltp": position.ltp,
            "pnl": position.pnl,
            "expiry_date": position.expiry_date,
            "right": position.right,
            "strike_price": position.strike_price,
            "segment": position.segment,
        }

    @staticmethod
    def _totals(positions: list[PositionSnapshot]) -> dict[str, Any]:
        return {
            "open_positions": len(positions),
            "long_positions": sum(1 for position in positions if position.quantity > 0),
            "short_positions": sum(1 for position in positions if position.quantity < 0),
            "total_pnl": round(sum(position.pnl or 0.0 for position in positions), 2),
        }

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None
