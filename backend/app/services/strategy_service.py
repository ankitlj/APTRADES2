from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select

from ..db import create_session_factory, ensure_tables
from ..models import Strategy


class StrategyServiceError(Exception):
    pass


@dataclass(frozen=True)
class StrategyLeg:
    action: str   # "buy" | "sell"
    right: str    # "call" | "put"
    strike: float
    quantity: int
    premium: float


class StrategyService:
    _NUM_CURVE_POINTS = 50
    _SPOT_MARGIN = 0.15

    def __init__(self, database_url: str | None) -> None:
        self.database_url = database_url

    def list_strategies(self) -> dict[str, Any]:
        if not self.database_url:
            return {"status": "ok", "strategies": []}
        ensure_tables(self.database_url)
        session_factory = create_session_factory(self.database_url)
        with session_factory() as session:
            rows = session.scalars(
                select(Strategy).order_by(Strategy.created_at.desc())
            ).all()
        return {"status": "ok", "strategies": [self._to_dict(row) for row in rows]}

    def create_strategy(
        self,
        name: str,
        underlying: str,
        exchange_code: str,
        expiry_date: date,
        legs: list[StrategyLeg],
    ) -> dict[str, Any]:
        if not self.database_url:
            raise StrategyServiceError("DATABASE_URL is not configured.")
        legs_json = json.dumps([self._leg_to_dict(leg) for leg in legs])
        ensure_tables(self.database_url)
        session_factory = create_session_factory(self.database_url)
        with session_factory() as session:
            strategy = Strategy(
                name=name,
                underlying=underlying,
                exchange_code=exchange_code,
                expiry_date=expiry_date,
                legs_json=legs_json,
            )
            session.add(strategy)
            session.commit()
            result = self._to_dict(strategy)
        return {"status": "ok", "strategy": result}

    def delete_strategy(self, strategy_id: int) -> dict[str, Any]:
        if not self.database_url:
            raise StrategyServiceError("DATABASE_URL is not configured.")
        ensure_tables(self.database_url)
        session_factory = create_session_factory(self.database_url)
        with session_factory() as session:
            strategy = session.get(Strategy, strategy_id)
            if strategy is None:
                raise StrategyServiceError(f"Strategy {strategy_id} not found.")
            session.delete(strategy)
            session.commit()
        return {"status": "ok", "deleted_id": strategy_id}

    def compute_payoff(self, legs: list[StrategyLeg]) -> dict[str, Any]:
        if not legs:
            raise StrategyServiceError("At least one leg is required.")

        strikes = [leg.strike for leg in legs]
        spot_min = min(strikes) * (1 - self._SPOT_MARGIN)
        spot_max = max(strikes) * (1 + self._SPOT_MARGIN)
        step = (spot_max - spot_min) / (self._NUM_CURVE_POINTS - 1)
        spots = [spot_min + step * i for i in range(self._NUM_CURVE_POINTS)]

        curve = [
            {"spot": round(s, 2), "pnl": round(self._total_pnl(legs, s), 2)}
            for s in spots
        ]

        pnl_values = [p["pnl"] for p in curve]
        net_premium = round(
            sum(
                leg.premium * leg.quantity * (1 if leg.action == "sell" else -1)
                for leg in legs
            ),
            2,
        )

        return {
            "net_premium": net_premium,
            "max_profit": round(max(pnl_values), 2),
            "max_loss": round(min(pnl_values), 2),
            "breakevens": [round(be, 2) for be in self._find_breakevens(curve)],
            "curve": curve,
        }

    @staticmethod
    def _total_pnl(legs: list[StrategyLeg], spot: float) -> float:
        total = 0.0
        for leg in legs:
            if leg.right == "call":
                intrinsic = max(spot - leg.strike, 0.0)
            else:
                intrinsic = max(leg.strike - spot, 0.0)
            if leg.action == "buy":
                total += (intrinsic - leg.premium) * leg.quantity
            else:
                total += (leg.premium - intrinsic) * leg.quantity
        return total

    @staticmethod
    def _find_breakevens(curve: list[dict[str, float]]) -> list[float]:
        breakevens: list[float] = []
        for i in range(len(curve) - 1):
            p1 = curve[i]["pnl"]
            p2 = curve[i + 1]["pnl"]
            s1 = curve[i]["spot"]
            s2 = curve[i + 1]["spot"]
            if (p1 < 0 < p2) or (p2 < 0 < p1):
                denom = abs(p2 - p1)
                if denom > 0:
                    be = s1 + (s2 - s1) * abs(p1) / denom
                    breakevens.append(be)
            elif p1 == 0.0:
                breakevens.append(s1)
        return breakevens

    def _to_dict(self, strategy: Strategy) -> dict[str, Any]:
        legs = json.loads(strategy.legs_json)
        net_premium = round(
            sum(
                leg["premium"] * leg["quantity"] * (1 if leg["action"] == "sell" else -1)
                for leg in legs
            ),
            2,
        )
        return {
            "id": strategy.id,
            "name": strategy.name,
            "underlying": strategy.underlying,
            "exchange_code": strategy.exchange_code,
            "expiry": strategy.expiry_date.isoformat(),
            "legs": legs,
            "net_premium": net_premium,
            "created_at": strategy.created_at.isoformat(),
        }

    @staticmethod
    def _leg_to_dict(leg: StrategyLeg) -> dict[str, Any]:
        return {
            "action": leg.action,
            "right": leg.right,
            "strike": leg.strike,
            "quantity": leg.quantity,
            "premium": leg.premium,
        }
