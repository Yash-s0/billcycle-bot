from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Card, Payment, PaymentMode, Person, Transaction, User
from .billing import get_current_billing_cycle, get_next_due_date

ZERO = Decimal("0")


@dataclass(slots=True)
class PersonPendingSummary:
    person_id: int
    person_name: str
    pending_amount: Decimal
    cashback_amount: Decimal
    total_amount: Decimal
    transaction_count: int


@dataclass(slots=True)
class PendingTransactionItem:
    transaction_id: int
    card_label: str
    txn_date: date
    notes: str
    final_amount: Decimal
    cashback_amount: Decimal
    recoverable_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal


@dataclass(slots=True)
class CardSummaryData:
    card_label: str
    cycle_start: date
    cycle_end: date
    total_spend: Decimal
    total_discounts: Decimal
    total_cashback: Decimal
    pending_receivables: Decimal
    upcoming_due_date: date
    recent_transactions: list[PendingTransactionItem]


@dataclass(slots=True)
class CardBreakdownItem:
    card_label: str
    total_billed: Decimal
    total_discount: Decimal
    total_cashback: Decimal
    effective_net: Decimal


@dataclass(slots=True)
class MonthlyReportData:
    month_start: date
    month_end: date
    total_spent: Decimal
    total_discounts: Decimal
    total_cashback: Decimal
    net_payable: Decimal
    amount_owed_by_others: Decimal
    top_notes: list[tuple[str, Decimal]]
    card_breakdown: list[CardBreakdownItem]


@dataclass(slots=True)
class RecentTransactionRow:
    transaction_id: int
    card_label: str
    payment_mode: str
    owner_user_id: int
    owner_name: str
    added_by_user_id: int
    added_by_name: str
    txn_date: date
    amount: Decimal
    discount_amount: Decimal
    cashback_amount: Decimal
    final_amount: Decimal
    notes: str
    reimbursement_status: str
    is_for_someone_else: bool
    person_name: str | None


