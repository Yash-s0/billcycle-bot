from __future__ import annotations

import logging
import traceback
from datetime import date, datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import months_keyboard, report_type_keyboard
from ..models import Card
from ..services.reports import (
    format_inr,
    get_card_summary_data,
    get_period_report_data,
    last_n_month_starts,
    list_people_pending_summary,
)
from ..states import ReportStates
from .common import card_label, get_user_by_telegram_id, render_pre_table, short_text

router = Router(name=__name__)
logger = logging.getLogger(__name__)


@router.message(Command("who_owes_me"))
async def who_owes_me_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("⚠️ <b>No profile found.</b> Use <b>/start</b> first.")
            return

        summary = await list_people_pending_summary(session, user.id)

    if not summary:
        await message.answer("✅ Nobody owes you right now.")
        return

    lines = ["💸 <b>Pending Receivables</b>"]
    for idx, item in enumerate(summary, start=1):
        person_name = escape(item.person_name)
        lines.extend(
            [
                "",
                f"{idx}. 👤 <b>{person_name}</b>",
                f"• <b>Owes:</b> {format_inr(item.pending_amount)}",
                f"• <b>Cashback:</b> {format_inr(item.cashback_amount)}",
                f"• <b>Total:</b> {format_inr(item.total_amount)}",
            ]
        )
    await message.answer("\n".join(lines))


@router.message(Command("card_summary"))
async def card_summary_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("⚠️ <b>No profile found.</b> Use <b>/start</b> first.")
            return

        cards = (
            await session.execute(
                select(Card)
                .where(Card.user_id == user.id)
                .order_by(Card.bank_name.asc(), Card.card_name.asc(), Card.id.asc())
            )
        ).scalars().all()

    if not cards:
        await message.answer("📭 No cards found. Use <b>/add_card</b> first.")
        return

    builder = InlineKeyboardBuilder()
    for card in cards:
        builder.button(text=short_text(card_label(card), 24), callback_data=f"card_summary:{card.id}")
    builder.adjust(1)

    await message.answer("💳 Select card for summary:", reply_markup=builder.as_markup())


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
            await callback.message.answer("⚠️ <b>No profile found.</b> Use <b>/start</b> first.")
            return

        summary = await get_card_summary_data(session, user.id, card_id, date.today())

    if not summary:
        await callback.message.answer("⚠️ Card not found.")
        return

    lines = [
        f"💳 <b>Card summary:</b> {summary.card_label}",
        f"🗓️ <b>Cycle:</b> {summary.cycle_start.isoformat()} to {summary.cycle_end.isoformat()}",
        f"💰 <b>Current cycle total billed:</b> {format_inr(summary.total_spend)}",
        f"💸 <b>Total discounts:</b> {format_inr(summary.total_discounts)}",
        f"🎁 <b>Total cashback:</b> {format_inr(summary.total_cashback)}",
        f"👥 <b>Pending receivables on this card:</b> {format_inr(summary.pending_receivables)}",
        f"⏰ <b>Upcoming due date:</b> {summary.upcoming_due_date.isoformat()}",
    ]

    if not summary.recent_transactions:
        lines.append("🧾 Recent 5 transactions: none in this cycle.")
    else:
        rows: list[list[str]] = []
        for item in summary.recent_transactions:
            rows.append(
                [
                    item.txn_date.isoformat(),
                    short_text(item.card_label, 12),
                    short_text(item.notes, 12),
                    format_inr(item.final_amount),
                ]
            )
        lines.append("")
        lines.append("🧾 <b>Recent 5 transactions:</b>")
        lines.append(
            render_pre_table(
                headers=["Date", "Card", "Notes", "Total"],
                rows=rows,
                right_align_cols={3},
            )
        )

    await callback.message.answer("\n".join(lines))


