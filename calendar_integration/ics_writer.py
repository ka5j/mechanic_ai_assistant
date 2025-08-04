# calendar_integration/ics_writer.py

from pathlib import Path
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
from ics import Calendar, Event
import time
import errno

ICS_FILE = Path("data/calendar/appointments.ics")
ICS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Base timezone
LOCAL_TZ = ZoneInfo("America/Toronto")
UTC_TZ = ZoneInfo("UTC")


def load_calendar(ics_path: Path | str = ICS_FILE) -> Calendar:
    if Path(ics_path).exists():
        try:
            with open(ics_path, "r", encoding="utf-8") as f:
                return Calendar(f.read())
        except Exception:
            # fallback to empty calendar if corrupted
            return Calendar()
    return Calendar()


def save_calendar(calendar: Calendar, ics_path: Path | str = ICS_FILE):
    with open(ics_path, "w", encoding="utf-8") as f:
        f.writelines(calendar.serialize_iter())


def to_local(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(LOCAL_TZ)


def to_utc(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC_TZ)


def has_conflict(new_start_local: datetime, duration_minutes: int, ics_path: Path | str = ICS_FILE):
    calendar = load_calendar(ics_path)

    if new_start_local.tzinfo is None:
        new_start_local = new_start_local.replace(tzinfo=LOCAL_TZ)
    new_end_local = new_start_local + timedelta(minutes=duration_minutes)

    conflicts = []
    for ev in calendar.events:
        existing_start = ev.begin.datetime
        existing_end = ev.end.datetime

        if existing_start.tzinfo is None:
            existing_start = existing_start.replace(tzinfo=LOCAL_TZ)
        if existing_end.tzinfo is None:
            existing_end = existing_end.replace(tzinfo=LOCAL_TZ)

        if not (new_end_local <= existing_start or new_start_local >= existing_end):
            conflicts.append({
                "name": ev.name,
                "start": existing_start.isoformat(),
                "end": existing_end.isoformat(),
                "description": ev.description,
            })
    return conflicts


def suggest_next_slot(desired_start_local: datetime, duration_minutes: int, ics_path: Path | str = ICS_FILE,
                      business_start: dtime = dtime(9, 0), business_end: dtime = dtime(17, 0), interval_minutes: int = 30,
                      max_lookahead_days: int = 7):
    from datetime import date

    if desired_start_local.tzinfo is None:
        desired_start_local = desired_start_local.replace(tzinfo=LOCAL_TZ)

    minute = (desired_start_local.minute // interval_minutes) * interval_minutes
    candidate = desired_start_local.replace(minute=minute, second=0, microsecond=0)

    for day_offset in range(0, max_lookahead_days + 1):
        current_day = (candidate + timedelta(days=day_offset)).date()
        slot_time = datetime.combine(current_day, business_start, tzinfo=LOCAL_TZ)
        end_of_day = datetime.combine(current_day, business_end, tzinfo=LOCAL_TZ)
        while slot_time + timedelta(minutes=duration_minutes) <= end_of_day:
            conflicts = has_conflict(slot_time, duration_minutes, ics_path=ics_path)
            if not conflicts:
                if day_offset == 0 and slot_time < candidate:
                    slot_time += timedelta(minutes=interval_minutes)
                    continue
                return slot_time
            slot_time += timedelta(minutes=interval_minutes)
    return None


# New error classes
class BookingError(Exception):
    pass

class TransientBookingError(BookingError):
    pass

class FatalBookingError(BookingError):
    pass


def add_event_to_calendar(title: str, start_dt_local: datetime, duration_minutes: int, description: str,
                          ics_path: Path | str = ICS_FILE, max_retries: int = 2, backoff_seconds: float = 0.5):
    """
    Adds event with retry for transient failures. Raises FatalBookingError if unrecoverable.
    """
    attempt = 0
    while attempt <= max_retries:
        try:
            calendar = load_calendar(ics_path)

            if start_dt_local.tzinfo is None:
                start_dt_local = start_dt_local.replace(tzinfo=LOCAL_TZ)
            end_dt_local = start_dt_local + timedelta(minutes=duration_minutes)

            event = Event()
            event.name = title
            event.begin = start_dt_local
            event.end = end_dt_local
            event.description = description

            calendar.events.add(event)
            save_calendar(calendar, ics_path)
            print("🗓️ Appointment added to .ics calendar.")
            return  # success
        except Exception as e:
            # Determine if transient: common file I/O errors, locking, etc.
            is_transient = False
            if isinstance(e, IOError):
                if getattr(e, "errno", None) in (errno.EAGAIN, errno.EBUSY, errno.EWOULDBLOCK):
                    is_transient = True
                else:
                    is_transient = True  # treat generic IO as transient initially
            else:
                # for other exceptions, we can consider them transient limitedly
                is_transient = True

            if attempt < max_retries and is_transient:
                time.sleep(backoff_seconds * (2 ** attempt))  # exponential backoff
                attempt += 1
                continue
            # Final failure
            raise FatalBookingError(f"Failed to write appointment after {attempt+1} attempts: {e}")
