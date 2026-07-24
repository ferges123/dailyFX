from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from datetime import time as time_of_day

logger = logging.getLogger(__name__)

WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_TO_INDEX = {code: index for index, code in enumerate(WEEKDAY_CODES)}
WEEKDAY_PRESETS = {
    "weekdays": (0, 1, 2, 3, 4),
    "weekends": (5, 6),
}
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class ParsedAutomationSchedule:
    kind: str
    days: tuple[int, ...]
    run_time: time_of_day | None
    valid: bool


def _local_now() -> datetime:
    return datetime.now().astimezone()


def _normalize_datetime(value: datetime | None, tzinfo) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=tzinfo)
    return value.astimezone(tzinfo)


def _parse_time_of_day(value: str | None) -> time_of_day | None:
    if not value:
        return None
    normalized = value.strip()
    if not TIME_RE.match(normalized):
        return None
    hour, minute = normalized.split(":")
    return time_of_day(hour=int(hour), minute=int(minute))


def _parse_weekdays(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    days: list[int] = []
    seen: set[int] = set()
    for raw_token in value.split(","):
        token = raw_token.strip().lower()
        if not token:
            continue
        index = WEEKDAY_TO_INDEX.get(token)
        if index is None or index in seen:
            return ()
        seen.add(index)
        days.append(index)
    return tuple(days)


def _parse_automation_schedule(schedule: str) -> ParsedAutomationSchedule:
    normalized = (schedule or "weekly").strip().lower()
    if normalized in {"daily", "weekly"}:
        return ParsedAutomationSchedule(kind=normalized, days=(), run_time=None, valid=True)

    parts = [part.strip() for part in normalized.split("@") if part.strip()]
    if not parts:
        return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    kind = parts[0]
    if kind not in {"daily", "weekly", "weekdays", "weekends"}:
        return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    days: tuple[int, ...] = ()
    run_time: time_of_day | None = None

    if kind in WEEKDAY_PRESETS:
        days = WEEKDAY_PRESETS[kind]
        if len(parts) >= 2:
            parsed_time = _parse_time_of_day(parts[1])
            if parsed_time is None:
                return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)
            run_time = parsed_time
        if len(parts) > 2:
            return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)
        return ParsedAutomationSchedule(kind=kind, days=days, run_time=run_time, valid=True)

    if len(parts) >= 2:
        parsed_time = _parse_time_of_day(parts[1])
        if parsed_time is not None:
            run_time = parsed_time
        else:
            days = _parse_weekdays(parts[1])
            if not days:
                return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    if len(parts) >= 3:
        parsed_time = _parse_time_of_day(parts[2])
        if parsed_time is None:
            return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)
        run_time = parsed_time

    if len(parts) > 3:
        return ParsedAutomationSchedule(kind="weekly", days=(), run_time=None, valid=False)

    return ParsedAutomationSchedule(kind=kind, days=days, run_time=run_time, valid=True)


def _scheduled_moment(current: datetime, run_time: time_of_day) -> datetime:
    return datetime.combine(current.date(), run_time).replace(tzinfo=current.tzinfo)


def _compute_next_run(schedule: str, last_run_at: datetime | None, now: datetime | None = None) -> datetime | None:
    current = now or _local_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_local_now().tzinfo)

    last = _normalize_datetime(last_run_at, current.tzinfo)
    parsed = _parse_automation_schedule(schedule)
    if not parsed.valid:
        return None

    if parsed.kind == "daily":
        scheduled = _scheduled_moment(current, parsed.run_time or time_of_day(0, 0))
        if current < scheduled and (last is None or last < scheduled):
            return scheduled
        return scheduled + timedelta(days=1)

    if parsed.days:
        for offset in range(0, 15):
            candidate_date = current.date() + timedelta(days=offset)
            if candidate_date.weekday() not in parsed.days:
                continue
            scheduled = datetime.combine(
                candidate_date,
                parsed.run_time or time_of_day(0, 0),
            ).replace(tzinfo=current.tzinfo)
            if scheduled > current and (last is None or last < scheduled):
                return scheduled
        return None

    if parsed.kind == "weekly":
        if last is None:
            return current + timedelta(days=7)
        return _scheduled_moment(current + timedelta(days=7), parsed.run_time or time_of_day(0, 0))

    return None


def should_run_automation(schedule: str, last_run_at: datetime | None, now: datetime | None = None) -> bool:
    current = now or _local_now()
    if current.tzinfo is None:
        current = current.replace(tzinfo=_local_now().tzinfo)

    last = _normalize_datetime(last_run_at, current.tzinfo)
    parsed = _parse_automation_schedule(schedule)

    if last is None:
        return True

    if parsed.kind == "daily":
        if parsed.run_time is None:
            return last.date() < current.date()
        scheduled = _scheduled_moment(current, parsed.run_time)
        return current >= scheduled and last < scheduled

    if parsed.days:
        if current.weekday() not in parsed.days:
            return False
        scheduled = _scheduled_moment(current, parsed.run_time or time_of_day(0, 0))
        return current >= scheduled and last < scheduled

    if parsed.valid:
        if parsed.run_time is not None:
            logger.debug("Weekly schedule has a time but no weekdays; using legacy weekly semantics.")
        return last.isocalendar()[:2] < current.isocalendar()[:2]

    logger.warning("Unknown automation schedule '%s', defaulting to weekly semantics.", schedule)
    return last.isocalendar()[:2] < current.isocalendar()[:2]
