from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("exchange_code", "contract_code", name="uq_instruments_exchange_contract"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    exchange_code: Mapped[str] = mapped_column(String(16), index=True)
    broker_symbol: Mapped[str] = mapped_column(String(64), index=True)
    contract_code: Mapped[str] = mapped_column(String(128), index=True)
    display_symbol: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    instrument_group: Mapped[str | None] = mapped_column(String(32), nullable=True)
    product_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tick_size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    series: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    option_right: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strike_price: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    aliases: Mapped[list["InstrumentAlias"]] = relationship(
        back_populates="instrument",
        cascade="all, delete-orphan",
    )


class InstrumentAlias(Base):
    __tablename__ = "instrument_aliases"
    __table_args__ = (
        UniqueConstraint("alias_scope", "normalized_alias", name="uq_instrument_aliases_scope_normalized"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(128))
    normalized_alias: Mapped[str] = mapped_column(String(128), index=True)
    alias_scope: Mapped[str] = mapped_column(String(16), index=True)
    alias_type: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    instrument: Mapped[Instrument] = relationship(back_populates="aliases")


class MasterContractRun(Base):
    __tablename__ = "master_contract_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    source_name: Mapped[str] = mapped_column(String(128))
    source_checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    security_master_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    csv_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    alias_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
