from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .breeze_gateway import BreezeGateway
from .option_chain_service import (
    OptionChainRequest,
    OptionChainService,
    OptionChainServiceError,
)


class OIServiceError(Exception):
    pass


@dataclass(frozen=True)
class OIRequest:
    underlying: str
    expiry_date: date
    exchange_code: str = "NFO"


class OIService:
    def __init__(
        self,
        database_url: str | None,
        redis_url: str | None,
        gateway: BreezeGateway,
    ) -> None:
        self._chain_service = OptionChainService(database_url, redis_url, gateway)

    def get_tracker(self, request: OIRequest) -> dict[str, Any]:
        chain = self._fetch_full_chain(request)
        rows = chain["rows"]
        flat = [self._flatten_row(row) for row in rows]
        sorted_rows = sorted(flat, key=lambda r: r["total_oi"], reverse=True)
        max_ce = max(flat, key=lambda r: r["ce_oi"], default=None) if flat else None
        max_pe = max(flat, key=lambda r: r["pe_oi"], default=None) if flat else None
        return {
            "status": "ok",
            "underlying": chain["underlying"],
            "exchange_code": chain["exchange_code"],
            "expiry": chain["expiry"],
            "underlying_ltp": chain["underlying_ltp"],
            "atm_strike": chain["atm_strike"],
            "pcr": chain["pcr"],
            "total_call_oi": chain["total_call_oi"],
            "total_put_oi": chain["total_put_oi"],
            "max_ce_oi_strike": max_ce["strike_price"] if max_ce else None,
            "max_pe_oi_strike": max_pe["strike_price"] if max_pe else None,
            "updated_at": chain["updated_at"],
            "rows": sorted_rows,
        }

    def get_profile(self, request: OIRequest) -> dict[str, Any]:
        chain = self._fetch_full_chain(request)
        # OptionChainService already returns rows sorted by strike_price ascending
        flat = [self._flatten_row(row) for row in chain["rows"]]
        return {
            "status": "ok",
            "underlying": chain["underlying"],
            "exchange_code": chain["exchange_code"],
            "expiry": chain["expiry"],
            "underlying_ltp": chain["underlying_ltp"],
            "atm_strike": chain["atm_strike"],
            "pcr": chain["pcr"],
            "total_call_oi": chain["total_call_oi"],
            "total_put_oi": chain["total_put_oi"],
            "updated_at": chain["updated_at"],
            "rows": flat,
        }

    def _fetch_full_chain(self, request: OIRequest) -> dict[str, Any]:
        try:
            return self._chain_service.get_option_chain(
                OptionChainRequest(
                    underlying=request.underlying,
                    expiry_date=request.expiry_date,
                    exchange_code=request.exchange_code,
                    strike_count=0,
                )
            )
        except OptionChainServiceError as error:
            raise OIServiceError(str(error)) from error

    @staticmethod
    def _flatten_row(row: dict[str, Any]) -> dict[str, Any]:
        ce = row.get("ce") or {}
        pe = row.get("pe") or {}
        ce_oi = ce.get("oi") or 0.0
        pe_oi = pe.get("oi") or 0.0
        return {
            "strike_price": row["strike_price"],
            "ce_oi": ce_oi,
            "pe_oi": pe_oi,
            "total_oi": ce_oi + pe_oi,
            "ce_ltp": ce.get("ltp"),
            "pe_ltp": pe.get("ltp"),
        }
