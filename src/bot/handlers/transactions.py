from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import cards_keyboard, skip_keyboard, yes_no_keyboard
from ..models import Card, Payment, ReimbursementStatus, Transaction
from ..services.reports import format_inr, list_recent_transactions
from ..states import AddTransactionStates, DeleteTransactionStates
from .common import (
    card_label,
    ensure_user,
    get_or_create_person,
    get_user_by_telegram_id,
    parse_non_negative_decimal,
    parse_positive_decimal,
)

router = Router(name=__name__)


@router.message(Command("add_txn"))
async def add_txn_command(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await ensure_user(session, message.from_user)
        cards = (
            await session.execute(
                select(Card)
                .where(Card.user_id == user.id)
                .order_by(Card.bank_name.asc(), Card.card_name.asc(), Card.id.asc())
            )
        ).scalars().all()

    if not cards:
        await message.answer("No cards found. Add a card first with /add_card.")
        return

    card_rows = [(card.id, card_label(card)) for card in cards]
    await state.clear()
    await state.set_state(AddTransactionStates.card)
    await state.update_data(user_id=user.id)
    await message.answer("Select card:", reply_markup=cards_keyboard(card_rows))


@router.callback_query(AddTransactionStates.card, F.data.startswith("card:"))
async def add_txn_select_card(callback: CallbackQuery, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not callback.message:
        return

    _, raw_card_id = callback.data.split(":", maxsplit=1)
    card_id = int(raw_card_id)
    data = await state.get_data()
    user_id = int(data["user_id"])

    async with session_maker() as session:
        card = await session.scalar(select(Card).where(Card.id == card_id, Card.user_id == user_id))

    if not card:
        await callback.answer("Card not found", show_alert=True)
        return

    await callback.answer()
    await state.update_data(card_id=card.id, card_label=card_label(card))
    await state.set_state(AddTransactionStates.amount)
    await callback.message.answer(f"Selected: {card_label(card)}\nEnter amount:")


@router.message(AddTransactionStates.amount)
async def add_txn_amount(message: Message, state: FSMContext) -> None:
    amount = parse_positive_decimal(message.text or "")
    if amount is None:
        await message.answer("Amount must be a positive number. Enter amount:")
        return

    await state.update_data(amount=str(amount))
    await state.set_state(AddTransactionStates.merchant)
    await message.answer("Enter merchant (or send 'skip'):", reply_markup=skip_keyboard("txn_merchant"))


@router.callback_query(AddTransactionStates.merchant, F.data == "txn_merchant:skip")
async def add_txn_skip_merchant(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    await callback.answer()
    await state.update_data(merchant=None)
    await state.set_state(AddTransactionStates.category)
    await callback.message.answer("Enter category (or send 'skip'):", reply_markup=skip_keyboard("txn_category"))


@router.message(AddTransactionStates.merchant)
async def add_txn_merchant(message: Message, state: FSMContext) -> None:
    merchant_raw = (message.text or "").strip()
    merchant = None if not merchant_raw or merchant_raw.lower() == "skip" else merchant_raw
    await state.update_data(merchant=merchant)
    await state.set_state(AddTransactionStates.category)
    await message.answer("Enter category (or send 'skip'):", reply_markup=skip_keyboard("txn_category"))


@router.callback_query(AddTransactionStates.category, F.data == "txn_category:skip")
async def add_txn_skip_category(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    await callback.answer()
    await state.update_data(category=None)
    await state.set_state(AddTransactionStates.txn_date)
    await callback.message.answer(
        "Enter transaction date in YYYY-MM-DD (or send 'skip' for today):",
        reply_markup=skip_keyboard("txn_date"),
    )


@router.message(AddTransactionStates.category)
async def add_txn_category(message: Message, state: FSMContext) -> None:
    category_raw = (message.text or "").strip()
    category = None if not category_raw or category_raw.lower() == "skip" else category_raw
    await state.update_data(category=category)
    await state.set_state(AddTransactionStates.txn_date)
    await message.answer(
        "Enter transaction date in YYYY-MM-DD (or send 'skip' for today):",
        reply_markup=skip_keyboard("txn_date"),
    )


@router.callback_query(AddTransactionStates.txn_date, F.data == "txn_date:skip")
async def add_txn_skip_date(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    await callback.answer()
    await state.update_data(txn_date=date.today().isoformat())
    await state.set_state(AddTransactionStates.has_discount)
    await callback.message.answer("Any discount/cashback?", reply_markup=yes_no_keyboard("txn_discount"))


@router.message(AddTransactionStates.txn_date)
async def add_txn_date(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    if raw.lower() == "skip" or not raw:
        txn_date = date.today()
    else:
        try:
            txn_date = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            await message.answer("Invalid date. Use YYYY-MM-DD or send 'skip'.")
            return

    await state.update_data(txn_date=txn_date.isoformat())
    await state.set_state(AddTransactionStates.has_discount)
    await message.answer("Any discount/cashback?", reply_markup=yes_no_keyboard("txn_discount"))


@router.callback_query(AddTransactionStates.has_discount, F.data.startswith("txn_discount:"))
async def add_txn_has_discount(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    await callback.answer()
    choice = callback.data.split(":", maxsplit=1)[1]

    if choice == "yes":
        await state.set_state(AddTransactionStates.discount_amount)
        await callback.message.answer("Enter discount amount:")
        return

    await state.update_data(discount_amount="0")
    await state.set_state(AddTransactionStates.ownership)
    await callback.message.answer("Is this purchase for someone else?", reply_markup=yes_no_keyboard("txn_someone"))


@router.message(AddTransactionStates.discount_amount)
async def add_txn_discount_amount(message: Message, state: FSMContext) -> None:
    discount = parse_non_negative_decimal(message.text or "")
    if discount is None:
        await message.answer("Discount must be a non-negative number. Enter discount amount:")
        return

    data = await state.get_data()
    amount = Decimal(str(data["amount"]))
    if discount > amount:
        await message.answer("Discount cannot exceed amount. Enter discount amount again:")
        return

    await state.update_data(discount_amount=str(discount))
    await state.set_state(AddTransactionStates.ownership)
    await message.answer("Is this purchase for someone else?", reply_markup=yes_no_keyboard("txn_someone"))


@router.callback_query(AddTransactionStates.ownership, F.data.startswith("txn_someone:"))
async def add_txn_ownership(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return

    await callback.answer()
    choice = callback.data.split(":", maxsplit=1)[1]

    if choice == "yes":
        await state.update_data(is_for_someone_else=True)
        await state.set_state(AddTransactionStates.person_name)
        await callback.message.answer("Enter person name:")
        return

    await state.update_data(
        is_for_someone_else=False,
        reimbursement_status=ReimbursementStatus.OWN.value,
        person_name=None,
    )
    await _persist_transaction(callback.message, state, session_maker=session_maker)


@router.message(AddTransactionStates.person_name)
async def add_txn_person_name(message: Message, state: FSMContext) -> None:
    person_name = (message.text or "").strip()
    if not person_name:
        await message.answer("Person name cannot be empty. Enter person name:")
        return

    await state.update_data(person_name=person_name)
    await state.set_state(AddTransactionStates.already_paid)
    await message.answer("Have they already paid you back?", reply_markup=yes_no_keyboard("txn_paid"))


@router.callback_query(AddTransactionStates.already_paid, F.data.startswith("txn_paid:"))
async def add_txn_already_paid(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return

    await callback.answer()
    choice = callback.data.split(":", maxsplit=1)[1]
    reimbursement_status = ReimbursementStatus.PAID if choice == "yes" else ReimbursementStatus.PENDING

    await state.update_data(reimbursement_status=reimbursement_status.value)
    await _persist_transaction(callback.message, state, session_maker=session_maker)


async def _persist_transaction(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession] | None,
) -> None:
    if session_maker is None:
        await message.answer("Internal error while saving transaction. Please try /add_txn again.")
        await state.clear()
        return

    data = await state.get_data()
    amount = Decimal(str(data["amount"]))
    discount_amount = Decimal(str(data.get("discount_amount", "0")))
    final_amount = amount - discount_amount

    if final_amount < 0:
        await message.answer("Final amount cannot be negative. Please try /add_txn again.")
        await state.clear()
        return

    txn_date = datetime.strptime(str(data["txn_date"]), "%Y-%m-%d").date()

    async with session_maker() as session:
        person_id = None
        if data.get("is_for_someone_else"):
            person = await get_or_create_person(session, int(data["user_id"]), str(data["person_name"]))
            person_id = person.id

        status = ReimbursementStatus(str(data.get("reimbursement_status", ReimbursementStatus.OWN.value)))
        txn = Transaction(
            user_id=int(data["user_id"]),
            card_id=int(data["card_id"]),
            amount=amount,
            discount_amount=discount_amount,
            final_amount=final_amount,
            merchant=data.get("merchant"),
            category=data.get("category"),
            txn_date=txn_date,
            is_for_someone_else=bool(data.get("is_for_someone_else", False)),
            person_id=person_id,
            reimbursement_status=status,
            notes=None,
        )
        session.add(txn)
        await session.flush()

        if txn.is_for_someone_else and person_id and status == ReimbursementStatus.PAID:
            session.add(
                Payment(
                    user_id=txn.user_id,
                    transaction_id=txn.id,
                    person_id=person_id,
                    amount_paid=final_amount,
                    notes="Marked as already paid while creating transaction.",
                )
            )
        await session.commit()

    await state.clear()
    await message.answer(
        "Transaction saved.\n"
        f"Amount: {format_inr(amount)}\n"
        f"Discount: {format_inr(discount_amount)}\n"
        f"Final: {format_inr(final_amount)}"
    )


@router.message(Command("recent_txns"))
async def recent_txns_command(message: Message, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("No profile found. Use /start first.")
            return

        txns = await list_recent_transactions(session, user.id, limit=10)

    if not txns:
        await message.answer("No transactions found. Use /add_txn.")
        return

    lines = ["Recent transactions:"]
    for txn in txns:
        lines.append(
            f"- ID {txn.transaction_id} | {txn.txn_date.isoformat()} | {txn.card_label} | "
            f"{format_inr(txn.final_amount)} | {txn.merchant} | {txn.category} | {txn.reimbursement_status}"
        )
    await message.answer("\n".join(lines))


@router.message(Command("delete_txn"))
async def delete_txn_command(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        user = await get_user_by_telegram_id(session, message.from_user.id)
        if not user:
            await message.answer("No profile found. Use /start first.")
            return

        recent = await list_recent_transactions(session, user.id, limit=10)

    if not recent:
        await message.answer("No transactions to delete.")
        return

    lines = ["Recent transactions:"]
    for txn in recent:
        lines.append(f"- ID {txn.transaction_id}: {txn.txn_date.isoformat()} {txn.card_label} {format_inr(txn.final_amount)}")

    await state.clear()
    await state.set_state(DeleteTransactionStates.transaction_id)
    await state.update_data(user_id=user.id)
    lines.append("\nEnter transaction ID to delete:")
    await message.answer("\n".join(lines))


@router.message(DeleteTransactionStates.transaction_id)
async def delete_txn_id_step(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    raw = (message.text or "").strip()
    if not raw.isdigit():
        await message.answer("Transaction ID must be numeric. Enter transaction ID:")
        return

    txn_id = int(raw)
    data = await state.get_data()
    user_id = int(data["user_id"])

    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user_id)
        )

    if not txn:
        await message.answer("Transaction not found for your account. Enter a valid transaction ID:")
        return

    await state.update_data(transaction_id=txn.id)
    await state.set_state(DeleteTransactionStates.confirm)
    await message.answer(
        f"Confirm delete transaction ID {txn.id} ({txn.txn_date.isoformat()}, {format_inr(txn.final_amount)})?",
        reply_markup=yes_no_keyboard("del_txn"),
    )


@router.callback_query(DeleteTransactionStates.confirm, F.data.startswith("del_txn:"))
async def delete_txn_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return

    await callback.answer()
    choice = callback.data.split(":", maxsplit=1)[1]

    if choice == "no":
        await state.clear()
        await callback.message.answer("Delete cancelled.")
        return

    data = await state.get_data()
    user_id = int(data["user_id"])
    txn_id = int(data["transaction_id"])

    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user_id)
        )
        if not txn:
            await state.clear()
            await callback.message.answer("Transaction not found. Nothing deleted.")
            return

        await session.delete(txn)
        await session.commit()

    await state.clear()
    await callback.message.answer(f"Deleted transaction ID {txn_id}.")