def _to_decimal(value: Decimal | int | float | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def format_inr(value: Decimal | int | float) -> str:
    quantized = _to_decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"₹{quantized:,.2f}"


def month_start_end(month: date) -> tuple[date, date]:
    start = month.replace(day=1)
    if start.month == 12:
        next_month = date(start.year + 1, 1, 1)
    else:
        next_month = date(start.year, start.month + 1, 1)
    end = next_month.fromordinal(next_month.toordinal() - 1)
    return start, end


def last_n_month_starts(today: date, count: int = 6) -> list[date]:
    months: list[date] = []
    cursor = today.replace(day=1)
    for _ in range(count):
        months.append(cursor)
        if cursor.month == 1:
            cursor = date(cursor.year - 1, 12, 1)
        else:
            cursor = date(cursor.year, cursor.month - 1, 1)
    return months


async def list_recent_transactions(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
    offset: int = 0,
) -> list[RecentTransactionRow]:
    owner_user = aliased(User)
    added_by_user = aliased(User)
    query = (
        select(
            Transaction,
            Card.card_name,
            Person.name,
            owner_user.full_name,
            added_by_user.full_name,
        )
        .outerjoin(Card, Transaction.card_id == Card.id)
        .outerjoin(Person, Person.id == Transaction.person_id)
        .join(owner_user, owner_user.id == Transaction.user_id)
        .join(added_by_user, added_by_user.id == Transaction.added_by_user_id)
        .where(
            or_(
                Transaction.user_id == user_id,
                Transaction.added_by_user_id == user_id,
            )
        )
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
        .offset(max(offset, 0))
        .limit(limit)
    )
    rows = (await session.execute(query)).all()
    result: list[RecentTransactionRow] = []
    for txn, card_name, person_name, owner_name, added_by_name in rows:
        if txn.payment_mode == PaymentMode.CARD:
            card_label = card_name or "Card"
        elif txn.payment_mode == PaymentMode.UPI:
            card_label = "UPI"
        else:
            card_label = "Cash"
        result.append(
            RecentTransactionRow(
                transaction_id=txn.id,
                card_label=card_label,
                payment_mode=txn.payment_mode.value,
                owner_user_id=txn.user_id,
                owner_name=owner_name,
                added_by_user_id=txn.added_by_user_id,
                added_by_name=added_by_name,
                txn_date=txn.txn_date,
                amount=txn.amount,
                discount_amount=txn.discount_amount,
                cashback_amount=txn.cashback_amount,
                final_amount=txn.final_amount,
                notes=txn.notes or "-",
                reimbursement_status=txn.reimbursement_status.value,
                is_for_someone_else=bool(txn.is_for_someone_else),
                person_name=person_name,
            )
        )
    return result


async def list_people_pending_summary(session: AsyncSession, user_id: int) -> list[PersonPendingSummary]:
    paid_subquery = (
        select(
            Payment.transaction_id.label("txn_id"),
            func.coalesce(func.sum(Payment.amount_paid), 0).label("paid_total"),
        )
        .where(Payment.user_id == user_id)
        .group_by(Payment.transaction_id)
        .subquery()
    )

    recoverable_expr = Transaction.final_amount - Transaction.cashback_amount
    outstanding_expr = recoverable_expr - func.coalesce(paid_subquery.c.paid_total, 0)
    open_cashback_expr = case((outstanding_expr > 0, Transaction.cashback_amount), else_=0)
    query = (
        select(
            Person.id,
            Person.name,
            func.sum(case((outstanding_expr > 0, 1), else_=0)),
            func.coalesce(func.sum(outstanding_expr), 0),
            func.coalesce(func.sum(open_cashback_expr), 0),
        )
        .join(
            Transaction,
            and_(
                Transaction.person_id == Person.id,
                Transaction.user_id == user_id,
                Transaction.is_for_someone_else.is_(True),
            ),
        )
        .outerjoin(paid_subquery, paid_subquery.c.txn_id == Transaction.id)
        .where(Person.user_id == user_id)
        .group_by(Person.id, Person.name)
        .having(func.sum(outstanding_expr) > 0)
        .order_by(func.sum(outstanding_expr).desc(), Person.name.asc())
    )

    rows = (await session.execute(query)).all()
    return [
        PersonPendingSummary(
            person_id=person_id,
            person_name=name,
            transaction_count=int(count or 0),
            pending_amount=_to_decimal(total_pending),
            cashback_amount=_to_decimal(total_cashback),
            total_amount=_to_decimal(total_pending) + _to_decimal(total_cashback),
        )
        for person_id, name, count, total_pending, total_cashback in rows
    ]


async def pending_transactions_for_person(
    session: AsyncSession,
    user_id: int,
    person_id: int,
) -> list[PendingTransactionItem]:
    paid_subquery = (
        select(
            Payment.transaction_id.label("txn_id"),
            func.coalesce(func.sum(Payment.amount_paid), 0).label("paid_total"),
        )
        .where(Payment.user_id == user_id)
        .group_by(Payment.transaction_id)
        .subquery()
    )

    query = (
        select(
            Transaction,
            Card.card_name,
            func.coalesce(paid_subquery.c.paid_total, 0).label("paid_total"),
        )
        .outerjoin(Card, Card.id == Transaction.card_id)
        .outerjoin(paid_subquery, paid_subquery.c.txn_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.person_id == person_id,
            Transaction.is_for_someone_else.is_(True),
        )
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    )

    rows = (await session.execute(query)).all()
    items: list[PendingTransactionItem] = []
    for txn, card_name, paid_total in rows:
        if txn.payment_mode == PaymentMode.CARD:
            source_label = card_name or "Card"
        elif txn.payment_mode == PaymentMode.UPI:
            source_label = "UPI"
        else:
            source_label = "Cash"
        paid_amount = _to_decimal(paid_total)
        recoverable_amount = max(ZERO, _to_decimal(txn.final_amount) - _to_decimal(txn.cashback_amount))
        pending_amount = max(ZERO, recoverable_amount - paid_amount)
        if pending_amount <= ZERO:
            continue
        items.append(
            PendingTransactionItem(
                transaction_id=txn.id,
                card_label=source_label,
                txn_date=txn.txn_date,
                notes=txn.notes or "-",
                final_amount=_to_decimal(txn.final_amount),
                cashback_amount=_to_decimal(txn.cashback_amount),
                recoverable_amount=recoverable_amount,
                paid_amount=paid_amount,
                pending_amount=pending_amount,
            )
        )
    return items


async def outstanding_amount_for_transaction(session: AsyncSession, user_id: int, transaction_id: int) -> Decimal:
    payment_total_query = (
        select(func.coalesce(func.sum(Payment.amount_paid), 0))
        .where(Payment.user_id == user_id, Payment.transaction_id == transaction_id)
    )
    paid_total = _to_decimal((await session.scalar(payment_total_query)) or ZERO)

    txn = await session.scalar(
        select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
    )
    if not txn:
        return ZERO
    recoverable_amount = max(ZERO, _to_decimal(txn.final_amount) - _to_decimal(txn.cashback_amount))
    return max(ZERO, recoverable_amount - paid_total)


async def get_card_summary_data(
    session: AsyncSession,
    user_id: int,
    card_id: int,
    today: date,
) -> CardSummaryData | None:
    card = await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))
    if not card:
        return None

    cycle_start, cycle_end = get_current_billing_cycle(card.billing_day, today)
    upcoming_due_date = get_next_due_date(card.due_day, today)

    paid_subquery = (
        select(
            Payment.transaction_id.label("txn_id"),
            func.coalesce(func.sum(Payment.amount_paid), 0).label("paid_total"),
        )
        .where(Payment.user_id == user_id)
        .group_by(Payment.transaction_id)
        .subquery()
    )

    cycle_transactions_query = (
        select(
            Transaction,
            func.coalesce(paid_subquery.c.paid_total, 0).label("paid_total"),
        )
        .outerjoin(paid_subquery, paid_subquery.c.txn_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.card_id == card_id,
            Transaction.txn_date >= cycle_start,
            Transaction.txn_date <= cycle_end,
        )
        .order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    )
    cycle_rows = (await session.execute(cycle_transactions_query)).all()

    total_spend = ZERO
    total_discounts = ZERO
    total_cashback = ZERO
    pending_receivables = ZERO
    recent_transactions: list[PendingTransactionItem] = []

    for idx, (txn, paid_total) in enumerate(cycle_rows):
        total_spend += _to_decimal(txn.final_amount)
        total_discounts += _to_decimal(txn.discount_amount)
        total_cashback += _to_decimal(txn.cashback_amount)

        paid_amount = _to_decimal(paid_total)
        recoverable_amount = max(ZERO, _to_decimal(txn.final_amount) - _to_decimal(txn.cashback_amount))
        pending_amount = max(ZERO, recoverable_amount - paid_amount)

        if txn.is_for_someone_else and pending_amount > ZERO:
            pending_receivables += pending_amount

        if idx < 5:
            recent_transactions.append(
                PendingTransactionItem(
                    transaction_id=txn.id,
                    card_label=card.card_name,
                    txn_date=txn.txn_date,
                    notes=txn.notes or "-",
                    final_amount=_to_decimal(txn.final_amount),
                    cashback_amount=_to_decimal(txn.cashback_amount),
                    recoverable_amount=recoverable_amount,
                    paid_amount=paid_amount,
                    pending_amount=pending_amount,
                )
            )

    return CardSummaryData(
        card_label=card.card_name,
        cycle_start=cycle_start,
        cycle_end=cycle_end,
        total_spend=total_spend,
        total_discounts=total_discounts,
        total_cashback=total_cashback,
        pending_receivables=pending_receivables,
        upcoming_due_date=upcoming_due_date,
        recent_transactions=recent_transactions,
    )


