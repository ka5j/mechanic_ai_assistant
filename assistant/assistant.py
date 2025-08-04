# assistant/assistant.py

from openai import OpenAI
from core.config_loader import load_env_variables
from utils.usage_guard import can_call_model, record_usage
from utils.structured_logger import log_event
from assistant.session import CallSession
from assistant.slot_extractor import extract_and_prepare
from assistant.escalation import escalation_message, mark_and_log
from calendar_integration.ics_writer import has_conflict, suggest_next_slot, add_event_to_calendar
from datetime import datetime, time as dtime
from typing import Optional

# Load configuration and OpenAI client
config = load_env_variables()
client = OpenAI(api_key=config["OPENAI_API_KEY"])

# === System prompt (detailed, bounded, unambiguous) ===
SYSTEM_PROMPT = """
You are a professional, strict, and cost-conscious AI receptionist for a mechanic shop.
Your domain is only:
  - Booking appointments (service, date, time)
  - Clarifying booking details
  - Providing information on services, prices, availability/hours
  - Confirming bookings
Do NOT answer anything outside those topics. If asked off-topic, reply: "I'm only trained to assist with mechanic shop-related questions."
Rules:
  1. Always extract or confirm the required booking slots: service, date (YYYY-MM-DD), time (HH:MM in 24h).
  2. If any slot is missing or ambiguous, ask one concise clarification question at a time.
  3. Echo back service, date, and time exactly when confirming: "Just to confirm: you want a <service> on <date> at <time>. Is that correct?"
  4. If requested slot conflicts, offer the next available slot and ask: "That slot is taken. The next available is <date> at <time>. Do you want that instead?"
  5. After two failed attempts per slot or rejection of valid alternative, escalate with: 
     "I'm having trouble completing that booking. I can transfer you to a human staff member for help."
  6. Be concise. Do not invent availability or services.
"""

# === Intent classification ===
def classify_intent(user_input: str) -> str:
    lowered = user_input.lower()
    if any(k in lowered for k in ["book", "appointment", "schedule", "reserve"]):
        return "booking"
    if any(k in lowered for k in ["price", "cost", "how much", "fee", "charge"]):
        return "pricing"
    if any(k in lowered for k in ["what", "when", "hours", "open", "close", "availability"]):
        return "information"
    return "general"

# === Prompt builder (minimal context) ===
def build_llm_prompt(user_input: str, session: CallSession, missing_slots: list[str]) -> list[dict]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.strip()},
    ]
    if missing_slots:
        messages.append({
            "role": "system",
            "content": f"User still needs to provide: {', '.join(missing_slots)}."
        })
    else:
        confirmed = ", ".join(f"{k}={v}" for k, v in session.state.items() if k in ["service", "date", "time"])
        messages.append({
            "role": "system",
            "content": f"Confirmed booking info: {confirmed}."
        })
    messages.append({"role": "user", "content": user_input.strip()})
    return messages

