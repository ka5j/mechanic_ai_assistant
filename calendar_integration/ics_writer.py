# calendar_integration/ics_writer.py

from pathlib import Path
from datetime import datetime
from ics import Calendar, Event

CALENDAR_DIR = Path("data/calendar")
CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
ICS_FILE = CALENDAR_DIR / "appointments.ics"

def add_event_to_calendar(date, time, title, description):
    """
    Adds a new event to the calendar .ics file.
    """
    try:
        # Parse datetime
        dt_str = f"{date} {time}"
        start_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

        # Load existing calendar if exists
        calendar = Calendar()
        if ICS_FILE.exists():
            with open(ICS_FILE, "r") as f:
                calendar = Calendar(f.read())

        # Create and add event
        event = Event()
        event.name = title
        event.begin = start_dt
        event.duration = {"hours": 1}
        event.description = description
        calendar.events.add(event)

        # Save calendar
        with open(ICS_FILE, "w") as f:
            f.writelines(calendar.serialize_iter())

        print("🗓️ Appointment added to .ics calendar.")
    except Exception as e:
        print(f"❌ Failed to add to calendar: {e}")