@router.message(Command("report"))
async def report_command(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not message.from_user:
        logger.warning("report_command skipped: missing from_user")
        return
    logger.info(
        "report_command received: telegram_id=%s chat_id=%s",
        message.from_user.id,
        message.chat.id,
    )

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            logger.warning("report_command no profile: telegram_id=%s", message.from_user.id)
            await message.answer("⚠️ <b>No profile found.</b> Use <b>/start</b> first.")
            return

    await state.clear()
    await state.set_state(ReportStates.menu)
    await message.answer(
        "📊 <b>Choose report type:</b>",
        reply_markup=report_type_keyboard("report_type"),
    )


@router.callback_query(ReportStates.menu, F.data.startswith("report_type:"))
async def report_type_selected(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        logger.warning("report_type_selected skipped: missing callback message/from_user")
        return

    await callback.answer()
    selected = callback.data.split(":", maxsplit=1)[1]
    logger.info(
        "report_type_selected: telegram_id=%s chat_id=%s selected=%s",
        callback.from_user.id,
        callback.message.chat.id,
        selected,
    )

    if selected == "cancel":
        await state.clear()
        await callback.message.answer("❌ Report cancelled.")
        return

    if selected == "today":
        today = date.today()
        await _send_period_report(
            callback.message,
            callback.from_user.id,
            today,
            today,
            state,
            session_maker,
            title="Today's report",
        )
        return

    if selected == "weekly":
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
        await _send_period_report(
            callback.message,
            callback.from_user.id,
            start_date,
            end_date,
            state,
            session_maker,
            title="Weekly report (last 7 days)",
        )
        return

    if selected == "monthly":
        month_options = last_n_month_starts(date.today(), count=6)[1:]
        await state.set_state(ReportStates.month)
        await callback.message.answer(
            "📅 Select month (or use <b>Current Month</b>):",
            reply_markup=months_keyboard(month_options, include_current_shortcut=True),
        )
        return

    if selected == "custom":
        await state.set_state(ReportStates.custom_from)
        await callback.message.answer("🗓️ Send start date in <b>YYYY-MM-DD</b>:")
        return

    await state.clear()
    await callback.message.answer("⚠️ Unknown option. Use <b>/report</b> again.")


@router.callback_query(ReportStates.month, F.data.startswith("month:"))
async def monthly_report_month_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        logger.warning("monthly_report_month_callback skipped: missing callback message/from_user")
        return

    await callback.answer()
    raw = callback.data.split(":", maxsplit=1)[1]
    logger.info(
        "monthly_report_month_callback: telegram_id=%s chat_id=%s raw=%s",
        callback.from_user.id,
        callback.message.chat.id,
        raw,
    )

    if raw == "current":
        target_month = date.today().replace(day=1)
    else:
        try:
            target_month = datetime.strptime(raw, "%Y-%m").date().replace(day=1)
        except ValueError:
            logger.warning(
                "monthly_report_month_callback invalid month: telegram_id=%s raw=%s",
                callback.from_user.id,
                raw,
            )
            await callback.message.answer("⚠️ Invalid month selected. Try <b>/report</b> again.")
            await state.clear()
            return

    await _send_monthly_report(callback.message, callback.from_user.id, target_month, state, session_maker)


@router.message(ReportStates.month)
async def monthly_report_month_text(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    raw = (message.text or "").strip()
    logger.info(
        "monthly_report_month_text: telegram_id=%s chat_id=%s raw=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
        raw,
    )
    if not raw or raw.lower() in {"current", "skip"}:
        target_month = date.today().replace(day=1)
    else:
        try:
            target_month = datetime.strptime(raw, "%Y-%m").date().replace(day=1)
        except ValueError:
            logger.warning(
                "monthly_report_month_text invalid month: telegram_id=%s raw=%s",
                message.from_user.id if message.from_user else None,
                raw,
            )
            await message.answer("⚠️ Enter month in <b>YYYY-MM</b> format, or type <b>current</b>.")
            return

    if not message.from_user:
        logger.warning("monthly_report_month_text skipped: missing from_user")
        return

    await _send_monthly_report(message, message.from_user.id, target_month, state, session_maker)


@router.message(ReportStates.custom_from)
async def custom_report_from_date(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    logger.info(
        "custom_report_from_date: telegram_id=%s chat_id=%s raw=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
        raw,
    )
    parsed = _parse_iso_date(raw)
    if parsed is None:
        logger.warning("custom_report_from_date invalid date: raw=%s", raw)
        await message.answer("⚠️ Invalid date. Send start date in <b>YYYY-MM-DD</b>:")
        return
    await state.update_data(custom_from=parsed.isoformat())
    await state.set_state(ReportStates.custom_to)
    await message.answer("🗓️ Send end date in <b>YYYY-MM-DD</b>:")


@router.message(ReportStates.custom_to)
async def custom_report_to_date(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    raw = (message.text or "").strip()
    logger.info(
        "custom_report_to_date: telegram_id=%s chat_id=%s raw=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
        raw,
    )
    end_date = _parse_iso_date(raw)
    if end_date is None:
        logger.warning("custom_report_to_date invalid end date: raw=%s", raw)
        await message.answer("⚠️ Invalid date. Send end date in <b>YYYY-MM-DD</b>:")
        return

    data = await state.get_data()
    start_raw = str(data.get("custom_from") or "")
    start_date = _parse_iso_date(start_raw)
    if start_date is None:
        logger.warning("custom_report_to_date missing/expired start date in state")
        await state.clear()
        await message.answer("⌛ Custom date range expired. Use <b>/report</b> again.")
        return
    if end_date < start_date:
        logger.warning(
            "custom_report_to_date invalid range: start=%s end=%s",
            start_date.isoformat(),
            end_date.isoformat(),
        )
        await message.answer("⚠️ End date cannot be before start date. Send end date again:")
        return
    if not message.from_user:
        logger.warning("custom_report_to_date skipped: missing from_user")
        return

    await _send_period_report(
        message,
        message.from_user.id,
        start_date,
        end_date,
        state,
        session_maker,
        title="Custom report",
    )


async def _send_monthly_report(
    message: Message,
    telegram_id: int,
    target_month: date,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    month_start = target_month.replace(day=1)
    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1) - timedelta(days=1)
    title = f"Monthly report: {month_start.strftime('%b %Y')}"
    logger.info(
        "_send_monthly_report: telegram_id=%s month=%s range=%s..%s",
        telegram_id,
        month_start.strftime("%Y-%m"),
        month_start.isoformat(),
        month_end.isoformat(),
    )
    await _send_period_report(
        message,
        telegram_id,
        month_start,
        month_end,
        state,
        session_maker,
        title=title,
    )


def _parse_iso_date(raw: str) -> date | None:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


async def _send_period_report(
    message: Message,
    telegram_id: int,
    start_date: date,
    end_date: date,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
    title: str,
) -> None:
    logger.info(
        "_send_period_report start: telegram_id=%s title=%s range=%s..%s",
        telegram_id,
        title,
        start_date.isoformat(),
        end_date.isoformat(),
    )
    try:
        async with session_maker() as session:
            user = await get_user_by_telegram_id(session, telegram_id)
            if not user:
                logger.warning("_send_period_report no profile: telegram_id=%s", telegram_id)
                await message.answer("⚠️ <b>No profile found.</b> Use <b>/start</b> first.")
                await state.clear()
                return

            report = await get_period_report_data(session, user.id, start_date, end_date)
    except Exception as exc:
        logger.exception(
            "_send_period_report failed: telegram_id=%s title=%s range=%s..%s",
            telegram_id,
            title,
            start_date.isoformat(),
            end_date.isoformat(),
        )
        # Fallback terminal output in case logging handlers are misconfigured.
        print(
            "[report-error] _send_period_report failed:",
            {
                "telegram_id": telegram_id,
                "title": title,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "error": repr(exc),
            },
            flush=True,
        )
        traceback.print_exc()

        error_text = str(exc).lower()
        if "payment_mode" in error_text and ("column" in error_text or "undefined" in error_text):
            await message.answer(
                "⚠️ Report failed because database schema is outdated.\n"
                "Run <code>alembic upgrade head</code>, restart the bot, and try again."
            )
        else:
            await message.answer("⚠️ Report failed due to an internal error. Please try again.")
        await state.clear()
        return

    lines = [
        f"📊 <b>{title}</b>",
        f"🗓️ <b>Period:</b> {report.month_start.isoformat()} to {report.month_end.isoformat()}",
        f"💰 <b>Total spent (all modes):</b> {format_inr(report.total_spent)}",
        f"💸 <b>Total discounts:</b> {format_inr(report.total_discounts)}",
        f"🎁 <b>Total cashback:</b> {format_inr(report.total_cashback)}",
        f"💳 <b>Card bill to repay (excl UPI/Cash):</b> {format_inr(report.net_payable)}",
        f"👥 <b>Amount owed by others:</b> {format_inr(report.amount_owed_by_others)}",
        "",
        "📝 <b>Top notes</b>:",
    ]

    if report.top_notes:
        for name, total in report.top_notes:
            lines.append(f"• {name}: {format_inr(total)}")
    else:
        lines.append("• No data")

    lines.append("")
    lines.append("🧾 <b>Spend breakdown (cards + UPI + cash)</b>:")

    if report.card_breakdown:
        for item in report.card_breakdown:
            lines.append(
                f"• {item.card_label}: Total {format_inr(item.total_billed)}, "
                f"Discount {format_inr(item.total_discount)}, Cashback {format_inr(item.total_cashback)}, "
                f"Net {format_inr(item.effective_net)}"
            )
    else:
        lines.append("• No transactions")

    await state.clear()
    logger.info(
        "_send_period_report success: telegram_id=%s title=%s tx_breakdown=%s notes=%s",
        telegram_id,
        title,
        len(report.card_breakdown),
        len(report.top_notes),
    )
    await message.answer("\n".join(lines))
