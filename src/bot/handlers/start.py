from __future__ import annotations

from datetime import time as dt_time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import Settings
from ..keyboards import (
    settings_invite_keyboard,
    settings_reminder_keyboard,
    settings_share_confirm_keyboard,
    settings_share_people_keyboard,
)
from ..models import SharedExpenseAccess, User
from ..states import SettingsStates
from .common import ensure_user, get_user_by_telegram_id, short_text

router = Router(name=__name__)

COMMANDS_TEXT = """✨ <b>Available Commands</b>
<b>/start</b> - Register and show welcome message
<b>/help</b> - Show this help menu
<b>/add_card</b> - Add a credit card
<b>/list_cards</b> - Manage cards (view/update/delete)
<b>/add_txn</b> - Add a transaction
<b>/edit_txn</b> - Update or delete a transaction
<b>/recent_txns</b> - Show recent transactions
<b>/who_owes_me</b> - Pending receivables by person
<b>/mark_paid</b> - Track card bill payments (full/partial)
<b>/card_summary</b> - Current cycle summary for a card
<b>/report</b> - Today/weekly/monthly/custom reports
<b>/settings</b> - Open settings"""


def _format_hhmm(value: dt_time) -> str:
    return f"{value.hour:02d}:{value.minute:02d}"


def _settings_overview_text(settings: Settings, user: User) -> str:
    reminder_status = "Enabled ✅" if user.reminders_enabled else "Disabled 🔕"
    return (
        "⚙️ <b>Settings</b>\n"
        f"🌍 <b>Timezone:</b> <i>{settings.timezone}</i>\n"
        f"⏰ <b>Daily reminder:</b> <i>{reminder_status}</i> at <b>{_format_hhmm(user.reminder_time)}</b>\n"
        "\n🔒 <b>Privacy</b>\n"
        "• Card numbers are <b>never</b> collected\n"
        "• CVV/OTP/PIN/passwords are <b>never</b> stored\n"
        "• Shared collaborators can <b>add transactions only</b>; they cannot view your private transaction history\n\n"
        "🤝 <b>Shared Expenses</b>\n"
        "• <b>Basic Invite</b>: send a basic bot invite link\n"
        "• <b>Invite + Share Expenses</b>: let someone add transactions to your account\n"
        "• <b>Manage Shared Access</b>: view/remove people with shared-add access"
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


def _settings_reminder_text(settings: Settings, user: User) -> str:
    status = "Enabled ✅" if user.reminders_enabled else "Disabled 🔕"
    return (
        "⏰ <b>Reminder Settings</b>\n"
        f"🌍 Timezone: <i>{settings.timezone}</i>\n"
        f"🔔 Status: <b>{status}</b>\n"
        f"🕒 Time: <b>{_format_hhmm(user.reminder_time)}</b>\n\n"
        "Send time in <b>HH:MM</b> format (24-hour), for example <b>09:00</b>."
    )


async def _send_settings_overview(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_maker: async_sessionmaker[AsyncSession],
    user_tg_id: int,
) -> None:
    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, user_tg_id)
    if not user:
        await state.clear()
        await message.answer("⚠️ <b>No profile found.</b>\nPlease use <b>/start</b> first.")
        return
    await state.set_state(SettingsStates.main)
    await message.answer(
        _settings_overview_text(settings, user),
        reply_markup=settings_invite_keyboard("settings_invite"),
    )


async def _send_reminder_settings(
    message: Message,
    settings: Settings,
    session_maker: async_sessionmaker[AsyncSession],
    user_tg_id: int,
) -> None:
    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, user_tg_id)
    if not user:
        await message.answer("⚠️ <b>No profile found.</b>\nPlease use <b>/start</b> first.")
        return
    await message.answer(
        _settings_reminder_text(settings, user),
        reply_markup=settings_reminder_keyboard(enabled=bool(user.reminders_enabled)),
    )


