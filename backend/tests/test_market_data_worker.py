import time
from unittest.mock import patch

from app.services.market_data_worker import (
    STATE_OFFLINE,
    MarketDataWorker,
    _is_numeric_token,
    build_stock_token,
)


class FakeBreeze:
    def __init__(self) -> None:
        self.on_ticks = None
        self.connected = False
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []
        self.subscribe_kwargs: list[dict] = []
        self.unsubscribe_kwargs: list[dict] = []

    def ws_connect(self) -> None:
        self.connected = True

    def ws_disconnect(self) -> None:
        self.connected = False

    def _call_key(self, stock_token=None, **_kwargs) -> str | None:
        """Return the canonical key for this subscribe/unsubscribe call."""
        if stock_token is not None:
            return str(stock_token)
        if _kwargs.get("exchange_code") and _kwargs.get("stock_code"):
            return f"{_kwargs['exchange_code']}:{_kwargs['stock_code']}:{_kwargs.get('product_type','?')}"
        return None

    def subscribe_feeds(self, stock_token=None, **_kwargs) -> None:
        self.subscribed.append(self._call_key(stock_token, **_kwargs))
        self.subscribe_kwargs.append({"stock_token": stock_token, **_kwargs})

    def unsubscribe_feeds(self, stock_token=None, **_kwargs) -> None:
        self.unsubscribed.append(self._call_key(stock_token, **_kwargs))
        self.unsubscribe_kwargs.append({"stock_token": stock_token, **_kwargs})


class FakeRedis:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, int]] = []

    def set(self, key, value, ex=None) -> None:
        self.calls.append((key, value, ex))


def _configured_worker(**kwargs) -> MarketDataWorker:
    return MarketDataWorker(
        app_key="key",
        secret_key="secret",
        session_token="token",
        **kwargs,
    )


def test_build_stock_token_maps_exchanges() -> None:
    assert build_stock_token("NSE", "2885") == "4.1!2885"
    assert build_stock_token("NFO", "62329") == "4.1!62329"
    assert build_stock_token("BSE", "500780") == "1.1!500780"
    assert build_stock_token("BFO", "999") == "8.1!999"


def test_build_stock_token_rejects_unknown_exchange_or_missing_token() -> None:
    assert build_stock_token("MCX", "123") is None
    assert build_stock_token("NSE", "") is None
    assert build_stock_token("", "123") is None


def test_build_stock_token_rejects_non_numeric_token() -> None:
    """A non-numeric token must not produce a stock_token for Breeze websocket."""
    assert build_stock_token("NSE", "NIFTY 50") is None
    assert build_stock_token("NFO", "BANK NIFTY") is None
    assert build_stock_token("NSE", "RELIND") is None
    assert build_stock_token("NFO", "4.1!62329") is None  # already-formatted is not digits-only


def test_numeric_token_guard_rejects_expected_inputs() -> None:
    assert _is_numeric_token("NIFTY 50") is False
    assert _is_numeric_token("BANK NIFTY") is False
    assert _is_numeric_token("RELIND") is False
    assert _is_numeric_token("") is False
    assert _is_numeric_token(None) is False
    assert _is_numeric_token("4.1!62329") is False


def test_numeric_token_guard_accepts_valid_inputs() -> None:
    assert _is_numeric_token("2885") is True
    assert _is_numeric_token("62329") is True
    assert _is_numeric_token("0") is True
    assert _is_numeric_token("999999") is True


def test_not_configured_worker_stays_offline() -> None:
    worker = MarketDataWorker(app_key=None, secret_key=None, session_token=None)
    assert worker.is_configured() is False

    worker.ensure_started()

    status = worker.status()
    assert status["state"] == STATE_OFFLINE
    assert status["configured"] is False
    assert status["subscriptions"] == 0


