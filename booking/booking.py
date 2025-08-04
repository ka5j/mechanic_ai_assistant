# booking/booking.py

from calendar_integration.ics_writer import load_calendar, save_calendar, add_event_to_calendar
from datetime import datetime, timedelta
import os
import re
from utils.call_logger import log_interaction

ICS_PATH = "data/calendar/appointments.ics"

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_time(time_str):
    return re.match(r"^\d{2}:\d{2}$", time_str)

def parse_datetime(date: str, time: str) -> datetime:
    return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")

def has_conflict(new_start: datetime, duration_minutes: int) -> bool:
    """
    Returns True if new appointment conflicts with existing events in the .ics.
    """
    from ics import Calendar

    if not os.path.exists(ICS_PATH):
        return False  # no calendar yet

    with open(ICS_PATH, "r") as f:
        calendar = Calendar(f.read())

    new_end = new_start + timedelta(minutes=duration_minutes)

    for event in calendar.events:
        if event.begin is None or event.end is None:
            continue
        existing_start = event.begin.datetime
        existing_end = event.end.datetime
        # overlap check
        if new_start < existing_end and new_end > existing_start:
            return True
    return False

def handle_booking(config: dict, phone_number: str):
    """
    Handles appointment booking with collision detection.
    """
    print("\n📅 Let's book your appointment.")

    customer_name = input("🧾 Full Name: ").strip()
    if not customer_name:
        print("❌ Name cannot be empty.")
        return

    car_model = input("🚘 Car Make/Model: ").strip()

    # Show available services
    services = config.get("services", [])
    print("\n🛠️ Available Services:")
    for i, service in enumerate(services, start=1):
        print(f"{i}. {service['name']} - {service['price']} ({service.get('duration_minutes', 30)} min)")

    while True:
        service_choice = input("🔢 Select a service by number: ").strip()
        if not service_choice.isdigit() or not (1 <= int(service_choice) <= len(services)):
            print("❌ Invalid selection. Try again.")
            continue
        selected_service = services[int(service_choice) - 1]
        break

    notes = input("📝 Additional notes (optional): ").strip()

    # Date/time input with validation
    while True:
        date = input("📆 Preferred Date (YYYY-MM-DD): ").strip()
        if not is_valid_date(date):
            print("❌ Invalid date format.")
            continue
        break

    while True:
        time_str = input("⏰ Preferred Time (HH:MM): ").strip()
        if not is_valid_time(time_str):
            print("❌ Invalid time format.")
            continue
        break

    # Parse and check past
    try:
        appointment_dt = parse_datetime(date, time_str)
    except ValueError:
        print("❌ Could not parse date/time.")
        return

    if appointment_dt < datetime.now():
        print("❌ Cannot book in the past.")
        return

    duration = selected_service.get("duration_minutes", 30)

    if has_conflict(appointment_dt, duration):
        print("❌ Time slot conflict: that time is already booked.")
        return

    # Confirm booking
    print("\n🔒 Confirm Booking:")
    print(f"Customer: {customer_name}")
    print(f"Phone: {phone_number}")
    print(f"Car: {car_model}")
    print(f"Service: {selected_service['name']}")
    print(f"When: {date} at {time_str} for {duration} minutes")
    if notes:
        print(f"Notes: {notes}")
    confirm = input("Confirm? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("❌ Booking cancelled.")
        return

    description = (
        f"Customer: {customer_name}\n"
        f"Phone: {phone_number}\n"
        f"Car: {car_model}\n"
        f"Service: {selected_service['name']}\n"
        f"Notes: {notes}"
    )

    add_event_to_calendar(date, time_str, "Mechanic Appointment", description, duration)
    log_interaction("booking_created", {
        "customer_name": customer_name,
        "car_model": car_model,
        "phone_number": phone_number,
        "service": selected_service["name"],
        "date": date,
        "time": time_str,
        "notes": notes
    })
    print(f"\n✅ Appointment booked for {customer_name} on {date} at {time_str}.")