async def get_period_report_data(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date,
) -> MonthlyReportData:
    paid_subquery = (
        select(
            Payment.transaction_id.label("txn_id"),
            func.coalesce(func.sum(Payment.amount_paid), 0).label("paid_total"),
        )
        .where(Payment.user_id == user_id)
        .group_by(Payment.transaction_id)
        .subquery()
    )

    txns_query = (
        select(Transaction, func.coalesce(paid_subquery.c.paid_total, 0).label("paid_total"))
        .outerjoin(paid_subquery, paid_subquery.c.txn_id == Transaction.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.txn_date >= start_date,
            Transaction.txn_date <= end_date,
        )
    )

    txn_rows = (await session.execute(txns_query)).all()

    total_spent = ZERO
    total_discounts = ZERO
    total_cashback = ZERO
    net_payable = ZERO
    amount_owed_by_others = ZERO

    for txn, paid_total in txn_rows:
        discount = _to_decimal(txn.discount_amount)
        cashback = _to_decimal(txn.cashback_amount)
        final_amount = _to_decimal(txn.final_amount)
        paid_amount = _to_decimal(paid_total)

        total_spent += final_amount
        total_discounts += discount
        total_cashback += cashback
        if txn.payment_mode == PaymentMode.CARD:
            net_payable += max(ZERO, final_amount - cashback)

        if txn.is_for_someone_else:
            recoverable_amount = max(ZERO, final_amount - cashback)
            outstanding = max(ZERO, recoverable_amount - paid_amount)
            amount_owed_by_others += outstanding

    notes_expr = func.coalesce(Transaction.notes, "No notes")
    notes_query = (
        select(
            notes_expr.label("notes"),
            func.coalesce(func.sum(Transaction.final_amount), 0).label("total"),
        )
        .where(
            Transaction.user_id == user_id,
            Transaction.txn_date >= start_date,
            Transaction.txn_date <= end_date,
        )
        .group_by(notes_expr)
        .order_by(func.sum(Transaction.final_amount).desc())
        .limit(5)
    )
    top_notes = [
        (name, _to_decimal(total))
        for name, total in (await session.execute(notes_query)).all()
    ]

    source_label_expr = case(
        (Transaction.payment_mode == PaymentMode.CARD, func.coalesce(Card.card_name, "Card")),
        (Transaction.payment_mode == PaymentMode.UPI, "UPI"),
        else_="Cash",
    )
    card_query = (
        select(
            source_label_expr.label("source_label"),
            func.coalesce(func.sum(Transaction.final_amount), 0),
            func.coalesce(func.sum(Transaction.discount_amount), 0),
            func.coalesce(func.sum(Transaction.cashback_amount), 0),
        )
        .outerjoin(Card, Card.id == Transaction.card_id)
        .where(
            Transaction.user_id == user_id,
            Transaction.txn_date >= start_date,
            Transaction.txn_date <= end_date,
        )
        .group_by(source_label_expr)
        .order_by(func.sum(Transaction.final_amount).desc())
    )

    card_breakdown: list[CardBreakdownItem] = []
    for source_label, billed_total, discount_total, cashback_total in (await session.execute(card_query)).all():
        billed_decimal = _to_decimal(billed_total)
        cashback_decimal = _to_decimal(cashback_total)
        card_breakdown.append(
            CardBreakdownItem(
                card_label=source_label,
                total_billed=billed_decimal,
                total_discount=_to_decimal(discount_total),
                total_cashback=cashback_decimal,
                effective_net=max(ZERO, billed_decimal - cashback_decimal),
            )
        )

    return MonthlyReportData(
        month_start=start_date,
        month_end=end_date,
        total_spent=total_spent,
        total_discounts=total_discounts,
        total_cashback=total_cashback,
        net_payable=net_payable,
        amount_owed_by_others=amount_owed_by_others,
        top_notes=top_notes,
        card_breakdown=card_breakdown,
    )


async def get_monthly_report_data(
    session: AsyncSession,
    user_id: int,
    month: date,
) -> MonthlyReportData:
    month_start, month_end = month_start_end(month)
    return await get_period_report_data(session, user_id, month_start, month_end)


def sum_amounts(values: Iterable[Decimal]) -> Decimal:
    total = ZERO
    for value in values:
        total += _to_decimal(value)
    return total