async def _send_manage_shared_access(
    message: Message,
    owner_tg_id: int,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    async with session_maker() as session:
        owner = await get_user_by_telegram_id(session, owner_tg_id)
        if not owner:
            await message.answer("⚠️ <b>No profile found.</b>\nPlease use <b>/start</b> first.")
            return
        collaborators = await _owner_collaborators(session, owner.id)

    if not collaborators:
        await message.answer(
            "📭 <b>Shared access is currently empty.</b>\n"
            "Use <b>🤝 Invite + Share Expenses</b> to add someone."
        )
        return

    lines = [
        f"🛡️ <b>Shared Access ({len(collaborators)})</b>",
        "These people can <b>add transactions</b> to your account:",
    ]
    keyboard_rows: list[tuple[int, str]] = []
    for idx, (collab_id, full_name, username) in enumerate(collaborators, start=1):
        label = _format_collaborator_label(full_name, username)
        lines.append(f"{idx}. {label}")
        keyboard_rows.append((collab_id, short_text(full_name, 24)))
    lines.append("")
    lines.append("Tap <b>🗑️ Remove</b> to revoke access immediately.")
    lines.append("<i>Existing transactions remain unchanged.</i>")
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
                    await message.answer("ℹ️ This sharing link belongs to you. Share it with someone else.")
                    return

                owner = await get_user_by_telegram_id(session, owner_tg_id)
                if not owner:
                    await message.answer("⚠️ This sharing invite is invalid or expired.")
                    return

                existing = await session.scalar(
                    select(SharedExpenseAccess).where(
                        SharedExpenseAccess.owner_user_id == owner.id,
                        SharedExpenseAccess.collaborator_user_id == user.id,
                    )
                )
                if existing:
                    await message.answer(
                        f"✅ You're already connected for shared expenses with <b>{owner.full_name}</b>.\n"
                        "Use <b>/add_txn</b> to add your own transactions or shared ones."
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
                    f"🎉 <b>Shared-expense invite accepted.</b>\n"
                    f"You can now add transactions for yourself and for <b>{owner.full_name}</b> via <b>/add_txn</b>."
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
            await message.answer("✅ Invite accepted. Use <b>/help</b> to explore commands.")
            return

    text = (
        "👋 <b>Welcome to BillCycle Bot</b>\n"
        "Track cards, transactions, billing cycles, due dates, discounts, and reimbursements.\n\n"
        "🚀 Start here: <b>/add_card</b>\n"
        "📚 See all commands: <b>/help</b>"
    )
    await message.answer(text)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(COMMANDS_TEXT)


@router.message(Command("settings"))
async def settings_command(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not message.from_user:
        return
    await _send_settings_overview(
        message,
        state,
        settings,
        session_maker=session_maker,
        user_tg_id=message.from_user.id,
    )


@router.callback_query(SettingsStates.main, F.data.startswith("settings_invite:"))
async def settings_invite_action(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
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
            "🔗 <b>Share this basic invite link:</b>\n"
            f"{invite_url}"
        )
        return

    if action == "share":
        invite_url = f"https://t.me/{username}?start=share_{callback.from_user.id}"
        await callback.answer()
        await callback.message.answer(
            "🤝 <b>Share this shared-expenses invite link:</b>\n"
            f"{invite_url}\n\n"
            "People who join through this link can <b>add expenses</b> to your account, "
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

    if action == "reminders":
        await callback.answer()
        await state.set_state(SettingsStates.main)
        await _send_reminder_settings(
            callback.message,
            settings=settings,
            session_maker=session_maker,
            user_tg_id=callback.from_user.id,
        )
        return

    await callback.answer("Unknown action", show_alert=True)


@router.callback_query(SettingsStates.main, F.data.startswith("settings_share_remove:"))
async def settings_remove_shared_access(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    if not callback.message or not callback.from_user:
        return

    raw_value = callback.data.split(":", maxsplit=1)[1]
    if raw_value == "back":
        await callback.answer()
        await _send_settings_overview(
            callback.message,
            state,
            settings,
            session_maker=session_maker,
            user_tg_id=callback.from_user.id,
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
        f"⚠️ <b>Remove shared-expense access</b> for <b>{collaborator_label}</b>?\n"
        "They will no longer be able to add transactions to your account.",
        reply_markup=settings_share_confirm_keyboard(collaborator_user_id),
    )


@router.callback_query(SettingsStates.main, F.data.startswith("settings_share_confirm:"))
async def settings_remove_shared_access_confirm(
    callback: CallbackQuery,
    state: FSMContext,
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
        await callback.message.answer("✅ Removal cancelled. Access is unchanged.")
        await state.set_state(SettingsStates.main)
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
        f"🗑️ Removed shared-expense access for <b>{removed_name}</b>.\n"
        "They can no longer add transactions to your account."
    )
    await state.set_state(SettingsStates.main)
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


@router.callback_query(SettingsStates.main, F.data.startswith("settings_reminder:"))
async def settings_reminder_action(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message or not callback.from_user:
        return

    action = callback.data.split(":", maxsplit=1)[1]
    if action == "back":
        await callback.answer()
        await _send_settings_overview(
            callback.message,
            state,
            settings,
            session_maker=session_maker,
            user_tg_id=callback.from_user.id,
        )
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, callback.from_user.id)
        if not user:
            await callback.answer("No profile found", show_alert=True)
            return

        if action == "toggle":
            user.reminders_enabled = not bool(user.reminders_enabled)
            await session.commit()
            await callback.answer("Updated")
        elif action == "time":
            await callback.answer()
            await state.set_state(SettingsStates.reminder_time_input)
            await callback.message.answer(
                "🕒 Send daily reminder time in <b>HH:MM</b> format.\nExample: <b>09:00</b>"
            )
            return
        else:
            await callback.answer("Unknown action", show_alert=True)
            return

    await state.set_state(SettingsStates.main)
    await _send_reminder_settings(
        callback.message,
        settings=settings,
        session_maker=session_maker,
        user_tg_id=callback.from_user.id,
    )


@router.message(SettingsStates.reminder_time_input)
async def settings_reminder_time_input(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not message.from_user:
        return

    raw = (message.text or "").strip()
    try:
        hour_text, minute_text = raw.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
    except Exception:
        await message.answer("⚠️ Invalid time. Use <b>HH:MM</b> (24-hour). Example: <b>21:30</b>")
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await state.clear()
            await message.answer("⚠️ <b>No profile found.</b>\nPlease use <b>/start</b> first.")
            return
        user.reminder_time = dt_time(hour=hour, minute=minute)
        user.reminders_enabled = True
        await session.commit()

    await state.set_state(SettingsStates.main)
    await message.answer(f"✅ Reminder time updated to <b>{hour:02d}:{minute:02d}</b>.")
    await _send_reminder_settings(
        message,
        settings=settings,
        session_maker=session_maker,
        user_tg_id=message.from_user.id,
    )
