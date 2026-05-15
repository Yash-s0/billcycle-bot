from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import card_bill_action_keyboard, cards_keyboard
from ..models import Card, CardBillPayment, PaymentMode, Transaction
from ..services.billing import get_current_billing_cycle, get_next_due_date
from ..services.reports import format_inr
from ..states import MarkPaidStates
from .common import card_label, get_user_by_telegram_id, parse_positive_decimal, short_text

router = Router(name=__name__)
ZERO = Decimal("0")


@dataclass(slots=True)
class CardBillPendingItem:
    card_id: int
    card_label: str
    cycle_start: date
    cycle_end: date
    due_date: date
    billed_amount: Decimal
    paid_amount: Decimal
    pending_amount: Decimal


def _is_card_bill_table_missing_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "card_bill_payments" in text
        and (
            "does not exist" in text
            or "undefined table" in text
            or "no such table" in text
        )
    )


async def _send_card_bill_setup_error(message: Message) -> None:
    await message.answer(
        "⚠️ <b>Card bill payment setup is incomplete.</b>\n"
        "Please run <code>alembic upgrade head</code>, restart the bot, then try <b>/mark_paid</b> again."
    )


async def _compute_cycle_bill_amounts(
    session: AsyncSession,
    user_id: int,
    card_id: int,
    cycle_start: date,
    cycle_end: date,
) -> tuple[Decimal, Decimal, Decimal]:
    billed_raw = await session.scalar(
        select(func.coalesce(func.sum(Transaction.final_amount - Transaction.cashback_amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.card_id == card_id,
            Transaction.payment_mode == PaymentMode.CARD,
            Transaction.txn_date >= cycle_start,
            Transaction.txn_date <= cycle_end,
        )
    )
    paid_raw = await session.scalar(
        select(func.coalesce(func.sum(CardBillPayment.amount_paid), 0)).where(
            CardBillPayment.user_id == user_id,
            CardBillPayment.card_id == card_id,
            CardBillPayment.cycle_start == cycle_start,
            CardBillPayment.cycle_end == cycle_end,
        )
    )
    billed = Decimal(str(billed_raw or 0))
    paid = Decimal(str(paid_raw or 0))
    pending = max(ZERO, billed - paid)
    return billed, paid, pending


async def _collect_card_pending_items(
    session: AsyncSession,
    user_id: int,
    cards: list[Card],
    today: date,
) -> list[CardBillPendingItem]:
    items: list[CardBillPendingItem] = []
    for card in cards:
        cycle_start, cycle_end = get_current_billing_cycle(card.billing_day, today)
        due_date = get_next_due_date(card.due_day, today)
        billed, paid, pending = await _compute_cycle_bill_amounts(
            session,
            user_id,
            card.id,
            cycle_start,
            cycle_end,
        )
        items.append(
            CardBillPendingItem(
                card_id=card.id,
                card_label=card_label(card),
                cycle_start=cycle_start,
                cycle_end=cycle_end,
                due_date=due_date,
                billed_amount=billed,
                paid_amount=paid,
                pending_amount=pending,
            )
        )
    return items


async def _show_card_bill_overview(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
    telegram_user_id: int,
) -> None:
    try:
        async with session_maker() as session:
            user = await get_user_by_telegram_id(session, telegram_user_id)
            if not user:
                await message.answer("⚠️ <b>No profile found.</b> Use <b>/start</b> first.")
                await state.clear()
                return

            cards = (
                await session.execute(
                    select(Card)
                    .where(Card.user_id == user.id)
                    .order_by(Card.bank_name.asc(), Card.card_name.asc(), Card.id.asc())
                )
            ).scalars().all()

            if not cards:
                await message.answer("📭 No cards found. Add one with <b>/add_card</b> first.")
                await state.clear()
                return

            items = await _collect_card_pending_items(session, user.id, list(cards), today=date.today())
    except Exception as exc:
        await state.clear()
        if _is_card_bill_table_missing_error(exc):
            await _send_card_bill_setup_error(message)
            return
        await message.answer("⚠️ Unable to load card bills right now. Please try again.")
        return

    lines = ["💳 <b>Card Bill Tracker</b>", "Select a card to update payment status:"]
    rows: list[tuple[int, str]] = []

    for idx, item in enumerate(items, start=1):
        lines.extend(
            [
                "",
                f"{idx}. <b>{escape(item.card_label)}</b>",
                f"• Cycle: {item.cycle_start.isoformat()} to {item.cycle_end.isoformat()}",
                f"• Billed: {format_inr(item.billed_amount)} | Paid: {format_inr(item.paid_amount)}",
                f"• <b>Pending: {format_inr(item.pending_amount)}</b> | Due: {item.due_date.isoformat()}",
            ]
        )
        rows.append((item.card_id, f"{short_text(item.card_label, 16)} • {format_inr(item.pending_amount)}"))

    await state.clear()
    await state.set_state(MarkPaidStates.card)
    await state.update_data(user_id=user.id)
    await message.answer("\n".join(lines), reply_markup=cards_keyboard(rows, prefix="bill_card", columns=2))


@router.message(Command("mark_paid"))
async def mark_paid_command(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not message.from_user:
        return
    await _show_card_bill_overview(message, state, session_maker, telegram_user_id=message.from_user.id)


@router.callback_query(MarkPaidStates.card, F.data.startswith("bill_card:"))
async def mark_paid_select_card(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        return

    await callback.answer()
    raw_card_id = callback.data.split(":", maxsplit=1)[1]
    if not raw_card_id.isdigit():
        await callback.answer("Invalid card", show_alert=True)
        return
    card_id = int(raw_card_id)

    data = await state.get_data()
    user_id = int(data["user_id"])

    try:
        async with session_maker() as session:
            card = await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))
            if not card:
                await callback.message.answer("⚠️ Card not found.")
                return

            cycle_start, cycle_end = get_current_billing_cycle(card.billing_day, date.today())
            due_date = get_next_due_date(card.due_day, date.today())
            billed, paid, pending = await _compute_cycle_bill_amounts(
                session,
                user_id,
                card.id,
                cycle_start,
                cycle_end,
            )
    except Exception as exc:
        if _is_card_bill_table_missing_error(exc):
            await _send_card_bill_setup_error(callback.message)
            await state.clear()
            return
        await callback.message.answer("⚠️ Unable to load this card bill right now. Please try again.")
        return

    if pending <= ZERO:
        await callback.message.answer(
            f"✅ <b>{escape(card_label(card))}</b> is already fully paid for this cycle.\n"
            f"Pending: {format_inr(pending)}"
        )
        return

    await state.update_data(
        card_id=card.id,
        card_name=card_label(card),
        cycle_start=cycle_start.isoformat(),
        cycle_end=cycle_end.isoformat(),
        pending_amount=str(pending),
    )
    await state.set_state(MarkPaidStates.action)
    await callback.message.answer(
        "🧾 <b>Card Payment Action</b>\n"
        f"Card: <b>{escape(card_label(card))}</b>\n"
        f"Cycle: {cycle_start.isoformat()} to {cycle_end.isoformat()}\n"
        f"Billed: {format_inr(billed)}\n"
        f"Paid: {format_inr(paid)}\n"
        f"<b>Pending: {format_inr(pending)}</b>\n"
        f"Due date: {due_date.isoformat()}\n\n"
        "Choose payment update:",
        reply_markup=card_bill_action_keyboard("card_bill_action"),
    )


@router.callback_query(MarkPaidStates.action, F.data.startswith("card_bill_action:"))
async def mark_paid_choose_action(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        return

    await callback.answer()
    action = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    pending = Decimal(str(data.get("pending_amount", "0")))

    if action == "cancel":
        await state.clear()
        await callback.message.answer("❌ Payment update cancelled.")
        return

    if action == "full":
        await _save_card_bill_payment(
            message=callback.message,
            state=state,
            session_maker=session_maker,
            telegram_user_id=callback.from_user.id,
            amount_paid=pending,
        )
        return

    if action == "partial":
        await state.set_state(MarkPaidStates.amount)
        await callback.message.answer(
            f"💰 Pending amount: <b>{format_inr(pending)}</b>\n"
            "Enter partial amount paid:"
        )
        return

    await callback.answer("Unknown action", show_alert=True)


@router.message(MarkPaidStates.amount)
async def mark_paid_partial_amount(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not message.from_user:
        return

    data = await state.get_data()
    pending = Decimal(str(data.get("pending_amount", "0")))
    parsed = parse_positive_decimal(message.text or "")
    if parsed is None:
        await message.answer("⚠️ Amount must be a positive number. Enter partial amount paid:")
        return
    if parsed > pending:
        await message.answer(
            f"⚠️ Amount cannot exceed pending bill ({format_inr(pending)}). Enter a valid amount:"
        )
        return

    await _save_card_bill_payment(
        message=message,
        state=state,
        session_maker=session_maker,
        telegram_user_id=message.from_user.id,
        amount_paid=parsed,
    )


async def _save_card_bill_payment(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
    telegram_user_id: int,
    amount_paid: Decimal,
) -> None:
    data = await state.get_data()
    user_id = int(data["user_id"])
    card_id = int(data["card_id"])
    card_name = str(data.get("card_name") or "Card")

    cycle_start = datetime.strptime(str(data["cycle_start"]), "%Y-%m-%d").date()
    cycle_end = datetime.strptime(str(data["cycle_end"]), "%Y-%m-%d").date()

    async with session_maker() as session:
        card = await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))
        if not card:
            await state.clear()
            await message.answer("⚠️ Card not found.")
            return

        try:
            billed, paid, outstanding = await _compute_cycle_bill_amounts(
                session,
                user_id,
                card_id,
                cycle_start,
                cycle_end,
            )
        except Exception as exc:
            await state.clear()
            if _is_card_bill_table_missing_error(exc):
                await _send_card_bill_setup_error(message)
                return
            await message.answer("⚠️ Unable to update card bill right now. Please try again.")
            return
        if amount_paid > outstanding:
            await message.answer(
                f"⚠️ Amount exceeds pending bill ({format_inr(outstanding)}). Please try again."
            )
            await state.set_state(MarkPaidStates.action)
            return

        try:
            session.add(
                CardBillPayment(
                    user_id=user_id,
                    card_id=card_id,
                    cycle_start=cycle_start,
                    cycle_end=cycle_end,
                    amount_paid=amount_paid,
                    notes="Recorded from /mark_paid card bill flow.",
                )
            )
            await session.commit()
        except Exception as exc:
            await state.clear()
            if _is_card_bill_table_missing_error(exc):
                await _send_card_bill_setup_error(message)
                return
            await message.answer("⚠️ Unable to save card payment right now. Please try again.")
            return

    remaining = max(ZERO, outstanding - amount_paid)
    status = "fully paid" if remaining <= ZERO else "partially paid"

    await message.answer(
        f"✅ <b>Payment recorded</b>\n"
        f"Card: <b>{escape(card_name)}</b>\n"
        f"Cycle: {cycle_start.isoformat()} to {cycle_end.isoformat()}\n"
        f"Billed: {format_inr(billed)}\n"
        f"Previously paid: {format_inr(paid)}\n"
        f"Paid now: {format_inr(amount_paid)}\n"
        f"<b>Pending now: {format_inr(remaining)}</b>\n"
        f"Status: <b>{status}</b>"
    )

    await _show_card_bill_overview(
        message,
        state,
        session_maker,
        telegram_user_id=telegram_user_id,
    )
