from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    new_month_index = (year * 12 + month - 1) + delta
    new_year, month_zero = divmod(new_month_index, 12)
    return new_year, month_zero + 1


def _clamp_day(year: int, month: int, day: int) -> int:
    _, last_day = monthrange(year, month)
    return max(1, min(day, last_day))


def _anchor_date(year: int, month: int, day: int) -> date:
    return date(year, month, _clamp_day(year, month, day))


def get_current_billing_cycle(billing_day: int, today: date) -> tuple[date, date]:
    """Return (start_date, end_date) inclusive for the current billing cycle."""
    current_month_anchor = _anchor_date(today.year, today.month, billing_day)

    if today >= current_month_anchor:
        cycle_start = current_month_anchor
    else:
        prev_year, prev_month = _shift_month(today.year, today.month, -1)
        cycle_start = _anchor_date(prev_year, prev_month, billing_day)

    next_year, next_month = _shift_month(cycle_start.year, cycle_start.month, 1)
    next_cycle_start = _anchor_date(next_year, next_month, billing_day)
    cycle_end = next_cycle_start - timedelta(days=1)
    return cycle_start, cycle_end


def get_next_due_date(due_day: int, today: date) -> date:
    """Return the next due date (today-inclusive)."""
    current_due = _anchor_date(today.year, today.month, due_day)
    if current_due >= today:
        return current_due

    next_year, next_month = _shift_month(today.year, today.month, 1)
    return _anchor_date(next_year, next_month, due_day)


def is_within_cycle(txn_date: date, cycle_start: date, cycle_end: date) -> bool:
    return cycle_start <= txn_date <= cycle_end