# === Core interaction function ===
def process_interaction(user_input: str, session: CallSession, io_adapter, max_slot_attempts: int = 2) -> str:
    """
    Handles a single high-level user interaction: intent detection, slot extraction/clarification,
    booking flow (with conflicts/suggestions), confirmation, and escalation.
    Returns the assistant's response string (which may be a booking confirmation, clarification question, or escalation).
    """
    call_id = session.call_id
    log_event(call_id, "user_input", input_data=user_input)
    intent = classify_intent(user_input)
    log_event(call_id, "intent_classified", input_data=user_input, output_data=intent)

    # Handle non-booking informational intents with deterministic replies
    if intent in ("pricing", "information"):
        reply = handle_info_intent(user_input, session)
        return reply

    if intent != "booking":
        fallback = "I'm only trained to assist with mechanic shop-related questions."
        io_adapter.prompt(fallback)
        log_event(call_id, "fallback", output_data=fallback)
        session.add_history("fallback", output_data=fallback)
        return fallback

    # 1. Extract/clarify initial slots from free-form input
    slots = extract_and_prepare(user_input, session, io_adapter, config)
    missing = [s for s in ["service", "date", "time"] if not session.state.get(s)]

    # 2. Clarify missing slots one by one (with limited attempts)
    for slot_name in missing:
        attempts = 0
        while not session.state.get(slot_name):
            if attempts >= max_slot_attempts:
                # Escalate
                io_adapter.prompt(escalation_message())
                mark_and_log(session, f"failed_clarify_{slot_name}")
                return escalation_message()
            if slot_name == "service":
                services_list = [s["name"] for s in config.get("services", [])]
                answer = io_adapter.collect(f"Which service would you like to book? Options: {', '.join(services_list)}: ")
                if answer:
                    session.update_slot("service", answer.strip().title())
                    session.add_history("clarified_service", input_data=answer)
                    log_event(call_id, "clarified_service", input_data=answer)
            elif slot_name == "date":
                answer = io_adapter.collect("What date would you like? (YYYY-MM-DD): ")
                if answer:
                    if validate_date_format(answer.strip()):
                        session.update_slot("date", answer.strip())
                        session.add_history("clarified_date", input_data=answer)
                        log_event(call_id, "clarified_date", input_data=answer)
                    else:
                        io_adapter.prompt("❌ Invalid date format. Use YYYY-MM-DD.")
                        session.add_history("date_invalid", input_data=answer)
                        log_event(call_id, "date_invalid", input_data=answer)
            elif slot_name == "time":
                answer = io_adapter.collect("What time works for you? (HH:MM 24h): ")
                if answer:
                    if validate_time_format(answer.strip()):
                        session.update_slot("time", answer.strip())
                        session.add_history("clarified_time", input_data=answer)
                        log_event(call_id, "clarified_time", input_data=answer)
                    else:
                        io_adapter.prompt("❌ Invalid time format. Use HH:MM in 24h.")
                        session.add_history("time_invalid", input_data=answer)
                        log_event(call_id, "time_invalid", input_data=answer)
            attempts += 1

    # All required slots present: confirm with user (via LLM)
    service = session.state.get("service")
    date = session.state.get("date")
    time_slot = session.state.get("time")

    confirmation_text = f"Just to confirm: you want a {service} on {date} at {time_slot}. Is that correct?"
    llm_prompt = build_llm_prompt(confirmation_text, session, missing_slots=[])
    if not can_call_model():
        io_adapter.prompt("⚠️ Usage limit reached. " + escalation_message())
        log_event(call_id, "usage_limit_hit")
        return escalation_message()

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=llm_prompt,
            temperature=0.1,
            max_tokens=100,
        )
        usage = {}
        try:
            usage = response.usage or {}
        except Exception:
            pass
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = prompt_tokens + completion_tokens
        if total_tokens:
            record_usage(total_tokens)
        reply = response.choices[0].message.content.strip().lower()
        log_event(call_id, "confirmation_response", input_data=confirmation_text, output_data=reply)
        session.add_history("confirmation_response", input_data=confirmation_text, output_data=reply)
    except Exception as e:
        io_adapter.prompt("⚠️ Error during confirmation. " + escalation_message())
        mark_and_log(session, "confirmation_llm_error", extra={"error": str(e)})
        return escalation_message()

    # Interpret confirmation
    if any(affirm in reply for affirm in ["yes", "correct", "that is right", "yep", "sure"]):
        # Proceed to booking
        try:
            desired_dt = parse_local_datetime(session.state["date"], session.state["time"])
        except Exception:
            io_adapter.prompt(escalation_message())
            mark_and_log(session, "parse_error")
            return escalation_message()

        # Determine duration for the service
        duration = 30
        for s in config.get("services", []):
            if s.get("name", "").lower() == service.lower():
                duration = s.get("duration_minutes", 30)
                break
        session.update_slot("duration_minutes", duration)

        # Conflict detection
        conflicts = has_conflict(desired_dt, duration, ics_path=config["calendar"].get("ics_path"))
        if conflicts:
            io_adapter.prompt("That slot is unavailable due to a conflict.")
            session.add_history("conflict_detected", extra={"conflicts": conflicts})
            log_event(call_id, "conflict_detected", extra={"conflicts": conflicts})

            # Suggest next slot
            interval = config.get("booking_slots", {}).get("interval_minutes", 30)
            suggestion = suggest_next_slot(
                desired_dt,
                duration,
                ics_path=config["calendar"].get("ics_path"),
                business_start=dtime(9, 0),
                business_end=dtime(17, 0),
                interval_minutes=interval,
                max_lookahead_days=7
            )
            if suggestion:
                readable = suggestion.strftime("%Y-%m-%d %H:%M")
                io_adapter.prompt(f"The next available slot is {readable}. Do you want that instead? (yes/no)")
                accept = io_adapter.collect("> ").lower()
                if accept.startswith("y"):
                    session.update_slot("date", suggestion.strftime("%Y-%m-%d"))
                    session.update_slot("time", suggestion.strftime("%H:%M"))
                    desired_dt = suggestion
                    session.add_history("accepted_suggestion", input_data=readable)
                    log_event(call_id, "accepted_suggestion", input_data=readable)
                else:
                    io_adapter.prompt(escalation_message())
                    mark_and_log(session, "user_rejected_suggestion")
                    return escalation_message()
            else:
                io_adapter.prompt(escalation_message())
                mark_and_log(session, "no_alternatives")
                return escalation_message()

        # Finalize and confirm booking
        try:
            title = f"{service} for {session.caller_number}"
            description = f"Booked service: {service}"
            add_event_to_calendar(title, desired_dt, duration, description, ics_path=config["calendar"].get("ics_path"))
            confirmation = f"✅ Appointment confirmed for {service} on {session.state['date']} at {session.state['time']}."
            io_adapter.prompt(confirmation)
            session.add_history("booking_confirmed", output_data={"service": service, "datetime": desired_dt.isoformat()})
            log_event(call_id, "booking_confirmed", output_data=session.state)
            return confirmation
        except Exception as e:
            io_adapter.prompt("❌ Failed to finalize booking. " + escalation_message())
            mark_and_log(session, "finalization_error", extra={"error": str(e)})
            return escalation_message()
    else:
        # User rejected confirmation; allow retry
        io_adapter.prompt("Okay, let's try again.")
        session.add_history("confirmation_rejected", output_data=reply)
        log_event(call_id, "confirmation_rejected", output_data=reply)
        return "Okay, let's try again."

