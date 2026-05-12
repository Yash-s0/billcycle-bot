from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import people_keyboard, skip_keyboard, transactions_keyboard
from ..models import Payment, ReimbursementStatus, Transaction
from ..services.reports import (
    format_inr,
    list_people_pending_summary,
    pending_transactions_for_person,
    outstanding_amount_for_transaction,
)
from ..states import MarkPaidStates
from .common import get_user_by_telegram_id, parse_positive_decimal

router = Router(name=__name__)


@router.message(Command("mark_paid"))
async def mark_paid_command(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("No profile found. Use /start first.")
            return

        people_summary = await list_people_pending_summary(session, user.id)

    if not people_summary:
        await message.answer("No pending reimbursements right now.")
        return

    rows = [
        (item.person_id, f"{item.person_name} • {format_inr(item.pending_amount)} ({item.transaction_count} txns)")
        for item in people_summary
    ]

    await state.clear()
    await state.set_state(MarkPaidStates.person)
    await state.update_data(user_id=user.id)
    await message.answer("Select person:", reply_markup=people_keyboard(rows))


@router.callback_query(MarkPaidStates.person, F.data.startswith("person:"))
async def mark_paid_select_person(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return

    await callback.answer()
    person_id = int(callback.data.split(":", maxsplit=1)[1])

    data = await state.get_data()
    user_id = int(data["user_id"])

    async with session_maker() as session:
        pending_txns = await pending_transactions_for_person(session, user_id, person_id)

    if not pending_txns:
        await callback.message.answer("No pending transactions for this person.")
        await state.clear()
        return

    rows = [
        (
            item.transaction_id,
            f"ID {item.transaction_id} | {item.txn_date.isoformat()} | {item.merchant} | "
            f"Pending {format_inr(item.pending_amount)}",
        )
        for item in pending_txns
    ]

    await state.update_data(person_id=person_id)
    await state.set_state(MarkPaidStates.transaction)
    await callback.message.answer("Select pending transaction:", reply_markup=transactions_keyboard(rows))


@router.callback_query(MarkPaidStates.transaction, F.data.startswith("txn:"))
async def mark_paid_select_transaction(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return

    await callback.answer()
    transaction_id = int(callback.data.split(":", maxsplit=1)[1])

    data = await state.get_data()
    user_id = int(data["user_id"])

    async with session_maker() as session:
        pending_amount = await outstanding_amount_for_transaction(session, user_id, transaction_id)

    if pending_amount <= Decimal("0"):
        await callback.message.answer("This transaction is already fully paid.")
        await state.clear()
        return

    await state.update_data(transaction_id=transaction_id, pending_amount=str(pending_amount))
    await state.set_state(MarkPaidStates.amount)
    await callback.message.answer(
        f"Pending amount: {format_inr(pending_amount)}\nEnter amount paid now (or type 'full')."
    )


@router.message(MarkPaidStates.amount)
async def mark_paid_amount(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    pending_amount = Decimal(str(data["pending_amount"]))

    raw = (message.text or "").strip().lower()
    if raw == "full":
        amount = pending_amount
    else:
        parsed = parse_positive_decimal(raw)
        if parsed is None:
            await message.answer("Amount must be a positive number or 'full'. Enter amount paid:")
            return
        amount = parsed

    if amount > pending_amount:
        await message.answer(
            f"Amount cannot exceed pending balance ({format_inr(pending_amount)}). Enter a valid amount:"
        )
        return

    await state.update_data(amount_paid=str(amount))
    await state.set_state(MarkPaidStates.notes)
    await message.answer("Add notes (optional). Send 'skip' to skip.", reply_markup=skip_keyboard("mark_paid_note"))


@router.callback_query(MarkPaidStates.notes, F.data == "mark_paid_note:skip")
async def mark_paid_skip_note(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return
    await callback.answer()
    await _save_payment(callback.message, state, session_maker, notes=None)


@router.message(MarkPaidStates.notes)
async def mark_paid_note(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    text = (message.text or "").strip()
    notes = None if not text or text.lower() == "skip" else text
    await _save_payment(message, state, session_maker, notes=notes)


async def _save_payment(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
    notes: str | None,
) -> None:
    data = await state.get_data()
    user_id = int(data["user_id"])
    person_id = int(data["person_id"])
    transaction_id = int(data["transaction_id"])
    amount_paid = Decimal(str(data["amount_paid"]))

    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(Transaction.id == transaction_id, Transaction.user_id == user_id)
        )
        if not txn:
            await state.clear()
            await message.answer("Transaction not found.")
            return

        existing_paid = (
            await session.scalar(
                select(func.coalesce(func.sum(Payment.amount_paid), 0)).where(
                    Payment.user_id == user_id,
                    Payment.transaction_id == transaction_id,
                )
            )
            or Decimal("0")
        )

        outstanding = max(Decimal("0"), Decimal(str(txn.final_amount)) - Decimal(str(existing_paid)))
        if amount_paid > outstanding:
            await state.clear()
            await message.answer(
                f"Payment exceeds pending balance ({format_inr(outstanding)}). Please start /mark_paid again."
            )
            return

        payment = Payment(
            user_id=user_id,
            transaction_id=transaction_id,
            person_id=person_id,
            amount_paid=amount_paid,
            notes=notes,
        )
        session.add(payment)

        remaining = outstanding - amount_paid
        txn.reimbursement_status = ReimbursementStatus.PAID if remaining <= 0 else ReimbursementStatus.PARTIAL
        await session.commit()

    await state.clear()
    await message.answer(
        f"Payment recorded: {format_inr(amount_paid)}\n"
        f"Transaction ID: {transaction_id}\n"
        f"Status: {'paid' if remaining <= 0 else 'partial'}"
    )
