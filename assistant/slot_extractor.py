# assistant/slot_extractor.py

from datetime import datetime
import re
from assistant.session import CallSession
from typing import Dict

# Patterns for basic extraction
DATE_PATTERN = r"(\d{4}-\d{2}-\d{2})"
TIME_PATTERN = r"([01]?\d|2[0-3]):[0-5]\d"

def extract_slots_deterministic(user_input: str, known_services: list[str]) -> Dict[str, str]:
    """
    Try to pull service, date, and time deterministically from user input.
    Returns any found slots; missing ones left out.
    """
    slots = {}
    # date
    date_match = re.search(DATE_PATTERN, user_input)
    if date_match:
        slots["date"] = date_match.group(1)
    # time
    time_match = re.search(TIME_PATTERN, user_input)
    if time_match:
        slots["time"] = time_match.group(1)
    # service: match by service name presence (case-insensitive)
    lowered = user_input.lower()
    for svc in known_services:
        if svc.lower() in lowered:
            slots["service"] = svc
            break
    return slots

def clarify_missing_slots(slots: Dict[str, str], session: CallSession, io_adapter, config: dict) -> Dict[str, str]:
    """
    Asks the user directly for any missing slot (service, date, time).
    Updates session with clarified values.
    """
    # Service
    if "service" not in slots or not slots["service"]:
        services_list = [s["name"] for s in config.get("services", [])]
        question = f"Which service would you like to book? Options: {', '.join(services_list)}"
        answer = io_adapter.collect(f"{question} ")
        if answer:
            slots["service"] = answer.strip().title()
            session.update_slot("service", slots["service"])
            session.add_history("clarified_service", input_data=answer)

    # Date
    if "date" not in slots or not slots["date"]:
        answer = io_adapter.collect("What date would you like? (YYYY-MM-DD) ")
        if answer:
            slots["date"] = answer.strip()
            session.update_slot("date", slots["date"])
            session.add_history("clarified_date", input_data=answer)

    # Time
    if "time" not in slots or not slots["time"]:
        answer = io_adapter.collect("What time would you prefer? (HH:MM in 24h) ")
        if answer:
            slots["time"] = answer.strip()
            session.update_slot("time", slots["time"])
            session.add_history("clarified_time", input_data=answer)

    return slots

def extract_and_prepare(user_input: str, session: CallSession, io_adapter, config: dict) -> Dict[str, str]:
    """
    Full pipeline: deterministic extraction using known services, then clarification for missing slots.
    """
    known_services = [s["name"] for s in config.get("services", [])]
    slots = extract_slots_deterministic(user_input, known_services)

    # Merge any already-known session state to prefer persisted values
    for k in ["service", "date", "time"]:
        if k in session.state and k not in slots:
            slots[k] = session.state[k]

    slots = clarify_missing_slots(slots, session, io_adapter, config)
    return slots