def test_subscribe_registers_and_calls_breeze() -> None:
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()  # establish the fake live connection without the supervisor thread

    result = worker.subscribe(
        [
            {
                "display_symbol": "NIFTY",
                "broker_symbol": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "token": "62329",
            }
        ]
    )

    assert result["count"] == 1
    assert "NFO:NIFTY:futures" in breeze.subscribed
    status = worker.status()
    assert status["subscriptions"] == 1
    assert status["symbols"] == ["NIFTY"]


def test_subscribe_skips_rows_without_token() -> None:
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()

    result = worker.subscribe([{"display_symbol": "NIFTY", "exchange_code": "NFO", "token": ""}])

    assert result["accepted"] == []
    assert result["skipped"][0]["symbol"] == "NIFTY"
    assert breeze.subscribed == []


def test_subscribe_skips_non_numeric_token() -> None:
    """A subscription request with a non-numeric token must be skipped."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()

    result = worker.subscribe(
        [
            {
                "display_symbol": "NIFTY",
                "broker_symbol": "NIFTY",
                "exchange_code": "NSE",
                "product_type": "cash",
                "token": "NIFTY 50",
            }
        ]
    )

    assert result["accepted"] == []
    assert len(result["skipped"]) == 1
    assert result["skipped"][0]["symbol"] == "NIFTY"
    assert breeze.subscribed == [], "Non-numeric token must not reach Breeze"


def test_subscribe_non_numeric_token_does_not_crash() -> None:
    """Rejecting a non-numeric token must not raise."""
    worker = _configured_worker()
    result = worker.subscribe(
        [
            {
                "display_symbol": "BANKNIFTY",
                "broker_symbol": "CNXBAN",
                "exchange_code": "NSE",
                "product_type": "cash",
                "token": "BANK NIFTY",
            }
        ]
    )
    assert result["accepted"] == []
    assert len(result["skipped"]) == 1


def test_subscribe_numeric_token_still_works_after_non_numeric_skipped() -> None:
    """A numeric token in the same batch as a non-numeric token must still be
    subscribed successfully."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()

    result = worker.subscribe(
        [
            {
                "display_symbol": "BANKNIFTY",
                "broker_symbol": "CNXBAN",
                "exchange_code": "NSE",
                "product_type": "cash",
                "token": "BANK NIFTY",
            },
            {
                "display_symbol": "NIFTY",
                "broker_symbol": "NIFTY",
                "exchange_code": "NSE",
                "product_type": "cash",
                "token": "2885",
            },
        ]
    )

    assert len(result["accepted"]) == 1
    assert len(result["skipped"]) == 1
    assert "4.1!2885" in breeze.subscribed
    assert "4.1!BANK NIFTY" not in breeze.subscribed


def test_on_ticks_normalizes_maps_symbol_and_publishes() -> None:
    published: list[tuple[str, dict]] = []
    breeze = FakeBreeze()
    worker = _configured_worker(
        breeze_factory=lambda: breeze,
        publish=lambda event, payload: published.append((event, payload)),
    )
    worker._connect()
    worker.subscribe(
        [
            {
                "display_symbol": "NIFTY",
                "broker_symbol": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "token": "62329",
            }
        ]
    )

    worker._on_ticks(
        {
            "symbol": "4.1!62329",
            "last": "23440.0",
            "close": "23451.7",
            "change": "-0.05",
            "ttq": "100",
            "oi": "4763100",
        }
    )

    tick_events = [payload for event, payload in published if event == "tick"]
    assert tick_events, "expected a tick to be published"
    tick = tick_events[-1]
    assert tick["symbol"] == "NIFTY"
    assert tick["broker_symbol"] == "NIFTY"
    assert tick["exchange_code"] == "NFO"
    assert tick["token"] == "62329"
    assert tick["ltp"] == 23440.0
    assert tick["close"] == 23451.7
    assert tick["change"] == -11.7
    assert tick["change_percent"] == -0.05
    assert tick["volume"] == 100.0
    assert tick["oi"] == 4763100.0

    snapshot = worker.snapshot()
    assert snapshot[0]["symbol"] == "NIFTY"
    assert worker.status()["last_tick_at"] is not None


