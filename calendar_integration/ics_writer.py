# calendar_integration/ics_writer.py

from pathlib import Path
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo
from ics import Calendar, Event

ICS_FILE = Path("data/calendar/appointments.ics")
ICS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Base timezone
LOCAL_TZ = ZoneInfo("America/Toronto")
UTC_TZ = ZoneInfo("UTC")


def load_calendar(ics_path: Path | str = ICS_FILE) -> Calendar:
    if Path(ics_path).exists():
        with open(ics_path, "r") as f:
            return Calendar(f.read())
    return Calendar()


def save_calendar(calendar: Calendar, ics_path: Path | str = ICS_FILE):
    with open(ics_path, "w") as f:
        f.writelines(calendar.serialize_iter())


def to_local(dt):
    if dt.tzinfo is None:
        # assume UTC if naive
        dt = dt.replace(tzinfo=UTC_TZ)
    return dt.astimezone(LOCAL_TZ)


def to_utc(dt):
    if dt.tzinfo is None:
        # assume local if naive
        dt = dt.replace(tzinfo=LOCAL_TZ)
    return dt.astimezone(UTC_TZ)


def has_conflict(new_start_local: datetime, duration_minutes: int, ics_path: Path | str = ICS_FILE):
    """
    Returns a list of conflicting events (empty if none). Input is local (America/Toronto).
    """
    calendar = load_calendar(ics_path)

    # Normalize new appointment to timezone-aware
    if new_start_local.tzinfo is None:
        new_start_local = new_start_local.replace(tzinfo=LOCAL_TZ)
    new_end_local = new_start_local + timedelta(minutes=duration_minutes)

    conflicts = []
    for ev in calendar.events:
        existing_start = ev.begin.datetime
        existing_end = ev.end.datetime

        # Normalize existing to local zone for comparison
        if existing_start.tzinfo is None:
            existing_start = existing_start.replace(tzinfo=LOCAL_TZ)
        if existing_end.tzinfo is None:
            existing_end = existing_end.replace(tzinfo=LOCAL_TZ)

        # Overlap if not (end <= existing_start or start >= existing_end)
        if not (new_end_local <= existing_start or new_start_local >= existing_end):
            conflicts.append({
                "name": ev.name,
                "start": existing_start.isoformat(),
                "end": existing_end.isoformat(),
                "description": ev.description,
            })
    return conflicts  # empty list if no conflict


def suggest_next_slot(desired_start_local: datetime, duration_minutes: int, ics_path: Path | str = ICS_FILE,
                      business_start: dtime = dtime(9, 0), business_end: dtime = dtime(17, 0), interval_minutes: int = 30,
                      max_lookahead_days: int = 7):
    """
    If desired slot conflicts, suggest the next available slot within lookahead window.
    Returns datetime of next slot (local), or None if none found.
    """
    from datetime import date

    # Ensure tz-aware
    if desired_start_local.tzinfo is None:
        desired_start_local = desired_start_local.replace(tzinfo=LOCAL_TZ)

    # Round desired to nearest interval
    minute = (desired_start_local.minute // interval_minutes) * interval_minutes
    candidate = desired_start_local.replace(minute=minute, second=0, microsecond=0)

    for day_offset in range(0, max_lookahead_days + 1):
        current_day = (candidate + timedelta(days=day_offset)).date()
        # iterate through business hours on that day
        slot_time = datetime.combine(current_day, business_start, tzinfo=LOCAL_TZ)
        end_of_day = datetime.combine(current_day, business_end, tzinfo=LOCAL_TZ)
        while slot_time + timedelta(minutes=duration_minutes) <= end_of_day:
            conflicts = has_conflict(slot_time, duration_minutes, ics_path=ics_path)
            if not conflicts:
                # skip if this is before original desired in same day unless day_offset>0
                if day_offset == 0 and slot_time < candidate:
                    slot_time += timedelta(minutes=interval_minutes)
                    continue
                return slot_time
            slot_time += timedelta(minutes=interval_minutes)
    return None  # no slot found in lookahead window


def add_event_to_calendar(title: str, start_dt_local: datetime, duration_minutes: int, description: str,
                          ics_path: Path | str = ICS_FILE):
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
    except Exception as e:
        print(f"❌ Failed to write appointment: {e}")
