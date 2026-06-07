from __future__ import annotations

import csv
import hashlib
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from sqlalchemy import delete, func, select

from ..db import create_session_factory, ensure_tables
from ..models import Instrument, InstrumentAlias, MasterContractRun


class MasterContractImportError(Exception):
    pass


@dataclass(frozen=True)
class SourcePayload:
    name: str
    rows: list[dict[str, str]]
    digest_source: bytes | None
    warnings: list[str]


class MasterContractService:
    def __init__(
        self,
        database_url: str | None,
        stock_script_csv_path: str | None,
        security_master_url: str,
    ):
        self.database_url = database_url
        self.stock_script_csv_path = stock_script_csv_path
        self.security_master_url = security_master_url

    def get_status(self) -> dict[str, Any]:
        if not self.database_url:
            return {
                "status": "not_configured",
                "database_configured": False,
                "csv_path": self.stock_script_csv_path,
                "csv_available": self._csv_available(),
                "security_master_url": self.security_master_url,
            }

        ensure_tables(self.database_url)
        session_factory = create_session_factory(self.database_url)

        with session_factory() as session:
            instrument_count = session.scalar(select(func.count()).select_from(Instrument)) or 0
            alias_count = session.scalar(select(func.count()).select_from(InstrumentAlias)) or 0
            latest_run = session.scalars(select(MasterContractRun).order_by(MasterContractRun.started_at.desc()).limit(1)).first()

        return {
            "status": "ok",
            "database_configured": True,
            "csv_path": self.stock_script_csv_path,
            "csv_available": self._csv_available(),
            "security_master_url": self.security_master_url,
            "instrument_count": instrument_count,
            "alias_count": alias_count,
            "latest_run": self._serialize_run(latest_run),
            "verified_aliases": self._verified_aliases(),
        }

    def import_master_contract(self) -> dict[str, Any]:
        if not self.database_url:
            raise MasterContractImportError("DATABASE_URL is not configured.")

        ensure_tables(self.database_url)
        sources = self._load_sources()
        rows: list[dict[str, str]] = []
        warnings: list[str] = []
        source_names: list[str] = []
        checksum_parts: list[bytes] = []
        for source in sources:
            if source.rows:
                rows.extend(source.rows)
                source_names.append(source.name)
            warnings.extend(source.warnings)
            if source.digest_source:
                checksum_parts.append(source.digest_source)

        if not rows:
            raise MasterContractImportError("No master-contract rows were available from SecurityMaster or StockScriptNew.csv.")

        instrument_payloads, alias_payloads = self._build_payloads(rows)
        checksum = hashlib.sha256(b"".join(checksum_parts)).hexdigest() if checksum_parts else None
        started_at = datetime.now(timezone.utc)
        session_factory = create_session_factory(self.database_url)

        with session_factory() as session:
            session.execute(delete(InstrumentAlias))
            session.execute(delete(Instrument))
            if instrument_payloads:
                session.bulk_insert_mappings(Instrument, instrument_payloads)
                session.flush()

            key_to_id = {
                (instrument.exchange_code, instrument.contract_code): instrument.id
                for instrument in session.scalars(select(Instrument)).all()
            }

            alias_records: list[dict[str, Any]] = []
            for payload in alias_payloads:
                instrument_id = key_to_id.get((payload["exchange_code"], payload["contract_code"]))
                if not instrument_id:
                    continue
                alias_records.append(
                    {
                        "instrument_id": instrument_id,
                        "alias": payload["alias"],
                        "normalized_alias": payload["normalized_alias"],
                        "alias_scope": payload["alias_scope"],
                        "alias_type": payload["alias_type"],
                        "source": payload["source"],
                    }
                )

            if alias_records:
                session.bulk_insert_mappings(InstrumentAlias, alias_records)

            run = MasterContractRun(
                status="success",
                source_name="+".join(source_names) if source_names else "unknown",
                source_checksum=checksum,
                security_master_url=self.security_master_url,
                csv_path=self.stock_script_csv_path,
                row_count=len(instrument_payloads),
                alias_count=len(alias_records),
                warning_count=len(warnings),
                error_message="\n".join(warnings) if warnings else None,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
            session.add(run)
            session.commit()

        return {
            "status": "ok",
            "row_count": len(instrument_payloads),
            "alias_count": len(alias_records),
            "source_name": "+".join(source_names) if source_names else "unknown",
            "source_checksum": checksum,
            "warnings": warnings,
        }

    def _load_sources(self) -> list[SourcePayload]:
        return [
            self._load_security_master_rows(),
            self._load_stock_script_rows(),
            self._load_seed_rows(),
        ]

    def _load_security_master_rows(self) -> SourcePayload:
        warnings: list[str] = []
        try:
            response = requests.get(self.security_master_url, timeout=(5, 8))
            response.raise_for_status()
            archive_bytes = response.content
        except requests.RequestException as error:
            warnings.append(f"SecurityMaster download failed: {error}")
            return SourcePayload(name="security_master", rows=[], digest_source=None, warnings=warnings)

        rows: list[dict[str, str]] = []
        try:
            with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
                for filename in archive.namelist():
                    if not filename.lower().endswith(".csv"):
                        continue
                    with archive.open(filename) as handle:
                        rows.extend(
                            self._read_csv_rows(
                                io.TextIOWrapper(handle, encoding="utf-8-sig", errors="ignore"),
                                source_name="security_master",
                            )
                        )
        except zipfile.BadZipFile as error:
            warnings.append(f"SecurityMaster archive could not be read: {error}")
            return SourcePayload(name="security_master", rows=[], digest_source=archive_bytes, warnings=warnings)

        if not rows:
            warnings.append("SecurityMaster archive contained no parsable CSV rows.")
        return SourcePayload(name="security_master", rows=rows, digest_source=archive_bytes, warnings=warnings)

    def _load_stock_script_rows(self) -> SourcePayload:
        warnings: list[str] = []
        if not self.stock_script_csv_path:
            warnings.append("StockScriptNew.csv path is not configured.")
            return SourcePayload(name="stock_script_csv", rows=[], digest_source=None, warnings=warnings)

        csv_path = self._resolve_csv_path()
        if not csv_path:
            warnings.append("StockScriptNew.csv path is not configured.")
            return SourcePayload(name="stock_script_csv", rows=[], digest_source=None, warnings=warnings)
        if not csv_path.exists():
            warnings.append(f"StockScriptNew.csv was not found at {csv_path}.")
            return SourcePayload(name="stock_script_csv", rows=[], digest_source=None, warnings=warnings)

        data = csv_path.read_bytes()
        text = data.decode("utf-8-sig", errors="ignore")
        rows = self._read_csv_rows(io.StringIO(text), source_name="stock_script_csv")
        return SourcePayload(name="stock_script_csv", rows=rows, digest_source=data, warnings=warnings)

    def _load_seed_rows(self) -> SourcePayload:
        seed_rows = [
            self._seed_row("RELIND", "RELIANCE INDUSTRIES", "NSE", "RELIND", "EQUITY", "2885", "1", "RELIND", "RELIANCE", "0.1", "INE002A01018", "EQ", ""),
            self._seed_row("ADAPOR", "ADANI PORT AND SPECIAL ECONO", "NSE", "ADAPOR", "EQUITY", "15083", "1", "ADAPOR", "ADANIPORTS", "0.1", "INE742F01042", "EQ", ""),
            self._seed_row("STABAN", "STATE BANK OF INDIA", "NSE", "STABAN", "EQUITY", "3045", "1", "STABAN", "SBIN", "0.1", "INE062A01020", "EQ", ""),
            self._seed_row("CNXBAN", "NIFTY BANK", "NSE", "CNXBAN", "EQUITY", "NIFTY BANK", "1", "CNXBAN", "BANK NIFTY", "0", "", "0", ""),
            self._seed_row("NIFTY", "NIFTY 50", "NSE", "NIFTY", "EQUITY", "NIFTY 50", "1", "NIFTY", "NIFTY", "0", "", "0", ""),
        ]
        return SourcePayload(
            name="seed_aliases",
            rows=seed_rows,
            digest_source="\n".join(row["SC"] for row in seed_rows).encode("utf-8"),
            warnings=["Using fallback seeded aliases because persistent source data may be unavailable."],
        )

    @staticmethod
    def _seed_row(
        sc: str,
        sn: str,
        ec: str,
        sm: str,
        sg: str,
        tk: str,
        ls: str,
        cd: str,
        ns: str,
        ts: str,
        isin: str,
        sr: str,
        si: str,
    ) -> dict[str, str]:
        return {
            "SC": sc,
            "SN": sn,
            "EC": ec,
            "SM": sm,
            "SG": sg,
            "TK": tk,
            "LS": ls,
            "CD": cd,
            "NS": ns,
            "TS": ts,
            "ISIN": isin,
            "SR": sr,
            "SI": si,
            "__source_name": "seed_aliases",
        }

    def _read_csv_rows(self, handle: io.TextIOBase | io.StringIO, *, source_name: str) -> list[dict[str, str]]:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            cleaned = {str(key).strip(): (value or "").strip() for key, value in row.items() if key}
            if not cleaned.get("SC") or not cleaned.get("EC"):
                continue
            cleaned["__source_name"] = source_name
            rows.append(cleaned)
        return rows

    def _build_payloads(self, rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        instruments_by_key: dict[tuple[str, str], dict[str, Any]] = {}
        aliases_by_key: dict[tuple[str, str], dict[str, Any]] = {}

        for row in rows:
            instrument_payload = self._instrument_payload(row)
            key = (instrument_payload["exchange_code"], instrument_payload["contract_code"])
            instruments_by_key[key] = instrument_payload

        for row in rows:
            instrument_payload = self._instrument_payload(row)
            if instrument_payload["product_type"] != "cash":
                continue
            key = (instrument_payload["exchange_code"], instrument_payload["contract_code"])
            for alias in self._alias_candidates(row):
                normalized = self._normalize_alias(alias)
                if not normalized:
                    continue
                alias_key = (instrument_payload["exchange_code"], normalized)
                aliases_by_key[alias_key] = {
                    "exchange_code": key[0],
                    "contract_code": key[1],
                    "alias": alias,
                    "normalized_alias": normalized,
                    "alias_scope": instrument_payload["exchange_code"],
                    "alias_type": "display" if normalized != instrument_payload["broker_symbol"] else "broker_symbol",
                    "source": instrument_payload["source"],
                }

        return list(instruments_by_key.values()), list(aliases_by_key.values())

    def _instrument_payload(self, row: dict[str, str]) -> dict[str, Any]:
        exchange_code = row.get("EC", "").upper()
        broker_symbol = row.get("SC", "").upper()
        contract_code = (row.get("SM") or broker_symbol).upper()
        display_symbol = row.get("NS") or row.get("SI") or broker_symbol
        product_type, expiry_date, option_right, strike_price = self._contract_attributes(contract_code, row)

        return {
            "exchange_code": exchange_code,
            "broker_symbol": broker_symbol,
            "contract_code": contract_code,
            "display_symbol": display_symbol,
            "name": row.get("SN") or display_symbol,
            "instrument_group": row.get("SG") or None,
            "product_type": product_type,
            "token": row.get("TK") or None,
            "lot_size": self._parse_int(row.get("LS")),
            "tick_size": row.get("TS") or None,
            "isin": row.get("ISIN") or None,
            "series": row.get("SR") or None,
            "expiry_date": expiry_date,
            "option_right": option_right,
            "strike_price": strike_price,
            "source": "stock_script_csv" if self._row_is_from_csv(row) else "security_master",
            "is_active": True,
            "last_seen_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    def _alias_candidates(self, row: dict[str, str]) -> list[str]:
        aliases: list[str] = []
        for value in (row.get("NS"), row.get("SI"), row.get("SC"), row.get("CD")):
            cleaned = (value or "").strip()
            if not cleaned:
                continue
            aliases.append(cleaned.upper())
            compact = re.sub(r"\s+", "", cleaned.upper())
            if compact and compact != cleaned.upper():
                aliases.append(compact)
        deduped: list[str] = []
        seen: set[str] = set()
        for alias in aliases:
            if alias in seen:
                continue
            seen.add(alias)
            deduped.append(alias)
        return deduped

    def _contract_attributes(self, contract_code: str, row: dict[str, str]) -> tuple[str, datetime.date | None, str | None, str | None]:
        product_group = row.get("SG", "").upper()
        if "~F:" in contract_code:
            _, expiry = contract_code.split("~F:", 1)
            return "futures", self._parse_expiry(expiry), "others", "0"
        if "~O:" in contract_code:
            parts = contract_code.split("~O:", 1)[1].split(":")
            expiry = self._parse_expiry(parts[0]) if parts else None
            right = parts[1].lower() if len(parts) > 1 else "others"
            strike_price = parts[2] if len(parts) > 2 else "0"
            return "options", expiry, right, strike_price
        if product_group == "EQUITY":
            return "cash", None, None, None
        return product_group.lower() if product_group else "unknown", None, None, None

    @staticmethod
    def _parse_expiry(expiry_text: str) -> datetime.date | None:
        try:
            return datetime.strptime(expiry_text.strip(), "%d-%b-%Y").date()
        except ValueError:
            return None

    @staticmethod
    def _parse_int(value: str | None) -> int | None:
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None

    @staticmethod
    def _normalize_alias(alias: str) -> str:
        return re.sub(r"[^A-Z0-9]", "", alias.upper())

    @staticmethod
    def _row_is_from_csv(row: dict[str, str]) -> bool:
        return row.get("__source_name") == "stock_script_csv"

    def _csv_available(self) -> bool:
        csv_path = self._resolve_csv_path()
        return bool(csv_path and csv_path.exists())

    def _resolve_csv_path(self) -> Path | None:
        if not self.stock_script_csv_path:
            return None

        csv_path = Path(self.stock_script_csv_path)
        if csv_path.is_absolute():
            return csv_path

        backend_root = Path(__file__).resolve().parents[2]
        return backend_root / csv_path

    @staticmethod
    def _serialize_run(run: MasterContractRun | None) -> dict[str, Any] | None:
        if not run:
            return None
        return {
            "status": run.status,
            "source_name": run.source_name,
            "source_checksum": run.source_checksum,
            "row_count": run.row_count,
            "alias_count": run.alias_count,
            "warning_count": run.warning_count,
            "error_message": run.error_message,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }

    @staticmethod
    def _verified_aliases() -> list[dict[str, str]]:
        return [
            {"display_symbol": "RELIANCE", "broker_symbol": "RELIND"},
            {"display_symbol": "ADANIPORTS", "broker_symbol": "ADAPOR"},
            {"display_symbol": "SBIN", "broker_symbol": "STABAN"},
            {"display_symbol": "BANKNIFTY", "broker_symbol": "CNXBAN"},
        ]
