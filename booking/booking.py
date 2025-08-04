# booking/booking.py

from calendar_integration.ics_writer import add_event_to_calendar, is_time_slot_available
from datetime import datetime
import re

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_time(time_str):
    return re.match(r"^\d{2}:\d{2}$", time_str)

def handle_booking(config, phone_number):
    """
    Handles booking interaction and adds appointment to calendar.
    """
    print("\n📅 Let's book your appointment.")

    customer_name = input("🧾 Full Name: ").strip()
    if not customer_name:
        print("❌ Name cannot be empty.")
        return

    car_model = input("🚘 Car Make/Model: ").strip()
    issue = input("🔧 Describe the issue or service needed: ").strip()

    date = input("📆 Preferred Date (YYYY-MM-DD): ").strip()
    if not is_valid_date(date):
        print("❌ Invalid date format.")
        return

    time = input("⏰ Preferred Time (HH:MM): ").strip()
    if not is_valid_time(time):
        print("❌ Invalid time format.")
        return

    # Check if in the past
    appointment_datetime = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    if appointment_datetime < datetime.now():
        print("❌ Cannot book in the past.")
        return

    # Check for double booking
    calendar_path = config["calendar"]["ics_path"]
    duration = config.get("booking_slots", {}).get("interval_minutes", 30)
    if not is_time_slot_available(calendar_path, date, time, duration):
        print("❌ This time slot is already booked. Please choose another.")
        return

    # All good, book it
    summary = f"{customer_name} - {car_model} - {issue}"
    description = f"Customer: {customer_name}\nPhone: {phone_number}\nCar: {car_model}\nIssue: {issue}"
    add_event_to_calendar(calendar_path, date, time, "Mechanic Appointment", description, duration)

    print(f"\n✅ Appointment booked for {customer_name} on {date} at {time}.")
