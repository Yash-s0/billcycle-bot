from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import skip_keyboard
from ..models import Card
from ..states import AddCardStates
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
    await message.answer("Enter bank name:")


@router.message(AddCardStates.bank_name)
async def add_card_bank_name(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Bank name cannot be empty. Enter bank name:")
        return

    await state.update_data(bank_name=value)
    await state.set_state(AddCardStates.card_name)
    await message.answer("Enter card nickname:")


@router.message(AddCardStates.card_name)
async def add_card_card_name(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if not value:
        await message.answer("Card nickname cannot be empty. Enter card nickname:")
        return

    await state.update_data(card_name=value)
    await state.set_state(AddCardStates.billing_day)
    await message.answer("Enter billing day of month (1-31):")


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
        await message.answer("Billing day must be between 1 and 31. Enter billing day:")
        return

    await state.update_data(billing_day=day)
    await state.set_state(AddCardStates.due_day)
    await message.answer("Enter due day of month (1-31):")


@router.message(AddCardStates.due_day)
async def add_card_due_day(message: Message, state: FSMContext) -> None:
    day = _parse_day((message.text or "").strip())
    if day is None:
        await message.answer("Due day must be between 1 and 31. Enter due day:")
        return

    await state.update_data(due_day=day)
    await state.set_state(AddCardStates.credit_limit)
    await message.answer(
        "Enter credit limit (optional). Send 'skip' to skip.",
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
    await callback.message.answer("Add notes (optional). Send 'skip' to skip.", reply_markup=skip_keyboard("card_notes"))


@router.message(AddCardStates.credit_limit)
async def add_card_credit_limit(message: Message, state: FSMContext) -> None:
    value = (message.text or "").strip()
    if value.lower() == "skip":
        await state.update_data(credit_limit=None)
    else:
        amount = _parse_credit_limit(value)
        if amount is None:
            await message.answer("Credit limit must be numeric or 'skip'. Enter credit limit:")
            return
        await state.update_data(credit_limit=amount)

    await state.set_state(AddCardStates.notes)
    await message.answer("Add notes (optional). Send 'skip' to skip.", reply_markup=skip_keyboard("card_notes"))


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
    await message.answer(f"Card saved: {card.bank_name}/{card.card_name}")


@router.message(Command("list_cards"))
async def list_cards_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
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
        await message.answer("You have no cards yet. Use /add_card.")
        return

    lines = ["Your cards:"]
    for card in cards:
        lines.append(
            f"- ID {card.id}: {card.bank_name}/{card.card_name} "
            f"(Billing {card.billing_day}, Due {card.due_day})"
        )
    await message.answer("\n".join(lines))
