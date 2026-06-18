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


def test_cleanup_candles_deletes_all_rows(tmp_path):
    from app.db import create_session_factory, ensure_tables
    from app.models import MarketCandle
    from datetime import datetime, timezone

    url = f"sqlite:///{tmp_path / 'candles.sqlite'}"
    ensure_tables(url)
    session_factory = create_session_factory(url)
    with session_factory() as session:
        session.add(MarketCandle(
            symbol="NIFTY",
            minute_start=datetime.now(timezone.utc),
            open=100.0, high=105.0, low=99.0, close=102.0,
            tick_count=10,
        ))
        session.commit()
        assert session.query(MarketCandle).count() == 1

    app = create_app()
    app.config.update(TESTING=True, DATABASE_URL=url)
    runner = app.test_cli_runner()
    result = runner.invoke(args=["market-data", "cleanup-candles"])
    assert result.exit_code == 0
    assert "Deleted 1 rows" in result.output

    with session_factory() as session:
        assert session.query(MarketCandle).count() == 0
