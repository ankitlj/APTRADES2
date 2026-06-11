import logging
import time

from app import create_app
from app.db import create_session_factory, ensure_tables
from app.models import MarketCandle
from app.services.market_data_worker import MarketDataWorker
from app.services.tick_recorder import TickRecorder


def _tick(symbol: str, ltp: float, **extra) -> dict:
    base = {
        "symbol": symbol,
        "exchange_code": "NFO",
        "token": "62329",
        "ltp": ltp,
        "volume": 100.0,
        "oi": 4763100.0,
    }
    base.update(extra)
    return base


# ----- tick recorder ---------------------------------------------------------


def test_recorder_aggregates_minute_ohlc(tmp_path):
    url = f"sqlite:///{tmp_path / 'candles.sqlite'}"
    ensure_tables(url)
    recorder = TickRecorder(url)

    recorder.record(_tick("NIFTY", 100.0))
    recorder.record(_tick("NIFTY", 105.0))
    recorder.record(_tick("NIFTY", 98.0))
    recorder.record(_tick("NIFTY", 102.0))

    assert recorder.flush() == 1

    session_factory = create_session_factory(url)
    with session_factory() as session:
        candle = session.query(MarketCandle).filter_by(symbol="NIFTY").one()

    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 98.0
    assert candle.close == 102.0
    assert candle.tick_count == 4
    assert candle.oi == 4763100.0


def test_recorder_is_disabled_without_database_url():
    recorder = TickRecorder(None)
    recorder.record(_tick("NIFTY", 100.0))
    assert recorder.enabled is False
    assert recorder.flush() == 0


def test_recorder_skips_ticks_without_ltp(tmp_path):
    url = f"sqlite:///{tmp_path / 'candles.sqlite'}"
    recorder = TickRecorder(url)
    recorder.record(_tick("NIFTY", None))
    assert recorder.flush() == 0


# ----- gap logger ------------------------------------------------------------


def test_log_gap_warns_past_threshold(caplog):
    worker = MarketDataWorker(app_key=None, secret_key=None, session_token=None, gap_log_seconds=5.0)
    worker._last_tick_monotonic = time.monotonic() - 10
    with caplog.at_level(logging.WARNING):
        worker._log_gap()
    assert any("stream gap" in record.getMessage() for record in caplog.records)


def test_log_gap_silent_within_threshold(caplog):
    worker = MarketDataWorker(app_key=None, secret_key=None, session_token=None, gap_log_seconds=5.0)
    worker._last_tick_monotonic = time.monotonic()
    with caplog.at_level(logging.WARNING):
        worker._log_gap()
    assert not any("stream gap" in record.getMessage() for record in caplog.records)


# ----- history endpoint ------------------------------------------------------


def test_history_endpoint_returns_recorded_candles(tmp_path):
    url = f"sqlite:///{tmp_path / 'history.sqlite'}"
    ensure_tables(url)
    recorder = TickRecorder(url)
    recorder.record(_tick("NIFTY", 100.0))
    recorder.record(_tick("NIFTY", 110.0))
    recorder.flush()

    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=url)

    with app.test_client() as client:
        response = client.get("/api/market-data/history?symbol=NIFTY&limit=10")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["symbol"] == "NIFTY"
    assert len(payload["candles"]) == 1
    assert payload["candles"][0]["high"] == 110.0


def test_history_endpoint_requires_symbol():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        response = client.get("/api/market-data/history")
    assert response.status_code == 400


def test_history_endpoint_empty_without_database(tmp_path):
    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=None)
    with app.test_client() as client:
        response = client.get("/api/market-data/history?symbol=NIFTY")
    assert response.status_code == 200
    assert response.get_json()["candles"] == []
