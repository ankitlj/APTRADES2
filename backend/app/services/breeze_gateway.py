from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


class BreezeGatewayError(Exception):
    pass


# Phase 18 Tier 1: one process-wide gateway reused across requests so the
# customerdetails token exchange happens once, not on every quote. Keyed by the
# credential tuple so a daily session-token refresh (redeploy) rebuilds it.
_gateway_lock = threading.Lock()


def get_gateway(
    extensions: dict[str, Any],
    app_key: str | None,
    secret_key: str | None,
    session_token: str | None,
) -> "BreezeGateway":
    key = (app_key, secret_key, session_token)
    cached = extensions.get("breeze_gateway")
    if cached is not None and cached[0] == key:
        return cached[1]
    with _gateway_lock:
        cached = extensions.get("breeze_gateway")
        if cached is not None and cached[0] == key:
            return cached[1]
        gateway = BreezeGateway(app_key, secret_key, session_token)
        extensions["breeze_gateway"] = (key, gateway)
        return gateway


@dataclass(frozen=True)
class BreezeInstrument:
    display_symbol: str
    stock_code: str
    exchange_code: str
    product_type: str
    right: str = "others"
    strike_price: str = "0"
    expiry_date: str = ""


class BreezeGateway:
    base_url = "https://api.icicidirect.com/breezeapi/api/v1"

    def __init__(self, app_key: str | None, secret_key: str | None, session_token: str | None):
        self.app_key = app_key
        self.secret_key = secret_key
        self.session_token = session_token
        self._customer_details_cache: dict[str, Any] | None = None
        self._customer_session_token_cache: str | None = None
        # The gateway is shared across gthread workers; guard the lazy token
        # fields. RLock because _customer_session_token nests get_customer_details.
        self._token_lock = threading.RLock()

    def is_configured(self) -> bool:
        return all([self.app_key, self.secret_key, self.session_token])

    def auth_diagnostic(self) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "status": "not_configured",
                "configured": False,
                "missing": self._missing_fields(),
            }

        details = self.get_customer_details()
        success = details.get("Success") or {}
        return {
            "status": "ok",
            "configured": True,
            "user_id": success.get("idirect_userid"),
            "user_name": success.get("idirect_user_name"),
            "session_token_received": bool(success.get("session_token")),
            "segments_allowed": success.get("segments_allowed"),
            "exchange_status": success.get("exg_status"),
        }

    def run_symbol_diagnostics(self) -> dict[str, Any]:
        diagnostics: list[dict[str, Any]] = []
        for instrument in self._diagnostic_instruments():
            try:
                quote = self.get_quote(instrument)
                diagnostics.append(
                    {
                        "symbol": instrument.display_symbol,
                        "broker_symbol": instrument.stock_code,
                        "status": "ok",
                        "exchange": instrument.exchange_code,
                        "product_type": instrument.product_type,
                        "quote": quote,
                    }
                )
            except BreezeGatewayError as error:
                diagnostics.append(
                    {
                        "symbol": instrument.display_symbol,
                        "broker_symbol": instrument.stock_code,
                        "status": "error",
                        "exchange": instrument.exchange_code,
                        "product_type": instrument.product_type,
                        "error": str(error),
                    }
                )

        return {
            "status": "ok" if any(item["status"] == "ok" for item in diagnostics) else "error",
            "configured": self.is_configured(),
            "symbols": diagnostics,
        }

    def get_customer_details(self) -> dict[str, Any]:
        if self._customer_details_cache is not None:
            return self._customer_details_cache

        with self._token_lock:
            if self._customer_details_cache is not None:
                return self._customer_details_cache
            payload = {
                "SessionToken": self.session_token,
                "AppKey": self.app_key,
            }
            response = self._request("GET", "/customerdetails", payload, requires_auth=False)
            self._customer_details_cache = response
            return response

    def get_quote(self, instrument: BreezeInstrument) -> Any:
        payload = {
            "stock_code": instrument.stock_code,
            "exchange_code": instrument.exchange_code,
            "expiry_date": instrument.expiry_date,
            "product_type": instrument.product_type,
            "right": instrument.right,
            "strike_price": instrument.strike_price,
        }
        response = self._request("GET", "/quotes", payload, requires_auth=True)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze quotes response missing Success field")
        return success

    def get_portfolio_positions(self, *, timeout_override: int | None = None, attempts_override: int | None = None) -> Any:
        response = self._request("GET", "/portfoliopositions", {}, requires_auth=True, timeout_override=timeout_override, attempts_override=attempts_override)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze portfolio positions response missing Success field")
        return success

    def get_order_list(self, *, exchange_code: str, from_date: datetime, to_date: datetime) -> Any:
        payload = {
            "exchange_code": exchange_code,
            "from_date": self._format_datetime(from_date),
            "to_date": self._format_datetime(to_date),
        }
        response = self._request("GET", "/order", payload, requires_auth=True)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze order list response missing Success field")
        return success

    def cancel_order(self, *, exchange_code: str, order_id: str) -> Any:
        payload = {
            "exchange_code": exchange_code,
            "order_id": order_id,
        }
        response = self._request("DELETE", "/order", payload, requires_auth=True)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze cancel order response missing Success field")
        return success

    def get_trade_list(
        self,
        *,
        from_date: datetime,
        to_date: datetime,
        exchange_code: str,
        product_type: str = "",
        action: str = "",
        stock_code: str = "",
    ) -> Any:
        payload = {
            "from_date": self._format_datetime(from_date),
            "to_date": self._format_datetime(to_date),
            "exchange_code": exchange_code,
            "product_type": product_type,
            "action": action,
            "stock_code": stock_code,
        }
        response = self._request("GET", "/trades", payload, requires_auth=True)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze trade list response missing Success field")
        return success

    def get_historical_charts(
        self,
        instrument: BreezeInstrument,
        *,
        interval: str,
        from_date: datetime,
        to_date: datetime,
    ) -> Any:
        payload = {
            "stock_code": instrument.stock_code,
            "exchange_code": instrument.exchange_code,
            "product_type": instrument.product_type,
            "expiry_date": instrument.expiry_date,
            "right": instrument.right,
            "strike_price": instrument.strike_price,
            "interval": interval,
            "from_date": self._format_datetime(from_date),
            "to_date": self._format_datetime(to_date),
        }
        response = self._request("GET", "/historicalcharts", payload, requires_auth=True)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze historical charts response missing Success field")
        return success

    def get_option_chain_quotes(self, instrument: BreezeInstrument) -> Any:
        payload = {
            "stock_code": instrument.stock_code,
            "exchange_code": instrument.exchange_code,
            "product_type": instrument.product_type,
            "expiry_date": instrument.expiry_date,
            "right": instrument.right,
            "strike_price": instrument.strike_price,
        }
        response = self._request("GET", "/optionchain", payload, requires_auth=True)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze option-chain response missing Success field")
        return success

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        *,
        requires_auth: bool,
        interactive: bool = True,
        timeout_override: int | None = None,
        attempts_override: int | None = None,
    ) -> dict[str, Any]:
        if requires_auth and not self.is_configured():
            raise BreezeGatewayError(f"Missing Breeze configuration: {', '.join(self._missing_fields())}")

        timeout = timeout_override if timeout_override is not None else (10 if interactive else 15)
        attempts = attempts_override if attempts_override is not None else (2 if interactive else 3)

        # Authenticated calls retry once on a session error: the cached customer
        # session token may have expired mid-session, so drop it and re-exchange.
        for auth_attempt in range(2):
            response = self._send(method, path, payload, requires_auth=requires_auth, timeout=timeout, attempts=attempts)
            if requires_auth and auth_attempt == 0 and self._is_session_error(response):
                self._invalidate_session()
                continue
            return response
        return response

    def _send(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        *,
        requires_auth: bool,
        timeout: int = 10,
        attempts: int = 2,
    ) -> dict[str, Any]:
        payload_json = json.dumps(payload, separators=(",", ":"))
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}

        if requires_auth:
            timestamp = self._timestamp()
            checksum = hashlib.sha256(f"{timestamp}{payload_json}{self.secret_key}".encode("utf-8")).hexdigest()
            headers.update(
                {
                    "X-Checksum": f"token {checksum}",
                    "X-Timestamp": timestamp,
                    "X-AppKey": self.app_key or "",
                    "X-SessionToken": self._customer_session_token(),
                }
            )

        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = requests.request(method, url, headers=headers, data=payload_json, timeout=timeout)
                if response.status_code in (401, 403):
                    # Surface as a session error so _request can refresh and retry.
                    return {"Success": None, "Status": response.status_code, "Error": "Breeze session expired or unauthorized."}
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt == attempts - 1:
                    break
                time.sleep(1)

        raise BreezeGatewayError(f"Breeze request failed for {path}: {last_error}")

    @staticmethod
    def _is_session_error(response: Any) -> bool:
        if not isinstance(response, dict):
            return False
        if response.get("Status") in (401, 403):
            return True
        error_text = str(response.get("Error") or "").lower()
        if not error_text:
            return False
        return "session" in error_text and any(token in error_text for token in ("expire", "invalid", "not exist"))

    def _invalidate_session(self) -> None:
        with self._token_lock:
            self._customer_details_cache = None
            self._customer_session_token_cache = None

    def _customer_session_token(self) -> str:
        if self._customer_session_token_cache:
            return self._customer_session_token_cache

        with self._token_lock:
            if self._customer_session_token_cache:
                return self._customer_session_token_cache
            details = self.get_customer_details()
            success = details.get("Success") or {}
            token = success.get("session_token")
            if not token:
                raise BreezeGatewayError("CustomerDetails response did not include session_token")
            self._customer_session_token_cache = token
            return token

    def _missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.app_key:
            missing.append("BREEZE_API_KEY")
        if not self.secret_key:
            missing.append("BREEZE_SECRET_KEY")
        if not self.session_token:
            missing.append("BREEZE_SESSION_TOKEN")
        return missing

    @staticmethod
    def _timestamp() -> str:
        return BreezeGateway._format_datetime(datetime.now(timezone.utc))

    @staticmethod
    def _format_datetime(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", ".000Z")

    @staticmethod
    def _diagnostic_instruments() -> list[BreezeInstrument]:
        return [
            BreezeInstrument("NIFTY", "NIFTY", "NFO", "futures", expiry_date=""),
            BreezeInstrument("BANKNIFTY", "CNXBAN", "NFO", "futures", expiry_date=""),
            BreezeInstrument("RELIANCE", "RELIND", "NSE", "cash"),
            BreezeInstrument("ADANIPORTS", "ADAPOR", "NSE", "cash"),
            BreezeInstrument("SBIN", "STABAN", "NSE", "cash"),
        ]
