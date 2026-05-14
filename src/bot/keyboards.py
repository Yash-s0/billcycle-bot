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


def txn_draft_keyboard(is_for_someone_else: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
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
    builder.adjust(2, 2, 2, 2, 1)
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


def delete_transactions_keyboard(
    transactions: Sequence[tuple[int, str]],
    prev_offset: int | None,
    next_offset: int | None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for txn_id, label in transactions:
        builder.button(text=label, callback_data=f"delpick:txn:{txn_id}")

    nav_count = 0
    if prev_offset is not None:
        builder.button(text="Previous", callback_data=f"delpick:page:{prev_offset}")
        nav_count += 1
    if next_offset is not None:
        builder.button(text="Next", callback_data=f"delpick:page:{next_offset}")
        nav_count += 1
    builder.button(text="Cancel", callback_data="delpick:cancel")

    row_sizes: list[int] = [1] * len(transactions)
    if nav_count > 0:
        row_sizes.append(nav_count)
    row_sizes.append(1)
    builder.adjust(*row_sizes)
    return builder.as_markup()


def delete_transaction_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Yes, Delete", callback_data="delpick:confirm:yes")
    builder.button(text="No", callback_data="delpick:confirm:no")
    builder.adjust(2)
    return builder.as_markup()
