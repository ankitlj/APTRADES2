from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app

from .breeze_gateway import BreezeGateway, BreezeGatewayError
from .master_contract_service import MasterContractService
from .positions_service import PositionsService, PositionsServiceError
from .quote_service import QuoteRequest, QuoteService, QuoteServiceError
from .symbol_resolver import ResolvedInstrument

_CHART_CACHE_TTL = 300  # 5 minutes — daily candles change slowly
_CHART_CACHE_KEY_PREFIX = "_DASHBOARD_CHART_CACHE_"
_chart_cache_lock = threading.Lock()


class DashboardServiceError(Exception):
    pass


# The 4 NSE cash/index symbols shown in the ORIENS top ticker, with their REST
# quote parameters and display labels. SENSEX was removed because Breeze does not
# return usable live quotes for BSE cash indices. Live websocket ticks (from the
# default watchlist in realtime.py) are overlaid on top of these snapshot values.
_TICKER_SYMBOLS: list[dict[str, str | None]] = [
    {"symbol": "NIFTY", "exchange_code": "NSE", "product_type": "cash", "label": "NIFTY 50"},
    {"symbol": "BANKNIFTY", "exchange_code": "NSE", "product_type": "cash", "label": "BANKNIFTY"},
    {"symbol": "NIFTYMID50", "exchange_code": "NSE", "product_type": "cash", "label": "MIDCAP50"},
    {"symbol": "FINNIFTY", "exchange_code": "NSE", "product_type": "cash", "label": "FINNIFTY"},
]

# Fallback TTL for last-known-good ticker quotes (seconds). When Breeze returns
# a null or invalid quote for a ticker symbol, the dashboard will reuse the most
# recent valid quote for up to this duration instead of showing Unavailable.
_FALLBACK_TTL = 120

