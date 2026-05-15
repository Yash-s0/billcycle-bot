from __future__ import annotations

from datetime import date, timedelta
from typing import Sequence

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes", callback_data=f"{prefix}:yes")
    builder.button(text="No", callback_data=f"{prefix}:no")
    builder.adjust(2)
    return builder.as_markup()


def skip_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Skip", callback_data=f"{prefix}:skip")
    return builder.as_markup()


def cards_keyboard(cards: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for card_id, label in cards:
        builder.button(text=label, callback_data=f"card:{card_id}")
    builder.adjust(1)
    return builder.as_markup()


def txn_mode_keyboard(prefix: str = "txn_mode") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Card", callback_data=f"{prefix}:card")
    builder.button(text="UPI", callback_data=f"{prefix}:upi")
    builder.button(text="Cash", callback_data=f"{prefix}:cash")
    builder.adjust(3)
    return builder.as_markup()


def txn_account_keyboard(accounts: Sequence[tuple[str, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for account_key, label in accounts:
        builder.button(text=label, callback_data=f"txn_account:{account_key}")
    builder.button(text="Cancel", callback_data="txn_account:cancel")
    builder.adjust(1)
    return builder.as_markup()


def people_keyboard(people: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for person_id, label in people:
        builder.button(text=label, callback_data=f"person:{person_id}")
    builder.adjust(1)
    return builder.as_markup()


def transactions_keyboard(transactions: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for txn_id, label in transactions:
        builder.button(text=label, callback_data=f"txn:{txn_id}")
    builder.adjust(1)
    return builder.as_markup()


def months_keyboard(months: Sequence[date], include_current_shortcut: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if include_current_shortcut:
        builder.button(text="Current Month", callback_data="month:current")
    for month in months:
        builder.button(text=month.strftime("%b %Y"), callback_data=f"month:{month.strftime('%Y-%m')}")
    builder.adjust(2)
    return builder.as_markup()


def report_type_keyboard(prefix: str = "report_type") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Today's Report", callback_data=f"{prefix}:today")
    builder.button(text="Weekly Report", callback_data=f"{prefix}:weekly")
    builder.button(text="Monthly Report", callback_data=f"{prefix}:monthly")
    builder.button(text="Custom Report", callback_data=f"{prefix}:custom")
    builder.button(text="Cancel", callback_data=f"{prefix}:cancel")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def settings_invite_keyboard(prefix: str = "settings_invite") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Basic Invite", callback_data=f"{prefix}:basic")
    builder.button(text="Invite + Share Expenses", callback_data=f"{prefix}:share")
    builder.button(text="Manage Shared Access", callback_data=f"{prefix}:manage_share")
    builder.adjust(1)
    return builder.as_markup()


def settings_share_people_keyboard(people: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for user_id, label in people:
        builder.button(text=f"Remove: {label}", callback_data=f"settings_share_remove:{user_id}")
    builder.button(text="Back to Settings", callback_data="settings_share_remove:back")
    builder.adjust(1)
    return builder.as_markup()


def settings_share_confirm_keyboard(collaborator_user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="Yes, Remove",
        callback_data=f"settings_share_confirm:{collaborator_user_id}:yes",
    )
    builder.button(
        text="No, Keep",
        callback_data=f"settings_share_confirm:{collaborator_user_id}:no",
    )
    builder.adjust(2)
    return builder.as_markup()


def txn_draft_keyboard(is_for_someone_else: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Category", callback_data="txn_opt:category")
    builder.button(text="Notes", callback_data="txn_opt:notes")
    builder.button(text="Date", callback_data="txn_opt:txn_date")
    builder.button(text="Discount", callback_data="txn_opt:discount_amount")
    builder.button(text="Cashback", callback_data="txn_opt:cashback_amount")
    builder.button(text="For Someone Else", callback_data="txn_opt:toggle_someone")
    if is_for_someone_else:
        builder.button(text="Person Name", callback_data="txn_opt:person_name")
        builder.button(text="Paid Back?", callback_data="txn_opt:toggle_paid")
    builder.button(text="Save Transaction", callback_data="txn_opt:save")
    builder.button(text="Cancel", callback_data="txn_opt:cancel")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def txn_recent_dates_keyboard(days: int = 7) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for offset in range(max(days, 1)):
        candidate = date.today() - timedelta(days=offset)
        if offset == 0:
            label = f"Today ({candidate.strftime('%d %b')})"
        elif offset == 1:
            label = f"Yesterday ({candidate.strftime('%d %b')})"
        else:
            label = candidate.strftime("%a (%d %b)")
        builder.button(text=label, callback_data=f"txn_datepick:{candidate.isoformat()}")

    builder.button(text="Custom Date", callback_data="txn_datepick:custom")
    builder.button(text="Back", callback_data="txn_datepick:back")
    builder.adjust(2, 2, 2, 1, 2)
    return builder.as_markup()


def edit_action_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Update", callback_data=f"{prefix}:update")
    builder.button(text="Delete", callback_data=f"{prefix}:delete")
    builder.button(text="Cancel", callback_data=f"{prefix}:cancel")
    builder.adjust(2, 1)
    return builder.as_markup()


def edit_card_fields_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Bank Name", callback_data="edit_card_field:bank_name")
    builder.button(text="Card Nickname", callback_data="edit_card_field:card_name")
    builder.button(text="Billing Day", callback_data="edit_card_field:billing_day")
    builder.button(text="Due Day", callback_data="edit_card_field:due_day")
    builder.button(text="Credit Limit", callback_data="edit_card_field:credit_limit")
    builder.button(text="Notes", callback_data="edit_card_field:notes")
    builder.button(text="Back", callback_data="edit_card_field:back")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


def edit_txn_fields_keyboard(is_for_someone_else: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Amount", callback_data="edit_txn_field:amount")
    builder.button(text="Category", callback_data="edit_txn_field:category")
    builder.button(text="Notes", callback_data="edit_txn_field:notes")
    builder.button(text="Date", callback_data="edit_txn_field:txn_date")
    builder.button(text="Discount", callback_data="edit_txn_field:discount_amount")
    builder.button(text="Cashback", callback_data="edit_txn_field:cashback_amount")
    builder.button(text="For Someone Else", callback_data="edit_txn_field:toggle_someone")
    if is_for_someone_else:
        builder.button(text="Person Name", callback_data="edit_txn_field:person_name")
        builder.button(text="Paid Back?", callback_data="edit_txn_field:toggle_paid")
    builder.button(text="Back", callback_data="edit_txn_field:back")
    builder.adjust(2, 2, 2, 2, 2, 1)
    return builder.as_markup()


def edit_confirm_delete_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes, Delete", callback_data=f"{prefix}:yes")
    builder.button(text="No", callback_data=f"{prefix}:no")
    builder.adjust(2)
    return builder.as_markup()


def edit_txn_select_keyboard(transactions: Sequence[tuple[int, str]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for txn_id, label in transactions:
        builder.button(text=label, callback_data=f"edit_txn_pick:{txn_id}")
    builder.button(text="Cancel", callback_data="edit_txn_pick:cancel")
    builder.adjust(1)
    return builder.as_markup()
