from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..keyboards import (
    cards_keyboard,
    edit_action_keyboard,
    edit_confirm_delete_keyboard,
    edit_txn_fields_keyboard,
    edit_txn_select_keyboard,
    txn_account_keyboard,
    txn_mode_keyboard,
    txn_draft_keyboard,
    txn_recent_dates_keyboard,
)
from ..models import Card, Payment, PaymentMode, ReimbursementStatus, SharedExpenseAccess, Transaction, User
from ..services.reports import RecentTransactionRow, format_inr, list_recent_transactions
from ..states import AddTransactionStates, EditTransactionStates
from .common import (
    ensure_user,
    get_or_create_person,
    get_user_by_telegram_id,
    parse_non_negative_decimal,
    parse_positive_decimal,
    short_text,
)

router = Router(name=__name__)


def _txn_card_picker_label(card: Card) -> str:
    return card.card_name


def _txn_is_accessible_clause(viewer_user_id: int) -> object:
    return or_(
        Transaction.user_id == viewer_user_id,
        Transaction.added_by_user_id == viewer_user_id,
    )


def _payment_mode_label(mode: PaymentMode | str) -> str:
    value = mode.value if isinstance(mode, PaymentMode) else str(mode)
    if value == PaymentMode.UPI.value:
        return "UPI"
    if value == PaymentMode.CASH.value:
        return "Cash"
    return "Card"


def _coerce_payment_mode(raw_mode: object) -> PaymentMode:
    raw_value = str(raw_mode or PaymentMode.CARD.value)
    if raw_value in {member.value for member in PaymentMode}:
        return PaymentMode(raw_value)
    return PaymentMode.CARD


async def _send_add_txn_mode_prompt(
    message: Message,
    prefill_amount: Decimal | None = None,
) -> None:
    prompt = "Select payment mode:"
    if prefill_amount is not None:
        prompt = f"Amount detected: {format_inr(prefill_amount)}\nSelect payment mode:"
    await message.answer(prompt, reply_markup=txn_mode_keyboard("txn_mode"))


async def _start_add_txn_account_selection(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
    prefill_amount: Decimal | None = None,
) -> None:
    if not message.from_user:
        return

    async with session_maker() as session:
        adder = await ensure_user(session, message.from_user)
        shared_owner_rows = (
            await session.execute(
                select(SharedExpenseAccess.owner_user_id, User.full_name)
                .join(User, User.id == SharedExpenseAccess.owner_user_id)
                .where(SharedExpenseAccess.collaborator_user_id == adder.id)
                .order_by(User.full_name.asc())
            )
        ).all()

    await state.clear()
    await state.update_data(
        adder_user_id=adder.id,
        prefill_amount=str(prefill_amount) if prefill_amount is not None else None,
    )

    if not shared_owner_rows:
        await state.update_data(
            user_id=adder.id,
            owner_label="You",
        )
        await state.set_state(AddTransactionStates.mode)
        await _send_add_txn_mode_prompt(message, prefill_amount)
        return

    account_rows: list[tuple[str, str]] = [("self", "You")]
    for owner_user_id, owner_name in shared_owner_rows:
        account_rows.append((f"owner:{owner_user_id}", short_text(owner_name, 22)))
    await state.set_state(AddTransactionStates.account)
    await message.answer("Add transaction for which account?", reply_markup=txn_account_keyboard(account_rows))


