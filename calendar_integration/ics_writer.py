# calendar_integration/ics_writer.py

from pathlib import Path
from datetime import datetime, timedelta
from ics import Calendar, Event

ICS_FILE = Path("data/calendar/appointments.ics")
ICS_FILE.parent.mkdir(parents=True, exist_ok=True)

def add_event_to_calendar(date, time, title, description, duration_minutes=30):
    """
    Adds a new event to the .ics file.
    """
    try:
        start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        # Load existing calendar or create new
        calendar = Calendar()
        if ICS_FILE.exists():
            with open(ICS_FILE, "r") as f:
                calendar = Calendar(f.read())

        # Add new event
        event = Event()
        event.name = title
        event.begin = start_dt
        event.end = end_dt
        event.description = description
        calendar.events.add(event)

        # Save calendar
        with open(ICS_FILE, "w") as f:
            f.writelines(calendar.serialize_iter())

        print("🗓️ Appointment added to .ics calendar.")

    except Exception as e:
        print(f"❌ Failed to write appointment: {e}")
