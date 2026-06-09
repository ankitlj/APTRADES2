from __future__ import annotations

from datetime import date

from flask import Blueprint, current_app, jsonify, request

from ..services.strategy_service import StrategyLeg, StrategyService, StrategyServiceError

strategy_bp = Blueprint("strategy", __name__)

_VALID_ACTIONS = {"buy", "sell"}
_VALID_RIGHTS = {"call", "put"}
_MAX_LEGS = 8


def _strategy_service() -> StrategyService:
    return StrategyService(database_url=current_app.config.get("DATABASE_URL"))


def _parse_legs(raw: object) -> list[StrategyLeg] | str:
    if not isinstance(raw, list) or len(raw) == 0:
        return "legs must be a non-empty list."
    if len(raw) > _MAX_LEGS:
        return f"legs must have at most {_MAX_LEGS} items."
    legs: list[StrategyLeg] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            return f"leg {i}: must be an object."
        action = str(item.get("action", "")).lower()
        right = str(item.get("right", "")).lower()
        if action not in _VALID_ACTIONS:
            return f"leg {i}: action must be 'buy' or 'sell'."
        if right not in _VALID_RIGHTS:
            return f"leg {i}: right must be 'call' or 'put'."
        try:
            strike = float(item["strike"])
            quantity = int(item["quantity"])
            premium = float(item["premium"])
        except (KeyError, TypeError, ValueError):
            return f"leg {i}: strike, quantity, and premium must be numbers."
        if strike <= 0:
            return f"leg {i}: strike must be positive."
        if quantity <= 0:
            return f"leg {i}: quantity must be positive."
        if premium < 0:
            return f"leg {i}: premium must be non-negative."
        legs.append(
            StrategyLeg(
                action=action,
                right=right,
                strike=strike,
                quantity=quantity,
                premium=premium,
            )
        )
    return legs


@strategy_bp.get("/strategies")
def list_strategies() -> tuple[object, int]:
    payload = _strategy_service().list_strategies()
    return jsonify(payload), 200


@strategy_bp.post("/strategies/payoff")
def compute_payoff() -> tuple[object, int]:
    body = request.get_json(silent=True) or {}
    legs_or_error = _parse_legs(body.get("legs"))
    if isinstance(legs_or_error, str):
        return jsonify({"status": "error", "error": legs_or_error}), 400
    try:
        result = _strategy_service().compute_payoff(legs_or_error)
    except StrategyServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400
    return jsonify({"status": "ok", **result}), 200


@strategy_bp.post("/strategies")
def create_strategy() -> tuple[object, int]:
    body = request.get_json(silent=True) or {}
    name = str(body.get("name", "")).strip()
    underlying = str(body.get("underlying", "")).strip().upper()
    exchange_code = str(body.get("exchange_code", "NFO")).strip().upper()
    expiry_text = str(body.get("expiry", "")).strip()

    if not name:
        return jsonify({"status": "error", "error": "name is required."}), 400
    if len(name) > 128:
        return jsonify({"status": "error", "error": "name must be 128 characters or fewer."}), 400
    if not underlying:
        return jsonify({"status": "error", "error": "underlying is required."}), 400
    if not expiry_text:
        return jsonify({"status": "error", "error": "expiry is required."}), 400

    try:
        expiry_date = date.fromisoformat(expiry_text)
    except ValueError:
        return jsonify({"status": "error", "error": "expiry must be a valid ISO date (YYYY-MM-DD)."}), 400

    legs_or_error = _parse_legs(body.get("legs"))
    if isinstance(legs_or_error, str):
        return jsonify({"status": "error", "error": legs_or_error}), 400

    try:
        payload = _strategy_service().create_strategy(
            name=name,
            underlying=underlying,
            exchange_code=exchange_code,
            expiry_date=expiry_date,
            legs=legs_or_error,
        )
    except StrategyServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 400

    return jsonify(payload), 201


@strategy_bp.delete("/strategies/<int:strategy_id>")
def delete_strategy(strategy_id: int) -> tuple[object, int]:
    try:
        payload = _strategy_service().delete_strategy(strategy_id)
    except StrategyServiceError as error:
        return jsonify({"status": "error", "error": str(error)}), 404
    return jsonify(payload), 200