@router.message(Command("add_txn"))
async def add_txn_command(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    await _start_add_txn_account_selection(message, state, session_maker=session_maker)


@router.message(StateFilter(None), F.text.regexp(r"^\s*\d[\d,]*(\.\d+)?\s*$"))
async def quick_add_txn_amount_trigger(
    message: Message,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    amount = parse_positive_decimal(message.text or "")
    if amount is None:
        return
    await _start_add_txn_account_selection(
        message,
        state,
        session_maker=session_maker,
        prefill_amount=amount,
    )


@router.callback_query(AddTransactionStates.account, F.data.startswith("txn_account:"))
async def add_txn_select_account(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return

    choice = callback.data.split(":", maxsplit=1)[1]
    data = await state.get_data()
    adder_user_id = int(data["adder_user_id"])
    prefill_amount_raw = data.get("prefill_amount")
    prefill_amount = parse_positive_decimal(str(prefill_amount_raw)) if prefill_amount_raw is not None else None

    if choice == "cancel":
        await callback.answer("Cancelled")
        await state.clear()
        await callback.message.answer("Add transaction cancelled.")
        return

    if choice == "self":
        await callback.answer()
        await state.update_data(user_id=adder_user_id, owner_label="You")
        await state.set_state(AddTransactionStates.mode)
        await _send_add_txn_mode_prompt(callback.message, prefill_amount)
        return

    if not choice.startswith("owner:"):
        await callback.answer("Invalid account", show_alert=True)
        return

    raw_owner_id = choice.split(":", maxsplit=1)[1]
    if not raw_owner_id.isdigit():
        await callback.answer("Invalid account", show_alert=True)
        return
    owner_user_id = int(raw_owner_id)

    async with session_maker() as session:
        owner = await session.scalar(select(User).where(User.id == owner_user_id))
        shared_access = await session.scalar(
            select(SharedExpenseAccess).where(
                SharedExpenseAccess.owner_user_id == owner_user_id,
                SharedExpenseAccess.collaborator_user_id == adder_user_id,
            )
        )
    if not owner or not shared_access:
        await callback.answer("Access not found", show_alert=True)
        return

    await callback.answer()
    await state.update_data(user_id=owner_user_id, owner_label=owner.full_name)
    await state.set_state(AddTransactionStates.mode)
    await _send_add_txn_mode_prompt(callback.message, prefill_amount)


@router.callback_query(AddTransactionStates.mode, F.data.startswith("txn_mode:"))
async def add_txn_select_mode(callback: CallbackQuery, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not callback.message:
        return

    raw_mode = callback.data.split(":", maxsplit=1)[1]
    if raw_mode not in {PaymentMode.CARD.value, PaymentMode.UPI.value, PaymentMode.CASH.value}:
        await callback.answer("Invalid mode", show_alert=True)
        return

    data = await state.get_data()
    user_id = int(data["user_id"])
    selected_mode = PaymentMode(raw_mode)
    await state.update_data(
        payment_mode=selected_mode.value,
        card_id=None,
        card_label=None,
    )

    if selected_mode == PaymentMode.CARD:
        async with session_maker() as session:
            cards = (
                await session.execute(
                    select(Card)
                    .where(Card.user_id == user_id)
                    .order_by(Card.bank_name.asc(), Card.card_name.asc(), Card.id.asc())
                )
            ).scalars().all()
        if not cards:
            await callback.answer("No cards found", show_alert=True)
            await callback.message.answer("No cards found. Add a card first with /add_card.")
            return

        card_rows = [(card.id, _txn_card_picker_label(card)) for card in cards]
        await callback.answer()
        await state.set_state(AddTransactionStates.card)
        await callback.message.answer("Select card:", reply_markup=cards_keyboard(card_rows))
        return

    prefill_amount_raw = data.get("prefill_amount")
    prefill_amount = parse_positive_decimal(str(prefill_amount_raw)) if prefill_amount_raw is not None else None
    source_label = _payment_mode_label(selected_mode)
    await callback.answer()
    if prefill_amount is not None:
        await callback.message.answer(f"Selected payment mode: {source_label}")
        await _open_add_txn_draft(callback.message, state, prefill_amount)
        return

    await state.set_state(AddTransactionStates.amount)
    await callback.message.answer(f"Selected payment mode: {source_label}\nEnter amount:")


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
    selected_card_label = _txn_card_picker_label(card)
    await state.update_data(
        payment_mode=PaymentMode.CARD.value,
        card_id=card.id,
        card_label=selected_card_label,
    )
    prefill_amount_raw = data.get("prefill_amount")
    if prefill_amount_raw is not None:
        prefill_amount = parse_positive_decimal(str(prefill_amount_raw))
        if prefill_amount is not None:
            await callback.message.answer(f"Selected: {selected_card_label}")
            await _open_add_txn_draft(callback.message, state, prefill_amount)
            return

    await state.set_state(AddTransactionStates.amount)
    await callback.message.answer(f"Selected: {selected_card_label}\nEnter amount:")


@router.message(AddTransactionStates.amount)
async def add_txn_amount(message: Message, state: FSMContext) -> None:
    amount = parse_positive_decimal(message.text or "")
    if amount is None:
        await message.answer("Amount must be a positive number. Enter amount:")
        return

    await _open_add_txn_draft(message, state, amount)


async def _open_add_txn_draft(message: Message, state: FSMContext, amount: Decimal) -> None:
    data = await state.get_data()
    payment_mode = _coerce_payment_mode(data.get("payment_mode"))
    await state.update_data(
        payment_mode=payment_mode.value,
        amount=str(amount),
        category=None,
        notes=None,
        txn_date=date.today().isoformat(),
        discount_amount="0",
        cashback_amount="0",
        is_for_someone_else=False,
        reimbursement_status=ReimbursementStatus.OWN.value,
        person_name=None,
        pending_field=None,
        prefill_amount=None,
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

    if action not in {"category", "notes", "txn_date", "discount_amount", "cashback_amount", "person_name"}:
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

    if field not in {"category", "notes", "txn_date", "discount_amount", "cashback_amount", "person_name"}:
        await state.set_state(AddTransactionStates.review)
        await message.answer("No field selected. Use the buttons below.")
        await _send_txn_draft_menu(message, state)
        return

    if field in {"category", "notes", "person_name"}:
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
    if field == "category":
        return "Send category (or send 'skip' to clear it):"
    if field == "notes":
        return "Send notes (or send 'skip' to clear it):"
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
    payment_mode = _coerce_payment_mode(data.get("payment_mode"))
    owner_label = str(data.get("owner_label") or "You")
    payment_source = (
        str(data.get("card_label") or "-")
        if payment_mode == PaymentMode.CARD
        else _payment_mode_label(payment_mode)
    )
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
    person_name = str(data.get("person_name") or "").strip()
    category = str(data.get("category") or "").strip()
    notes = str(data.get("notes") or "").strip()
    txn_date = str(data.get("txn_date") or "").strip()

    lines = [
        "Transaction draft",
        f"Account: {owner_label}",
        f"Payment mode: {_payment_mode_label(payment_mode)}",
        f"Source: {payment_source}",
        f"Amount: {format_inr(amount)}",
    ]
    if category:
        lines.append(f"Category: {category}")
    if notes:
        lines.append(f"Notes: {notes}")
    if txn_date:
        lines.append(f"Date: {txn_date}")
    if discount_amount > 0:
        lines.append(f"Discount: {format_inr(discount_amount)}")
    if cashback_amount > 0:
        lines.append(f"Cashback: {format_inr(cashback_amount)}")
    if is_for_someone_else:
        lines.append("For someone else: Yes")
        if person_name:
            lines.append(f"Person: {person_name}")
        lines.append(f"Reimbursement: {reimbursement_text}")
    lines.extend(
        [
            f"Total after discount: {format_inr(final_amount)}",
            f"Owes/Net after cashback: {format_inr(recoverable_amount)}",
            "",
            "Use the buttons below to update only the fields you need, then Save Transaction.",
        ]
    )
    draft_text = "\n".join(lines)
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
    owner_user_id = int(data["user_id"])
    added_by_user_id = int(data.get("adder_user_id", owner_user_id))
    payment_mode = _coerce_payment_mode(data.get("payment_mode"))
    raw_card_id = data.get("card_id")
    card_id = int(raw_card_id) if raw_card_id is not None else None
    if payment_mode == PaymentMode.CARD and card_id is None:
        await message.answer("Select a card for card-mode transactions. Please try /add_txn again.")
        await state.clear()
        return
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
        if payment_mode == PaymentMode.CARD:
            card = await session.scalar(
                select(Card).where(
                    Card.id == card_id,
                    Card.user_id == owner_user_id,
                )
            )
            if not card:
                await message.answer("Selected card was not found for this account. Please try /add_txn again.")
                await state.clear()
                return

        person_id = None
        if data.get("is_for_someone_else"):
            person_name = str(data.get("person_name") or "").strip()
            if not person_name:
                await message.answer("Person name is required for reimbursements. Please use /add_txn again.")
                await state.clear()
                return
            person = await get_or_create_person(session, owner_user_id, person_name)
            person_id = person.id

        status = ReimbursementStatus(str(data.get("reimbursement_status", ReimbursementStatus.OWN.value)))
        txn = Transaction(
            user_id=owner_user_id,
            added_by_user_id=added_by_user_id,
            card_id=card_id,
            payment_mode=payment_mode,
            amount=amount,
            discount_amount=discount_amount,
            cashback_amount=cashback_amount,
            final_amount=final_amount,
            txn_date=txn_date,
            is_for_someone_else=bool(data.get("is_for_someone_else", False)),
            person_id=person_id,
            reimbursement_status=status,
            category=data.get("category"),
            notes=data.get("notes"),
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

    own_txns = [txn for txn in txns if txn.owner_user_id == user.id and txn.added_by_user_id == user.id]
    added_by_others = [txn for txn in txns if txn.owner_user_id == user.id and txn.added_by_user_id != user.id]
    added_to_others = [txn for txn in txns if txn.owner_user_id != user.id and txn.added_by_user_id == user.id]

    lines = ["Recent transactions:"]

    def _append_txn_block(title: str, rows: list[RecentTransactionRow], include_owner: bool, include_adder: bool) -> None:
        if not rows:
            return
        lines.append("")
        lines.append(title)
        for txn in rows:
            owes_amount = txn.final_amount - txn.cashback_amount
            lines.append(
                f"{txn.txn_date.isoformat()} | {short_text(txn.card_label, 18)} | Total {format_inr(txn.final_amount)}"
            )
            details = [
                f"Cashbk {format_inr(txn.cashback_amount)}",
                f"Owes {format_inr(owes_amount)}",
            ]
            if include_owner:
                details.append(f"Account {short_text(txn.owner_name, 16)}")
            if include_adder:
                details.append(f"Added by {short_text(txn.added_by_name, 16)}")
            if txn.is_for_someone_else and txn.person_name:
                details.append(f"For {short_text(txn.person_name, 16)}")
            category = "-" if txn.category == "-" else short_text(txn.category, 24)
            details.append(f"Category {category}")
            notes = "-" if txn.notes == "-" else short_text(txn.notes, 40)
            details.append(f"Notes {notes}")
            lines.append(" | ".join(details))
            lines.append("")

    _append_txn_block("Your transactions:", own_txns, include_owner=False, include_adder=False)
    _append_txn_block("Added to your account by others:", added_by_others, include_owner=False, include_adder=True)
    _append_txn_block("Transactions you added to others:", added_to_others, include_owner=True, include_adder=False)

    if len(lines) == 1:
        # Fallback: if rows are somehow filtered out from all sections, show generic list.
        for txn in txns:
            owes_amount = txn.final_amount - txn.cashback_amount
            lines.append(
                f"{txn.txn_date.isoformat()} | {short_text(txn.card_label, 18)} | Total {format_inr(txn.final_amount)}"
            )
            lines.append(
                f"Cashbk {format_inr(txn.cashback_amount)} | Owes {format_inr(owes_amount)} | "
                f"Category {short_text(txn.category, 24)} | Notes {short_text(txn.notes, 40)}"
            )
            lines.append("")

    await message.answer("\n".join(lines).strip())


@router.message(Command("edit_txn"))
async def edit_txn_command(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
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

    rows = [(txn.transaction_id, _txn_picker_button_label(txn)) for txn in txns]
    await state.clear()
    await state.set_state(EditTransactionStates.transaction)
    await state.update_data(user_id=user.id)
    await message.answer("Select a transaction to edit:", reply_markup=edit_txn_select_keyboard(rows))


@router.callback_query(EditTransactionStates.transaction, F.data.startswith("edit_txn_pick:"))
async def edit_txn_select(callback: CallbackQuery, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not callback.message:
        return
    await callback.answer()

    raw = callback.data.split(":", maxsplit=1)[1]
    if raw == "cancel":
        await state.clear()
        await callback.message.answer("Edit transaction cancelled.")
        return
    if not raw.isdigit():
        await callback.message.answer("Invalid transaction.")
        await state.clear()
        return

    txn_id = int(raw)
    data = await state.get_data()
    user_id = int(data["user_id"])
    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(
                Transaction.id == txn_id,
                _txn_is_accessible_clause(user_id),
            )
        )
    if not txn:
        await callback.message.answer("Transaction not found.")
        await state.clear()
        return

    await state.update_data(edit_txn_id=txn.id)
    await state.set_state(EditTransactionStates.action)
    await callback.message.answer(
        _format_txn_summary(txn),
        reply_markup=edit_action_keyboard("edit_txn_action"),
    )


@router.callback_query(EditTransactionStates.action, F.data.startswith("edit_txn_action:"))
async def edit_txn_action(callback: CallbackQuery, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    if not callback.message:
        return
    await callback.answer()
    action = callback.data.split(":", maxsplit=1)[1]

    if action == "cancel":
        await state.clear()
        await callback.message.answer("Edit transaction cancelled.")
        return
    if action == "delete":
        await state.set_state(EditTransactionStates.confirm_delete)
        await callback.message.answer(
            "Delete this transaction?",
            reply_markup=edit_confirm_delete_keyboard("edit_txn_delete"),
        )
        return

    data = await state.get_data()
    user_id = int(data["user_id"])
    txn_id = int(data["edit_txn_id"])
    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(
                Transaction.id == txn_id,
                _txn_is_accessible_clause(user_id),
            )
        )
    if not txn:
        await state.clear()
        await callback.message.answer("Transaction not found.")
        return
    await state.set_state(EditTransactionStates.field)
    await callback.message.answer(
        "Choose what to update:",
        reply_markup=edit_txn_fields_keyboard(bool(txn.is_for_someone_else)),
    )


@router.callback_query(EditTransactionStates.confirm_delete, F.data.startswith("edit_txn_delete:"))
async def edit_txn_delete_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return
    await callback.answer()
    choice = callback.data.split(":", maxsplit=1)[1]
    if choice == "no":
        await state.set_state(EditTransactionStates.action)
        await callback.message.answer("Delete cancelled.", reply_markup=edit_action_keyboard("edit_txn_action"))
        return

    data = await state.get_data()
    user_id = int(data["user_id"])
    txn_id = int(data["edit_txn_id"])
    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(
                Transaction.id == txn_id,
                _txn_is_accessible_clause(user_id),
            )
        )
        if not txn:
            await state.clear()
            await callback.message.answer("Transaction not found. Nothing deleted.")
            return
        await session.delete(txn)
        await session.commit()

    await state.clear()
    await callback.message.answer(f"Deleted transaction ID {txn_id}.")


@router.callback_query(EditTransactionStates.field, F.data.startswith("edit_txn_field:"))
async def edit_txn_field_select(
    callback: CallbackQuery,
    state: FSMContext,
    session_maker: async_sessionmaker[AsyncSession],
) -> None:
    if not callback.message:
        return
    await callback.answer()
    field = callback.data.split(":", maxsplit=1)[1]

    if field == "back":
        await state.set_state(EditTransactionStates.action)
        await callback.message.answer("Back to actions.", reply_markup=edit_action_keyboard("edit_txn_action"))
        return

    data = await state.get_data()
    user_id = int(data["user_id"])
    txn_id = int(data["edit_txn_id"])

    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(
                Transaction.id == txn_id,
                _txn_is_accessible_clause(user_id),
            )
        )
        if not txn:
            await state.clear()
            await callback.message.answer("Transaction not found.")
            return

        if field == "toggle_someone":
            if txn.is_for_someone_else:
                txn.is_for_someone_else = False
                txn.person_id = None
                txn.reimbursement_status = ReimbursementStatus.OWN
            else:
                txn.is_for_someone_else = True
                if txn.reimbursement_status == ReimbursementStatus.OWN:
                    txn.reimbursement_status = ReimbursementStatus.PENDING
            await session.commit()
            await session.refresh(txn)
            await callback.message.answer(
                "Updated.\n" + _format_txn_summary(txn),
                reply_markup=edit_txn_fields_keyboard(bool(txn.is_for_someone_else)),
            )
            return

        if field == "toggle_paid":
            if not txn.is_for_someone_else:
                await callback.message.answer("Enable 'For Someone Else' first.")
                return
            txn.reimbursement_status = (
                ReimbursementStatus.PENDING
                if txn.reimbursement_status == ReimbursementStatus.PAID
                else ReimbursementStatus.PAID
            )
            await session.commit()
            await session.refresh(txn)
            await callback.message.answer(
                "Updated.\n" + _format_txn_summary(txn),
                reply_markup=edit_txn_fields_keyboard(bool(txn.is_for_someone_else)),
            )
            return

    await state.update_data(edit_txn_pending_field=field)
    await state.set_state(EditTransactionStates.input_value)
    await callback.message.answer(_edit_txn_field_prompt(field))


@router.message(EditTransactionStates.input_value)
async def edit_txn_field_input(message: Message, state: FSMContext, session_maker: async_sessionmaker[AsyncSession]) -> None:
    data = await state.get_data()
    field = str(data.get("edit_txn_pending_field") or "")
    user_id = int(data["user_id"])
    txn_id = int(data["edit_txn_id"])
    raw = (message.text or "").strip()
    raw_lower = raw.lower()

    async with session_maker() as session:
        txn = await session.scalar(
            select(Transaction).where(
                Transaction.id == txn_id,
                _txn_is_accessible_clause(user_id),
            )
        )
        if not txn:
            await state.clear()
            await message.answer("Transaction not found.")
            return

        amount = Decimal(str(txn.amount))
        discount = Decimal(str(txn.discount_amount))
        cashback = Decimal(str(txn.cashback_amount))

        if field == "amount":
            parsed = parse_positive_decimal(raw)
            if parsed is None:
                await message.answer("Amount must be a positive number. Enter again:")
                return
            amount = parsed
        elif field == "category":
            txn.category = None if raw_lower == "skip" or not raw else raw
        elif field == "notes":
            txn.notes = None if raw_lower == "skip" or not raw else raw
        elif field == "txn_date":
            if raw_lower in {"skip", "today", ""}:
                txn.txn_date = date.today()
            else:
                try:
                    txn.txn_date = datetime.strptime(raw, "%Y-%m-%d").date()
                except ValueError:
                    await message.answer("Invalid date. Use YYYY-MM-DD, or send 'skip' for today:")
                    return
        elif field == "discount_amount":
            parsed = parse_non_negative_decimal(raw)
            if parsed is None:
                await message.answer("Discount must be non-negative. Enter again:")
                return
            discount = parsed
        elif field == "cashback_amount":
            parsed = parse_non_negative_decimal(raw)
            if parsed is None:
                await message.answer("Cashback must be non-negative. Enter again:")
                return
            cashback = parsed
        elif field == "person_name":
            if not txn.is_for_someone_else:
                await message.answer("Enable 'For Someone Else' first.")
                return
            if raw_lower == "skip" or not raw:
                txn.person_id = None
            else:
                person = await get_or_create_person(session, user_id, raw)
                txn.person_id = person.id
        else:
            await state.set_state(EditTransactionStates.field)
            await message.answer("Unknown field.", reply_markup=edit_txn_fields_keyboard(bool(txn.is_for_someone_else)))
            return

        final_amount = amount - discount
        if final_amount < 0:
            await message.answer("Discount cannot exceed amount. Enter again:")
            return
        if cashback > final_amount:
            await message.answer("Cashback cannot exceed total after discount. Enter again:")
            return

        txn.amount = amount
        txn.discount_amount = discount
        txn.cashback_amount = cashback
        txn.final_amount = final_amount
        if not txn.is_for_someone_else:
            txn.reimbursement_status = ReimbursementStatus.OWN
            txn.person_id = None
        elif txn.reimbursement_status == ReimbursementStatus.OWN:
            txn.reimbursement_status = ReimbursementStatus.PENDING

        await session.commit()
        await session.refresh(txn)
        summary = _format_txn_summary(txn)
        is_for_someone_else = bool(txn.is_for_someone_else)

    await state.update_data(edit_txn_pending_field=None)
    await state.set_state(EditTransactionStates.field)
    await message.answer("Updated.\n" + summary, reply_markup=edit_txn_fields_keyboard(is_for_someone_else))


def _txn_picker_button_label(txn: RecentTransactionRow) -> str:
    label = f"{txn.txn_date.isoformat()} | {format_inr(txn.final_amount)}"
    if txn.owner_user_id != txn.added_by_user_id:
        label = f"{label} | {short_text(txn.owner_name, 12)}"
    if txn.is_for_someone_else and txn.person_name:
        return f"{label} | {short_text(txn.person_name, 14)}"
    return label


def _format_txn_summary(txn: Transaction) -> str:
    payment_mode = _coerce_payment_mode(txn.payment_mode)
    mode_label = _payment_mode_label(payment_mode)
    if payment_mode == PaymentMode.CARD:
        source_label = f"Card ID {txn.card_id}" if txn.card_id is not None else "Card"
    else:
        source_label = mode_label
    return (
        f"Transaction ID: {txn.id}\n"
        f"Payment mode: {mode_label}\n"
        f"Source: {source_label}\n"
        f"Date: {txn.txn_date.isoformat()}\n"
        f"Amount: {format_inr(txn.amount)}\n"
        f"Discount: {format_inr(txn.discount_amount)}\n"
        f"Cashback: {format_inr(txn.cashback_amount)}\n"
        f"Total: {format_inr(txn.final_amount)}\n"
        f"Category: {txn.category or '-'}\n"
        f"Notes: {txn.notes or '-'}\n"
        f"For someone else: {'Yes' if txn.is_for_someone_else else 'No'}\n"
        f"Reimbursement: {txn.reimbursement_status.value}"
    )


def _edit_txn_field_prompt(field: str) -> str:
    if field == "amount":
        return "Enter new amount:"
    if field == "category":
        return "Enter new category, or send 'skip' to clear:"
    if field == "notes":
        return "Enter new notes, or send 'skip' to clear:"
    if field == "txn_date":
        return "Enter new date in YYYY-MM-DD, or send 'skip' for today:"
    if field == "discount_amount":
        return "Enter new discount amount:"
    if field == "cashback_amount":
        return "Enter new cashback amount:"
    if field == "person_name":
        return "Enter person name, or send 'skip' to clear:"
    return "Enter value:"
