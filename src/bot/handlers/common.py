from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from aiogram.types import User as TelegramUser
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Card, Person, User


def card_label(card: Card) -> str:
    return f"{card.bank_name}/{card.card_name} • ****{card.last_four}"


def parse_positive_decimal(value: str) -> Decimal | None:
    text = value.strip().replace(",", "")
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if amount <= 0:
        return None
    return amount


def parse_non_negative_decimal(value: str) -> Decimal | None:
    text = value.strip().replace(",", "")
    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    if amount < 0:
        return None
    return amount


def parse_date_input(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except Exception:
            continue
    return None


async def ensure_user(session: AsyncSession, tg_user: TelegramUser) -> User:
    user = await session.scalar(select(User).where(User.telegram_id == tg_user.id))
    if user:
        changed = False
        if user.full_name != tg_user.full_name:
            user.full_name = tg_user.full_name
            changed = True
        username = tg_user.username
        if user.username != username:
            user.username = username
            changed = True
        if changed:
            await session.commit()
        return user

    user = User(
        telegram_id=tg_user.id,
        full_name=tg_user.full_name,
        username=tg_user.username,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return await session.scalar(select(User).where(User.telegram_id == telegram_id))


async def get_or_create_person(session: AsyncSession, user_id: int, raw_name: str) -> Person:
    name = " ".join(raw_name.split())
    person = await session.scalar(
        select(Person).where(
            Person.user_id == user_id,
            func.lower(Person.name) == name.lower(),
        )
    )
    if person:
        return person

    person = Person(user_id=user_id, name=name)
    session.add(person)
    await session.flush()
    return person
