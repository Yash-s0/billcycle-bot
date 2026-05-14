from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import cards_keyboard, txn_draft_keyboard, txn_recent_dates_keyboard, yes_no_keyboard
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
    render_pre_table,
    short_text,
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

    await state.update_data(
        amount=str(amount),
        merchant=None,
        category=None,
        txn_date=date.today().isoformat(),
        discount_amount="0",
        cashback_amount="0",
        is_for_someone_else=False,
        reimbursement_status=ReimbursementStatus.OWN.value,
        person_name=None,
        pending_field=None,
    )
    await state.set_state(AddTransactionStates.review)
    await _send_txn_draft_menu(message, state)


@router.callback_query(AddTransactionStates.review, F.data.startswith("txn_opt:"))
@router.callback_query(AddTransactionStates.input_optional, F.data.startswith("txn_opt:"))
async def add_txn_draft_action(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return

    action = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    is_for_someone_else = bool(data.get("is_for_someone_else", False))

    if action == "cancel":
        await callback.answer("Cancelled")
        await state.clear()
        await callback.message.answer("Transaction creation cancelled.")
        return

    if action == "save":
        if is_for_someone_else and not str(data.get("person_name", "")).strip():
            await callback.answer("Add person name first", show_alert=True)
            await callback.message.answer(
                "This is marked as 'for someone else'. Tap Person Name and add it before saving."
            )
            return
        await callback.answer()
        await _persist_transaction(callback.message, state, session_maker=session_maker)
        return

    if action == "toggle_someone":
        if is_for_someone_else:
            await state.update_data(
                is_for_someone_else=False,
                reimbursement_status=ReimbursementStatus.OWN.value,
                person_name=None,
            )
        else:
            await state.update_data(
                is_for_someone_else=True,
                reimbursement_status=ReimbursementStatus.PENDING.value,
            )
        await callback.answer()
        await state.set_state(AddTransactionStates.review)
        await _send_txn_draft_menu(callback.message, state)
        return

    if action == "toggle_paid":
        if not is_for_someone_else:
            await callback.answer("Enable 'For Someone Else' first", show_alert=True)
            return
        current_status = str(data.get("reimbursement_status", ReimbursementStatus.PENDING.value))
        next_status = (
            ReimbursementStatus.PENDING.value
            if current_status == ReimbursementStatus.PAID.value
            else ReimbursementStatus.PAID.value
        )
        await state.update_data(reimbursement_status=next_status)
        await callback.answer()
        await state.set_state(AddTransactionStates.review)
        await _send_txn_draft_menu(callback.message, state)
        return

    if action not in {"merchant", "category", "txn_date", "discount_amount", "cashback_amount", "person_name"}:
        await callback.answer("Unknown option", show_alert=True)
        return

    await callback.answer()
    await state.update_data(pending_field=action)
    await state.set_state(AddTransactionStates.input_optional)
    if action == "txn_date":
        await callback.message.answer(
            "Pick transaction date (or use Custom Date):",
            reply_markup=txn_recent_dates_keyboard(days=7),
        )
        return
    await callback.message.answer(_prompt_for_optional_field(action))


@router.callback_query(AddTransactionStates.input_optional, F.data.startswith("txn_datepick:"))
async def add_txn_pick_recent_date(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.message:
        return

    choice = callback.data.split(":", maxsplit=1)[1]
    if choice == "back":
        await callback.answer()
        await state.update_data(pending_field=None)
        await state.set_state(AddTransactionStates.review)
        await _send_txn_draft_menu(callback.message, state)
        await _delete_message_safely(callback.message)
        return

    if choice == "custom":
        await callback.answer()
        await callback.message.answer("Send transaction date in YYYY-MM-DD (or send 'skip' for today):")
        return

    try:
        picked_date = datetime.strptime(choice, "%Y-%m-%d").date()
    except ValueError:
        await callback.answer("Invalid date option", show_alert=True)
        return

    await callback.answer()
    await state.update_data(txn_date=picked_date.isoformat(), pending_field=None)
    await state.set_state(AddTransactionStates.review)
    await _send_txn_draft_menu(callback.message, state)
    await _delete_message_safely(callback.message)


@router.message(AddTransactionStates.input_optional)
async def add_txn_optional_field_input(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    field = str(data.get("pending_field", "")).strip()
    raw = (message.text or "").strip()
    raw_lower = raw.lower()

    if field not in {"merchant", "category", "txn_date", "discount_amount", "cashback_amount", "person_name"}:
        await state.set_state(AddTransactionStates.review)
        await message.answer("No field selected. Use the buttons below.")
        await _send_txn_draft_menu(message, state)
        return

    if field in {"merchant", "category", "person_name"}:
        value = None if raw_lower == "skip" or not raw else raw
        if field == "person_name" and bool(data.get("is_for_someone_else", False)) and not value:
            await message.answer("Person name cannot be empty for 'For Someone Else'. Enter a name:")
            return
        await state.update_data(**{field: value}, pending_field=None)
    elif field == "txn_date":
        if raw_lower in {"skip", "today", ""}:
            txn_date = date.today()
        else:
            try:
                txn_date = datetime.strptime(raw, "%Y-%m-%d").date()
            except ValueError:
                await message.answer("Invalid date. Use YYYY-MM-DD, or send 'skip' for today:")
                return
        await state.update_data(txn_date=txn_date.isoformat(), pending_field=None)
    elif field == "discount_amount":
        discount = parse_non_negative_decimal(raw)
        if discount is None:
            await message.answer("Discount must be a non-negative number. Enter discount amount:")
            return
        amount = Decimal(str(data["amount"]))
        if discount > amount:
            await message.answer("Discount cannot exceed amount. Enter discount amount again:")
            return
        cashback = Decimal(str(data.get("cashback_amount", "0")))
        final_amount = amount - discount
        if cashback > final_amount:
            await message.answer(
                f"Discount makes total {format_inr(final_amount)}, which is below current cashback {format_inr(cashback)}. "
                "Lower cashback first or enter a smaller discount:"
            )
            return
        await state.update_data(discount_amount=str(discount), pending_field=None)
    elif field == "cashback_amount":
        cashback = parse_non_negative_decimal(raw)
        if cashback is None:
            await message.answer("Cashback must be a non-negative number. Enter cashback amount:")
            return
        amount = Decimal(str(data["amount"]))
        discount = Decimal(str(data.get("discount_amount", "0")))
        final_amount = amount - discount
        if cashback > final_amount:
            await message.answer("Cashback cannot exceed total after discount. Enter cashback again:")
            return
        await state.update_data(cashback_amount=str(cashback), pending_field=None)

    await state.set_state(AddTransactionStates.review)
    await _send_txn_draft_menu(message, state)


def _prompt_for_optional_field(field: str) -> str:
    if field == "merchant":
        return "Send merchant name (or send 'skip' to clear it):"
    if field == "category":
        return "Send category (or send 'skip' to clear it):"
    if field == "txn_date":
        return "Send transaction date in YYYY-MM-DD (or send 'skip' for today):"
    if field == "discount_amount":
        return "Send discount amount (non-negative):"
    if field == "cashback_amount":
        return "Send cashback amount (non-negative):"
    if field == "person_name":
        return "Send person name (or send 'skip' to clear it):"
    return "Send value:"


async def _send_txn_draft_menu(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    amount = Decimal(str(data["amount"]))
    discount_amount = Decimal(str(data.get("discount_amount", "0")))
    cashback_amount = Decimal(str(data.get("cashback_amount", "0")))
    final_amount = amount - discount_amount
    recoverable_amount = final_amount - cashback_amount
    is_for_someone_else = bool(data.get("is_for_someone_else", False))
    reimbursement_status = str(data.get("reimbursement_status", ReimbursementStatus.OWN.value))
    reimbursement_text = (
        reimbursement_status
        if is_for_someone_else
        else ReimbursementStatus.OWN.value
    )
    person_name = str(data.get("person_name") or "-")

    draft_text = (
        "Transaction draft\n"
        f"Card: {data.get('card_label', '-')}\n"
        f"Amount: {format_inr(amount)}\n"
        f"Merchant: {data.get('merchant') or '-'}\n"
        f"Category: {data.get('category') or '-'}\n"
        f"Date: {data.get('txn_date', '-')}\n"
        f"Discount: {format_inr(discount_amount)}\n"
        f"Cashback: {format_inr(cashback_amount)}\n"
        f"For someone else: {'Yes' if is_for_someone_else else 'No'}\n"
        f"Person: {person_name}\n"
        f"Reimbursement: {reimbursement_text}\n"
        f"Total after discount: {format_inr(final_amount)}\n"
        f"Owes/Net after cashback: {format_inr(recoverable_amount)}\n\n"
        "Use the buttons below to update only the fields you need, then Save Transaction."
    )
    reply_markup = txn_draft_keyboard(is_for_someone_else=is_for_someone_else)
    draft_message_id_raw = data.get("draft_message_id")
    draft_chat_id_raw = data.get("draft_chat_id")

    if draft_message_id_raw and draft_chat_id_raw:
        try:
            await message.bot.edit_message_text(
                text=draft_text,
                chat_id=int(draft_chat_id_raw),
                message_id=int(draft_message_id_raw),
                reply_markup=reply_markup,
            )
            return
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return

    sent = await message.answer(draft_text, reply_markup=reply_markup)
    await state.update_data(draft_chat_id=sent.chat.id, draft_message_id=sent.message_id)


async def _delete_message_safely(message: Message) -> None:
    try:
        await message.delete()
    except TelegramBadRequest:
        return


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
    cashback_amount = Decimal(str(data.get("cashback_amount", "0")))
    final_amount = amount - discount_amount

    if final_amount < 0:
        await message.answer("Final amount cannot be negative. Please try /add_txn again.")
        await state.clear()
        return
    if cashback_amount > final_amount:
        await message.answer("Cashback cannot exceed total after discount. Please try /add_txn again.")
        await state.clear()
        return

    txn_date = datetime.strptime(str(data["txn_date"]), "%Y-%m-%d").date()
    recoverable_amount = final_amount - cashback_amount

    async with session_maker() as session:
        person_id = None
        if data.get("is_for_someone_else"):
            person_name = str(data.get("person_name") or "").strip()
            if not person_name:
                await message.answer("Person name is required for reimbursements. Please use /add_txn again.")
                await state.clear()
                return
            person = await get_or_create_person(session, int(data["user_id"]), person_name)
            person_id = person.id

        status = ReimbursementStatus(str(data.get("reimbursement_status", ReimbursementStatus.OWN.value)))
        txn = Transaction(
            user_id=int(data["user_id"]),
            card_id=int(data["card_id"]),
            amount=amount,
            discount_amount=discount_amount,
            cashback_amount=cashback_amount,
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

        if (
            txn.is_for_someone_else
            and person_id
            and status == ReimbursementStatus.PAID
            and recoverable_amount > 0
        ):
            session.add(
                Payment(
                    user_id=txn.user_id,
                    transaction_id=txn.id,
                    person_id=person_id,
                    amount_paid=recoverable_amount,
                    notes="Marked as already paid while creating transaction.",
                )
            )
        await session.commit()

    await state.clear()
    await message.answer(
        "Transaction saved.\n"
        f"Total: {format_inr(final_amount)}\n"
        f"Amount entered: {format_inr(amount)}\n"
        f"Discount: {format_inr(discount_amount)}\n"
        f"Cashback: {format_inr(cashback_amount)}\n"
        f"Owes/Net after cashback: {format_inr(recoverable_amount)}"
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

    rows: list[list[str]] = []
    for txn in txns:
        owes_amount = txn.final_amount - txn.cashback_amount
        rows.append(
            [
                str(txn.transaction_id),
                txn.txn_date.isoformat(),
                short_text(txn.card_label, 14),
                format_inr(txn.final_amount),
                format_inr(txn.cashback_amount),
                format_inr(owes_amount),
                short_text(txn.merchant, 14),
                short_text(txn.category, 12),
                txn.reimbursement_status,
            ]
        )
    table = render_pre_table(
        headers=["ID", "Date", "Card", "Total", "Cashbk", "Owes", "Merchant", "Category", "Status"],
        rows=rows,
        right_align_cols={0, 3, 4, 5},
    )
    await message.answer("Recent transactions:")
    await message.answer(table)


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

    rows: list[list[str]] = []
    for txn in recent:
        owes_amount = txn.final_amount - txn.cashback_amount
        rows.append(
            [
                str(txn.transaction_id),
                txn.txn_date.isoformat(),
                short_text(txn.card_label, 14),
                format_inr(txn.final_amount),
                format_inr(txn.cashback_amount),
                format_inr(owes_amount),
            ]
        )

    await state.clear()
    await state.set_state(DeleteTransactionStates.transaction_id)
    await state.update_data(user_id=user.id)
    table = render_pre_table(
        headers=["ID", "Date", "Card", "Total", "Cashbk", "Owes"],
        rows=rows,
        right_align_cols={0, 3, 4, 5},
    )
    await message.answer(f"Recent transactions:\n{table}\n\nEnter transaction ID to delete:")


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
