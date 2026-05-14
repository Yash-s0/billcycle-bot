from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..keyboards import settings_invite_keyboard
from ..models import SharedExpenseAccess
from ..states import SettingsStates
from .common import ensure_user, get_user_by_telegram_id

router = Router(name=__name__)

COMMANDS_TEXT = """Available commands:
/start - Register and welcome message
/help - Show this help
/add_card - Add a credit card
/list_cards - Manage cards (view/update/delete)
/add_txn - Add a transaction
/edit_txn - Update or delete a transaction
/recent_txns - Show recent transactions
/who_owes_me - Pending receivables by person
/mark_paid - Record reimbursement payment
/card_summary - Current cycle summary for a card
/report - Today/weekly/monthly/custom reports
/settings - Show bot settings overview"""


@router.message(Command("start"))
async def start_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await ensure_user(session, message.from_user)

        payload = ""
        raw_text = (message.text or "").strip()
        if " " in raw_text:
            payload = raw_text.split(" ", maxsplit=1)[1].strip()

        if payload.startswith("share_"):
            owner_tg_raw = payload.split("_", maxsplit=1)[1].strip()
            if owner_tg_raw.isdigit():
                owner_tg_id = int(owner_tg_raw)
                if owner_tg_id == message.from_user.id:
                    await message.answer("This sharing link belongs to you. Share it with someone else.")
                    return

                owner = await get_user_by_telegram_id(session, owner_tg_id)
                if not owner:
                    await message.answer("This sharing invite is invalid or expired.")
                    return

                existing = await session.scalar(
                    select(SharedExpenseAccess).where(
                        SharedExpenseAccess.owner_user_id == owner.id,
                        SharedExpenseAccess.collaborator_user_id == user.id,
                    )
                )
                if existing:
                    await message.answer(
                        f"You're already connected for shared expenses with {owner.full_name}.\n"
                        "Use /add_txn to add your own transactions or shared ones."
                    )
                    return

                session.add(
                    SharedExpenseAccess(
                        owner_user_id=owner.id,
                        collaborator_user_id=user.id,
                    )
                )
                await session.commit()
                await message.answer(
                    f"Shared-expense invite accepted.\n"
                    f"You can now add transactions for yourself and for {owner.full_name} via /add_txn."
                )
                try:
                    await message.bot.send_message(
                        chat_id=owner.telegram_id,
                        text=(
                            f"{user.full_name} joined your shared-expense access.\n"
                            "They can now add transactions to your account."
                        ),
                    )
                except Exception:
                    # Best effort notification.
                    pass
                return

        if payload.startswith("invite"):
            await message.answer("Invite accepted. Use /help to explore commands.")
            return

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
async def settings_command(message: Message, state: FSMContext, settings: Settings) -> None:
    if settings.database_url.startswith("postgresql"):
        db_mode = "PostgreSQL"
    elif settings.database_url.startswith("sqlite"):
        db_mode = "SQLite"
    else:
        db_mode = "Custom DB URL"

    await state.set_state(SettingsStates.main)
    text = (
        "Settings:\n"
        f"- Timezone: {settings.timezone}\n"
        f"- Database: {db_mode}\n"
        "\nPrivacy:\n"
        "- Card numbers are never collected\n"
        "- CVV/OTP/PIN/passwords are never stored\n\n"
        "Invites:\n"
        "- Invite: basic bot invite\n"
        "- Invite + Share Expenses: invite someone who can add txns to your account"
    )
    await message.answer(text, reply_markup=settings_invite_keyboard("settings_invite"))


@router.callback_query(SettingsStates.main, F.data.startswith("settings_invite:"))
async def settings_invite_action(callback: CallbackQuery) -> None:
    if not callback.message or not callback.from_user:
        return

    action = callback.data.split(":", maxsplit=1)[1]
    bot_info = await callback.bot.get_me()
    username = bot_info.username or ""
    if not username:
        await callback.answer("Bot username missing", show_alert=True)
        return

    if action == "basic":
        invite_url = f"https://t.me/{username}?start=invite"
        await callback.answer()
        await callback.message.answer(
            "Share this basic invite link:\n"
            f"{invite_url}"
        )
        return

    if action == "share":
        invite_url = f"https://t.me/{username}?start=share_{callback.from_user.id}"
        await callback.answer()
        await callback.message.answer(
            "Share this shared-expenses invite link:\n"
            f"{invite_url}\n\n"
            "People who join through this link can add expenses to your account, "
            "but they cannot view your personal transactions."
        )
        return

    await callback.answer("Unknown action", show_alert=True)
