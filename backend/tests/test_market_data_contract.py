def test_market_data_status_endpoint_reports_offline_without_config(client) -> None:
    response = client.get("/api/market-data/status")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["market_data"]["state"] == "offline"
    assert payload["market_data"]["configured"] is False
    assert payload["market_data"]["subscriptions"] == 0


def test_market_data_snapshot_endpoint_returns_empty_list_without_ticks(client) -> None:
    response = client.get("/api/market-data/snapshot")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["ticks"] == []


def test_market_data_watchlist_endpoint_returns_default_symbols(client) -> None:
    response = client.get("/api/market-data/watchlist")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    watchlist = {item["symbol"]: item for item in payload["watchlist"]}
    assert watchlist["NIFTY"]["exchange"] == "NFO"
    assert watchlist["NIFTY"]["product_type"] == "futures"
    assert watchlist["BANKNIFTY"]["exchange"] == "NFO"
    assert watchlist["BANKNIFTY"]["product_type"] == "futures"
    assert watchlist["FINNIFTY"]["exchange"] == "NFO"
    assert watchlist["FINNIFTY"]["product_type"] == "futures"
