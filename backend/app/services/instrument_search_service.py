from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import or_, select

from ..db import create_session_factory
from ..models import Instrument, InstrumentAlias


_INSTRUMENT_ALIAS_MAP: dict[str, str] = {
    "NIFTY 50": "NIFTY",
    "NIFTY50": "NIFTY",
    "BANK NIFTY": "BANKNIFTY",
    "BANKNIFTY": "BANKNIFTY",
    "FIN NIFTY": "FINNIFTY",
    "FINNIFTY": "FINNIFTY",
    "MIDCAP NIFTY": "NIFTYMID50",
    "MIDCAPNIFTY": "NIFTYMID50",
    "MIDCAP": "NIFTYMID50",
    "NIFTY MIDCAP": "NIFTYMID50",
    "SENSEX": "SENSEX",
}


def normalize_query(text: str) -> str:
    cleaned = text.strip().upper()
    cleaned = re.sub(r"\s+", " ", cleaned)
    mapped = _INSTRUMENT_ALIAS_MAP.get(cleaned)
    return mapped if mapped else cleaned


def normalize_display_strike(raw_strike: Any) -> Decimal | None:
    if raw_strike is None:
        return None
    try:
        val = Decimal(str(raw_strike).replace(",", ""))
    except InvalidOperation:
        return None
    if val == 0:
        return None
    if val >= Decimal("100000"):
        return val / Decimal("100")
    return val


