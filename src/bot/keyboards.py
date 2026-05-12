from __future__ import annotations

from datetime import date
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