# Helper for info/pricing queries
def handle_info_intent(user_input: str, session: CallSession) -> str:
    call_id = session.call_id
    lowered = user_input.lower()
    if "hours" in lowered or "open" in lowered or "close" in lowered:
        hours = config.get("hours", {})
        open_h = hours.get("open", "09:00")
        close_h = hours.get("close", "17:00")
        reply = f"We are open from {open_h} to {close_h}."
        log_event(call_id, "info_response", output_data=reply)
        session.add_history("info_response", output_data=reply)
        return reply
    if "price" in lowered or "cost" in lowered:
        services = config.get("services", [])
        found = []
        for s in services:
            if s["name"].lower() in lowered:
                found.append(f"{s['name']}: {s.get('price', 'N/A')}")
        if found:
            reply = "Pricing: " + "; ".join(found)
        else:
            reply = "Which service are you asking about? Options: " + ", ".join([s["name"] for s in services])
        log_event(call_id, "pricing_response", output_data=reply)
        session.add_history("pricing_response", output_data=reply)
        return reply
    # fallback
    fallback = "I'm only trained to assist with mechanic shop-related questions."
    log_event(call_id, "fallback_info", output_data=fallback)
    session.add_history("fallback_info", output_data=fallback)
    return fallback

# Validators
def validate_date_format(date_str: str) -> bool:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False

def validate_time_format(time_str: str) -> bool:
    parts = time_str.split(":")
    if len(parts) != 2:
        return False
    h, m = parts
    try:
        h_i = int(h)
        m_i = int(m)
        return 0 <= h_i <= 23 and 0 <= m_i <= 59
    except ValueError:
        return False

def parse_local_datetime(date_str: str, time_str: str) -> datetime:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/Toronto")
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=LOCAL_TZ)
