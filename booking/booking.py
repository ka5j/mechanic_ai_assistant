# booking/booking.py

from calendar_integration.ics_writer import has_conflict, add_event_to_calendar, suggest_next_slot
from datetime import datetime
import re
from assistant.slot_extractor import extract_and_prepare
from assistant.escalation import escalation_message, mark_and_log
from utils.structured_logger import log_event

DATE_RETRY_LIMIT = 3
TIME_RETRY_LIMIT = 3

def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def is_valid_time(time_str):
    return re.match(r"^([01]?\d|2[0-3]):[0-5]\d$", time_str) is not None

def parse_local_datetime(date_str: str, time_str: str):
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/Toronto")
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=LOCAL_TZ)

def handle_booking(config: dict, phone_number: str, call_id: str, session, io_adapter):
    """
    Handles appointment booking with extraction, conflict detection, suggestion, confirmation, and escalation.
    """
    io_adapter.prompt("\nLet's book your appointment.")
    session.add_history("booking_start")
    log_event(session.call_id, "booking_start")

    # Attempt to get free-form request and extract needed slots
    raw_request = io_adapter.collect("What would you like to book? (e.g., 'Oil change next Tuesday at 10:00') ")
    session.add_history("raw_booking_request", input_data=raw_request)
    log_event(session.call_id, "raw_booking_request", input_data=raw_request)

    slots = extract_and_prepare(raw_request, session, io_adapter, config)
    service = slots.get("service", "")
    date_str = slots.get("date", "")
    time_str = slots.get("time", "")

    if not service or not date_str or not time_str:
        io_adapter.prompt(escalation_message())
        mark_and_log(session, "incomplete_after_extraction", extra={"slots": slots})
        return

    session.update_slot("service", service)
    session.update_slot("date", date_str)
    session.update_slot("time", time_str)

    # Validate date
    if not is_valid_date(date_str):
        io_adapter.prompt(f"'{date_str}' is not a valid date format. Expected YYYY-MM-DD.")
        session.add_history("date_invalid", input_data=date_str)
        log_event(session.call_id, "date_invalid", input_data=date_str)
        io_adapter.prompt(escalation_message())
        mark_and_log(session, "invalid_date_format", extra={"provided": date_str})
        return

    # Validate time
    if not is_valid_time(time_str):
        io_adapter.prompt(f"'{time_str}' is not a valid time format. Expected HH:MM in 24h.")
        session.add_history("time_invalid", input_data=time_str)
        log_event(session.call_id, "time_invalid", input_data=time_str)
        io_adapter.prompt(escalation_message())
        mark_and_log(session, "invalid_time_format", extra={"provided": time_str})
        return

    # Parse desired datetime
    try:
        desired_dt = parse_local_datetime(date_str, time_str)
    except Exception as e:
        io_adapter.prompt("Failed to parse date/time. Escalating.")
        mark_and_log(session, "parse_error", extra={"error": str(e)})
        return

    # Lookup service duration safely
    services = config.get("services", [])
    duration = 30
    for s in services:
        if s.get("name", "").lower() == service.lower():
            duration = s.get("duration_minutes", 30)
            break
    session.update_slot("duration_minutes", duration)

    # Conflict detection
    conflicts = has_conflict(desired_dt, duration, ics_path=config["calendar"].get("ics_path"))
    if conflicts:
        io_adapter.prompt("The requested slot is unavailable due to a conflict.")
        session.add_history("conflict_detected", extra={"conflicts": conflicts})
        log_event(session.call_id, "conflict_detected", extra={"conflicts": conflicts})

        # Attempt next available suggestion
        # Business hours fallback to config or defaults
        from datetime import time as dtime
        business_start = dtime(9, 0)
        business_end = dtime(17, 0)
        booking_slots = config.get("booking_slots", {})
        interval = booking_slots.get("interval_minutes", 30)

        suggestion = suggest_next_slot(
            desired_dt,
            duration,
            ics_path=config["calendar"].get("ics_path"),
            business_start=business_start,
            business_end=business_end,
            interval_minutes=interval,
            max_lookahead_days=7
        )

        if suggestion:
            readable = suggestion.strftime("%Y-%m-%d %H:%M")
            io_adapter.prompt(f"Next available slot: {readable}. Accept? (yes/no)")
            accept = io_adapter.collect("> ").lower()
            if accept.startswith("y"):
                desired_dt = suggestion
                session.update_slot("date", desired_dt.strftime("%Y-%m-%d"))
                session.update_slot("time", desired_dt.strftime("%H:%M"))
                session.add_history("accepted_suggestion", input_data=readable)
                log_event(session.call_id, "accepted_suggestion", input_data=readable)
            else:
                io_adapter.prompt(escalation_message())
                mark_and_log(session, "user_rejected_suggestion")
                return
        else:
            io_adapter.prompt("No available alternative slot found in the next window. Escalating.")
            mark_and_log(session, "no_alternatives")
            return

    # Finalize booking
    try:
        title = f"{service} for {phone_number}"
        description = f"Booked service: {service}"
        add_event_to_calendar(title, desired_dt, duration, description, ics_path=config["calendar"].get("ics_path"))
        io_adapter.confirm(f"Appointment confirmed for {service} on {desired_dt.strftime('%Y-%m-%d')} at {desired_dt.strftime('%H:%M')}.")
        session.add_history("booking_confirmed", output_data={"service": service, "datetime": desired_dt.isoformat()})
        log_event(session.call_id, "booking_confirmed", output_data=session.state)
    except Exception as e:
        io_adapter.prompt(f"Booking failed: {e}")
        session.add_history("booking_error", extra={"error": str(e)})
        log_event(session.call_id, "booking_error", outcome="error", extra={"error": str(e)})
