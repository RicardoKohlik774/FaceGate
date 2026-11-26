"""Database tables, as Python classes (SQLAlchemy).

Each class is one table and each attribute one column. Alembic compares these
classes with the database and writes the migration that creates or changes
the tables (see database/README.md). The design is in docs/PLAN.md, section 2.

Conventions:
- every time is stored in UTC (TIMESTAMPTZ);
- money is a whole number of Czech crowns (499 = 499 Kč), so there are no
  rounding errors and no other currency;
- a column with fixed values ("status") is TEXT with a CHECK rule, which is
  easier to change later than a PostgreSQL enum type.

Only the tables needed by step 4 exist so far. Consents, payments, entry codes
and admins come with the steps that use them.
"""
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Gives every constraint a predictable name, e.g. "ck_users_status". Alembic
# needs the names to change or drop a constraint later.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def created_at_column() -> Mapped[datetime]:
    """A "created at" time that the database fills in itself."""
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def one_of(column: str, *values: str) -> str:
    """SQL rule: the column must hold one of the given values."""
    allowed = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({allowed})"


class User(Base):
    """A customer. Identity comes from BankID; there is no password."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # BankID's stable ID for the person; empty for demo users.
    bankid_sub: Mapped[str | None] = mapped_column(Text, unique=True)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        # pending = registration not finished
        CheckConstraint(one_of("status", "pending", "active", "deactivated"), name="status"),
    )


class FaceEmbedding(Base):
    """The face of a user as encrypted numbers. Photos are never stored."""

    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    # CASCADE: deleting the user deletes their face data too.
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # 128 numbers, encrypted by the backend before they are saved.
    embedding_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    # Embeddings from different models cannot be compared, so we keep which one.
    model_name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


class MembershipPlan(Base):
    """What can be bought, e.g. "Month" for 30 days."""

    __tablename__ = "membership_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    duration_days: Mapped[int] = mapped_column(Integer)
    price_czk: Mapped[int] = mapped_column(Integer)  # whole crowns: 499 = 499 Kč
    is_active: Mapped[bool] = mapped_column(server_default="true")

    __table_args__ = (
        CheckConstraint("duration_days > 0", name="duration_days_positive"),
        CheckConstraint("price_czk >= 0", name="price_not_negative"),
    )


class Membership(Base):
    """A plan that a user bought, and when it is valid."""

    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # No CASCADE: a plan that someone bought cannot be deleted.
    plan_id: Mapped[int] = mapped_column(ForeignKey("membership_plans.id"))
    status: Mapped[str] = mapped_column(Text, server_default="pending_payment")
    # Empty until the payment is confirmed.
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at_column()

    __table_args__ = (
        CheckConstraint(one_of("status", "pending_payment", "active", "cancelled"), name="status"),
        CheckConstraint("valid_until > valid_from", name="valid_until_after_valid_from"),
    )


class Device(Base):
    """A camera at the door. Its direction decides entry or exit."""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text)  # e.g. "Front door - outside"
    direction: Mapped[str] = mapped_column(Text)
    # The device logs in with a secret key; only its hash is stored.
    api_key_hash: Mapped[str] = mapped_column(Text, unique=True)
    is_active: Mapped[bool] = mapped_column(server_default="true")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(one_of("direction", "entry", "exit"), name="direction"),
    )


class AccessEvent(Base):
    """One recognition attempt at the door, including denied ones and strangers."""

    __tablename__ = "access_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"))
    # Copied from the device, so history stays right if the device changes later.
    direction: Mapped[str] = mapped_column(Text)
    # Empty = unknown face, or the user was deleted (SET NULL keeps the event).
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    method: Mapped[str] = mapped_column(Text)
    result: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    # Best match score; kept to tune the threshold later.
    similarity: Mapped[float | None] = mapped_column(Float)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    __table_args__ = (
        CheckConstraint(one_of("direction", "entry", "exit"), name="direction"),
        CheckConstraint(one_of("method", "face", "code"), name="method"),
        CheckConstraint(one_of("result", "granted", "denied"), name="result"),
        CheckConstraint(
            one_of(
                "reason",
                "ok",
                "unknown_face",
                "no_valid_membership",
                "user_deactivated",
                "liveness_failed",
                "bad_code",
            ),
            name="reason",
        ),
    )


class Visit(Base):
    """One stay: entry time and exit time. Exit empty = still inside."""

    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_reason: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(one_of("close_reason", "exit", "reentry", "auto_closed"), name="close_reason"),
        CheckConstraint("exited_at >= entered_at", name="exit_not_before_entry"),
        # An open visit has no close reason; a closed one must have one.
        CheckConstraint("(exited_at IS NULL) = (close_reason IS NULL)", name="closed_with_reason"),
    )
