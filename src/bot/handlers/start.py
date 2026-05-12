from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from .common import ensure_user

router = Router(name=__name__)

COMMANDS_TEXT = """Available commands:
/start - Register and welcome message
/help - Show this help
/add_card - Add a credit card
/list_cards - List your saved cards
/add_txn - Add a transaction
/recent_txns - Show recent transactions
/who_owes_me - Pending receivables by person
/mark_paid - Record reimbursement payment
/card_summary - Current cycle summary for a card
/monthly_report - Monthly spending report
/delete_txn - Delete one of your transactions
/settings - Show bot settings overview"""


@router.message(Command("start"))
async def start_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        await ensure_user(session, message.from_user)

    text = (
        "Welcome to BillCycle Bot.\n"
        "Track cards, transactions, billing cycles, due dates, discounts, and reimbursements.\n\n"
        "Use /help to see all commands."
    )
    await message.answer(text)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(COMMANDS_TEXT)


@router.message(Command("settings"))
async def settings_command(message: Message, settings: Settings) -> None:
    if settings.database_url.startswith("postgresql"):
        db_mode = "PostgreSQL"
    elif settings.database_url.startswith("sqlite"):
        db_mode = "SQLite"
    else:
        db_mode = "Custom DB URL"
    text = (
        "Settings:\n"
        f"- Timezone: {settings.timezone}\n"
        f"- Database: {db_mode}\n"
        "\nPrivacy:\n"
        "- Full card numbers are never collected\n"
        "- CVV/OTP/PIN/password are never stored"
    )
    await message.answer(text)
