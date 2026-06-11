from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from ..db import create_session_factory
from ..models import MarketCandle


def _minute_floor(moment: datetime) -> datetime:
    return moment.replace(second=0, microsecond=0)


class TickRecorder:
    """Phase 19: aggregate streamed ticks into 1-minute OHLC+volume+OI candles
    and persist them in batches.

    Kept off the tick hot path: ``record`` only mutates an in-memory dict under a
    lock; ``flush`` (called periodically from a background thread) writes the
    accumulated candles to the DB and prunes minutes that have closed. Reuses the
    Phase 18 cached engine. Degraded-safe: a missing DATABASE_URL disables it."""

    def __init__(self, database_url: str | None):
        self.database_url = database_url
        self._lock = threading.Lock()
        # (symbol, minute_start) -> accumulator dict
        self._candles: dict[tuple[str, datetime], dict[str, Any]] = {}

    @property
    def enabled(self) -> bool:
        return bool(self.database_url)

    def record(self, tick: dict[str, Any]) -> None:
        if not self.enabled:
            return
        symbol = tick.get("symbol")
        ltp = tick.get("ltp")
        if not symbol or ltp is None:
            return

        minute = _minute_floor(datetime.now(timezone.utc))
        key = (symbol, minute)
        with self._lock:
            candle = self._candles.get(key)
            if candle is None:
                self._candles[key] = {
                    "exchange_code": tick.get("exchange_code"),
                    "token": tick.get("token"),
                    "open": ltp,
                    "high": ltp,
                    "low": ltp,
                    "close": ltp,
                    "volume": tick.get("volume"),
                    "oi": tick.get("oi"),
                    "tick_count": 1,
                }
            else:
                candle["high"] = max(candle["high"], ltp)
                candle["low"] = min(candle["low"], ltp)
                candle["close"] = ltp
                candle["tick_count"] += 1
                if tick.get("volume") is not None:
                    candle["volume"] = tick.get("volume")
                if tick.get("oi") is not None:
                    candle["oi"] = tick.get("oi")

    def flush(self) -> int:
        """Upsert accumulated candles to the DB; prune closed minutes. Returns the
        number of candles written. Best-effort: swallows DB errors so a transient
        outage never kills the worker."""
        if not self.enabled:
            return 0
        with self._lock:
            snapshot = {key: dict(value) for key, value in self._candles.items()}
        if not snapshot:
            return 0

        try:
            session_factory = create_session_factory(self.database_url)
            with session_factory() as session:
                for (symbol, minute), candle in snapshot.items():
                    existing = session.scalar(
                        select(MarketCandle).where(
                            MarketCandle.symbol == symbol,
                            MarketCandle.minute_start == minute,
                        )
                    )
                    if existing is None:
                        session.add(
                            MarketCandle(
                                symbol=symbol,
                                exchange_code=candle["exchange_code"],
                                token=candle["token"],
                                minute_start=minute,
                                open=candle["open"],
                                high=candle["high"],
                                low=candle["low"],
                                close=candle["close"],
                                volume=candle["volume"],
                                oi=candle["oi"],
                                tick_count=candle["tick_count"],
                            )
                        )
                    else:
                        existing.high = candle["high"]
                        existing.low = candle["low"]
                        existing.close = candle["close"]
                        existing.volume = candle["volume"]
                        existing.oi = candle["oi"]
                        existing.tick_count = candle["tick_count"]
                session.commit()
        except Exception:  # noqa: BLE001 — recording is best-effort
            return 0

        # Drop minutes that have closed; keep the current (still-filling) minute.
        current_minute = _minute_floor(datetime.now(timezone.utc))
        with self._lock:
            for key in list(self._candles.keys()):
                if key[1] < current_minute:
                    del self._candles[key]
        return len(snapshot)
