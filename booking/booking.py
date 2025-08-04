# booking/booking.py

from calendar_integration.ics_writer import has_conflict, add_event_to_calendar
from datetime import datetime
import re
import uuid
from utils.call_logger import log_interaction

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

def handle_booking(config: dict, phone_number: str, call_id: str):
    """
    Handles appointment booking with conflict detection, confirmation, and logging.
    """
    print("\n📅 Let's book your appointment.")

    car_model = input("🚘 Car Make/Model (optional): ").strip()
    issue = input("🔧 Describe the issue or service needed (optional): ").strip()

    # Show available services
    services = config.get("services", [])
    if not services:
        print("❌ No services configured.")
        return

    print("\n🛠️ Available Services:")
    for i, service in enumerate(services, start=1):
        duration = service.get("duration_minutes", 30)
        print(f"{i}. {service['name']} - {service.get('price','N/A')} ({duration} min)")

    while True:
        svc_choice = input("🔢 Select service by number: ").strip()
        if not svc_choice.isdigit() or not (1 <= int(svc_choice) <= len(services)):
            print("❌ Invalid selection. Try again.")
            continue
        selected_service = services[int(svc_choice) - 1]
        break

    # Date input
    while True:
        date = input("📆 Preferred Date (YYYY-MM-DD): ").strip()
        if not is_valid_date(date):
            print("❌ Invalid date format.")
            continue
        break

    # Time input
    while True:
        time_str = input("⏰ Preferred Time (HH:MM): ").strip()
        if not is_valid_time(time_str):
            print("❌ Invalid time format.")
            continue
        break

    # Parse datetime
    try:
        appointment_dt = parse_datetime(date, time_str)
    except ValueError:
        print("❌ Could not parse date/time.")
        return

    if appointment_dt < datetime.now():
        print("❌ Cannot book in the past.")
        return

    duration = selected_service.get("duration_minutes", 30)

    # Conflict detection
    if has_conflict(appointment_dt, duration):
        print("❌ That time slot is already booked.")
        return

    # Confirmation
    short_phone = phone_number[-4:]
    appointment_id = str(uuid.uuid4())[:8]
    print("\n🔒 Confirm Booking:")
    print(f"Service: {selected_service['name']}")
    print(f"When: {date} at {time_str} for {duration} minutes")
    print(f"Phone: ending in {short_phone}")
    if car_model:
        print(f"Car: {car_model}")
    if issue:
        print(f"Issue/Notes: {issue}")
    print(f"Appointment ID: {appointment_id}")
    confirm = input("Confirm? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("❌ Booking cancelled.")
        return

    # Compose description
    description = (
        f"Appointment ID: {appointment_id}\n"
        f"Phone: {phone_number}\n"
        f"Service: {selected_service['name']}\n"
        f"Car: {car_model or 'N/A'}\n"
        f"Issue/Notes: {issue or 'N/A'}"
    )

    # Add to calendar
    add_event_to_calendar(date, time_str, "Mechanic Appointment", description, duration)

    # Log booking
    log_interaction("booking_created", {
        "appointment_id": appointment_id,
        "phone_number": phone_number,
        "service": selected_service["name"],
        "date": date,
        "time": time_str,
        "car_model": car_model,
        "issue": issue
    })

    print(f"\n✅ Appointment booked for {selected_service['name']} on {date} at {time_str}.")
    print(f"📌 Appointment ID: {appointment_id}. A reminder will be sent.")
