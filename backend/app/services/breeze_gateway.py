from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests


class BreezeGatewayError(Exception):
    pass


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

    def get_portfolio_positions(self) -> Any:
        response = self._request("GET", "/portfoliopositions", {}, requires_auth=True)
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
        response = self._request("GET", "/orderlist", payload, requires_auth=True)
        success = response.get("Success")
        if success is None:
            raise BreezeGatewayError(response.get("Error") or "Breeze order list response missing Success field")
        return success

    def cancel_order(self, *, exchange_code: str, order_id: str) -> Any:
        payload = {
            "exchange_code": exchange_code,
            "order_id": order_id,
        }
        response = self._request("DELETE", "/cancelorder", payload, requires_auth=True)
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
        response = self._request("GET", "/tradelist", payload, requires_auth=True)
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

    def _request(self, method: str, path: str, payload: dict[str, Any], *, requires_auth: bool) -> dict[str, Any]:
        if requires_auth and not self.is_configured():
            raise BreezeGatewayError(f"Missing Breeze configuration: {', '.join(self._missing_fields())}")

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
        for attempt in range(3):
            try:
                response = requests.request(method, url, headers=headers, data=payload_json, timeout=15)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt == 2:
                    break
                time.sleep(1)

        raise BreezeGatewayError(f"Breeze request failed for {path}: {last_error}")

    def _customer_session_token(self) -> str:
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
