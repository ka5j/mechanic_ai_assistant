# calendar_integration/ics_writer.py

import json
import threading
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from typing import Optional

from ics import Calendar, Event

from core.paths import BASE_DATA_DIR

# Paths
ICS_PATH_DEFAULT = Path(BASE_DATA_DIR) / "calendar" / "appointments.ics"
JSON_PATH        = Path(BASE_DATA_DIR) / "calendar" / "appointments.json"

_lock = threading.Lock()

class FatalBookingError(Exception):
    """Raised when we cannot write to the calendar."""
    pass

def load_calendar(ics_path: Optional[Path] = None) -> Calendar:
    if ics_path is None:
        ics_path = ICS_PATH_DEFAULT
    ics_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        text = ics_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        # initialize empty calendar
        ics_path.write_text("BEGIN:VCALENDAR\nVERSION:2.0\nEND:VCALENDAR\n", encoding="utf-8")
        text = ics_path.read_text(encoding="utf-8")

    try:
        return Calendar(text)
    except Exception:
        # corrupt → fresh Calendar
        return Calendar()

def _dump_calendar_json(ics_path: Path):
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        cal = Calendar(ics_path.read_text(encoding="utf-8"))
    except Exception:
        JSON_PATH.write_text("[]", encoding="utf-8")
        return

    events = []
    for ev in cal.events:
        # ev.begin.datetime and ev.end.datetime are aware datetimes
        events.append({
            "summary":     ev.name,
            "description": ev.description,
            "begin":       ev.begin.datetime.isoformat(),
            "end":         ev.end.datetime.isoformat(),
            "uid":         ev.uid,
        })
    JSON_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")

def add_event_to_calendar(
    title: str,
    start_dt: datetime,
    duration_minutes: int,
    description: str,
    ics_path: Optional[Path] = None
):
    if ics_path is None:
        ics_path = ICS_PATH_DEFAULT

    with _lock:
        cal = load_calendar(ics_path)
        ev = Event()
        ev.name = title
        ev.begin = start_dt
        ev.duration = timedelta(minutes=duration_minutes)
        ev.description = description
        cal.events.add(ev)

        try:
            ics_path.parent.mkdir(parents=True, exist_ok=True)
            # use .serialize() to avoid FutureWarning, but str(cal) still works
            ics_path.write_text(cal.serialize(), encoding="utf-8")
        except Exception as e:
            raise FatalBookingError(f"Failed to write calendar: {e}")

        # mirror to JSON
        try:
            _dump_calendar_json(ics_path)
        except Exception:
            pass

def has_conflict(
    desired_dt: datetime,
    duration_minutes: int,
    ics_path: Optional[Path] = None
) -> bool:
    """
    Return True iff there is any event overlapping
    [desired_dt, desired_dt + duration_minutes).
    """
    cal = load_calendar(ics_path)
    end_dt = desired_dt + timedelta(minutes=duration_minutes)

    for ev in cal.events:
        # use aware datetimes for comparison
        begin = ev.begin.datetime
        end   = ev.end.datetime
        if begin < end_dt and end > desired_dt:
            return True
    return False

def suggest_next_slot(
    desired_dt: datetime,
    duration_minutes: int,
    ics_path: Optional[Path],
    business_start: dtime,
    business_end: dtime,
    interval_minutes: int,
    max_lookahead_days: int = 7
) -> Optional[datetime]:
    cal = load_calendar(ics_path)
    slot = desired_dt
    delta = timedelta(minutes=duration_minutes)
    cutoff = desired_dt + timedelta(days=max_lookahead_days)

    while slot < cutoff:
        slot_end = slot + delta
        # check business hours
        if business_start <= slot.time() < business_end and slot_end.time() <= business_end:
            conflict = False
            for ev in cal.events:
                begin = ev.begin.datetime
                end   = ev.end.datetime
                if begin < slot_end and end > slot:
                    conflict = True
                    break
            if not conflict:
                return slot
        slot += timedelta(minutes=interval_minutes)

    return None
