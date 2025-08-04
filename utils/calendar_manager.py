# utils/calendar_manager.py

from ics import Calendar, Event
from datetime import datetime, timedelta
import os

CALENDAR_FILE = "data/appointments.ics"

def load_calendar():
    """
    Load or create the .ics calendar file.
    """
    if os.path.exists(CALENDAR_FILE):
        with open(CALENDAR_FILE, 'r') as f:
            return Calendar(f.read())
    else:
        return Calendar()

def save_calendar(calendar: Calendar):
    """
    Save calendar to file.
    """
    with open(CALENDAR_FILE, 'w') as f:
        f.writelines(calendar.serialize_iter())

def add_appointment(customer_name, service, date_str, time_str, duration_minutes=30):
    """
    Add a new appointment to the calendar.
    """
    calendar = load_calendar()
    event = Event()

    # Parse datetime
    start_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end_time = start_time + timedelta(minutes=duration_minutes)

    # Fill event data
    event.name = f"Service for {customer_name}"
    event.begin = start_time
    event.end = end_time
    event.description = f"Service: {service}\nCustomer: {customer_name}"

    calendar.events.add(event)
    save_calendar(calendar)
    print(f"📅 Appointment added to calendar: {start_time} - {end_time}")
