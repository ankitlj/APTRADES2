from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

from flask import current_app

from .breeze_gateway import BreezeGateway, BreezeGatewayError, BreezeInstrument
from .instrument_search_service import InstrumentSearchService
from .master_contract_service import MasterContractService
from .positions_service import PositionsService, PositionsServiceError
from .quote_service import QuoteRequest, QuoteService, QuoteServiceError
from .symbol_resolver import ResolvedInstrument, SymbolResolver

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
        self.instrument_search = InstrumentSearchService(dependencies.database_url)

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

    _OPTION_ORDERBOOK_UNDERLYINGS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "NIFTYMID50"}

    def get_option_orderbook(
        self,
        underlying: str,
        exchange: str,
        expiry: str,
        strike: str,
        right: str,
    ) -> dict[str, Any]:
        normalized_underlying = underlying.strip().upper()
        normalized_exchange = exchange.strip().upper()
        normalized_expiry = expiry.strip()
        normalized_strike = strike.strip()
        normalized_right = right.strip().lower()

        if not normalized_underlying or normalized_underlying not in self._OPTION_ORDERBOOK_UNDERLYINGS:
            raise DashboardServiceError(
                f"Unsupported underlying '{underlying}'. Supported: {', '.join(sorted(self._OPTION_ORDERBOOK_UNDERLYINGS))}."
            )
        if not normalized_expiry:
            raise DashboardServiceError("expiry is required (ISO date string).")
        if not normalized_strike:
            raise DashboardServiceError("strike is required.")
        if normalized_right not in ("call", "put"):
            raise DashboardServiceError("right must be 'call' or 'put'.")

        try:
            resolver = SymbolResolver(self.dependencies.database_url)
            cash_resolved = resolver.resolve(normalized_underlying, "NSE", product_type="cash")
            broker_symbol = cash_resolved.broker_symbol
        except Exception as error:
            raise DashboardServiceError(f"Failed to resolve underlying '{normalized_underlying}': {error}") from error

        expiry_value = f"{normalized_expiry}T06:00:00.000Z"
        instrument = BreezeInstrument(
            display_symbol=broker_symbol,
            stock_code=broker_symbol,
            exchange_code=normalized_exchange,
            product_type="options",
            right=normalized_right,
            strike_price=normalized_strike,
            expiry_date=expiry_value,
        )

        try:
            rows = self.gateway.get_option_chain_quotes(instrument)
        except BreezeGatewayError as error:
            raise DashboardServiceError(f"Breeze option chain request failed: {error}") from error

        if not isinstance(rows, list) or len(rows) == 0:
            return self._empty_option_orderbook(
                underlying=normalized_underlying,
                exchange=normalized_exchange,
                expiry=normalized_expiry,
                strike=normalized_strike,
                right=normalized_right,
                broker_symbol=broker_symbol,
                error="Breeze returned no data for this option contract.",
            )

        row = rows[0] if isinstance(rows[0], dict) else {}
        ltp = self._to_float(row.get("ltp"))
        bid_price = self._to_float(row.get("best_bid_price") or row.get("bid_price"))
        ask_price = self._to_float(row.get("best_offer_price") or row.get("ask_price"))
        bid_qty = self._to_float(
            row.get("best_bid_quantity") or row.get("best_bid_qty") or row.get("bid_qty")
        )
        ask_qty = self._to_float(
            row.get("best_offer_quantity") or row.get("best_offer_qty") or row.get("ask_qty") or row.get("ask_quantity")
        )
        previous_close = self._to_float(row.get("previous_close") or row.get("close"))
        oi = self._to_float(row.get("open_interest") or row.get("oi") or row.get("openinterest"))
        volume = self._to_float(
            row.get("total_quantity_traded") or row.get("volume") or row.get("trade_volume")
        )
        spot_price = self._to_float(row.get("spot_price"))

        total_buy_raw = self._to_float(row.get("total_buy_qty"))
        total_sell_raw = self._to_float(row.get("total_sell_qty"))
        if total_buy_raw is not None:
            total_buy = total_buy_raw
        else:
            total_buy = bid_qty if bid_qty is not None else 0.0
        if total_sell_raw is not None:
            total_sell = total_sell_raw
        else:
            total_sell = ask_qty if ask_qty is not None else 0.0
        total = total_buy + total_sell
        buy_percent = round((total_buy / total) * 100, 1) if total > 0 else 50.0
        sell_percent = round((total_sell / total) * 100, 1) if total > 0 else 50.0

        token = str(row.get("token") or "").strip() or None

        level = {}
        if bid_qty is not None:
            level["bid_qty"] = bid_qty
        if bid_price is not None:
            level["bid_price"] = bid_price
        if ask_price is not None:
            level["ask_price"] = ask_price
        if ask_qty is not None:
            level["ask_qty"] = ask_qty

        return {
            "status": "ok",
            "underlying": normalized_underlying,
            "exchange": normalized_exchange,
            "expiry": normalized_expiry,
            "strike": self._to_float(normalized_strike) or normalized_strike,
            "right": normalized_right,
            "instrument": {
                "display_symbol": broker_symbol,
                "broker_symbol": broker_symbol,
                "stock_code": broker_symbol,
                "exchange_code": normalized_exchange,
                "product_type": "options",
                "token": token,
                "stock_token": token,
            },
            "ltp": ltp,
            "previous_close": previous_close,
            "bid_price": bid_price,
            "bid_qty": bid_qty,
            "ask_price": ask_price,
            "ask_qty": ask_qty,
            "levels": [level] if level else [],
            "total_buy_qty": total_buy,
            "total_sell_qty": total_sell,
            "buy_percent": buy_percent,
            "sell_percent": sell_percent,
            "spot_price": spot_price,
            "underlying_ltp": spot_price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def search_instruments(self, query: str, tab: str = "all") -> dict[str, object]:
        return self.instrument_search.search(query, tab=tab)

    def get_orderbook(
        self,
        broker_symbol: str,
        exchange_code: str,
        product_type: str,
        expiry_date: str | None = None,
        right: str | None = None,
        strike_price: str | None = None,
    ) -> dict[str, object]:
        normalized_symbol = broker_symbol.strip().upper()
        normalized_exchange = exchange_code.strip().upper()
        normalized_product = product_type.strip().lower()

        if not normalized_symbol:
            raise DashboardServiceError("broker_symbol is required.")
        if not normalized_exchange:
            raise DashboardServiceError("exchange_code is required.")
        if normalized_product not in ("cash", "futures", "options"):
            raise DashboardServiceError("product_type must be 'cash', 'futures', or 'options'.")

        try:
            resolver = SymbolResolver(self.dependencies.database_url)
            parsed_expiry = None
            if expiry_date:
                from datetime import date as date_type
                parsed_expiry = date_type.fromisoformat(expiry_date.split("T")[0])

            resolved = resolver.resolve(
                normalized_symbol,
                normalized_exchange,
                product_type=normalized_product,
                expiry_date=parsed_expiry,
                right=right,
                strike_price=strike_price,
            )
        except Exception as error:
            raise DashboardServiceError(f"Failed to resolve instrument: {error}") from error

        breeze_expiry = ""
        if isinstance(resolved.expiry_date, date):
            breeze_expiry = f"{resolved.expiry_date.isoformat()}T06:00:00.000Z"
        breeze_instrument = BreezeInstrument(
            display_symbol=resolved.display_symbol,
            stock_code=resolved.broker_symbol,
            exchange_code=resolved.exchange_code,
            product_type=normalized_product,
            right=resolved.right,
            strike_price=resolved.strike_price,
            expiry_date=breeze_expiry,
        )

        try:
            if normalized_product == "options":
                rows = self.gateway.get_option_chain_quotes(breeze_instrument)
            else:
                rows = self.gateway.get_quote(breeze_instrument)
        except BreezeGatewayError as error:
            raise DashboardServiceError(f"Breeze request failed: {error}") from error

        if not isinstance(rows, list) or len(rows) == 0:
            return self._empty_orderbook(
                broker_symbol=normalized_symbol,
                exchange_code=normalized_exchange,
                product_type=normalized_product,
                error="Breeze returned no data for this instrument.",
            )

        row = rows[0] if isinstance(rows[0], dict) else {}
        ltp = self._to_float(row.get("ltp"))
        bid_price = self._to_float(row.get("best_bid_price") or row.get("bid_price"))
        ask_price = self._to_float(row.get("best_offer_price") or row.get("ask_price"))
        bid_qty = self._to_float(
            row.get("best_bid_quantity") or row.get("best_bid_qty") or row.get("bid_qty")
        )
        ask_qty = self._to_float(
            row.get("best_offer_quantity") or row.get("best_offer_qty") or row.get("ask_qty") or row.get("ask_quantity")
        )
        previous_close = self._to_float(row.get("previous_close") or row.get("close"))
        spot_price = self._to_float(row.get("spot_price"))

        total_buy_raw = self._to_float(row.get("total_buy_qty"))
        total_sell_raw = self._to_float(row.get("total_sell_qty"))
        if total_buy_raw is not None:
            total_buy = total_buy_raw
        else:
            total_buy = bid_qty if bid_qty is not None else 0.0
        if total_sell_raw is not None:
            total_sell = total_sell_raw
        else:
            total_sell = ask_qty if ask_qty is not None else 0.0
        total = total_buy + total_sell
        buy_percent = round((total_buy / total) * 100, 1) if total > 0 else 50.0
        sell_percent = round((total_sell / total) * 100, 1) if total > 0 else 50.0

        token = str(row.get("token") or "").strip() or None

        level = {}
        if bid_qty is not None:
            level["bid_qty"] = bid_qty
        if bid_price is not None:
            level["bid_price"] = bid_price
        if ask_price is not None:
            level["ask_price"] = ask_price
        if ask_qty is not None:
            level["ask_qty"] = ask_qty

        return {
            "status": "ok",
            "instrument": {
                "display_symbol": resolved.display_symbol,
                "broker_symbol": resolved.broker_symbol,
                "stock_code": resolved.broker_symbol,
                "exchange_code": resolved.exchange_code,
                "product_type": normalized_product,
                "token": token,
                "stock_token": token,
            },
            "ltp": ltp,
            "previous_close": previous_close,
            "bid_price": bid_price,
            "bid_qty": bid_qty,
            "ask_price": ask_price,
            "ask_qty": ask_qty,
            "levels": [level] if level else [],
            "total_buy_qty": total_buy,
            "total_sell_qty": total_sell,
            "buy_percent": buy_percent,
            "sell_percent": sell_percent,
            "spot_price": spot_price,
            "underlying_ltp": spot_price,
            "product_type": normalized_product,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _empty_orderbook(
        *,
        broker_symbol: str,
        exchange_code: str,
        product_type: str,
        error: str,
    ) -> dict[str, object]:
        return {
            "status": "error",
            "instrument": {
                "display_symbol": broker_symbol,
                "broker_symbol": broker_symbol,
                "stock_code": broker_symbol,
                "exchange_code": exchange_code,
                "product_type": product_type,
                "token": None,
                "stock_token": None,
            },
            "ltp": None,
            "previous_close": None,
            "bid_price": None,
            "bid_qty": None,
            "ask_price": None,
            "ask_qty": None,
            "levels": [],
            "total_buy_qty": 0,
            "total_sell_qty": 0,
            "buy_percent": 50.0,
            "sell_percent": 50.0,
            "spot_price": None,
            "underlying_ltp": None,
            "product_type": product_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }

    @staticmethod
    def _empty_option_orderbook(
        *,
        underlying: str,
        exchange: str,
        expiry: str,
        strike: str,
        right: str,
        broker_symbol: str,
        error: str,
    ) -> dict[str, Any]:
        return {
            "status": "error",
            "underlying": underlying,
            "exchange": exchange,
            "expiry": expiry,
            "strike": strike,
            "right": right,
            "instrument": {
                "display_symbol": broker_symbol,
                "broker_symbol": broker_symbol,
                "stock_code": broker_symbol,
                "exchange_code": exchange,
                "product_type": "options",
                "token": None,
                "stock_token": None,
            },
            "ltp": None,
            "previous_close": None,
            "bid_price": None,
            "bid_qty": None,
            "ask_price": None,
            "ask_qty": None,
            "levels": [],
            "total_buy_qty": 0,
            "total_sell_qty": 0,
            "buy_percent": 50.0,
            "sell_percent": 50.0,
            "spot_price": None,
            "underlying_ltp": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }

    def _resolve_chart_instrument(self, symbol: str) -> ResolvedInstrument:
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

    def get_order_preview(self, params: dict[str, Any]) -> dict[str, Any]:
        broker_symbol = params.get("broker_symbol", "").strip().upper()
        exchange_code = params.get("exchange_code", "").strip().upper()
        product_type = params.get("product_type", "").strip().lower()
        action = params.get("action", "buy").strip().lower()
        quantity_str = params.get("quantity", "1")
        price_str = params.get("price", "0")
        expiry_date_str = params.get("expiry_date", "")
        right = params.get("right", "others").strip().lower()
        strike_price = params.get("strike_price", "0")

        if not broker_symbol or not exchange_code or product_type not in ("cash", "futures", "options"):
            return {"status": "error", "error": "Invalid instrument parameters."}
        if action not in ("buy", "sell"):
            return {"status": "error", "error": "action must be 'buy' or 'sell'."}

        try:
            from datetime import date as date_type
            parsed_expiry = None
            if expiry_date_str:
                parsed_expiry = date_type.fromisoformat(expiry_date_str.split("T")[0])

            resolver = SymbolResolver(self.dependencies.database_url)
            resolved = resolver.resolve(
                broker_symbol,
                exchange_code,
                product_type=product_type,
                expiry_date=parsed_expiry,
                right=right,
                strike_price=strike_price,
            )
        except Exception as error:
            return {"status": "error", "error": f"Failed to resolve instrument: {error}"}

        try:
            lot_size = resolved.lot_size or 1
            quantity_lots = max(1, int(float(quantity_str)))
            quantity = quantity_lots * lot_size
            price = float(price_str) if price_str else 0.0

            breeze_product = product_type
            if product_type == "futures":
                breeze_product = "futures"
            elif product_type == "options":
                breeze_product = "options"

            breeze_expiry = ""
            if resolved.expiry_date and isinstance(resolved.expiry_date, date):
                breeze_expiry = resolved.expiry_date.strftime("%d-%b-%Y")

            breeze_right = resolved.right
            breeze_strike = resolved.strike_price

            margin_result: dict[str, Any] = {"margin_status": "not_calculated"}
            fund_result: dict[str, Any] = {}

            if product_type in ("futures", "options") and price > 0:
                try:
                    calc_position = {
                        "strike_price": breeze_strike,
                        "quantity": str(quantity),
                        "right": breeze_right.capitalize() if breeze_right != "others" else "Others",
                        "product": breeze_product,
                        "action": action,
                        "price": str(price),
                        "expiry_date": breeze_expiry,
                        "stock_code": resolved.broker_symbol,
                        "cover_order_flow": "N",
                        "fresh_order_type": "N",
                        "cover_limit_rate": "0",
                        "cover_sltp_price": "0",
                        "fresh_limit_rate": "0",
                        "open_quantity": "0",
                    }
                    calc_resp = self.gateway.get_margin_calculator([calc_position], exchange_code)
                    span_margin = self._to_float(calc_resp.get("span_margin_required"))
                    non_span_margin = self._to_float(calc_resp.get("non_span_margin_required"))
                    margin_result = {
                        "margin_status": "ok",
                        "span_margin": span_margin,
                        "non_span_margin": non_span_margin,
                        "order_value": self._to_float(calc_resp.get("order_value")),
                        "order_margin": self._to_float(calc_resp.get("order_margin")),
                        "trade_margin": self._to_float(calc_resp.get("trade_margin")),
                        "block_trade_margin": self._to_float(calc_resp.get("block_trade_margin")),
                        "total_margin": (span_margin or 0) + (non_span_margin or 0),
                    }
                except Exception as error:
                    margin_result = {"margin_status": "error", "error": str(error)}

            if exchange_code in ("NSE", "NFO"):
                try:
                    fund_resp = self.gateway.get_funds()
                    if exchange_code == "NFO":
                        allocated = self._to_float(fund_resp.get("allocated_fno"))
                        blocked = self._to_float(fund_resp.get("block_by_trade_fno"))
                    else:
                        allocated = self._to_float(fund_resp.get("allocated_equity"))
                        blocked = self._to_float(fund_resp.get("block_by_trade_equity"))
                    unallocated = self._to_float(fund_resp.get("unallocated_balance"))
                    fund_result = {
                        "fund_status": "ok",
                        "allocated": allocated,
                        "blocked_by_trade": blocked,
                        "unallocated_balance": unallocated,
                    }
                except Exception as error:
                    fund_result = {"fund_status": "error", "error": str(error)}

            return {
                "status": "ok",
                "instrument": {
                    "display_symbol": resolved.display_symbol,
                    "broker_symbol": resolved.broker_symbol,
                    "exchange_code": resolved.exchange_code,
                    "product_type": resolved.product_type,
                    "token": resolved.token,
                    "contract_code": resolved.contract_code,
                    "lot_size": lot_size,
                    "tick_size": resolved.tick_size,
                    "expiry_date": resolved.expiry_date.isoformat() if isinstance(resolved.expiry_date, date) else None,
                    "right": resolved.right,
                    "strike_price": resolved.strike_price,
                },
                "preview": {
                    "product_type": product_type,
                    "action": action,
                    "quantity": quantity,
                    "price": price,
                    "lots": max(1, quantity // lot_size) if lot_size else quantity,
                    "total_quantity": quantity,
                    "margin": margin_result,
                    "funds": fund_result,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as error:
            return {"status": "error", "error": f"Preview build failed: {error}"}

    def place_order(self, params: dict[str, Any]) -> dict[str, Any]:
        broker_symbol = params.get("broker_symbol", "").strip().upper()
        exchange_code = params.get("exchange_code", "").strip().upper()
        product_type = params.get("product_type", "").strip().lower()
        action = params.get("action", "buy").strip().lower()
        quantity = params.get("quantity", "1")
        price = params.get("price", "0")
        order_type = params.get("order_type", "limit").strip().lower()
        validity = params.get("validity", "day").strip().lower()
        expiry_date_str = params.get("expiry_date", "")
        right = params.get("right", "others").strip().lower()
        strike_price = params.get("strike_price", "0")

        if not broker_symbol or not exchange_code:
            raise DashboardServiceError("broker_symbol and exchange_code are required.")
        if product_type not in ("cash", "futures", "options"):
            raise DashboardServiceError("product_type must be 'cash', 'futures', or 'options'.")
        if action not in ("buy", "sell"):
            raise DashboardServiceError("action must be 'buy' or 'sell'.")

        try:
            from datetime import date as date_type
            parsed_expiry = None
            if expiry_date_str:
                parsed_expiry = date_type.fromisoformat(expiry_date_str.split("T")[0])

            resolver = SymbolResolver(self.dependencies.database_url)
            resolved = resolver.resolve(
                broker_symbol, exchange_code,
                product_type=product_type,
                expiry_date=parsed_expiry,
                right=right,
                strike_price=strike_price,
            )
        except Exception as error:
            raise DashboardServiceError(f"Failed to resolve instrument: {error}")

        try:
            lot_size = resolved.lot_size or 1
            quantity_lots = max(1, int(float(quantity)))
            quantity_actual = quantity_lots * lot_size

            breeze_payload: dict[str, str] = {
                "stock_code": resolved.broker_symbol,
                "exchange_code": resolved.exchange_code,
                "product": product_type,
                "action": action,
                "order_type": order_type,
                "quantity": str(quantity_actual),
                "price": str(price),
                "validity": validity,
                "stoploss": "",
                "disclosed_quantity": "0",
                "user_remark": "dashboard",
            }

            if product_type in ("futures", "options") and isinstance(resolved.expiry_date, date):
                breeze_payload["expiry_date"] = resolved.expiry_date.strftime("%Y-%m-%d") + "T06:00:00.000Z"
            if product_type == "options":
                breeze_payload["right"] = resolved.right
                breeze_payload["strike_price"] = resolved.strike_price

            result = self.gateway.place_order(breeze_payload)
        except Exception as error:
            raise DashboardServiceError(f"Order placement failed: {error}")

        return {
            "status": "ok",
            "order_id": result.get("order_id", ""),
            "message": result.get("message", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

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
