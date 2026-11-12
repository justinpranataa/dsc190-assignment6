# nldate

Parse English date expressions into `datetime.date` objects.

```python
from datetime import date
from nldate import parse

today = date(2025, 11, 26)
parse("two weeks from tomorrow", today=today)  # date(2025, 12, 11)
parse("5 days before December 1st, 2025")  # date(2025, 11, 26)
parse("1 year and 2 months after yesterday", today=today)  # date(2027, 1, 25)
parse("next Tuesday", today=today)  # date(2025, 12, 2)
parse("2025-12-01")  # date(2025, 12, 1)
```

`parse(s, today=None)` returns a `date`. `today` is the reference point for relative
expressions and defaults to the current date. Empty strings and anything it does not
recognise raise `ValueError`, as do impossible dates such as `February 30, 2025`.

## Supported input

- **Named days:** `today`, `now`, `tonight`, `tomorrow`, `yesterday`, `the day after tomorrow`,
  `the day before yesterday`.
- **Weekdays:** `Tuesday`, `tue`, `this Friday`, `next Tuesday`, `last Friday`.
- **Periods:** `next week`, `last month`, `this year`, `first day of next month`,
  `last day of last year`.
- **Offsets:** `in 3 days`, `2 weeks ago`, `a week from tomorrow`, `five days before <date>`,
  `1 year and 2 months after yesterday`. Units are days, weeks, fortnights, months and years.
  Numbers can be digits or words up to twenty, and `a`/`an` count as one.
- **Absolute dates:** `2025-12-01`, `2025/12/01`, `20251201`, `12/01/2025`, `12-01-25`,
  `12.01.2025`, `December 1st, 2025`, `Dec. 1 2025`, `1 December 2025`, `1st of December 2025`.
  An optional weekday prefix such as `Monday, December 1, 2025` is checked against the date.

## Interpretation choices

These are the places where an expression can reasonably mean more than one thing:

| Input | Behaviour |
|---|---|
| `12/01/2025` | Month first (US order). |
| `25/12/2025` | Day first, because 25 cannot be a month. Applies to `/`, `-` and `.` separators. |
| `Tuesday` / `this Tuesday` | The next Tuesday on or after the reference date (today counts). |
| `next Tuesday` | The first Tuesday strictly after the reference date. |
| `last Tuesday` | The most recent Tuesday strictly before the reference date. |
| `December 1st` (no year) | The next December 1 on or after the reference date. |
| `next week` | Seven days after the reference date. |
| `1 month before March 31, 2026` | Months are clamped to the end of the target month, giving February 28. Months and years are applied before days. |

Times of day (`tomorrow at noon`) and phrases such as `monday next week` are not supported
and raise `ValueError`.

## Development

Managed with [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run pytest
uv run mypy src/
uv run ruff check
uv run ruff format --check
```
