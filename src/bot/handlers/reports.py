from __future__ import annotations

from datetime import date, datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import months_keyboard
from ..models import Card
from ..services.reports import (
    format_inr,
    get_card_summary_data,
    get_monthly_report_data,
    last_n_month_starts,
    list_people_pending_summary,
)
from ..states import MonthlyReportStates
from .common import card_label, get_user_by_telegram_id

router = Router(name=__name__)


@router.message(Command("who_owes_me"))
async def who_owes_me_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("No profile found. Use /start first.")
            return

        summary = await list_people_pending_summary(session, user.id)

    if not summary:
        await message.answer("Nobody owes you right now.")
        return

    lines = ["Pending receivables:"]
    for item in summary:
        lines.append(
            f"- {item.person_name}: Owes {format_inr(item.pending_amount)} | "
            f"Cashback {format_inr(item.cashback_amount)} | Total {format_inr(item.total_amount)} "
            f"across {item.transaction_count} transaction(s)"
        )
    await message.answer("\n".join(lines))


@router.message(Command("card_summary"))
async def card_summary_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("No profile found. Use /start first.")
            return

        cards = (
            await session.execute(
                select(Card)
                .where(Card.user_id == user.id)
                .order_by(Card.bank_name.asc(), Card.card_name.asc(), Card.id.asc())
            )
        ).scalars().all()

    if not cards:
        await message.answer("No cards found. Use /add_card first.")
        return

    builder = InlineKeyboardBuilder()
    for card in cards:
        builder.button(text=card_label(card), callback_data=f"card_summary:{card.id}")
    builder.adjust(1)

    await message.answer("Select card for summary:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("card_summary:"))
async def card_summary_selected(
    callback: CallbackQuery,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        return

    await callback.answer()
    _, raw_card_id = callback.data.split(":", maxsplit=1)
    card_id = int(raw_card_id)

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.message.answer("No profile found. Use /start first.")
            return

        summary = await get_card_summary_data(session, user.id, card_id, date.today())

    if not summary:
        await callback.message.answer("Card not found.")
        return

    lines = [
        f"Card summary: {summary.card_label}",
        f"Cycle: {summary.cycle_start.isoformat()} to {summary.cycle_end.isoformat()}",
        f"Current cycle total billed: {format_inr(summary.total_spend)}",
        f"Total discounts: {format_inr(summary.total_discounts)}",
        f"Total cashback: {format_inr(summary.total_cashback)}",
        f"Pending receivables on this card: {format_inr(summary.pending_receivables)}",
        f"Upcoming due date: {summary.upcoming_due_date.isoformat()}",
        "",
        "Recent 5 transactions:",
    ]

    if not summary.recent_transactions:
        lines.append("- No transactions in this cycle.")
    else:
        for item in summary.recent_transactions:
            lines.append(
                f"- ID {item.transaction_id} | {item.txn_date.isoformat()} | {item.merchant} | "
                f"Total {format_inr(item.final_amount)} | Cashback {format_inr(item.cashback_amount)} | "
                f"Owes {format_inr(item.recoverable_amount)} | Pending {format_inr(item.pending_amount)}"
            )

    await callback.message.answer("\n".join(lines))


@router.message(Command("monthly_report"))
async def monthly_report_command(
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

    month_options = last_n_month_starts(date.today(), count=6)[1:]
    await state.set_state(MonthlyReportStates.month)
    await message.answer(
        "Select month (or use Current Month):",
        reply_markup=months_keyboard(month_options, include_current_shortcut=True),
    )


@router.callback_query(MonthlyReportStates.month, F.data.startswith("month:"))
async def monthly_report_month_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        return

    await callback.answer()
    raw = callback.data.split(":", maxsplit=1)[1]

    if raw == "current":
        target_month = date.today().replace(day=1)
    else:
        try:
            target_month = datetime.strptime(raw, "%Y-%m").date().replace(day=1)
        except ValueError:
            await callback.message.answer("Invalid month selected. Try /monthly_report again.")
            await state.clear()
            return

    await _send_monthly_report(callback.message, callback.from_user.id, target_month, state, session_maker)


@router.message(MonthlyReportStates.month)
async def monthly_report_month_text(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    raw = (message.text or "").strip()
    if not raw or raw.lower() in {"current", "skip"}:
        target_month = date.today().replace(day=1)
    else:
        try:
            target_month = datetime.strptime(raw, "%Y-%m").date().replace(day=1)
        except ValueError:
            await message.answer("Enter month in YYYY-MM format, or type 'current'.")
            return

    if not message.from_user:
        return

    await _send_monthly_report(message, message.from_user.id, target_month, state, session_maker)


async def _send_monthly_report(
    message: Message,
    telegram_id: int,
    target_month: date,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, telegram_id)
        if not user:
            await message.answer("No profile found. Use /start first.")
            await state.clear()
            return

        report = await get_monthly_report_data(session, user.id, target_month)

    lines = [
        f"Monthly report: {report.month_start.strftime('%b %Y')}",
        f"Period: {report.month_start.isoformat()} to {report.month_end.isoformat()}",
        f"Total billed: {format_inr(report.total_spent)}",
        f"Total discounts: {format_inr(report.total_discounts)}",
        f"Total cashback: {format_inr(report.total_cashback)}",
        f"Net after cashback: {format_inr(report.net_payable)}",
        f"Amount owed by others: {format_inr(report.amount_owed_by_others)}",
        "",
        "Top categories:",
    ]

    if report.top_categories:
        for name, total in report.top_categories:
            lines.append(f"- {name}: {format_inr(total)}")
    else:
        lines.append("- No data")

    lines.append("")
    lines.append("Card-wise breakdown:")

    if report.card_breakdown:
        for item in report.card_breakdown:
            lines.append(
                f"- {item.card_label}: Total {format_inr(item.total_billed)}, "
                f"Discount {format_inr(item.total_discount)}, Cashback {format_inr(item.total_cashback)}, "
                f"Net {format_inr(item.effective_net)}"
            )
    else:
        lines.append("- No transactions")

    await state.clear()
    await message.answer("\n".join(lines))