def test_on_ticks_without_subscription_falls_back_to_stock_code() -> None:
    published: list[tuple[str, dict]] = []
    worker = _configured_worker(publish=lambda event, payload: published.append((event, payload)))

    worker._on_ticks({"symbol": "4.1!2885", "stock_code": "RELIND", "last": "1209.05", "close": "1234.85"})

    tick = [payload for event, payload in published if event == "tick"][-1]
    assert tick["symbol"] == "RELIND"
    assert tick["ltp"] == 1209.05
    assert tick["change"] == -25.8


def test_unsubscribe_removes_subscription() -> None:
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item = {
        "display_symbol": "BANKNIFTY",
        "broker_symbol": "CNXBAN",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62326",
    }
    worker.subscribe([item])

    result = worker.unsubscribe([item])

    assert "4.1!62326" in result["removed"]
    assert result["count"] == 0
    assert "NFO:CNXBAN:futures" in breeze.unsubscribed


def test_on_ticks_writes_to_redis_when_configured() -> None:
    fake_redis = FakeRedis()
    with patch("app.services.market_data_worker.create_redis_client", return_value=fake_redis):
        worker = _configured_worker(redis_url="redis://localhost:6379/0")
        worker.subscribe(
            [
                {
                    "display_symbol": "NIFTY",
                    "broker_symbol": "NIFTY",
                    "exchange_code": "NFO",
                    "product_type": "futures",
                    "token": "62329",
                }
            ]
        )

        worker._on_ticks({"symbol": "4.1!62329", "last": "23440.0", "close": "23451.7"})

    assert fake_redis.calls, "expected a redis write"
    key, _value, ttl = fake_redis.calls[-1]
    assert key == "md:tick:NFO:62329"
    assert ttl == 60


