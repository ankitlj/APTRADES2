from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .breeze_gateway import BreezeGateway, BreezeGatewayError
from .master_contract_service import MasterContractService
from .positions_service import PositionsService, PositionsServiceError
from .quote_service import QuoteRequest, QuoteService, QuoteServiceError
from .symbol_resolver import ResolvedInstrument


class DashboardServiceError(Exception):
    pass


@dataclass(frozen=True)
class DashboardDependencies:
    database_url: str | None
    stock_script_csv_path: str | None
    security_master_url: str
    security_master_connect_timeout: int
    security_master_read_timeout: int
    gateway: BreezeGateway


class DashboardService:
    def __init__(self, dependencies: DashboardDependencies):
        self.dependencies = dependencies
        self.quote_service = QuoteService(dependencies.database_url, dependencies.gateway)
        self.positions_service = PositionsService(dependencies.gateway, dependencies.database_url)
        self.master_contract_service = MasterContractService(
            database_url=dependencies.database_url,
            stock_script_csv_path=dependencies.stock_script_csv_path,
            security_master_url=dependencies.security_master_url,
            security_master_connect_timeout=dependencies.security_master_connect_timeout,
            security_master_read_timeout=dependencies.security_master_read_timeout,
        )
        self.gateway = dependencies.gateway

    def get_summary(self) -> dict[str, Any]:
        quote_results = self.quote_service.get_batch_quotes(
            [
                QuoteRequest(symbol="NIFTY", exchange_code="NFO", product_type="futures"),
                QuoteRequest(symbol="BANKNIFTY", exchange_code="NFO", product_type="futures"),
            ]
        )["results"]

        try:
            positions_payload = self.positions_service.get_positions()
        except PositionsServiceError as error:
            positions_payload = {
                "status": "error",
                "positions": [],
                "totals": {
                    "open_positions": 0,
                    "long_positions": 0,
                    "short_positions": 0,
                    "total_pnl": 0.0,
                },
                "error": str(error),
            }

        market_cards = [self._market_card(result) for result in quote_results]
        totals = positions_payload["totals"]
        metrics = [
            *market_cards,
            {
                "key": "open_positions",
                "label": "Open positions",
                "value": totals["open_positions"],
                "meta": f"{totals['long_positions']} long / {totals['short_positions']} short",
                "tone": "neutral",
            },
            {
                "key": "total_pnl",
                "label": "Total p&l",
                "value": totals["total_pnl"],
                "meta": "Breeze portfolio positions",
                "tone": "positive" if totals["total_pnl"] > 0 else "negative" if totals["total_pnl"] < 0 else "neutral",
            },
        ]

        return {
            "status": "ok",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "ticker": [self._ticker_item(result) for result in quote_results],
            "positions_status": positions_payload["status"],
            "positions_error": positions_payload.get("error"),
            "positions": positions_payload["positions"][:8],
        }

    def get_alerts(self) -> dict[str, Any]:
        alerts: list[dict[str, str]] = []
        master_contract_status = self.master_contract_service.get_status()
        auth_status = self.gateway.auth_diagnostic()

        if auth_status.get("status") == "ok":
            alerts.append(
                {
                    "level": "success",
                    "title": "Breeze session active",
                    "message": f"Authenticated as {auth_status.get('user_id') or 'configured user'} and quote services are available.",
                }
            )
        else:
            alerts.append(
                {
                    "level": "warning",
                    "title": "Breeze needs attention",
                    "message": auth_status.get("error")
                    or f"Gateway status is {auth_status.get('status', 'unknown')}. Refresh the session token if quotes stop updating.",
                }
            )

        latest_run = master_contract_status.get("latest_run") or {}
        source_name = latest_run.get("source_name") or master_contract_status.get("status", "unknown")
        row_count = master_contract_status.get("instrument_count", 0)
        alerts.append(
            {
                "level": "info",
                "title": "Master contract loaded",
                "message": f"{row_count} instruments are available from {source_name}.",
            }
        )

        try:
            positions_payload = self.positions_service.get_positions()
            position_count = positions_payload["totals"]["open_positions"]
            if position_count:
                alerts.append(
                    {
                        "level": "info",
                        "title": "Active positions detected",
                        "message": f"{position_count} live positions are flowing into the dashboard table.",
                    }
                )
            else:
                alerts.append(
                    {
                        "level": "info",
                        "title": "No active positions",
                        "message": "Breeze returned no open positions, so the positions table will stay empty until a live position exists.",
                    }
                )
        except PositionsServiceError as error:
            alerts.append(
                {
                    "level": "warning",
                    "title": "Positions temporarily unavailable",
                    "message": str(error),
                }
            )

        return {"status": "ok", "alerts": alerts}

    def get_chart(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise DashboardServiceError("symbol is required.")

        try:
            resolved = self._resolve_chart_instrument(normalized_symbol)
        except Exception as error:  # noqa: BLE001
            raise DashboardServiceError(str(error)) from error

        from_date = datetime.now(timezone.utc) - timedelta(days=30)
        to_date = datetime.now(timezone.utc)
        try:
            candles = self.gateway.get_historical_charts(
                QuoteService._to_breeze_instrument(resolved),
                interval="day",
                from_date=from_date,
                to_date=to_date,
            )
        except BreezeGatewayError as error:
            raise DashboardServiceError(str(error)) from error

        points = [self._chart_point(candle) for candle in candles if isinstance(candle, dict)]
        return {
            "status": "ok",
            "symbol": normalized_symbol,
            "resolved": self._serialize_resolved(resolved),
            "interval": "day",
            "points": points,
        }

    def _resolve_chart_instrument(self, symbol: str) -> ResolvedInstrument:
        if symbol in {"NIFTY", "BANKNIFTY"}:
            return self.quote_service.symbol_resolver.resolve(symbol, "NFO", product_type="futures")
        return self.quote_service.symbol_resolver.resolve(symbol, "NSE", product_type="cash")

    @staticmethod
    def _market_card(result: dict[str, Any]) -> dict[str, Any]:
        resolved = result.get("resolved") or {}
        quote = result.get("quote") or {}
        ltp = DashboardService._to_float(quote.get("ltp"))
        previous_close = DashboardService._to_float(quote.get("previous_close"))
        change = round(ltp - previous_close, 2) if ltp is not None and previous_close is not None else None
        return {
            "key": result["symbol"].lower(),
            "label": f"{result['symbol']} futures",
            "value": ltp,
            "change": change,
            "previous_close": previous_close,
            "expiry_date": quote.get("expiry_date") or resolved.get("expiry_date"),
            "meta": f"token {resolved.get('token') or 'n/a'}",
            "tone": "positive" if change and change > 0 else "negative" if change and change < 0 else "neutral",
            "status": result["status"],
        }

    @staticmethod
    def _ticker_item(result: dict[str, Any]) -> dict[str, Any]:
        resolved = result.get("resolved") or {}
        quote = result.get("quote") or {}
        ltp = DashboardService._to_float(quote.get("ltp"))
        previous_close = DashboardService._to_float(quote.get("previous_close"))
        change_percent = None
        if ltp is not None and previous_close not in (None, 0):
            change_percent = round(((ltp - previous_close) / previous_close) * 100, 2)
        return {
            "symbol": result["symbol"],
            "broker_symbol": resolved.get("broker_symbol"),
            "ltp": ltp,
            "change_percent": change_percent,
            "status": result["status"],
        }

    @staticmethod
    def _chart_point(candle: dict[str, Any]) -> dict[str, Any]:
        return {
            "time": candle.get("datetime"),
            "open": DashboardService._to_float(candle.get("open")),
            "high": DashboardService._to_float(candle.get("high")),
            "low": DashboardService._to_float(candle.get("low")),
            "close": DashboardService._to_float(candle.get("close")),
            "volume": DashboardService._to_float(candle.get("volume")),
        }

    @staticmethod
    def _serialize_resolved(resolved: ResolvedInstrument) -> dict[str, Any]:
        return {
            "display_symbol": resolved.display_symbol,
            "broker_symbol": resolved.broker_symbol,
            "exchange_code": resolved.exchange_code,
            "product_type": resolved.product_type,
            "token": resolved.token,
            "contract_code": resolved.contract_code,
            "expiry_date": resolved.expiry_date.isoformat() if resolved.expiry_date else None,
        }

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            return None
