from datetime import date, datetime

import pytest

from nldate import parse

# Wednesday, 2025-11-26. All relative expectations below are computed from this.
REF = date(2025, 11, 26)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("today", date(2025, 11, 26)),
        ("now", date(2025, 11, 26)),
        ("tomorrow", date(2025, 11, 27)),
        ("yesterday", date(2025, 11, 25)),
        ("the day after tomorrow", date(2025, 11, 28)),
        ("the day before yesterday", date(2025, 11, 24)),
    ],
)
def test_named_days(text: str, expected: date) -> None:
    assert parse(text, today=REF) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Monday", date(2025, 12, 1)),
        ("this Friday", date(2025, 11, 28)),
        ("next Tuesday", date(2025, 12, 2)),
        ("next Wednesday", date(2025, 12, 3)),  # today is Wednesday: strictly after
        ("last Friday", date(2025, 11, 21)),
        ("thurs", date(2025, 11, 27)),
    ],
)
def test_weekdays(text: str, expected: date) -> None:
    assert parse(text, today=REF) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("in three days", date(2025, 11, 29)),
        ("3 days from now", date(2025, 11, 29)),
        ("3 days ago", date(2025, 11, 23)),
        ("a week ago", date(2025, 11, 19)),
        ("two weeks from tomorrow", date(2025, 12, 11)),
        ("5 days before December 1st, 2025", date(2025, 11, 26)),
        ("5 days before next Tuesday", date(2025, 11, 27)),
        ("1 year and 2 months after yesterday", date(2027, 1, 25)),
        ("one year ago", date(2024, 11, 26)),
        ("three years ago", date(2022, 11, 26)),
    ],
)
def test_relative_offsets(text: str, expected: date) -> None:
    assert parse(text, today=REF) == expected


def test_month_arithmetic_clamps_to_month_end() -> None:
    assert parse("1 month before March 31, 2026", today=REF) == date(2026, 2, 28)
    assert parse("1 month after January 31, 2026", today=REF) == date(2026, 2, 28)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("December 1st, 2025", date(2025, 12, 1)),
        ("Dec. 1 2025", date(2025, 12, 1)),
        ("1 December 2025", date(2025, 12, 1)),
        ("1st of December 2025", date(2025, 12, 1)),
        ("the 1st of december 2025", date(2025, 12, 1)),
        ("Monday, December 1, 2025", date(2025, 12, 1)),
        ("2025-12-01", date(2025, 12, 1)),
        ("2025/12/01", date(2025, 12, 1)),
        ("20251201", date(2025, 12, 1)),
        ("12/01/2025", date(2025, 12, 1)),
        ("12-01-25", date(2025, 12, 1)),
        ("25/12/2025", date(2025, 12, 25)),  # day-first, since 25 cannot be a month
        ("12.01.2025", date(2025, 12, 1)),
        (
            "01.12.2025",
            date(2025, 1, 12),
        ),  # dotted is month-first when valid, like slashes
    ],
)
def test_absolute_dates(text: str, expected: date) -> None:
    assert parse(text, today=REF) == expected


def test_missing_year_uses_next_occurrence() -> None:
    assert parse("December 1st", today=REF) == date(2025, 12, 1)
    assert parse("March 3", today=REF) == date(2026, 3, 3)
    assert parse("11/26", today=REF) == date(2025, 11, 26)  # on the reference day


def test_period_phrases() -> None:
    assert parse("next week", today=REF) == date(2025, 12, 3)
    assert parse("first day of next month", today=REF) == date(2025, 12, 1)
    assert parse("last day of next month", today=REF) == date(2025, 12, 31)
    assert parse("first day of last year", today=REF) == date(2024, 1, 1)


def test_case_and_whitespace_are_ignored() -> None:
    assert parse("  TOMORROW ", today=REF) == date(2025, 11, 27)
    assert parse("in   three    days", today=REF) == date(2025, 11, 29)


def test_datetime_reference_uses_its_date() -> None:
    assert parse("tomorrow", today=datetime(2025, 11, 26, 15, 30)) == date(2025, 11, 27)


def test_defaults_to_current_date() -> None:
    assert parse("today") == date.today()


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "banana",
        "not a date",
        "2 weeks",  # a duration with no direction or anchor
        "tomorrow at noon",  # times are not supported
        "on",
        "the",
    ],
)
def test_unrecognized_input_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        parse(text, today=REF)


@pytest.mark.parametrize(
    "text",
    [
        "February 30, 2025",
        "2025-13-01",
        "13/45/2025",
        "32nd of December 2025",
        "Tuesday, December 1, 2025",  # December 1, 2025 is a Monday
    ],
)
def test_impossible_or_contradictory_dates_raise_value_error(text: str) -> None:
    with pytest.raises(ValueError):
        parse(text, today=REF)