def test_on_ticks_survives_redis_write_failure() -> None:
    """_on_ticks must not crash when Redis write fails, and the in-memory
    snapshot path must still work."""
    published: list[tuple[str, dict]] = []
    worker = _configured_worker(
        redis_url="redis://localhost:6379/0",
        publish=lambda event, payload: published.append((event, payload)),
    )
    worker.subscribe([{"display_symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "product_type": "futures", "token": "62329"}])

    with patch("app.services.market_data_worker.MarketDataWorker._redis_client") as mock_client:
        mock_client.side_effect = RuntimeError("connection refused")
        worker._on_ticks({"symbol": "4.1!62329", "last": "23440.0", "close": "23451.7"})

    # In-memory snapshot must still be written despite Redis failure
    snapshot = worker.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["symbol"] == "NIFTY"
    assert snapshot[0]["ltp"] == 23440.0
    # Publish must still fire despite Redis failure
    assert any(event == "tick" for event, _ in published)


def test_set_publish_can_be_attached_later() -> None:
    published: list[tuple[str, dict]] = []
    worker = _configured_worker()
    worker.set_publish(lambda event, payload: published.append((event, payload)))

    worker._on_ticks({"symbol": "4.1!2885", "stock_code": "RELIND", "last": "1209.05", "close": "1234.85"})

    assert any(event == "tick" for event, _ in published)


def test_redis_write_retries_with_fresh_client() -> None:
    """On first Redis failure, cached client is reset and a fresh client is
    created for the retry. The second attempt succeeds."""
    class FirstFailRedis:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, int]] = []
            self._attempt = 0

        def set(self, key, value, ex=None) -> None:
            self._attempt += 1
            if self._attempt == 1:
                raise ConnectionError("first attempt fails")
            self.calls.append((key, value, ex))

    fake = FirstFailRedis()
    worker = _configured_worker(redis_url="redis://localhost:6379/0")
    worker.subscribe([{"display_symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "product_type": "futures", "token": "62329"}])

    with patch("app.services.market_data_worker.create_redis_client", return_value=fake):
        worker._on_ticks({"symbol": "4.1!62329", "last": "23440.0", "close": "23451.7"})

    assert len(fake.calls) == 1, "expected retry to succeed"
    assert fake.calls[0][0] == "md:tick:NFO:62329"
    # After retry succeeds, snapshot must still work
    assert len(worker.snapshot()) == 1


def test_redis_write_retry_does_not_crash_on_second_failure() -> None:
    """Both Redis attempts fail — worker must not crash and must still
    update the in-memory snapshot."""
    worker = _configured_worker(redis_url="redis://localhost:6379/0")
    worker.subscribe([{"display_symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "product_type": "futures", "token": "62329"}])

    with patch("app.services.market_data_worker.create_redis_client") as mock_factory:
        mock_factory.return_value.set.side_effect = RuntimeError("persistent failure")
        worker._on_ticks({"symbol": "4.1!62329", "last": "23440.0", "close": "23451.7"})

    # create_redis_client must have been called twice (original + retry)
    assert mock_factory.call_count == 2
    # In-memory snapshot must still be written
    snapshot = worker.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["symbol"] == "NIFTY"


def test_on_ticks_survives_emit_failure() -> None:
    """_on_ticks must not crash when the publish callback raises, and the
    in-memory snapshot path must still work."""
    def failing_publish(event: str, payload: dict) -> None:
        raise RuntimeError("emit failed")

    worker = _configured_worker(publish=failing_publish)
    worker.subscribe([{"display_symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "product_type": "futures", "token": "62329"}])

    worker._on_ticks({"symbol": "4.1!62329", "last": "23440.0", "close": "23451.7"})

    # In-memory snapshot must still be written despite emit failure
    snapshot = worker.snapshot()
    assert len(snapshot) == 1
    assert snapshot[0]["symbol"] == "NIFTY"
    assert snapshot[0]["ltp"] == 23440.0


def test_status_exposes_error_counters() -> None:
    """Status payload must include the five error-counter fields with correct
    initial values, and they must update after failures."""
    worker = _configured_worker(redis_url="redis://localhost:6379/0")
    worker.subscribe([{"display_symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "product_type": "futures", "token": "62329"}])

    status = worker.status()
    assert status["redis_write_error_count"] == 0
    assert status["redis_write_retry_count"] == 0
    assert status["last_redis_write_error_at"] is None
    assert status["emit_error_count"] == 0
    assert status["last_emit_error_at"] is None

    # Trigger a Redis failure and verify counters update
    with patch("app.services.market_data_worker.create_redis_client") as mock_factory:
        mock_factory.return_value.set.side_effect = RuntimeError("fail")
        worker._on_ticks({"symbol": "4.1!62329", "last": "23440.0", "close": "23451.7"})

    status = worker.status()
    assert status["redis_write_error_count"] == 2  # initial + retry
    assert status["redis_write_retry_count"] == 1
    assert status["last_redis_write_error_at"] is not None


def test_status_exposes_emit_error_counters() -> None:
    """Emit error counters must update after a publish failure."""
    def failing_publish(event: str, payload: dict) -> None:
        raise RuntimeError("emit failed")

    worker = _configured_worker(publish=failing_publish)
    worker.subscribe([{"display_symbol": "NIFTY", "broker_symbol": "NIFTY", "exchange_code": "NFO", "product_type": "futures", "token": "62329"}])

    assert worker.status()["emit_error_count"] == 0
    assert worker.status()["last_emit_error_at"] is None

    worker._on_ticks({"symbol": "4.1!62329", "last": "23440.0", "close": "23451.7"})

    status = worker.status()
    assert status["emit_error_count"] == 1
    assert status["last_emit_error_at"] is not None


def test_subscribe_same_token_twice_increments_ref_count(tmp_path) -> None:
    """Two subscribe calls for the same token: Breeze subscribe called once,
    ref count increments."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item = {
        "display_symbol": "NIFTY",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62329",
    }
    r1 = worker.subscribe([item])
    r2 = worker.subscribe([item])

    assert r1["count"] == 1
    assert r2["count"] == 1
    # Breeze subscribe should have been called exactly once
    assert breeze.subscribed.count("NFO:NIFTY:futures") == 1
    assert len(breeze.subscribed) == 1
    # Ref count should be 2 (two callers)
    assert worker._subscription_ref_counts.get("4.1!62329") == 2


def test_unsubscribe_while_another_keeps_token(tmp_path) -> None:
    """One unsubscribe while another subscriber still exists:
    Breeze unsubscribe NOT called, token remains active."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item = {
        "display_symbol": "NIFTY",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62329",
    }
    worker.subscribe([item])  # caller 1: ref=1
    worker.subscribe([item])  # caller 2: ref=2

    result = worker.unsubscribe([item])  # caller 2 leaves: ref=1

    assert "4.1!62329" in result["removed"]
    assert result["count"] == 1  # token still active
    # Breeze unsubscribe should NOT have been called
    assert "NFO:NIFTY:futures" not in breeze.unsubscribed
    assert worker._subscription_ref_counts.get("4.1!62329") == 1
    # Token still in subscriptions dict
    assert "4.1!62329" in worker._subscriptions


def test_last_unsubscribe_tears_down_token(tmp_path) -> None:
    """Final unsubscribe: Breeze unsubscribe called once, token removed."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item = {
        "display_symbol": "NIFTY",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62329",
    }
    worker.subscribe([item])  # caller 1: ref=1
    worker.subscribe([item])  # caller 2: ref=2

    # Both callers unsubscribe
    worker.unsubscribe([item])  # caller 2: ref=1
    result = worker.unsubscribe([item])  # caller 1: ref=0

    assert "4.1!62329" in result["removed"]
    assert result["count"] == 0  # token removed
    # Breeze unsubscribe should have been called exactly once
    assert breeze.unsubscribed.count("NFO:NIFTY:futures") == 1
    assert "4.1!62329" not in worker._subscriptions
    assert worker._subscription_ref_counts.get("4.1!62329") is None


def test_mixed_unrelated_tokens_unaffected_by_ref_count(tmp_path) -> None:
    """Unrelated token subscriptions must not be affected by ref-counting
    of a different token."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item_nifty = {
        "display_symbol": "NIFTY",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62329",
    }
    item_banknifty = {
        "display_symbol": "BANKNIFTY",
        "broker_symbol": "CNXBAN",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62326",
    }
    # Both tokens subscribed once each
    worker.subscribe([item_nifty])
    worker.subscribe([item_banknifty])

    assert worker._subscription_ref_counts.get("4.1!62329") == 1
    assert worker._subscription_ref_counts.get("4.1!62326") == 1

    # Unsubscribe banknifty — nifty must remain
    result = worker.unsubscribe([item_banknifty])

    assert "4.1!62326" in result["removed"]
    assert result["count"] == 1  # only nifty left
    assert "NFO:CNXBAN:futures" in breeze.unsubscribed
    assert "NFO:NIFTY:futures" not in breeze.unsubscribed
    assert "4.1!62329" in worker._subscriptions
    assert worker._subscription_ref_counts.get("4.1!62329") == 1


def test_subscribe_same_token_many_then_all_unsubscribe(tmp_path) -> None:
    """Three subscribers for the same token: only last unsubscribe tears down."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item = {
        "display_symbol": "NIFTY",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62329",
    }
    # Three callers subscribe
    worker.subscribe([item])  # ref=1
    worker.subscribe([item])  # ref=2
    worker.subscribe([item])  # ref=3

    assert worker._subscription_ref_counts.get("4.1!62329") == 3
    assert breeze.subscribed.count("NFO:NIFTY:futures") == 1  # only once

    # Two leave
    worker.unsubscribe([item])  # ref=2
    worker.unsubscribe([item])  # ref=1

    assert "NFO:NIFTY:futures" not in breeze.unsubscribed  # still one subscriber
    assert "4.1!62329" in worker._subscriptions

    # Last leaves
    result = worker.unsubscribe([item])  # ref=0

    assert "4.1!62329" in result["removed"]
    assert result["count"] == 0
    assert breeze.unsubscribed.count("NFO:NIFTY:futures") == 1
    assert "4.1!62329" not in worker._subscriptions


def test_subscribe_with_empty_items_still_increments_counter() -> None:
    """Calling subscribe([]) must increment the diagnostic counter even
    though no subscriptions are created. This validates that the
    'subscribe_requests_total > 0' observation can coexist with
    'subscriptions = 0'."""
    worker = _configured_worker()
    before = worker.status()["subscribe_requests_total"]

    result = worker.subscribe([])

    assert result["accepted"] == []
    assert result["count"] == 0
    assert worker.status()["subscribe_requests_total"] == before + 1
    assert worker.status()["subscriptions"] == 0


def test_subscribe_all_skipped_still_increments_counter() -> None:
    """Calling subscribe() where every item is rejected by _to_subscription
    must increment the diagnostic counter but leave subscriptions unchanged."""
    worker = _configured_worker()
    before = worker.status()["subscribe_requests_total"]

    result = worker.subscribe([
        {"display_symbol": "NIFTY", "exchange_code": "NFO", "token": ""},
        {"display_symbol": "BANKNIFTY", "exchange_code": "NFO", "token": "NOT_A_NUMBER"},
    ])

    assert len(result["accepted"]) == 0
    assert len(result["skipped"]) == 2
    assert result["count"] == 0
    assert worker.status()["subscribe_requests_total"] == before + 1
    assert worker.status()["subscriptions"] == 0


def test_resolve_subscription_items_requires_database_for_symbol_lookup() -> None:
    """When DATABASE_URL is not configured, unresolved symbols still cannot be
    looked up through SymbolResolver."""
    from app.realtime import resolve_subscription_items

    result = resolve_subscription_items(None, [{"symbol": "NIFTY", "exchange": "NSE"}])

    assert result == []


def test_resolve_subscription_items_keeps_pre_resolved_token_without_database_url() -> None:
    """Pre-resolved option/orderbook tokens must not be blocked by DB access."""
    from app.realtime import resolve_subscription_items

    result = resolve_subscription_items(
        None,
        [{
            "symbol": "NIFTY|24000|CE",
            "broker_symbol": "NIFTY",
            "exchange": "NFO",
            "product_type": "options",
            "token": "12345",
            "expiry_date": "2026-06-30",
            "strike_price": "24000",
            "right": "call",
        }],
    )

    assert result == [{
        "display_symbol": "NIFTY|24000|CE",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "options",
        "token": "12345",
        "expiry_date": "2026-06-30",
        "strike_price": "24000",
        "right": "call",
    }]


def test_subscribe_then_unsubscribe_cycle_leaves_subscriptions_zero() -> None:
    """Full subscribe → unsubscribe cycle must leave subscriptions=0 even
    when the worker is connected and items are valid."""
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item = {
        "display_symbol": "NIFTY",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "futures",
        "token": "62329",
    }

    sub_result = worker.subscribe([item])
    assert sub_result["count"] == 1

    unsub_result = worker.unsubscribe([item])
    assert unsub_result["count"] == 0

    status = worker.status()
    assert status["subscriptions"] == 0
    assert status["subscribe_requests_total"] == 1


def test_subscribe_preserves_requests_total_across_multiple_calls() -> None:
    """The subscribe_requests_total counter must accumulate across multiple
    subscribe calls, even when items are empty or skipped."""
    worker = _configured_worker()

    worker.subscribe([])                          # empty
    worker.subscribe([{"display_symbol": "NIFTY", "exchange_code": "NFO", "token": ""}])  # skipped
    worker.subscribe([])                          # empty again

    assert worker.status()["subscribe_requests_total"] == 3
    assert worker.status()["subscriptions"] == 0


def test_option_subscription_uses_breeze_contract_params() -> None:
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()

    result = worker.subscribe(
        [
            {
                "display_symbol": "NIFTY|24000|CE",
                "broker_symbol": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "options",
                "token": "51219",
                "expiry_date": "2026-06-30",
                "strike_price": "24000",
                "right": "ce",
            }
        ]
    )

    assert result["count"] == 1
    assert result["accepted"] == ["4.1!51219"]
    payload = breeze.subscribe_kwargs[-1]
    assert payload["stock_token"] is None
    assert payload["exchange_code"] == "NFO"
    assert payload["stock_code"] == "NIFTY"
    assert payload["expiry_date"] == "30-Jun-2026"
    assert payload["strike_price"] == "24000"
    assert payload["right"] == "call"
    assert payload["product_type"] == "options"
    assert payload["get_market_depth"] is False
    assert payload["get_exchange_quotes"] is True


def test_option_unsubscription_uses_breeze_contract_params() -> None:
    breeze = FakeBreeze()
    worker = _configured_worker(breeze_factory=lambda: breeze)
    worker._connect()
    item = {
        "display_symbol": "NIFTY|24000|PE",
        "broker_symbol": "NIFTY",
        "exchange_code": "NFO",
        "product_type": "options",
        "token": "51220",
        "expiry_date": "2026-06-30",
        "strike_price": "24000",
        "right": "pe",
    }

    worker.subscribe([item])
    result = worker.unsubscribe([item])

    assert result["removed"] == ["4.1!51220"]
    payload = breeze.unsubscribe_kwargs[-1]
    assert payload["stock_token"] is None
    assert payload["exchange_code"] == "NFO"
    assert payload["stock_code"] == "NIFTY"
    assert payload["expiry_date"] == "30-Jun-2026"
    assert payload["strike_price"] == "24000"
    assert payload["right"] == "put"
    assert payload["product_type"] == "options"


def test_stale_stream_reason_requires_active_subscription() -> None:
    worker = _configured_worker(stale_reconnect_seconds=0.0)
    worker._last_connect_monotonic = 1.0

    assert worker._stale_stream_reason() is None


def test_stale_stream_reason_detects_silent_connected_stream() -> None:
    breeze = FakeBreeze()
    worker = _configured_worker(
        breeze_factory=lambda: breeze,
        stale_reconnect_seconds=10.0,
    )
    worker._connect()
    worker.subscribe(
        [
            {
                "display_symbol": "NIFTY",
                "broker_symbol": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "token": "62329",
            }
        ]
    )
    worker._last_connect_monotonic = 1.0
    worker._last_tick_monotonic = None

    reason = worker._stale_stream_reason()

    assert reason is not None
    assert "no market-data ticks" in reason
    assert "subscriptions=1" in reason


def test_stale_stream_reason_uses_recent_tick_activity() -> None:
    breeze = FakeBreeze()
    worker = _configured_worker(
        breeze_factory=lambda: breeze,
        stale_reconnect_seconds=60.0,
    )
    worker._connect()
    worker.subscribe(
        [
            {
                "display_symbol": "NIFTY",
                "broker_symbol": "NIFTY",
                "exchange_code": "NFO",
                "product_type": "futures",
                "token": "62329",
            }
        ]
    )
    worker._last_connect_monotonic = 1.0
    worker._last_tick_monotonic = time.monotonic()

    assert worker._stale_stream_reason() is None


def test_status_exposes_stale_reconnect_diagnostics() -> None:
    worker = _configured_worker(stale_reconnect_seconds=75.0)

    status = worker.status()

    assert status["stale_reconnect_count"] == 0
    assert status["last_stale_reconnect_at"] is None
    assert status["stale_reconnect_seconds"] == 75.0