# Per-symbol cache of the last valid ticker quote. Keyed by _TICKER_SYMBOLS
# symbol key (e.g. "NIFTY"). Each entry: {"ltp": float, "change_percent": float | None,
# "ts": monotonic()}. Guarded by _last_good_lock.
_last_good_quotes: dict[str, dict[str, Any]] = {}
_last_good_lock = threading.Lock()


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
                QuoteRequest(
                    symbol=str(item["symbol"]),
                    exchange_code=str(item["exchange_code"]),
                    product_type=item.get("product_type") or None,
                )
                for item in _TICKER_SYMBOLS
            ]
        )["results"]

        try:
            positions_payload = self.positions_service.get_positions(gateway_timeout=4, gateway_attempts=1)
        except PositionsServiceError as error:
            positions_payload = {
                "status": "degraded",
                "positions": [],
                "totals": self._empty_position_totals(),
                "error": str(error),
            }

        totals = positions_payload["totals"]
        metrics = self._portfolio_metrics(totals)

        ticker: list[dict[str, Any]] = []
        for result, item in zip(quote_results, _TICKER_SYMBOLS):
            symbol_key = str(item["symbol"])
            ticker_item = self._ticker_item(result, str(item.get("label", result["symbol"])))
            ticker_item = self._apply_fallback(ticker_item, symbol_key)
            ticker.append(ticker_item)

        return {
            "status": "ok",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "ticker": ticker,
            "positions_status": positions_payload["status"],
            "positions_error": positions_payload.get("error"),
            "positions": positions_payload["positions"][:8],
        }

    def get_alerts(self) -> dict[str, Any]:
        alerts: list[dict[str, str]] = []
        master_contract_status = self.master_contract_service.get_status()
        auth_status: dict[str, Any]
        try:
            auth_status = self.gateway.auth_diagnostic(timeout_override=4)
        except Exception:
            auth_status = {"status": "degraded"}

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

        cached_positions = self.positions_service.get_cached_positions()
        if cached_positions is not None:
            position_count = cached_positions["totals"]["open_positions"]
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
        else:
            alerts.append(
                {
                    "level": "info",
                    "title": "Positions snapshot pending",
                    "message": "Position data will appear after the first positions refresh completes.",
                }
            )

        return {"status": "ok", "alerts": alerts}

    def get_chart(self, symbol: str) -> dict[str, Any]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise DashboardServiceError("symbol is required.")

        cache_key = _CHART_CACHE_KEY_PREFIX + normalized_symbol
        cache_store = self._get_cache_store()
        if cache_store is not None:
            with _chart_cache_lock:
                entry = cache_store.get(cache_key)
            if entry is not None and (time.monotonic() - entry[0]) < _CHART_CACHE_TTL:
                return entry[1]

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
        result = {
            "status": "ok",
            "symbol": normalized_symbol,
            "resolved": self._serialize_resolved(resolved),
            "interval": "day",
            "points": points,
        }
        if cache_store is not None:
            with _chart_cache_lock:
                cache_store[cache_key] = (time.monotonic(), result)
        return result

    def _resolve_chart_instrument(self, symbol: str) -> ResolvedInstrument:
        if symbol in {"NIFTY", "BANKNIFTY"}:
            return self.quote_service.symbol_resolver.resolve(symbol, "NFO", product_type="futures")
        return self.quote_service.symbol_resolver.resolve(symbol, "NSE", product_type="cash")

    @staticmethod
    def _get_cache_store() -> dict[str, Any] | None:
        try:
            return current_app.config
        except RuntimeError:
            return None

    @staticmethod
    def _portfolio_metrics(totals: dict[str, Any]) -> list[dict[str, Any]]:
        day_pnl = DashboardService._to_float(totals.get("day_pnl")) or 0.0
        realized_pnl = DashboardService._to_float(totals.get("realized_pnl")) or 0.0
        unrealized_pnl = DashboardService._to_float(totals.get("unrealized_pnl")) or 0.0
        open_positions = int(DashboardService._to_float(totals.get("open_positions")) or 0)
        option_positions = int(DashboardService._to_float(totals.get("option_positions")) or 0)
        future_positions = int(DashboardService._to_float(totals.get("future_positions")) or 0)
        equity_positions = int(DashboardService._to_float(totals.get("equity_positions")) or 0)
        return [
            {
                "key": "day_pnl",
                "label": "Day's P&L",
                "value": day_pnl,
                "format": "currency",
                "meta": "",
                "tone": DashboardService._value_tone(day_pnl),
                "submetrics": [
                    {"label": "Realized", "value": realized_pnl, "format": "currency", "tone": DashboardService._value_tone(realized_pnl)},
                    {
                        "label": "Unrealized",
                        "value": unrealized_pnl,
                        "format": "currency",
                        "tone": DashboardService._value_tone(unrealized_pnl),
                    },
                ],
            },
            {
                "key": "open_positions",
                "label": "Open positions",
                "value": open_positions,
                "format": "number",
                "meta": "",
                "tone": "neutral",
                "submetrics": [
                    {"label": "Options", "value": option_positions, "format": "number", "tone": "neutral"},
                    {"label": "Future", "value": future_positions, "format": "number", "tone": "neutral"},
                    {"label": "Equity", "value": equity_positions, "format": "number", "tone": "neutral"},
                ],
            },
            {
                "key": "monthly_roi",
                "label": "Monthly ROI",
                "value": None,
                "format": "percent",
                "meta": "",
                "tone": "neutral",
                "submetrics": [{"label": "Annual ROI (FY)", "value": None, "format": "percent", "tone": "neutral"}],
            },
            {
                "key": "margin_used",
                "label": "Margin used",
                "value": 0.0,
                "format": "currency",
                "meta": "",
                "tone": "warning",
                "submetrics": [],
            },
        ]

    @staticmethod
    def _empty_position_totals() -> dict[str, Any]:
        return {
            "open_positions": 0,
            "long_positions": 0,
            "short_positions": 0,
            "option_positions": 0,
            "future_positions": 0,
            "equity_positions": 0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "day_pnl": 0.0,
            "total_pnl": 0.0,
        }

    @staticmethod
    def _value_tone(value: float) -> str:
        if value > 0:
            return "positive"
        if value < 0:
            return "negative"
        return "neutral"

    @staticmethod
    def _ticker_item(result: dict[str, Any], label: str) -> dict[str, Any]:
        resolved = result.get("resolved") or {}
        quote = result.get("quote") or {}
        ltp = DashboardService._to_float(quote.get("ltp"))
        previous_close = DashboardService._to_float(quote.get("previous_close"))
        change_percent = None
        if ltp is not None and previous_close not in (None, 0):
            change_percent = round(((ltp - previous_close) / previous_close) * 100, 2)
        return {
            "symbol": result["symbol"],
            "label": label,
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

    @staticmethod
    def _is_valid_ticker_quote(result: dict[str, Any]) -> bool:
        if result.get("status") != "ok":
            return False
        quote = result.get("quote")
        if not isinstance(quote, dict):
            return False
        ltp = DashboardService._to_float(quote.get("ltp"))
        if ltp is None or ltp <= 0:
            return False
        return True

    def _apply_fallback(self, ticker_item: dict[str, Any], symbol_key: str) -> dict[str, Any]:
        current_ltp = ticker_item.get("ltp")
        if current_ltp is not None and current_ltp > 0:
            with _last_good_lock:
                _last_good_quotes[symbol_key] = {
                    "ltp": current_ltp,
                    "change_percent": ticker_item.get("change_percent"),
                    "ts": time.monotonic(),
                }
            return ticker_item

        with _last_good_lock:
            cached = _last_good_quotes.get(symbol_key)

        if cached is not None and (time.monotonic() - cached["ts"]) < _FALLBACK_TTL:
            return {
                "symbol": ticker_item["symbol"],
                "label": ticker_item["label"],
                "broker_symbol": ticker_item.get("broker_symbol"),
                "ltp": cached["ltp"],
                "change_percent": cached["change_percent"],
                "status": ticker_item["status"],
            }

        return ticker_item
