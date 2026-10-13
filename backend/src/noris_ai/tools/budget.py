"""Durable conservative accounting. All mutators lock owner before chat resources."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from noris_ai.chat.repository import ModelDatabase, utc_now
from noris_ai.db.base import Base
from noris_ai.tools.errors import ToolError


@dataclass(frozen=True)
class BudgetAmount:
    calls: int = 0
    tokens: int = 0
    bytes: int = 0
    cost: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 0 for v in (self.calls, self.tokens, self.bytes)):
            raise ValueError("Invalid budget amount")
        if (
            not self.cost.is_finite()
            or self.cost < 0
            or cast(int, self.cost.as_tuple().exponent) < -8
        ):
            raise ValueError("Invalid cost bound")

    def fits(self, limit: "BudgetAmount") -> bool:
        return all(getattr(self, k) <= getattr(limit, k) for k in DIMENSIONS)


DIMENSIONS = ("calls", "tokens", "bytes", "cost")
BudgetBucket = Literal["tools", "text"]


class BudgetDay(Base):
    __tablename__ = "chat_budget_day"
    __table_args__ = (
        CheckConstraint("bucket IN ('tools', 'text')", name="budget_bucket"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="budget_currency"),
        CheckConstraint(
            "calls >= 0 AND tokens >= 0 AND bytes >= 0 AND cost >= 0 AND cost <> 'NaN'::numeric",
            name="budget_amount",
        ),
    )
    owner_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    budget_day: Mapped[date] = mapped_column(Date, primary_key=True)
    bucket: Mapped[str] = mapped_column(Text, primary_key=True)
    currency: Mapped[str] = mapped_column(Text, primary_key=True)
    calls: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=Decimal(0))


class BudgetReservation(Base):
    __tablename__ = "chat_budget_reservation"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "run_id", "id", name="uq_chat_budget_reservation_owner_run_id"
        ),
        CheckConstraint("bucket <> 'tools' OR run_id IS NOT NULL", name="reservation_tool_scope"),
        ForeignKeyConstraint(
            ["owner_id", "run_id"],
            ["chat_tool_run.owner_id", "chat_tool_run.id"],
            name="reservation_run",
        ),
        ForeignKeyConstraint(
            ["owner_id", "budget_day", "bucket", "currency"],
            [
                "chat_budget_day.owner_id",
                "chat_budget_day.budget_day",
                "chat_budget_day.bucket",
                "chat_budget_day.currency",
            ],
            name="reservation_day",
        ),
        Index("ix_chat_budget_reservation_run_id", "run_id"),
        CheckConstraint("bucket IN ('tools', 'text')", name="reservation_bucket"),
        CheckConstraint(
            "state IN ('reserved', 'dispatched', 'accounted', 'released', 'unknown')",
            name="reservation_state",
        ),
        CheckConstraint(
            "calls >= 0 AND tokens >= 0 AND bytes >= 0 AND cost >= 0 AND cost <> 'NaN'::numeric",
            name="reservation_amount",
        ),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="reservation_currency"),
        CheckConstraint(
            "length(phase_key) BETWEEN 1 AND 200 AND attempt BETWEEN 1 AND 2",
            name="reservation_phase",
        ),
        CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="reservation_digest"),
        CheckConstraint(
            "measured IS NULL OR (jsonb_typeof(measured) = 'object' "
            "AND octet_length(measured::text) <= 1024)",
            name="reservation_measured",
        ),
    )
    # Composite PK is also the idempotency key across UTC day boundaries.
    owner_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    bucket: Mapped[str] = mapped_column(Text, primary_key=True)
    phase_key: Mapped[str] = mapped_column(Text, primary_key=True)
    attempt: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True, default=uuid4)
    run_id: Mapped[UUID | None] = mapped_column(Uuid)
    budget_day: Mapped[date] = mapped_column(Date, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    input_digest: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False, default="reserved")
    calls: Mapped[int] = mapped_column(BigInteger, nullable=False)
    tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    measured: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


async def lock_owner(session: AsyncSession, owner_id: UUID) -> None:
    await bound_transaction(session)
    # Stable signed bigint; owner UUID collision only serializes unrelated owners.
    key = int.from_bytes(owner_id.bytes[:8], "big", signed=True)
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


async def bound_transaction(session: AsyncSession) -> None:
    # Never let a blocked claim/cancel outlive an HTTP tool timeout indefinitely.
    # SET LOCAL applies only to this transaction, including on pooled connections.
    await session.execute(text("SET LOCAL lock_timeout = '1500ms'"))
    await session.execute(text("SET LOCAL statement_timeout = '3000ms'"))


class BudgetCoordinator:
    def __init__(self, database: ModelDatabase) -> None:
        self.database = database

    async def reserve_in(
        self,
        session: AsyncSession,
        owner: UUID,
        bucket: BudgetBucket,
        phase: str,
        attempt: int,
        digest: str,
        amount: BudgetAmount,
        limit: "BudgetAmount",
        currency: str,
        *,
        run_id: UUID | None = None,
    ) -> BudgetReservation:
        # Caller holds owner lock; runtime adds scope checks in this same transaction.
        existing = await session.get(BudgetReservation, (owner, bucket, phase, attempt))
        if existing is not None:
            if (
                existing.input_digest != digest
                or existing.currency != currency
                or existing.run_id != run_id
                or any(getattr(existing, k) != getattr(amount, k) for k in DIMENSIONS)
            ):
                raise ToolError("TOOL_CONFLICT")
            return existing
        today = utc_now().date()
        day = await session.get(BudgetDay, (owner, today, bucket, currency))
        if day is None:
            day = BudgetDay(
                owner_id=owner,
                budget_day=today,
                bucket=bucket,
                currency=currency,
                calls=0,
                tokens=0,
                bytes=0,
                cost=Decimal(0),
            )
            session.add(day)
        total = BudgetAmount(**{k: getattr(day, k) + getattr(amount, k) for k in DIMENSIONS})
        if not total.fits(limit):
            raise ToolError("BUDGET_LIMIT")
        for k in DIMENSIONS:
            setattr(day, k, getattr(total, k))
        reservation = BudgetReservation(
            owner_id=owner,
            bucket=bucket,
            phase_key=phase,
            attempt=attempt,
            run_id=run_id,
            budget_day=today,
            currency=currency,
            input_digest=digest,
            **{k: getattr(amount, k) for k in DIMENSIONS},
        )
        session.add(reservation)
        await session.flush()
        return reservation

    async def settle_in(
        self,
        session: AsyncSession,
        reservation: BudgetReservation,
        *,
        unused: bool,
        unknown: bool = False,
    ) -> None:
        if reservation.state in ("accounted", "released", "unknown"):
            return
        if unused and reservation.state == "reserved":
            day = await session.get(
                BudgetDay,
                (
                    reservation.owner_id,
                    reservation.budget_day,
                    reservation.bucket,
                    reservation.currency,
                ),
            )
            if day is None:
                raise ToolError("TOOL_STATE_CONFLICT")
            for k in DIMENSIONS:
                setattr(day, k, getattr(day, k) - getattr(reservation, k))
            reservation.state = "released"
        else:
            # Unknown usage is never represented as zero; full ceiling stays charged.
            reservation.state = "unknown" if unknown else "accounted"

    async def reserve_text(
        self, owner: UUID, phase: str, digest: str, tokens: int, limit: int
    ) -> None:
        async with self.database() as session, session.begin():
            await lock_owner(session, owner)
            reservation = await self.reserve_in(
                session,
                owner,
                "text",
                phase,
                1,
                digest,
                BudgetAmount(calls=1, tokens=tokens),
                BudgetAmount(calls=10_000_000, tokens=limit),
                "USD",
            )
            if reservation.state != "reserved":
                raise ToolError("TOOL_CONFLICT")

    async def dispatch_text(self, owner: UUID, phase: str) -> None:
        async with self.database() as session, session.begin():
            await lock_owner(session, owner)
            reservation = await session.get(BudgetReservation, (owner, "text", phase, 1))
            if reservation is None or reservation.state != "reserved":
                raise ToolError("TOOL_CONFLICT")
            reservation.state = "dispatched"

    async def finish_text(self, owner: UUID, phase: str, *, unknown: bool = False) -> None:
        async with self.database() as session, session.begin():
            await lock_owner(session, owner)
            reservation = await session.get(BudgetReservation, (owner, "text", phase, 1))
            if reservation is not None:
                await self.settle_in(session, reservation, unused=True, unknown=unknown)

    async def recover_text(self, owner: UUID) -> None:
        async with self.database() as session, session.begin():
            await lock_owner(session, owner)
            rows = await session.scalars(
                select(BudgetReservation).where(
                    BudgetReservation.owner_id == owner,
                    BudgetReservation.bucket == "text",
                    BudgetReservation.state.in_(("reserved", "dispatched")),
                )
            )
            for reservation in rows:
                await self.settle_in(session, reservation, unused=True, unknown=True)
