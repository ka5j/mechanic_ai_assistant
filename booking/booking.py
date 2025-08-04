# booking/booking.py

from calendar_integration.ics_writer import add_event_to_calendar

def handle_booking(config, phone_number):
    """
    Simulate booking process. In real implementation, this would be dynamic.
    """
    print("\n📅 Let's book your appointment.")
    
    customer_name = input("🧾 Full Name: ").strip()
    car_model = input("🚘 Car Make/Model: ").strip()
    issue = input("🔧 Describe the issue or service needed: ").strip()
    date = input("📆 Preferred Date (YYYY-MM-DD): ").strip()
    time = input("⏰ Preferred Time (HH:MM): ").strip()

    summary = f"{customer_name} - {car_model} - {issue}"
    event_title = "Mechanic Appointment"
    description = f"Customer: {customer_name}\nPhone: {phone_number}\nCar: {car_model}\nIssue: {issue}"
    add_event_to_calendar(date, time, event_title, description)

    print(f"\n✅ Appointment booked for {customer_name} on {date} at {time}.")
