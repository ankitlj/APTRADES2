from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ..cache import create_redis_client

logger = logging.getLogger(__name__)

# Breeze stock-token format is "X.Y!token".
#   X = exchange code: 1 = BSE, 2 = BFO OHLC, 4 = NSE / NFO, 8 = BFO live data
#   Y = market level:  1 = exchange quote data, 2 = market depth data
# We always stream exchange quotes (level 1), so the worker subscribes by token.
_EXCHANGE_WS_PREFIX = {
    "NSE": "4",
    "NFO": "4",
    "BSE": "1",
    "BFO": "8",
}
_QUOTE_LEVEL = "1"

# Worker lifecycle states surfaced to the topbar live/degraded/offline badge.
STATE_OFFLINE = "offline"  # not configured / not started — REST keeps serving
STATE_CONNECTING = "connecting"
STATE_LIVE = "live"
STATE_DEGRADED = "degraded"  # connect/stream failed — REST keeps serving

# Diagnostic freshness classification (never emitted to frontend badge; exposed
# via the status endpoint so we can distinguish "transport alive but no data"
# from "active streaming").
FRESHNESS_NO_TICKS_EVER = "no_ticks_ever"
FRESHNESS_STALE = "stale"         # last tick older than freshness threshold
FRESHNESS_ACTIVE = "active"       # recent ticks flowing
_FRESHNESS_THRESHOLD_SECONDS = 30  # no tick in 30s → stale

# Type of the optional publish callback (Socket.IO emit): publish(event, payload).
PublishFn = Callable[[str, dict[str, Any]], None]
# Type of the optional Breeze client factory (injected in tests).
BreezeFactory = Callable[[], Any]


@dataclass(frozen=True)
class Subscription:
    """One streaming subscription, keyed by its Breeze stock-token."""

    display_symbol: str
    broker_symbol: str
    exchange_code: str
    product_type: str
    token: str
    stock_token: str


def _is_numeric_token(token: object) -> bool:
    """Return True when *token* is a non-empty string of digits (no sign,
    no decimal point, no whitespace). Non-numeric tokens cannot be sent to
    the Breeze websocket and indicate a bad DB row or resolver output."""
    text = str(token or "").strip()
    return text.isdigit()


def build_stock_token(exchange_code: str, token: str) -> str | None:
    """Return the Breeze ``X.Y!token`` exchange-quote stream key, or None if it
    cannot be built (unknown exchange, missing token, or non-numeric token)."""
    prefix = _EXCHANGE_WS_PREFIX.get((exchange_code or "").strip().upper())
    cleaned_token = (token or "").strip()
    if not prefix or not cleaned_token or not _is_numeric_token(cleaned_token):
        return None
    return f"{prefix}.{_QUOTE_LEVEL}!{cleaned_token}"


