from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..keyboards import (
    settings_invite_keyboard,
    settings_share_confirm_keyboard,
    settings_share_people_keyboard,
)
from ..models import SharedExpenseAccess, User
from ..states import SettingsStates
from .common import ensure_user, get_user_by_telegram_id, short_text

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


def _settings_overview_text(settings: Settings) -> str:
    return (
        "Settings:\n"
        f"- Timezone: {settings.timezone}\n"
        "\nPrivacy:\n"
        "- Card numbers are never collected\n"
        "- CVV/OTP/PIN/passwords are never stored\n"
        "- Shared collaborators can add transactions only; they cannot view your private transaction history\n\n"
        "Shared Expenses:\n"
        "- Invite: send a basic bot invite link\n"
        "- Invite + Share Expenses: let someone add transactions to your account\n"
        "- Manage Shared Access: view/remove people with shared-add access"
    )


async def _owner_collaborators(
    session: AsyncSession,
    owner_user_id: int,
) -> list[tuple[int, str, str | None]]:
    rows = (
        await session.execute(
            select(
                SharedExpenseAccess.collaborator_user_id,
                User.full_name,
                User.username,
            )
            .join(User, User.id == SharedExpenseAccess.collaborator_user_id)
            .where(SharedExpenseAccess.owner_user_id == owner_user_id)
            .order_by(User.full_name.asc(), User.id.asc())
        )
    ).all()
    return [(collab_id, full_name, username) for collab_id, full_name, username in rows]


def _format_collaborator_label(full_name: str, username: str | None) -> str:
    if username:
        return f"{full_name} (@{username})"
    return full_name


async def _send_manage_shared_access(
    message: Message,
    owner_tg_id: int,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        owner = await get_user_by_telegram_id(session, owner_tg_id)
        if not owner:
            await message.answer("No profile found. Use /start first.")
            return
        collaborators = await _owner_collaborators(session, owner.id)

    if not collaborators:
        await message.answer(
            "Shared access is currently empty.\n"
            "Use 'Invite + Share Expenses' to add someone."
        )
        return

    lines = [
        f"Shared access ({len(collaborators)}):",
        "These people can add transactions to your account:",
    ]
    keyboard_rows: list[tuple[int, str]] = []
    for idx, (collab_id, full_name, username) in enumerate(collaborators, start=1):
        label = _format_collaborator_label(full_name, username)
        lines.append(f"{idx}. {label}")
        keyboard_rows.append((collab_id, short_text(full_name, 24)))
    lines.append("")
    lines.append("Tap Remove to revoke access immediately.")
    lines.append("Existing transactions remain unchanged.")
    await message.answer(
        "\n".join(lines),
        reply_markup=settings_share_people_keyboard(keyboard_rows),
    )


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
    await state.set_state(SettingsStates.main)
    text = _settings_overview_text(settings)
    await message.answer(text, reply_markup=settings_invite_keyboard("settings_invite"))


@router.callback_query(SettingsStates.main, F.data.startswith("settings_invite:"))
async def settings_invite_action(
    callback: CallbackQuery,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
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

    if action == "manage_share":
        await callback.answer()
        await _send_manage_shared_access(
            callback.message,
            owner_tg_id=callback.from_user.id,
            session_maker=session_maker,
        )
        return

    await callback.answer("Unknown action", show_alert=True)


@router.callback_query(SettingsStates.main, F.data.startswith("settings_share_remove:"))
async def settings_remove_shared_access(
    callback: CallbackQuery,
    session_maker: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    if not callback.message or not callback.from_user:
        return

    raw_value = callback.data.split(":", maxsplit=1)[1]
    if raw_value == "back":
        await callback.answer()
        await callback.message.answer(
            _settings_overview_text(settings),
            reply_markup=settings_invite_keyboard("settings_invite"),
        )
        return

    if not raw_value.isdigit():
        await callback.answer("Invalid selection", show_alert=True)
        return
    collaborator_user_id = int(raw_value)

    collaborator_label = ""
    async with session_maker() as session:
        owner = await get_user_by_telegram_id(session, callback.from_user.id)
        if not owner:
            await callback.answer("No profile found", show_alert=True)
            return

        access = await session.scalar(
            select(SharedExpenseAccess).where(
                SharedExpenseAccess.owner_user_id == owner.id,
                SharedExpenseAccess.collaborator_user_id == collaborator_user_id,
            )
        )
        if not access:
            await callback.answer("Access already removed", show_alert=True)
            await _send_manage_shared_access(
                callback.message,
                owner_tg_id=callback.from_user.id,
                session_maker=session_maker,
            )
            return

        collaborator = await session.scalar(select(User).where(User.id == collaborator_user_id))
        if collaborator:
            collaborator_label = _format_collaborator_label(collaborator.full_name, collaborator.username)
        else:
            collaborator_label = f"User {collaborator_user_id}"

    await callback.answer()
    await callback.message.answer(
        f"Remove shared-expense access for {collaborator_label}?\n"
        "They will no longer be able to add transactions to your account.",
        reply_markup=settings_share_confirm_keyboard(collaborator_user_id),
    )


@router.callback_query(SettingsStates.main, F.data.startswith("settings_share_confirm:"))
async def settings_remove_shared_access_confirm(
    callback: CallbackQuery,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        return

    parts = callback.data.split(":", maxsplit=2)
    if len(parts) != 3:
        await callback.answer("Invalid action", show_alert=True)
        return

    _, raw_user_id, decision = parts
    if not raw_user_id.isdigit() or decision not in {"yes", "no"}:
        await callback.answer("Invalid action", show_alert=True)
        return
    collaborator_user_id = int(raw_user_id)

    if decision == "no":
        await callback.answer("Kept access")
        await callback.message.answer("Removal cancelled. Access is unchanged.")
        await _send_manage_shared_access(
            callback.message,
            owner_tg_id=callback.from_user.id,
            session_maker=session_maker,
        )
        return

    removed_name = ""
    removed_tg_id: int | None = None
    async with session_maker() as session:
        owner = await get_user_by_telegram_id(session, callback.from_user.id)
        if not owner:
            await callback.answer("No profile found", show_alert=True)
            return

        access = await session.scalar(
            select(SharedExpenseAccess).where(
                SharedExpenseAccess.owner_user_id == owner.id,
                SharedExpenseAccess.collaborator_user_id == collaborator_user_id,
            )
        )
        if not access:
            await callback.answer("Access already removed", show_alert=True)
            await _send_manage_shared_access(
                callback.message,
                owner_tg_id=callback.from_user.id,
                session_maker=session_maker,
            )
            return

        collaborator = await session.scalar(select(User).where(User.id == collaborator_user_id))
        if collaborator:
            removed_name = _format_collaborator_label(collaborator.full_name, collaborator.username)
            removed_tg_id = collaborator.telegram_id
        else:
            removed_name = f"User {collaborator_user_id}"

        await session.delete(access)
        await session.commit()

    await callback.answer("Access removed")
    await callback.message.answer(
        f"Removed shared-expense access for {removed_name}. "
        "They can no longer add transactions to your account."
    )
    if removed_tg_id:
        try:
            await callback.bot.send_message(
                chat_id=removed_tg_id,
                text=(
                    f"{callback.from_user.full_name} removed your shared-expense access.\n"
                    "You can no longer add transactions to their account."
                ),
            )
        except Exception:
            # Best effort notification.
            pass
    await _send_manage_shared_access(
        callback.message,
        owner_tg_id=callback.from_user.id,
        session_maker=session_maker,
    )
