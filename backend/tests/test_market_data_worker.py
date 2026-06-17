from unittest.mock import patch

from app.services.market_data_worker import (
    STATE_OFFLINE,
    MarketDataWorker,
    build_stock_token,
)


class FakeBreeze:
    def __init__(self) -> None:
        self.on_ticks = None
        self.connected = False
        self.subscribed: list[str] = []
        self.unsubscribed: list[str] = []

    def ws_connect(self) -> None:
        self.connected = True

    def ws_disconnect(self) -> None:
        self.connected = False

    def subscribe_feeds(self, stock_token=None, **_kwargs) -> None:
        self.subscribed.append(stock_token)

    def unsubscribe_feeds(self, stock_token=None, **_kwargs) -> None:
        self.unsubscribed.append(stock_token)


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
    assert "4.1!62329" in breeze.subscribed
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
    assert "4.1!62326" in breeze.unsubscribed


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
