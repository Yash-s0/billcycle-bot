from __future__ import annotations

import logging
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import and_, case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..models import Card, Payment, Person, ReminderDelivery, Transaction, User
from .billing import get_next_due_date
from .reports import format_inr

logger = logging.getLogger(__name__)


async def _pending_older_than_days(
    session: AsyncSession,
    user_id: int,
    older_than_days: int,
    today: date,
) -> list[tuple[str, Decimal, int]]:
    paid_subquery = (
        select(
            Payment.transaction_id.label("txn_id"),
            func.coalesce(func.sum(Payment.amount_paid), 0).label("paid_total"),
        )
        .where(Payment.user_id == user_id)
        .group_by(Payment.transaction_id)
        .subquery()
    )

    cutoff_date = today - timedelta(days=older_than_days)
    recoverable_expr = Transaction.final_amount - Transaction.cashback_amount
    outstanding_expr = recoverable_expr - func.coalesce(paid_subquery.c.paid_total, 0)

    query = (
        select(
            Person.name,
            func.coalesce(func.sum(outstanding_expr), 0).label("outstanding"),
            func.sum(case((outstanding_expr > 0, 1), else_=0)),
        )
        .join(
            Transaction,
            and_(
                Transaction.person_id == Person.id,
                Transaction.user_id == user_id,
                Transaction.is_for_someone_else.is_(True),
                Transaction.txn_date <= cutoff_date,
            ),
        )
        .outerjoin(paid_subquery, paid_subquery.c.txn_id == Transaction.id)
        .where(Person.user_id == user_id)
        .group_by(Person.id, Person.name)
        .having(func.sum(outstanding_expr) > 0)
        .order_by(func.sum(outstanding_expr).desc())
    )

    return [
        (name, Decimal(str(total)), int(count))
        for name, total, count in (await session.execute(query)).all()
    ]


async def _build_reminder_message(session: AsyncSession, user: User, today: date) -> str | None:
    card_rows = (
        await session.execute(select(Card).where(Card.user_id == user.id).order_by(Card.bank_name.asc(), Card.card_name.asc()))
    ).scalars().all()

    due_today: list[str] = []
    due_tomorrow: list[str] = []
    due_in_three: list[str] = []

    for card in card_rows:
        due_date = get_next_due_date(card.due_day, today)
        days_left = (due_date - today).days
        label = f"{card.bank_name}/{card.card_name} ({due_date.isoformat()})"
        if days_left == 0:
            due_today.append(label)
        elif days_left == 1:
            due_tomorrow.append(label)
        elif days_left == 3:
            due_in_three.append(label)

    pending_people = await _pending_older_than_days(session, user.id, older_than_days=7, today=today)

    if not (due_today or due_tomorrow or due_in_three or pending_people):
        return None

    lines: list[str] = ["Daily reminder:"]

    if due_in_three:
        lines.append("\nDue in 3 days:")
        lines.extend([f"- {item}" for item in due_in_three])

    if due_tomorrow:
        lines.append("\nDue tomorrow:")
        lines.extend([f"- {item}" for item in due_tomorrow])

    if due_today:
        lines.append("\nDue today:")
        lines.extend([f"- {item}" for item in due_today])

    if pending_people:
        lines.append("\nPending reimbursements older than 7 days:")
        for name, amount, count in pending_people:
            lines.append(f"- {name}: {format_inr(amount)} across {count} transaction(s)")

    return "\n".join(lines)


async def run_daily_reminders(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    timezone_name: str,
) -> None:
    await _run_reminders_for_date(
        bot=bot,
        session_maker=session_maker,
        timezone_name=timezone_name,
        backfill_mode=False,
    )


async def run_backfill_reminders(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    timezone_name: str,
) -> None:
    await _run_reminders_for_date(
        bot=bot,
        session_maker=session_maker,
        timezone_name=timezone_name,
        backfill_mode=True,
    )


async def _run_reminders_for_date(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    timezone_name: str,
    backfill_mode: bool,
) -> None:
    now_local = datetime.now(ZoneInfo(timezone_name))
    today = now_local.date()
    current_hm = (now_local.hour, now_local.minute)
    async with session_maker() as session:
        users = (await session.execute(select(User).order_by(User.id.asc()))).scalars().all()

    for user in users:
        try:
            if not bool(user.reminders_enabled):
                continue
            reminder_time = user.reminder_time or dt_time(hour=9, minute=0)
            reminder_hm = (reminder_time.hour, reminder_time.minute)
            should_send_now = current_hm == reminder_hm
            should_backfill_now = current_hm >= reminder_hm
            if backfill_mode and not should_backfill_now:
                continue
            if not backfill_mode and not should_send_now:
                continue

            async with session_maker() as session:
                already_sent = await session.scalar(
                    select(ReminderDelivery.id).where(
                        ReminderDelivery.user_id == user.id,
                        ReminderDelivery.reminder_date == today,
                    )
                )
                if already_sent:
                    continue

            async with session_maker() as session:
                text = await _build_reminder_message(session, user, today)
            if text:
                if backfill_mode:
                    text = "Backfill reminder (bot was offline earlier):\n\n" + text
                await bot.send_message(chat_id=user.telegram_id, text=text)
                async with session_maker() as session:
                    session.add(ReminderDelivery(user_id=user.id, reminder_date=today))
                    try:
                        await session.commit()
                    except IntegrityError:
                        await session.rollback()
        except Exception:  # pragma: no cover - logging path
            logger.exception("Failed to send reminder to user=%s", user.id)


def setup_scheduler(
    bot: Bot,
    session_maker: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        run_daily_reminders,
        trigger="cron",
        minute="*",
        kwargs={"bot": bot, "session_maker": session_maker, "timezone_name": settings.timezone},
        id="daily_reminders",
        replace_existing=True,
    )
    return scheduler
