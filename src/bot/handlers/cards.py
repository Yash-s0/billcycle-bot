from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import (
    cards_keyboard,
    edit_action_keyboard,
    edit_card_fields_keyboard,
    edit_confirm_delete_keyboard,
    skip_keyboard,
)
from ..models import Card
from ..states import AddCardStates, EditCardStates
from .common import ensure_user, get_user_by_telegram_id

router = Router(name=__name__)


@router.message(Command("add_card"))
async def add_card_command(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await ensure_user(session, message.from_user)

    await state.clear()
    await state.set_state(AddCardStates.bank_name)
    await state.update_data(user_id=user.id)
    await message.answer("🏦 <b>Add Card</b>\nEnter bank name:")


@router.message(AddCardStates.bank_name)
async def add_card_bank_name(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("⚠️ Bank name cannot be empty. Please enter bank name:")
        return

    await state.update_data(bank_name=value)
    await state.set_state(AddCardStates.card_name)
    await message.answer("💳 Enter card nickname:")


@router.message(AddCardStates.card_name)
async def add_card_card_name(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("⚠️ Card nickname cannot be empty. Please enter card nickname:")
        return

    await state.update_data(card_name=value)
    await state.set_state(AddCardStates.billing_day)
    await message.answer("🧾 Enter billing day of month (1-31):")


def _parse_day(value: str) -> int | None:
    if not value.isdigit():
        return None
    day = int(value)
    if day < 1 or day > 31:
        return None
    return day


@router.message(AddCardStates.billing_day)
async def add_card_billing_day(message: Message, state: FSMContext) -> None:
    day = _parse_day((message.text or "").strip())
    if day is None:
        await message.answer("⚠️ Billing day must be between 1 and 31. Enter billing day again:")
        return

    await state.update_data(billing_day=day)
    await state.set_state(AddCardStates.due_day)
    await message.answer("⏰ Enter due day of month (1-31):")


@router.message(AddCardStates.due_day)
async def add_card_due_day(message: Message, state: FSMContext) -> None:
    day = _parse_day((message.text or "").strip())
    if day is None:
        await message.answer("⚠️ Due day must be between 1 and 31. Enter due day again:")
        return

    await state.update_data(due_day=day)
    await state.set_state(AddCardStates.credit_limit)
    await message.answer(
        "💰 Enter credit limit (<i>optional</i>). Send <b>skip</b> to skip.",
        reply_markup=skip_keyboard("card_limit"),
    )


def _parse_credit_limit(raw_value: str) -> Decimal | None:
    value = raw_value.replace(",", "").strip()
    if not value:
        return None
    try:
        amount = Decimal(value)
    except Exception:
        return None
    if amount <= 0:
        return None
    return amount


@router.callback_query(AddCardStates.credit_limit, F.data == "card_limit:skip")
async def add_card_credit_limit_skip(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    await callback.answer()
    await state.update_data(credit_limit=None)
    await state.set_state(AddCardStates.notes)
    await callback.message.answer("📝 Add notes (<i>optional</i>). Send <b>skip</b> to skip.", reply_markup=skip_keyboard("card_notes"))


@router.message(AddCardStates.credit_limit)
async def add_card_credit_limit(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if value.lower() == "skip":
        await state.update_data(credit_limit=None)
    else:
        amount = _parse_credit_limit(value)
        if amount is None:
            await message.answer("⚠️ Credit limit must be numeric or <b>skip</b>. Enter credit limit again:")
            return
        await state.update_data(credit_limit=amount)

    await state.set_state(AddCardStates.notes)
    await message.answer("📝 Add notes (<i>optional</i>). Send <b>skip</b> to skip.", reply_markup=skip_keyboard("card_notes"))


@router.callback_query(AddCardStates.notes, F.data == "card_notes:skip")
async def add_card_notes_skip(callback: CallbackQuery, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not callback.message:
        return
    await callback.answer()
    await _save_card(callback.message, state, session_maker, notes=None)


@router.message(AddCardStates.notes)
async def add_card_notes(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    value = (message.text or "").strip()
    notes = None if not value or value.lower() == "skip" else value
    await _save_card(message, state, session_maker, notes=notes)


async def _save_card(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
    notes: str | None,
) -> None:
    data = await state.get_data()

    card = Card(
        user_id=int(data["user_id"]),
        bank_name=str(data["bank_name"]),
        card_name=str(data["card_name"]),
        billing_day=int(data["billing_day"]),
        due_day=int(data["due_day"]),
        credit_limit=data.get("credit_limit"),
        notes=notes,
    )

    async with session_maker() as session:
        session.add(card)
        await session.commit()

    await state.clear()
    await message.answer(f"✅ <b>Card saved</b>\n{card.bank_name}/{card.card_name}")


@router.message(Command("list_cards"))
async def manage_cards_command(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
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
        await message.answer("📭 You have no cards yet. Use <b>/add_card</b>.")
        return

    rows = [(card.id, f"{card.card_name} | {card.bank_name}") for card in cards]
    await state.clear()
    await state.set_state(EditCardStates.card)
    await state.update_data(user_id=user.id)
    await message.answer("🧩 Select a card to manage:", reply_markup=cards_keyboard(rows, columns=2))


@router.callback_query(EditCardStates.card, F.data.startswith("card:"))
async def edit_card_select(callback: CallbackQuery, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not callback.message:
        return
    await callback.answer()

    card_id = int(callback.data.split(":", maxsplit=1)[1])
    data = await state.get_data()
    user_id = int(data["user_id"])

    async with session_maker() as session:
        card = await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))
    if not card:
        await callback.message.answer("⚠️ Card not found.")
        await state.clear()
        return

    await state.update_data(edit_card_id=card.id)
    await state.set_state(EditCardStates.action)
    await callback.message.answer(
        _format_card_summary(card),
        reply_markup=edit_action_keyboard("edit_card_action"),
    )


@router.callback_query(EditCardStates.action, F.data.startswith("edit_card_action:"))
async def edit_card_action(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return
    await callback.answer()
    action = callback.data.split(":", maxsplit=1)[1]

    if action == "cancel":
        await state.clear()
        await callback.message.answer("❌ Edit card cancelled.")
        return
    if action == "delete":
        await state.set_state(EditCardStates.confirm_delete)
        await callback.message.answer(
            "⚠️ <b>Delete this card?</b>\nThis will also delete transactions linked to this card.",
            reply_markup=edit_confirm_delete_keyboard("edit_card_delete"),
        )
        return

    await state.set_state(EditCardStates.field)
    await callback.message.answer("✏️ Choose what to update:", reply_markup=edit_card_fields_keyboard())


@router.callback_query(EditCardStates.confirm_delete, F.data.startswith("edit_card_delete:"))
async def edit_card_delete_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return
    await callback.answer()
    choice = callback.data.split(":", maxsplit=1)[1]
    if choice == "no":
        await state.set_state(EditCardStates.action)
        await callback.message.answer("✅ Delete cancelled.", reply_markup=edit_action_keyboard("edit_card_action"))
        return

    data = await state.get_data()
    user_id = int(data["user_id"])
    card_id = int(data["edit_card_id"])
    async with session_maker() as session:
        card = await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))
        if not card:
            await state.clear()
            await callback.message.answer("⚠️ Card not found. Nothing deleted.")
            return
        await session.delete(card)
        await session.commit()

    await state.clear()
    await callback.message.answer(f"🗑️ Deleted card ID <b>{card_id}</b>.")


@router.callback_query(EditCardStates.field, F.data.startswith("edit_card_field:"))
async def edit_card_field_select(callback: CallbackQuery, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not callback.message:
        return
    await callback.answer()
    field = callback.data.split(":", maxsplit=1)[1]

    if field == "back":
        await state.set_state(EditCardStates.action)
        await callback.message.answer("⬅️ Back to actions.", reply_markup=edit_action_keyboard("edit_card_action"))
        return

    await state.update_data(edit_card_pending_field=field)
    await state.set_state(EditCardStates.input_value)
    await callback.message.answer(_card_field_prompt(field))


@router.message(EditCardStates.input_value)
async def edit_card_field_input(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    data = await state.get_data()
    field = str(data.get("edit_card_pending_field") or "")
    user_id = int(data["user_id"])
    card_id = int(data["edit_card_id"])
    raw = (message.text or "").strip()
    raw_lower = raw.lower()

    update_value: object
    if field in {"bank_name", "card_name"}:
        if not raw:
            await message.answer("⚠️ Value cannot be empty. Enter again:")
            return
        update_value = raw
    elif field in {"billing_day", "due_day"}:
        day = _parse_day(raw)
        if day is None:
            await message.answer("⚠️ Day must be between 1 and 31. Enter again:")
            return
        update_value = day
    elif field == "credit_limit":
        if raw_lower == "skip" or not raw:
            update_value = None
        else:
            limit = _parse_credit_limit(raw)
            if limit is None:
                await message.answer("⚠️ Credit limit must be numeric or <b>skip</b>. Enter again:")
                return
            update_value = limit
    elif field == "notes":
        update_value = None if raw_lower == "skip" or not raw else raw
    else:
        await state.set_state(EditCardStates.field)
        await message.answer("⚠️ Unknown field. Choose again:", reply_markup=edit_card_fields_keyboard())
        return

    async with session_maker() as session:
        card = await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))
        if not card:
            await state.clear()
            await message.answer("⚠️ Card not found.")
            return
        setattr(card, field, update_value)
        await session.commit()
        await session.refresh(card)
        summary = _format_card_summary(card)

    await state.update_data(edit_card_pending_field=None)
    await state.set_state(EditCardStates.field)
    await message.answer("✅ <b>Updated</b>\n" + summary, reply_markup=edit_card_fields_keyboard())


def _format_card_summary(card: Card) -> str:
    return (
        f"💳 <b>Card:</b> {card.bank_name}/{card.card_name}\n"
        f"🧾 <b>Billing day:</b> {card.billing_day}\n"
        f"⏰ <b>Due day:</b> {card.due_day}\n"
        f"💰 <b>Credit limit:</b> {card.credit_limit if card.credit_limit is not None else '-'}\n"
        f"📝 <b>Notes:</b> {card.notes or '-'}"
    )


def _card_field_prompt(field: str) -> str:
    if field == "bank_name":
        return "🏦 Enter new bank name:"
    if field == "card_name":
        return "💳 Enter new card nickname:"
    if field == "billing_day":
        return "🧾 Enter new billing day (1-31):"
    if field == "due_day":
        return "⏰ Enter new due day (1-31):"
    if field == "credit_limit":
        return "💰 Enter new credit limit, or send <b>skip</b> to clear:"
    if field == "notes":
        return "📝 Enter new notes, or send <b>skip</b> to clear:"
    return "✍️ Enter value:"