def _parse_strike(value: object) -> Decimal | None:
    """Safely parse a strike price value to Decimal for comparison/sorting.

    Returns None for any unparseable input (None, empty, non-numeric) so callers
    never raise on fractional strikes like "292.5" or garbage text.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def classify_instrument(exchange_code: str, product_type: str | None, option_right: str | None, expiry_date: date | None) -> str:
    exchange = (exchange_code or "").strip().upper()
    product = (product_type or "").strip().lower()
    right = (option_right or "").strip().lower()

    if exchange in ("NFO", "BFO") and right in ("call", "put", "ce", "pe"):
        return "option"
    if exchange in ("NFO", "BFO") and product == "options":
        return "option"
    if exchange in ("NFO", "BFO") and product in ("futures", "future", ""):
        if expiry_date is not None:
            return "future"
        return "future"
    return "cash"


RankEntry = tuple[int, int, str, str, date | None]


def _rank_key(row: Instrument, query: str, kind: str) -> RankEntry:
    upper_symbol = (row.broker_symbol or "").upper()
    upper_display = (row.display_symbol or "").upper()
    upper_name = (row.name or "").upper()
    query_upper = query.upper()

    priority = 100
    if upper_symbol == query_upper or upper_display == query_upper:
        priority = 0
    elif query_upper in _INSTRUMENT_ALIAS_MAP and _INSTRUMENT_ALIAS_MAP[query_upper] == upper_symbol:
        priority = 1
    elif upper_symbol.startswith(query_upper) or upper_display.startswith(query_upper):
        priority = 2
    elif upper_name.startswith(query_upper):
        priority = 3
    elif query_upper in upper_symbol or query_upper in upper_display:
        priority = 4
    elif query_upper in upper_name:
        priority = 5
    else:
        priority = 10

    kind_order = 0 if kind == "cash" else 1 if kind == "future" else 2

    neg_expiry_order = 0
    if row.expiry_date is not None:
        neg_expiry_order = -(row.expiry_date - date.today()).days if row.expiry_date >= date.today() else 99999

    return (priority, kind_order, neg_expiry_order, upper_symbol, row.expiry_date)


class InstrumentSearchService:
    def __init__(self, database_url: str | None):
        self.database_url = database_url

    def search(self, query: str, tab: str = "all") -> dict[str, object]:
        cleaned_query = normalize_query(query)
        if not cleaned_query or len(cleaned_query) < 1:
            return {"status": "ok", "query": query, "tab": tab, "results": []}

        if not self.database_url:
            return {"status": "ok", "query": query, "tab": tab, "results": []}

        pattern = f"%{cleaned_query}%"
        session_factory = create_session_factory(self.database_url)
        today = date.today()

        with session_factory() as session:
            base = (
                session.query(Instrument)
                .filter(Instrument.is_active.is_(True))
            )

            name_clause = or_(
                Instrument.broker_symbol.like(pattern),
                Instrument.display_symbol.like(pattern),
                Instrument.name.like(pattern),
            )

            alias_subq = select(InstrumentAlias.instrument_id).where(
                InstrumentAlias.normalized_alias.like(pattern)
            )

            base = base.filter(
                or_(
                    name_clause,
                    Instrument.id.in_(alias_subq),
                )
            )

            base = base.filter(Instrument.exchange_code.in_(["NSE", "NFO"]))

            rows = base.all()

        classified: list[tuple[Instrument, str]] = []
        for r in rows:
            kind = classify_instrument(r.exchange_code, r.product_type, r.option_right, r.expiry_date)

            if tab == "stocks" and kind != "cash":
                continue
            if tab == "fno" and kind not in ("future", "option"):
                continue

            if kind in ("future", "option"):
                if r.expiry_date is None or r.expiry_date < today:
                    continue

            classified.append((r, kind))

        ranked = sorted(classified, key=lambda item: _rank_key(item[0], cleaned_query, item[1]))

        if not ranked:
            return {"status": "ok", "query": query, "tab": tab, "results": []}

        tops = self._apply_option_diversity(ranked, cleaned_query)

        # Ensure kind diversity: guarantee at least 3 futures and 5 options
        # appear in results when available, even if native rank/kind_order
        # would push them past the limit.
        diverse: list[tuple[Instrument, str]] = []
        held_futures: list[tuple[Instrument, str]] = []
        held_options: list[tuple[Instrument, str]] = []
        for item in tops:
            if item[1] == "future" and len(held_futures) < 3:
                held_futures.append(item)
            elif item[1] == "option" and len(held_options) < 5:
                held_options.append(item)
            else:
                diverse.append(item)
        interleaved = held_futures + held_options + diverse

        results = []
        for r, kind in interleaved[:60]:
            raw_strike = r.strike_price
            display_strike = normalize_display_strike(raw_strike)
            right_str = None
            if kind == "option":
                raw_right = (r.option_right or "").lower()
                if raw_right in ("call", "ce"):
                    right_str = "CE"
                elif raw_right in ("put", "pe"):
                    right_str = "PE"

            label_parts = [r.display_symbol or r.broker_symbol]
            sublabel_parts = []

            if kind == "future" and r.expiry_date:
                label_parts.append(r.expiry_date.isoformat())
                sublabel_parts.append(f"Expiry {r.expiry_date.isoformat()}")
            elif kind == "option":
                if display_strike is not None:
                    label_parts.append(str(int(display_strike)) if display_strike == display_strike.to_integral_value() else str(display_strike))
                else:
                    label_parts.append(raw_strike or "?")
                if right_str:
                    label_parts.append(right_str)
                if r.expiry_date:
                    sublabel_parts.append(f"Expiry {r.expiry_date.isoformat()}")

            sublabel_parts.append(f"{r.exchange_code} {kind}")
            sublabel = " | ".join(sublabel_parts) if sublabel_parts else f"{r.exchange_code} {kind}"

            badges = [r.exchange_code]
            if kind == "cash":
                badges.append("EQ")
            elif kind == "future":
                badges.append("FUT")
            elif kind == "option":
                badges.append("OPT")
                if right_str:
                    badges.append(right_str)

            results.append({
                "id": r.id,
                "symbol": r.broker_symbol,
                "broker_symbol": r.broker_symbol,
                "display_symbol": r.display_symbol,
                "name": r.name,
                "exchange_code": r.exchange_code,
                "product_type": r.product_type or kind,
                "instrument_kind": kind,
                "expiry_date": r.expiry_date.isoformat() if r.expiry_date else None,
                "strike_price": raw_strike,
                "display_strike": str(int(display_strike)) if display_strike is not None and display_strike == display_strike.to_integral_value() else str(display_strike) if display_strike is not None else None,
                "right": right_str,
                "lot_size": r.lot_size,
                "label": " ".join(label_parts),
                "sublabel": sublabel,
                "badges": badges,
                "rank": rank_val(priority=0),
            })

        return {
            "status": "ok",
            "query": query,
            "tab": tab,
            "results": results,
        }

    def _apply_option_diversity(
        self,
        ranked: list[tuple[Instrument, str]],
        query: str,
    ) -> list[tuple[Instrument, str]]:
        cash_future: list[tuple[Instrument, str]] = []
        options: list[tuple[Instrument, str]] = []
        for item in ranked:
            if item[1] == "option":
                options.append(item)
            else:
                cash_future.append(item)

        if not options:
            return ranked

        option_by_underlying: dict[str, list[tuple[Instrument, str]]] = {}
        for item in options:
            sym = item[0].broker_symbol.upper()
            option_by_underlying.setdefault(sym, []).append(item)

        for sym, opt_list in option_by_underlying.items():
            expiry_groups: dict[str, list[tuple[Instrument, str]]] = {}
            for item in opt_list:
                exp_key = item[0].expiry_date.isoformat() if item[0].expiry_date else "unknown"
                expiry_groups.setdefault(exp_key, []).append(item)

            sorted_expiries = sorted(expiry_groups.keys())
            chosen_sym: list[tuple[Instrument, str]] = []

            for exp_key in sorted_expiries[:2]:
                group = expiry_groups[exp_key]
                strikes_with_kind: list[tuple[tuple[Instrument, str], Decimal]] = []
                for item in group:
                    parsed = _parse_strike(item[0].strike_price)
                    if parsed is not None:
                        strikes_with_kind.append((item, abs(parsed)))
                strikes_with_kind.sort(key=lambda x: x[1])
                central_idx = len(strikes_with_kind) // 2
                start = max(0, central_idx - 2)
                end = min(len(strikes_with_kind), central_idx + 3)
                chosen_sym.extend(strikes_with_kind[i][0] for i in range(start, end))

            option_by_underlying[sym] = chosen_sym

        result: list[tuple[Instrument, str]] = list(cash_future)
        for sym_items in option_by_underlying.values():
            result.extend(sym_items)

        seen = set()
        deduped: list[tuple[Instrument, str]] = []
        for item in result:
            key = (item[0].id, item[1])
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        return deduped


def rank_val(priority: int) -> int:
    return priority
