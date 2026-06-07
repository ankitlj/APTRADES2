from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from .breeze_gateway import BreezeGateway, BreezeGatewayError, BreezeInstrument
from .symbol_resolver import ResolvedInstrument, SymbolResolver, SymbolResolverError


class QuoteServiceError(Exception):
    pass


@dataclass(frozen=True)
class QuoteRequest:
    symbol: str
    exchange_code: str
    product_type: str | None = None
    expiry_date: date | None = None
    right: str | None = None
    strike_price: str | None = None


class QuoteService:
    def __init__(self, database_url: str | None, gateway: BreezeGateway):
        self.gateway = gateway
        self.symbol_resolver = SymbolResolver(database_url)

    def get_quote(self, request: QuoteRequest) -> dict[str, Any]:
        try:
            resolved = self.symbol_resolver.resolve(
                request.symbol,
                request.exchange_code,
                product_type=request.product_type,
                expiry_date=request.expiry_date,
                right=request.right,
                strike_price=request.strike_price,
            )
            quote = self.gateway.get_quote(self._to_breeze_instrument(resolved))
        except (SymbolResolverError, BreezeGatewayError) as error:
            raise QuoteServiceError(str(error)) from error

        primary_quote = quote[0] if isinstance(quote, list) and quote else quote
        return {
            "status": "ok",
            "symbol": request.symbol.upper(),
            "resolved": self._serialize_resolved(resolved),
            "quote": primary_quote,
        }

    def get_batch_quotes(self, requests: list[QuoteRequest]) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        for request in requests:
            try:
                results.append(self.get_quote(request))
            except QuoteServiceError as error:
                results.append(
                    {
                        "status": "error",
                        "symbol": request.symbol.upper(),
                        "exchange_code": request.exchange_code.upper(),
                        "product_type": (request.product_type or "").lower() or None,
                        "error": str(error),
                    }
                )

        return {
            "status": "ok" if any(item["status"] == "ok" for item in results) else "error",
            "results": results,
        }

    @staticmethod
    def _to_breeze_instrument(resolved: ResolvedInstrument) -> BreezeInstrument:
        expiry_date = ""
        if resolved.expiry_date is not None:
            expiry_date = f"{resolved.expiry_date.isoformat()}T06:00:00.000Z"

        return BreezeInstrument(
            display_symbol=resolved.display_symbol,
            stock_code=resolved.broker_symbol,
            exchange_code=resolved.exchange_code,
            product_type=resolved.product_type,
            right=resolved.right,
            strike_price=resolved.strike_price,
            expiry_date=expiry_date,
        )

    @staticmethod
    def _serialize_resolved(resolved: ResolvedInstrument) -> dict[str, Any]:
        return {
            "display_symbol": resolved.display_symbol,
            "broker_symbol": resolved.broker_symbol,
            "exchange_code": resolved.exchange_code,
            "product_type": resolved.product_type,
            "token": resolved.token,
            "contract_code": resolved.contract_code,
            "expiry_date": resolved.expiry_date.isoformat() if resolved.expiry_date else None,
            "right": resolved.right,
            "strike_price": resolved.strike_price,
            "lot_size": resolved.lot_size,
            "tick_size": resolved.tick_size,
            "source": resolved.source,
            "resolution_source": resolved.resolution_source,
        }
