from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, or_, select

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


@dataclass
class ParsedQuery:
    root: str
    raw_root: str
    has_futures_intent: bool
    has_options_intent: bool
    right: str | None
    strike: str | None


def parse_search_query(raw: str) -> ParsedQuery:
    text = raw.strip().upper()
    raw_root = text

    has_futures = False
    for suffix in [" FUTURES", " FUTURE", " FUT"]:
        if text.endswith(suffix):
            has_futures = True
            text = text[: -len(suffix)].strip()
            break

    right: str | None = None
    for token in [" PE", " CE"]:
        if token in text:
            parts = text.rsplit(token, 1)
            text = parts[0].strip()
            right = token.strip().lower()
            break

    strike: str | None = None
    words = text.split()
    remaining: list[str] = []
    for w in words:
        if w.isdigit() and strike is None:
            strike = w
        else:
            remaining.append(w)
    text = " ".join(remaining).strip()

    return ParsedQuery(
        root=text,
        raw_root=raw_root,
        has_futures_intent=has_futures,
        has_options_intent=right is not None,
        right=right,
        strike=strike,
    )


def resolve_canonical_display(text: str, session_factory) -> str | None:
    root_upper = text.upper().strip()
    if not root_upper:
        return None

    alias_map_upper = {k.upper(): v for k, v in _INSTRUMENT_ALIAS_MAP.items()}
    if root_upper in alias_map_upper:
        return alias_map_upper[root_upper]

    with session_factory() as session:
        direct = (
            session.query(Instrument.display_symbol)
            .filter(
                func.upper(Instrument.display_symbol) == root_upper,
                Instrument.exchange_code.in_(["NSE", "NFO"]),
                Instrument.is_active.is_(True),
            )
            .first()
        )
        if direct and direct[0]:
            return direct[0]

        broker = (
            session.query(Instrument.display_symbol)
            .filter(
                func.upper(Instrument.broker_symbol) == root_upper,
                Instrument.exchange_code.in_(["NSE", "NFO"]),
                Instrument.is_active.is_(True),
            )
            .first()
        )
        if broker and broker[0]:
            return broker[0]

        alias = (
            session.query(Instrument.display_symbol)
            .join(InstrumentAlias, InstrumentAlias.instrument_id == Instrument.id)
            .filter(
                func.upper(InstrumentAlias.normalized_alias) == root_upper,
                Instrument.is_active.is_(True),
            )
            .first()
        )
        if alias and alias[0]:
            return alias[0]

    return None


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


def _rank_key(row: Instrument, query: str, parsed: ParsedQuery, kind: str) -> float:
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

    score = float(priority) * 100000.0

    if parsed.has_futures_intent:
        if kind == "future":
            score += 0.0
        elif kind == "cash":
            score += 20000.0
        else:
            score += 40000.0
    elif parsed.has_options_intent:
        if kind == "option":
            row_right = (row.option_right or "").lower()
            row_right_short = "ce" if row_right in ("call", "ce") else ("pe" if row_right in ("put", "pe") else None)
            if row_right_short == parsed.right:
                score += 0.0
            else:
                score += 5000.0
        elif kind == "future":
            score += 20000.0
        else:
            score += 30000.0
    else:
        if kind == "future":
            score += 0.0
        elif kind == "option":
            score += 10000.0
        else:
            score += 20000.0

    if parsed.strike and kind == "option":
        row_strike = _parse_strike(row.strike_price)
        if row_strike is not None:
            dist = abs(row_strike - Decimal(parsed.strike))
            score += float(min(dist, Decimal("5000")))

    if kind in ("future", "option") and row.expiry_date is not None:
        days_to = (row.expiry_date - date.today()).days
        if days_to < 0:
            score += 99999.0
        else:
            score += float(min(days_to, 365)) * 100.0

    return score


