# core/booking_handler.py

import re
from utils.calendar_manager import add_appointment, load_calendar
from utils.call_logger import log_interaction

def validate_date(date_str):
    """
    Check format: YYYY-MM-DD
    """
    return re.match(r"\d{4}-\d{2}-\d{2}", date_str)

def validate_time(time_str):
    """
    Check format: HH:MM (24h)
    """
    return re.match(r"\d{2}:\d{2}", time_str)

def is_time_conflict(date_str, time_str, duration_minutes=30):
    """
    Check if an appointment already exists at this time.
    """
    from datetime import datetime, timedelta

    calendar = load_calendar()
    start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    end = start + timedelta(minutes=duration_minutes)

    for event in calendar.events:
        if (start < event.end and end > event.begin):
            return True
    return False

def handle_booking_flow():
    """
    Guide user through booking an appointment.
    """
    print("📋 Let's book your appointment!")

    name = input("Customer name: ").strip()
    service = input("Service type (e.g., oil change): ").strip()
    date = input("Date (YYYY-MM-DD): ").strip()
    time = input("Time (HH:MM 24hr format): ").strip()

    if not validate_date(date):
        print("❌ Invalid date format.")
        return

    if not validate_time(time):
        print("❌ Invalid time format.")
        return

    if is_time_conflict(date, time):
        print("⚠️ Conflict: There's already an appointment at that time.")
        return

    add_appointment(name, service, date, time)
    
    # Save to logs
    log_interaction("booking", {
        "name": name,
        "service": service,
        "date": date,
        "time": time
    })

    print("✅ Booking confirmed and added to calendar.")
