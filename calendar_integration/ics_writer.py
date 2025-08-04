# calendar_integration/ics_writer.py

from pathlib import Path
from datetime import datetime, timedelta
from ics import Calendar, Event

ICS_FILE = Path("data/calendar/appointments.ics")
ICS_FILE.parent.mkdir(parents=True, exist_ok=True)


def load_calendar(ics_path: Path | str = ICS_FILE) -> Calendar:
    if Path(ics_path).exists():
        with open(ics_path, "r") as f:
            return Calendar(f.read())
    return Calendar()


def save_calendar(calendar: Calendar, ics_path: Path | str = ICS_FILE):
    with open(ics_path, "w") as f:
        f.writelines(calendar.serialize_iter())


def _to_naive(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def has_conflict(new_start: datetime, duration_minutes: int, ics_path: Path | str = ICS_FILE) -> bool:
    """
    Returns True if the new appointment (new_start + duration) overlaps any existing event.
    """
    calendar = load_calendar(ics_path)
    new_start_naive = _to_naive(new_start)
    new_end_naive = new_start_naive + timedelta(minutes=duration_minutes)

    for event in calendar.events:
        if event.begin is None or event.end is None:
            continue
        existing_start = _to_naive(event.begin.datetime)
        existing_end = _to_naive(event.end.datetime)
        if new_start_naive < existing_end and new_end_naive > existing_start:
            return True  # overlap
    return False


def add_event_to_calendar(date: str, time: str, title: str, description: str, duration_minutes: int = 30, ics_path: Path | str = ICS_FILE):
    """
    Adds a new appointment to the .ics calendar file.
    """
    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        calendar = load_calendar(ics_path)

        event = Event()
        event.name = title
        event.begin = start_dt
        event.end = end_dt
        event.description = description

        calendar.events.add(event)
        save_calendar(calendar, ics_path)
        print("🗓️ Appointment added to .ics calendar.")
    except Exception as e:
        print(f"❌ Failed to write appointment: {e}")