class MarketDataWorker:
    """Owns the Breeze WebSocket connection for the whole app.

    Mirrors the BreezeGateway rule for REST: every piece of Breeze *streaming*
    logic lives here, in one place. Pages and Socket.IO handlers never talk to
    breeze-connect directly.

    Degrades safely. If breeze-connect is not installed, Breeze is not
    configured, or the live connection fails, the worker simply reports a
    non-live state and the REST quote endpoints keep serving data.
    """

    def __init__(
        self,
        *,
        app_key: str | None,
        secret_key: str | None,
        session_token: str | None,
        redis_url: str | None = None,
        publish: PublishFn | None = None,
        breeze_factory: BreezeFactory | None = None,
        tick_ttl_seconds: int = 60,
        reconnect_backoff_seconds: float = 5.0,
        max_backoff_seconds: float = 60.0,
        gap_log_seconds: float = 5.0,
    ):
        self._app_key = app_key
        self._secret_key = secret_key
        self._session_token = session_token
        self._redis_url = redis_url
        self._publish = publish
        self._breeze_factory = breeze_factory
        self._tick_ttl_seconds = tick_ttl_seconds
        self._reconnect_backoff_seconds = reconnect_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        self._gap_log_seconds = gap_log_seconds

        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._breeze: Any | None = None
        self._redis: Any | None = None
        self._last_tick_monotonic: float | None = None

        self._state = STATE_OFFLINE
        self._error: str | None = None
        self._last_tick_at: str | None = None

        # stock_token -> Subscription (the broker key we receive ticks on)
        self._subscriptions: dict[str, Subscription] = {}
        # stock_token -> reference count (how many active subscribers need it)
        self._subscription_ref_counts: dict[str, int] = {}
        # display_symbol -> last normalized tick (in-memory snapshot fallback)
        self._last_ticks: dict[str, dict[str, Any]] = {}

        # ----- diagnostic counters (never emitted to badge, exposed in status) ----
        self._ticks_received_ever: bool = False
        self._first_tick_at: str | None = None
        self._tick_count_total: int = 0
        self._per_symbol_tick_counts: dict[str, int] = {}
        self._subscribe_requests_total: int = 0      # total subscribe() calls
        self._subscribe_attempt_count: int = 0        # total _feed_subscribe calls
        self._subscribe_error_count: int = 0          # failed _feed_subscribe calls
        self._redis_write_error_count: int = 0
        self._redis_write_retry_count: int = 0
        self._last_redis_write_error_at: str | None = None
        self._emit_error_count: int = 0
        self._last_emit_error_at: str | None = None

    # ----- configuration -------------------------------------------------

    def is_configured(self) -> bool:
        return all([self._app_key, self._secret_key, self._session_token])

    def set_publish(self, publish: PublishFn | None) -> None:
        with self._lock:
            self._publish = publish

    # ----- lifecycle -----------------------------------------------------

    def ensure_started(self) -> None:
        """Start the supervisor thread once. Idempotent and safe to call from
        any Socket.IO connect handler."""
        if not self.is_configured():
            self._set_state(STATE_OFFLINE, error="Breeze streaming is not configured.")
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run_supervisor,
                name="market-data-worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            breeze = self._breeze
            self._breeze = None
        if breeze is not None:
            try:
                breeze.ws_disconnect()
            except Exception:  # noqa: BLE001 — shutdown best effort
                pass
        self._set_state(STATE_OFFLINE, error=None)

    def _run_supervisor(self) -> None:
        backoff = self._reconnect_backoff_seconds
        while not self._stop.is_set():
            try:
                self._set_state(STATE_CONNECTING, error=None)
                self._connect()
                self._resubscribe_all()
                self._set_state(STATE_LIVE, error=None)
                backoff = self._reconnect_backoff_seconds
                # breeze-connect runs its own socket.io thread and invokes
                # on_ticks from there, so the supervisor only needs to stay
                # alive and watch for a dropped client.
                while not self._stop.is_set():
                    with self._lock:
                        breeze = self._breeze
                    if breeze is None:
                        raise RuntimeError("Breeze websocket client was lost.")
                    self._stop.wait(5)
            except Exception as error:  # noqa: BLE001 — keep supervisor alive
                self._teardown_breeze()
                if self._stop.is_set():
                    break
                self._set_state(STATE_DEGRADED, error=str(error))
                self._stop.wait(backoff)
                backoff = min(backoff * 2, self._max_backoff_seconds)

    def _connect(self) -> None:
        breeze = self._create_breeze()
        breeze.on_ticks = self._on_ticks
        breeze.ws_connect()
        with self._lock:
            self._breeze = breeze

    def _create_breeze(self) -> Any:
        if self._breeze_factory is not None:
            return self._breeze_factory()
        try:
            from breeze_connect import BreezeConnect  # type: ignore import-not-found
        except Exception as error:  # noqa: BLE001
            raise RuntimeError(
                "breeze-connect is not installed; live streaming is unavailable."
            ) from error
        breeze = BreezeConnect(api_key=self._app_key)
        breeze.generate_session(api_secret=self._secret_key, session_token=self._session_token)
        return breeze

    def _teardown_breeze(self) -> None:
        with self._lock:
            breeze = self._breeze
            self._breeze = None
        if breeze is not None:
            try:
                breeze.ws_disconnect()
            except Exception:  # noqa: BLE001
                pass

    # ----- subscriptions -------------------------------------------------

    def subscribe(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Subscribe to a list of instruments.

        Each item must provide ``token`` and ``exchange_code``; the broker key
        ``stock_token`` is derived from them. Returns a summary of what was
        accepted and skipped (skips never raise — degraded-safe)."""
        self._subscribe_requests_total += 1
        accepted: list[str] = []
        skipped: list[dict[str, str]] = []
        new_subscriptions: list[Subscription] = []

        print(f"[diag] worker.subscribe items_in={len(items)} subs_before={len(self._subscriptions)}")

        for item in items:
            subscription = self._to_subscription(item)
            if subscription is None:
                sym = str(item.get("display_symbol") or item.get("symbol") or "?")
                tok = str(item.get("token") or "")
                exc = str(item.get("exchange_code") or item.get("exchange") or "")
                print(f"[diag]   SKIP symbol={sym} exchange={exc} token={tok} reason=to_subscription_none")
                skipped.append(
                    {
                        "symbol": sym,
                        "reason": "missing token or unsupported exchange",
                    }
                )
                continue
            with self._lock:
                if subscription.stock_token in self._subscriptions:
                    self._subscription_ref_counts[subscription.stock_token] += 1
                    accepted.append(subscription.stock_token)
                    print(f"[diag]   REF_INC stock_token={subscription.stock_token} display_symbol={subscription.display_symbol} ref_count={self._subscription_ref_counts[subscription.stock_token]}")
                    continue
                self._subscriptions[subscription.stock_token] = subscription
                self._subscription_ref_counts[subscription.stock_token] = 1
            logger.info(
                "market-data subscribe: %s -> stock_token=%s display_symbol=%s broker_symbol=%s",
                item.get("display_symbol") or item.get("symbol") or "?",
                subscription.stock_token,
                subscription.display_symbol,
                subscription.broker_symbol,
            )
            print(f"[diag]   NEW stock_token={subscription.stock_token} display_symbol={subscription.display_symbol} exchange={subscription.exchange_code} token={subscription.token}")
            new_subscriptions.append(subscription)
            accepted.append(subscription.stock_token)

        for subscription in new_subscriptions:
            self._feed_subscribe(subscription)

        result_count = len(self._subscriptions)
        print(f"[diag] worker.subscribe done accepted={len(accepted)} skipped={len(skipped)} total_subs={result_count}")
        return {"accepted": accepted, "skipped": skipped, "count": result_count}

    def unsubscribe(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        removed: list[str] = []
        unsub_feeds: list[Subscription] = []
        print(f"[diag] worker.unsubscribe items_in={len(items)} subs_before={len(self._subscriptions)}")
        for item in items:
            subscription = self._to_subscription(item)
            if subscription is None:
                sym = str(item.get("display_symbol") or item.get("symbol") or "?")
                print(f"[diag]   UNSUB_SKIP symbol={sym} reason=to_subscription_none")
                continue
            with self._lock:
                existing = self._subscriptions.get(subscription.stock_token)
                if existing is None:
                    print(f"[diag]   UNSUB_SKIP stock_token={subscription.stock_token} reason=not_in_subscriptions")
                    continue
                current_count = self._subscription_ref_counts.get(subscription.stock_token, 0)
                if current_count <= 1:
                    self._subscriptions.pop(subscription.stock_token, None)
                    self._subscription_ref_counts.pop(subscription.stock_token, None)
                    unsub_feeds.append(existing)
                    print(f"[diag]   UNSUB_TEARDOWN stock_token={subscription.stock_token} display_symbol={subscription.display_symbol} ref_was={current_count}")
                else:
                    self._subscription_ref_counts[subscription.stock_token] = current_count - 1
                    print(f"[diag]   UNSUB_REF_DECR stock_token={subscription.stock_token} display_symbol={subscription.display_symbol} ref_now={current_count - 1}")
            removed.append(subscription.stock_token)
        for subscription in unsub_feeds:
            self._feed_unsubscribe(subscription)
        result_count = len(self._subscriptions)
        print(f"[diag] worker.unsubscribe done removed={len(unsub_feeds)} ref_decrements={len(removed) - len(unsub_feeds)} total_subs={result_count}")
        return {"removed": removed, "count": result_count}

    def _resubscribe_all(self) -> None:
        with self._lock:
            subscriptions = list(self._subscriptions.values())
        for subscription in subscriptions:
            self._feed_subscribe(subscription)

    def _feed_subscribe(self, subscription: Subscription) -> None:
        self._subscribe_attempt_count += 1
        with self._lock:
            breeze = self._breeze
        if breeze is None:
            logger.warning("market-data feed subscribe skipped: breeze not connected for %s", subscription.stock_token)
            return
        try:
            breeze.subscribe_feeds(stock_token=subscription.stock_token)
        except Exception as error:  # noqa: BLE001 — one bad symbol must not kill the stream
            self._subscribe_error_count += 1
            logger.error("market-data feed subscribe failed for %s: %s", subscription.stock_token, error)
            self._set_state(self._state, error=f"subscribe failed for {subscription.stock_token}: {error}")

    def _feed_unsubscribe(self, subscription: Subscription) -> None:
        with self._lock:
            breeze = self._breeze
        if breeze is None:
            return
        try:
            breeze.unsubscribe_feeds(stock_token=subscription.stock_token)
        except Exception:  # noqa: BLE001
            pass

    def _to_subscription(self, item: dict[str, Any]) -> Subscription | None:
        exchange_code = str(item.get("exchange_code") or item.get("exchange") or "").strip().upper()
        token = str(item.get("token") or "").strip()
        if not _is_numeric_token(token):
            logger.warning(
                "market-data subscribe skipped: non-numeric token "
                "display_symbol=%s broker_symbol=%s exchange=%s product_type=%s token=%s reason=non_numeric_token",
                item.get("display_symbol") or "?",
                item.get("broker_symbol") or item.get("display_symbol") or "?",
                exchange_code,
                item.get("product_type") or "?",
                token[:32],
            )
            return None
        stock_token = build_stock_token(exchange_code, token)
        if stock_token is None:
            return None
        display_symbol = str(item.get("display_symbol") or item.get("symbol") or "").strip().upper()
        broker_symbol = str(item.get("broker_symbol") or display_symbol).strip().upper()
        product_type = str(item.get("product_type") or "").strip().lower()
        return Subscription(
            display_symbol=display_symbol or broker_symbol or stock_token,
            broker_symbol=broker_symbol or display_symbol or stock_token,
            exchange_code=exchange_code,
            product_type=product_type,
            token=token,
            stock_token=stock_token,
        )

    # ----- tick handling -------------------------------------------------

    def _freshness(self) -> str:
        """Diagnostic classification: no_ticks_ever / stale / active."""
        if not self._ticks_received_ever:
            return FRESHNESS_NO_TICKS_EVER
        if self._last_tick_at is None:
            return FRESHNESS_NO_TICKS_EVER
        try:
            last = datetime.fromisoformat(self._last_tick_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - last).total_seconds()
            if age > _FRESHNESS_THRESHOLD_SECONDS:
                return FRESHNESS_STALE
        except (ValueError, TypeError):
            pass
        return FRESHNESS_ACTIVE

    def _on_ticks(self, tick: Any) -> None:
        """Breeze on_ticks callback. Runs on the breeze-connect socket thread."""
        if not isinstance(tick, dict):
            return
        normalized = self._normalize_tick(tick)
        if normalized is None:
            return
        self._log_gap()
        now_ts = normalized["ts"]
        self._last_tick_at = now_ts
        if not self._ticks_received_ever:
            self._ticks_received_ever = True
            self._first_tick_at = now_ts
            logger.info("market-data first tick received for %s at %s", normalized["symbol"], now_ts)
        self._tick_count_total += 1
        sym = normalized["symbol"]
        with self._lock:
            self._last_ticks[sym] = normalized
            self._per_symbol_tick_counts[sym] = self._per_symbol_tick_counts.get(sym, 0) + 1
        self._write_redis(normalized)
        self._emit(normalized)

    def _log_gap(self) -> None:
        """Warn when the stream stalled longer than the configured threshold, so
        Railway logs show exactly when and for how long ticks stopped arriving."""
        now = time.monotonic()
        previous = self._last_tick_monotonic
        self._last_tick_monotonic = now
        if previous is not None:
            gap = now - previous
            if gap >= self._gap_log_seconds:
                logger.warning("market-data stream gap of %.1fs", gap)

    def _normalize_tick(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        stock_token = str(tick.get("symbol") or "").strip()
        subscription = self._subscriptions.get(stock_token) if stock_token else None

        ltp = self._to_float(tick.get("last") if "last" in tick else tick.get("close"))
        close = self._to_float(tick.get("close"))
        change_percent = self._to_float(tick.get("change"))
        change_abs = None
        if ltp is not None and close is not None:
            change_abs = round(ltp - close, 2)
            if change_percent is None and close != 0:
                change_percent = round((ltp - close) / close * 100, 2)

        display_symbol = (
            subscription.display_symbol
            if subscription is not None
            else str(tick.get("stock_code") or stock_token or "UNKNOWN").upper()
        )

        return {
            "symbol": display_symbol,
            "broker_symbol": subscription.broker_symbol if subscription else display_symbol,
            "exchange_code": subscription.exchange_code if subscription else str(tick.get("exchange_code") or ""),
            "product_type": subscription.product_type if subscription else "",
            "token": subscription.token if subscription else "",
            "stock_token": stock_token,
            "ltp": ltp,
            "open": self._to_float(tick.get("open")),
            "high": self._to_float(tick.get("high")),
            "low": self._to_float(tick.get("low")),
            "close": close,
            "change": change_abs,
            "change_percent": change_percent,
            "volume": self._to_float(tick.get("ttq") if "ttq" in tick else tick.get("volume")),
            "oi": self._to_float(tick.get("oi")),
            "bid_price": self._to_float(tick.get("bPrice")),
            "bid_qty": self._to_float(tick.get("bQty")),
            "ask_price": self._to_float(tick.get("sPrice")),
            "ask_qty": self._to_float(tick.get("sQty")),
            "total_buy_qty": self._to_float(tick.get("totalBuyQt")),
            "total_sell_qty": self._to_float(tick.get("totalSellQ")),
            "ts": self._utc_now(),
        }

    def _write_redis(self, tick: dict[str, Any]) -> None:
        if not self._redis_url:
            return
        key = f"md:tick:{tick['exchange_code']}:{tick['token']}" if tick["token"] else f"md:tick:{tick['symbol']}"
        try:
            client = self._redis_client()
            client.set(key, json.dumps(tick), ex=self._tick_ttl_seconds)
        except Exception as exc:  # noqa: BLE001 — Redis is a best-effort cache
            now = self._utc_now()
            with self._lock:
                self._redis_write_error_count += 1
                self._last_redis_write_error_at = now
            logger.warning(
                "redis write failed sym=%s broker=%s ex=%s token=%s key=%s: %s %s",
                tick.get("symbol", "?"),
                tick.get("broker_symbol", "?"),
                tick.get("exchange_code", "?"),
                tick.get("token", "?"),
                key,
                type(exc).__name__,
                exc,
            )
            # Reset cached client and retry once — handles stale connections
            with self._lock:
                self._redis = None
                self._redis_write_retry_count += 1
            try:
                client = self._redis_client()
                client.set(key, json.dumps(tick), ex=self._tick_ttl_seconds)
            except Exception as retry_exc:  # noqa: BLE001
                with self._lock:
                    self._redis_write_error_count += 1
                    self._last_redis_write_error_at = self._utc_now()
                logger.warning(
                    "redis write retry also failed sym=%s key=%s: %s %s",
                    tick.get("symbol", "?"),
                    key,
                    type(retry_exc).__name__,
                    retry_exc,
                )

    def _redis_client(self) -> Any:
        if self._redis is None:
            self._redis = create_redis_client(self._redis_url)  # type: ignore[arg-type]
        return self._redis

    def _emit(self, tick: dict[str, Any]) -> None:
        with self._lock:
            publish = self._publish
        if publish is None:
            return
        try:
            publish("tick", tick)
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._emit_error_count += 1
                self._last_emit_error_at = self._utc_now()
            logger.warning(
                "emit failed event=tick sym=%s ex=%s token=%s: %s %s",
                tick.get("symbol", "?"),
                tick.get("exchange_code", "?"),
                tick.get("token", "?"),
                type(exc).__name__,
                exc,
            )

    # ----- status --------------------------------------------------------

    def _set_state(self, state: str, *, error: str | None) -> None:
        with self._lock:
            old = self._state
            self._state = state
            self._error = error
        if state != old:
            logger.info("market-data worker state %s -> %s (error=%s)", old, state, error)
        with self._lock:
            publish = self._publish
        if publish is not None:
            try:
                publish("status", self.status())
            except Exception:  # noqa: BLE001
                pass

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "configured": self.is_configured(),
                "subscriptions": len(self._subscriptions),
                "symbols": sorted({sub.display_symbol for sub in self._subscriptions.values()}),
                "last_tick_at": self._last_tick_at,
                "first_tick_at": self._first_tick_at,
                "tick_count_total": self._tick_count_total,
                "per_symbol_tick_counts": dict(self._per_symbol_tick_counts),
                "subscribe_requests_total": self._subscribe_requests_total,
                "subscribe_attempt_count": self._subscribe_attempt_count,
                "subscribe_error_count": self._subscribe_error_count,
                "redis_write_error_count": self._redis_write_error_count,
                "redis_write_retry_count": self._redis_write_retry_count,
                "last_redis_write_error_at": self._last_redis_write_error_at,
                "emit_error_count": self._emit_error_count,
                "last_emit_error_at": self._last_emit_error_at,
                "ticks_received_ever": self._ticks_received_ever,
                "freshness": self._freshness(),
                "error": self._error,
            }

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._last_ticks.values())

    # ----- helpers -------------------------------------------------------

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None
