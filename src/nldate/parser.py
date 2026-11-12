"""Parse English date expressions into :class:`datetime.date` objects.

Supported forms (case-insensitive):

* Named days: ``today``, ``now``, ``tonight``, ``tomorrow``, ``yesterday``,
  ``the day after tomorrow``, ``the day before yesterday``.
* Weekdays: ``Tuesday`` (the next occurrence, today included), ``this Tuesday``
  (same as bare), ``next Tuesday`` (strictly after today), ``last Tuesday``
  (strictly before today). Abbreviations such as ``tue`` or ``thurs`` work too.
* Week, month and year phrases: ``next week`` (+7 days), ``last month``,
  ``this year``; ``first day of next month``, ``last day of last year``.
* Offsets: ``in 3 days``, ``2 weeks ago``, ``five days before <date>``,
  ``1 year and 2 months after yesterday``, ``a week from tomorrow``. Units are
  days, weeks, fortnights, months and years; numbers may be digits or words
  up to twenty (``a``/``an`` count as one). Months and years are added first,
  clamped to the end of the target month, then days.
* Absolute dates: ``2025-12-01``, ``20251201``, ``2025/12/01``,
  ``12/01/2025`` (month first), ``25/12/2025`` (day first, because 25 cannot be
  a month), ``12-01-25``, ``December 1st, 2025``, ``Dec. 1 2025``,
  ``1 December 2025``, ``1st of December 2025``, and an optional weekday prefix
  such as ``Monday, December 1, 2025`` (checked against the date).

When the year is omitted (``December 1st``, ``12/01``) the next occurrence on or
after the reference date is used.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta

__all__ = ["parse"]

_WEEKDAYS: dict[str, int] = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

# Keyed by the first three letters of the month name.
_MONTHS: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_NUMBER_WORDS: dict[str, int] = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_NAMED_OFFSETS: dict[str, int] = {
    "today": 0,
    "now": 0,
    "tonight": 0,
    "tomorrow": 1,
    "yesterday": -1,
    "day after tomorrow": 2,
    "day before yesterday": -2,
}

# Step applied to a base period for "this", "next", "last" / "previous".
_STEP: dict[str, int] = {"this": 0, "next": 1, "last": -1, "previous": -1}

_BACKWARD_WORDS = frozenset({"before", "prior to", "earlier than"})

_WEEKDAY_ALT = "|".join(sorted(_WEEKDAYS, key=len, reverse=True))
_NUM_ALT = r"\d+|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
_UNIT_ALT = r"days?|weeks?|fortnights?|months?|years?"
_MONTH_ALT = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?"
    r"|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)

_PART = rf"\b(?:{_NUM_ALT})\s+(?:{_UNIT_ALT})\b"
_DURATION = rf"{_PART}(?:(?:\s*,\s*|\s+and\s+|\s+){_PART})*"
_PART_RE = re.compile(rf"\b({_NUM_ALT})\s+({_UNIT_ALT})\b")

_FILLER_RE = re.compile(r"^(?:(?:on|the) )+")
_WEEKDAY_RE = re.compile(rf"(?:(this|next|last) )?({_WEEKDAY_ALT})")
_WEEKDAY_PREFIX_RE = re.compile(rf"({_WEEKDAY_ALT}) (.+)")
_PERIOD_RE = re.compile(r"(this|next|last) (week|month|year)")
_EDGE_RE = re.compile(r"(first|last) day of (this|next|last|previous) (month|year)")
_MONTH_DAY_RE = re.compile(
    rf"({_MONTH_ALT}) (\d{{1,2}})(?:st|nd|rd|th)?(?: (\d{{4}}))?"
)
_DAY_MONTH_RE = re.compile(
    rf"(\d{{1,2}})(?:st|nd|rd|th)? (?:of )?({_MONTH_ALT})(?: (\d{{4}}))?"
)
_ISO_RE = re.compile(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")
_COMPACT_RE = re.compile(r"(\d{4})(\d{2})(\d{2})")
_NUMERIC_RE = re.compile(r"(\d{1,2})[-/](\d{1,2})(?:[-/](\d{2}|\d{4}))?")
_DOTTED_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})")
_IN_RE = re.compile(rf"in ({_DURATION})")
_AGO_RE = re.compile(rf"({_DURATION}) ago")
_OFFSET_RE = re.compile(
    rf"({_DURATION}) (after|from|following|past|before|prior to|earlier than) (.+)"
)


def parse(s: str, today: date | None = None) -> date:
    """Return the date that the English expression ``s`` refers to.

    ``today`` is the reference point for relative expressions. It defaults to
    the current local date. A :class:`datetime.datetime` is accepted and its
    date part is used.

    Raises:
        ValueError: if ``s`` is empty, is not a recognised date expression, or
            names an impossible date (such as ``February 30``).
    """
    reference = _reference(today)
    text = _normalize(s)
    if not text:
        raise ValueError("cannot parse an empty date expression")
    try:
        result = _parse_expr(text, reference)
    except OverflowError as exc:
        raise ValueError(f"{s!r} is outside the supported date range") from exc
    if result is None:
        raise ValueError(f"unrecognized date expression: {s!r}")
    return result


def _reference(today: date | None) -> date:
    if today is None:
        return date.today()
    if isinstance(today, datetime):
        return today.date()
    return today


def _normalize(s: str) -> str:
    text = s.strip().lower()
    text = re.sub(r"[,?!]", " ", text)
    # Drop periods that end an abbreviation, e.g. "dec." -> "dec".
    text = re.sub(r"(?<=[a-z])\.(?=\s|$)", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return _FILLER_RE.sub("", text)


def _parse_expr(text: str, ref: date) -> date | None:
    if text in _NAMED_OFFSETS:
        return ref + timedelta(days=_NAMED_OFFSETS[text])
    if match := _WEEKDAY_RE.fullmatch(text):
        return _weekday(match.group(1), _WEEKDAYS[match.group(2)], ref)
    if match := _PERIOD_RE.fullmatch(text):
        return _period(match.group(1), match.group(2), ref)
    if match := _EDGE_RE.fullmatch(text):
        return _edge(match.group(1), match.group(2), match.group(3), ref)
    result = _absolute(text, ref)
    if result is None:
        result = _offset(text, ref)
    return result


def _weekday(modifier: str | None, target: int, ref: date) -> date:
    ahead = (target - ref.weekday()) % 7
    if modifier == "next":
        return ref + timedelta(days=ahead or 7)
    if modifier == "last":
        return ref - timedelta(days=((ref.weekday() - target) % 7) or 7)
    return ref + timedelta(days=ahead)


def _period(modifier: str, unit: str, ref: date) -> date:
    step = _STEP[modifier]
    if unit == "week":
        return ref + timedelta(days=7 * step)
    if unit == "month":
        return _shift(ref, step, 0)
    return _shift(ref, 12 * step, 0)


def _edge(edge: str, modifier: str, unit: str, ref: date) -> date:
    step = _STEP[modifier]
    if unit == "month":
        first_day = _shift(ref.replace(day=1), step, 0)
        if edge == "first":
            return first_day
        last = calendar.monthrange(first_day.year, first_day.month)[1]
        return first_day.replace(day=last)
    year = ref.year + step
    return date(year, 1, 1) if edge == "first" else date(year, 12, 31)


def _absolute(text: str, ref: date) -> date | None:
    weekday: int | None = None
    body = text
    if prefix := _WEEKDAY_PREFIX_RE.fullmatch(text):
        weekday = _WEEKDAYS[prefix.group(1)]
        body = prefix.group(2)
    result = _absolute_core(body, ref)
    if result is not None and weekday is not None and result.weekday() != weekday:
        raise ValueError(f"the weekday in {text!r} does not match the date")
    return result


def _absolute_core(text: str, ref: date) -> date | None:
    if match := _ISO_RE.fullmatch(text):
        year, month, day = map(int, match.groups())
        return _build(year, month, day)
    if match := _COMPACT_RE.fullmatch(text):
        year, month, day = map(int, match.groups())
        return _build(year, month, day)
    if match := _NUMERIC_RE.fullmatch(text) or _DOTTED_RE.fullmatch(text):
        return _numeric(match.group(1), match.group(2), match.group(3), ref)
    if match := _MONTH_DAY_RE.fullmatch(text):
        month = _MONTHS[match.group(1)[:3]]
        return _resolve(month, int(match.group(2)), _full_year(match.group(3)), ref)
    if match := _DAY_MONTH_RE.fullmatch(text):
        month = _MONTHS[match.group(2)[:3]]
        return _resolve(month, int(match.group(1)), _full_year(match.group(3)), ref)
    return None


def _numeric(
    first_text: str, second_text: str, year_text: str | None, ref: date
) -> date:
    """Read an all-numeric date as month-first, unless the first part cannot be a month."""
    first, second = int(first_text), int(second_text)
    if first > 12 and second <= 12:
        # Day-first, e.g. "25/12/2025" or "25.12.2025".
        month, day = second, first
    else:
        month, day = first, second
    return _resolve(month, day, _full_year(year_text), ref)


def _offset(text: str, ref: date) -> date | None:
    if match := _IN_RE.fullmatch(text):
        months, days = _duration(match.group(1))
        return _shift(ref, months, days)
    if match := _AGO_RE.fullmatch(text):
        months, days = _duration(match.group(1))
        return _shift(ref, -months, -days)
    if match := _OFFSET_RE.fullmatch(text):
        amount, direction, anchor_text = match.group(1), match.group(2), match.group(3)
        anchor = _parse_expr(anchor_text, ref)
        if anchor is None:
            return None
        months, days = _duration(amount)
        sign = -1 if direction in _BACKWARD_WORDS else 1
        return _shift(anchor, sign * months, sign * days)
    return None


def _duration(text: str) -> tuple[int, int]:
    """Return the total ``(months, days)`` for a phrase such as "1 year and 2 weeks"."""
    months = 0
    days = 0
    for number, unit in _PART_RE.findall(text):
        count = _to_int(number)
        if unit.startswith("month"):
            months += count
        elif unit.startswith("year"):
            months += 12 * count
        elif unit.startswith("fortnight"):
            days += 14 * count
        elif unit.startswith("week"):
            days += 7 * count
        else:
            days += count
    return months, days


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else _NUMBER_WORDS[token]


def _full_year(text: str | None) -> int | None:
    if text is None:
        return None
    value = int(text)
    return 2000 + value if len(text) == 2 else value


def _resolve(month: int, day: int, year: int | None, ref: date) -> date:
    if year is None:
        return _next_occurrence(month, day, ref)
    return _build(year, month, day)


def _build(year: int, month: int, day: int) -> date:
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError(
            f"{year:04d}-{month:02d}-{day:02d} is not a real calendar date"
        ) from exc


def _next_occurrence(month: int, day: int, ref: date) -> date:
    for year in range(ref.year, ref.year + 9):
        try:
            candidate = date(year, month, day)
        except ValueError:
            continue
        if candidate >= ref:
            return candidate
    raise ValueError(f"no upcoming date falls on month {month}, day {day}")


def _shift(base: date, months: int, days: int) -> date:
    """Add calendar months (clamping to month end), then days."""
    index = base.year * 12 + (base.month - 1) + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day) + timedelta(days=days)
