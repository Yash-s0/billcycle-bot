from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReimbursementStatus(str, Enum):
    OWN = "own"
    PENDING = "pending"
    PARTIAL = "partial"
    PAID = "paid"


class PaymentMode(str, Enum):
    CARD = "card"
    UPI = "upi"
    CASH = "cash"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    cards: Mapped[list["Card"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    people: Mapped[list["Person"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Transaction.user_id",
    )
    added_transactions: Mapped[list["Transaction"]] = relationship(
        foreign_keys="Transaction.added_by_user_id",
        back_populates="added_by_user",
    )
    payments: Mapped[list["Payment"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    shared_expense_access_as_owner: Mapped[list["SharedExpenseAccess"]] = relationship(
        foreign_keys="SharedExpenseAccess.owner_user_id",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    shared_expense_access_as_collaborator: Mapped[list["SharedExpenseAccess"]] = relationship(
        foreign_keys="SharedExpenseAccess.collaborator_user_id",
        back_populates="collaborator",
        cascade="all, delete-orphan",
    )


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    bank_name: Mapped[str] = mapped_column(String(120))
    card_name: Mapped[str] = mapped_column(String(120))
    billing_day: Mapped[int] = mapped_column(Integer)
    due_day: Mapped[int] = mapped_column(Integer)
    credit_limit: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="cards")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="card")


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_people_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="people")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="person")
    payments: Mapped[list["Payment"]] = relationship(back_populates="person")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    added_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), nullable=True, index=True)
    payment_mode: Mapped[PaymentMode] = mapped_column(
        SAEnum(
            PaymentMode,
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=PaymentMode.CARD,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    cashback_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    final_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    txn_date: Mapped[date] = mapped_column(Date)
    is_for_someone_else: Mapped[bool] = mapped_column(Boolean, default=False)
    person_id: Mapped[Optional[int]] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"), nullable=True, index=True)
    reimbursement_status: Mapped[ReimbursementStatus] = mapped_column(
        SAEnum(
            ReimbursementStatus,
            native_enum=False,
            validate_strings=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=ReimbursementStatus.OWN,
    )
    category: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="transactions", foreign_keys=[user_id])
    added_by_user: Mapped[User] = relationship(back_populates="added_transactions", foreign_keys=[added_by_user_id])
    card: Mapped[Optional[Card]] = relationship(back_populates="transactions")
    person: Mapped[Optional[Person]] = relationship(back_populates="transactions")
    payments: Mapped[list["Payment"]] = relationship(back_populates="transaction", cascade="all, delete-orphan")


class SharedExpenseAccess(Base):
    __tablename__ = "shared_expense_access"
    __table_args__ = (UniqueConstraint("owner_user_id", "collaborator_user_id", name="uq_shared_owner_collaborator"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    collaborator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(foreign_keys=[owner_user_id], back_populates="shared_expense_access_as_owner")
    collaborator: Mapped[User] = relationship(
        foreign_keys=[collaborator_user_id],
        back_populates="shared_expense_access_as_collaborator",
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship(back_populates="payments")
    transaction: Mapped[Transaction] = relationship(back_populates="payments")
    person: Mapped[Person] = relationship(back_populates="payments")
