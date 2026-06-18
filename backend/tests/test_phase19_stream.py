import logging
import time

from app import create_app
from app.services.market_data_worker import MarketDataWorker


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