class InstrumentSearchService:
    def __init__(self, database_url: str | None):
        self.database_url = database_url

    def search(self, query: str, tab: str = "all") -> dict[str, object]:
        cleaned_query = normalize_query(query)
        if not cleaned_query or len(cleaned_query) < 1:
            return {"status": "ok", "query": query, "tab": tab, "results": []}

        if not self.database_url:
            return {"status": "ok", "query": query, "tab": tab, "results": []}

        parsed = parse_search_query(query)
        session_factory = create_session_factory(self.database_url)
        today = date.today()

        canonical_display: str | None = None
        if tab == "fno" and parsed.root:
            canonical_display = resolve_canonical_display(parsed.root, session_factory)

        root_for_search = parsed.root if parsed.root else cleaned_query
        pattern = f"%{root_for_search}%"

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

        if canonical_display and tab == "fno":
            canonical_upper = canonical_display.upper()
            classified = [
                item for item in classified
                if (item[0].display_symbol or "").upper() == canonical_upper
            ]

        ranked = sorted(classified, key=lambda item: _rank_key(item[0], cleaned_query, parsed, item[1]))

        if not ranked:
            return {"status": "ok", "query": query, "tab": tab, "results": []}

        tops = self._apply_option_diversity(ranked, parsed, canonical_display)

        if parsed.has_futures_intent:
            future_items = [item for item in tops if item[1] == "future"]
            option_items = [item for item in tops if item[1] == "option"][:3]
            interleaved = future_items + option_items
        elif parsed.has_options_intent:
            option_items = [item for item in tops if item[1] == "option"]
            future_items = [item for item in tops if item[1] == "future"][:1]
            interleaved = option_items + future_items
        else:
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
        parsed: ParsedQuery,
        canonical_display: str | None,
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

        option_by_ul: dict[str, list[tuple[Instrument, str]]] = {}
        for item in options:
            sym = (item[0].display_symbol or item[0].broker_symbol).upper()
            option_by_ul.setdefault(sym, []).append(item)

        for sym, opt_list in option_by_ul.items():
            expiry_groups: dict[str, list[tuple[Instrument, str]]] = {}
            for item in opt_list:
                exp_key = item[0].expiry_date.isoformat() if item[0].expiry_date else "unknown"
                expiry_groups.setdefault(exp_key, []).append(item)

            sorted_expiries = sorted(expiry_groups.keys())
            side_filter: str | None = None
            if parsed.has_options_intent and parsed.right:
                side_filter = parsed.right

            ordered: list[tuple[Instrument, str]] = []

            for exp_key in sorted_expiries[:2]:
                group = expiry_groups[exp_key]

                all_strikes: list[Decimal] = []
                for item in group:
                    ps = _parse_strike(item[0].strike_price)
                    if ps is not None:
                        all_strikes.append(ps)
                if not all_strikes:
                    continue
                all_strikes.sort()
                median_strike = all_strikes[len(all_strikes) // 2]

                ce_by_dist: list[tuple[tuple[Instrument, str], Decimal]] = []
                pe_by_dist: list[tuple[tuple[Instrument, str], Decimal]] = []
                for item in group:
                    ps = _parse_strike(item[0].strike_price)
                    if ps is None:
                        continue
                    dist = abs(ps - median_strike)
                    row_right = (item[0].option_right or "").lower()
                    if row_right in ("call", "ce"):
                        ce_by_dist.append((item, dist))
                    elif row_right in ("put", "pe"):
                        pe_by_dist.append((item, dist))

                ce_by_dist.sort(key=lambda x: x[1])
                pe_by_dist.sort(key=lambda x: x[1])

                if side_filter == "ce":
                    ordered.extend(item for item, _ in ce_by_dist)
                elif side_filter == "pe":
                    ordered.extend(item for item, _ in pe_by_dist)
                else:
                    max_len = max(len(ce_by_dist), len(pe_by_dist))
                    for i in range(max_len):
                        if i < len(ce_by_dist):
                            ordered.append(ce_by_dist[i][0])
                        if i < len(pe_by_dist):
                            ordered.append(pe_by_dist[i][0])

            option_by_ul[sym] = ordered

        result: list[tuple[Instrument, str]] = list(cash_future)
        for sym_items in option_by_ul.values():
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
