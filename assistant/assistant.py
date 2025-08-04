# assistant/assistant.py

from openai import OpenAI
from core.config_loader import load_env_variables, load_config
from utils.usage_guard import can_call_model, record_usage
from utils.persistence import persist_appointment, persist_call_session, persist_usage
from utils.structured_logger import log_event
from assistant.session import CallSession
from assistant.slot_extractor import extract_and_prepare
from assistant.escalation import escalation_message, mark_and_log
from calendar_integration.ics_writer import (
    has_conflict,
    suggest_next_slot,
    add_event_to_calendar,
    FatalBookingError,
)
from datetime import datetime, time as dtime
from typing import Optional

# ==== LLM confirmation helper & exceptions ====

class UsageLimitError(Exception):
    """Raised when can_call_model() returns False."""
    pass

def llm_confirm(paraphrase: str, session: 'CallSession') -> bool | None:
    """
    Ask the LLM a yes/no question (paraphrase).
    Returns True for yes, False for no, or None if unclear.
    Raises UsageLimitError if calling the model is disallowed.
    """
    # Check quota
    if not can_call_model():
        raise UsageLimitError()

    # Build the LLM prompt
    messages = build_llm_prompt(paraphrase, session, missing_slots=[])
    # Call GPT deterministically
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=0.0,
        max_tokens=32,
    )

    # Record token usage
    usage = getattr(response, "usage", {}) or {}
    total = usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
    if total:
        record_usage(total)
        try:
            persist_usage(session.call_id, total)
        except Exception:
            # best effort
            pass

    # Extract and normalize output
    text = response.choices[0].message.content.strip().lower()
    log_event(session.call_id, "llm_confirm_reply", input_data=paraphrase, output_data=text)
    session.add_history("llm_confirm_reply", input_data=paraphrase, output_data=text)

    # Map to boolean or None
    if any(kw in text for kw in AFFIRMATIVE_KEYWORDS):
        return True
    if any(kw in text for kw in NEGATIVE_KEYWORDS):
        return False
    return None


# Load configuration and OpenAI client
env = load_env_variables()
client = OpenAI(api_key=env["OPENAI_API_KEY"])
config = load_config()

# === System prompt ===
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

# Intent helper
def classify_intent(user_input: str) -> str:
    lowered = user_input.lower()
    if any(k in lowered for k in ["book", "appointment", "schedule", "reserve"]):
        return "booking"
    if any(k in lowered for k in ["price", "cost", "how much", "rate", "charge"]):
        return "pricing"
    if any(k in lowered for k in ["what", "when", "hours", "open", "close", "availability"]):
        return "information"
    return "general"

# Confirmation keywords
AFFIRMATIVE_KEYWORDS = {
    "yes", "yep", "correct", "that is right", "sure", "sounds good", "affirmative",
    "yup", "right", "yeah", "please do", "go ahead", "works", "okay", "ok"
}
NEGATIVE_KEYWORDS = {
    "no", "nah", "incorrect", "don't", "do not", "nope", "not really", "wrong",
    "actually", "change", "cancel"
}

# Build LLM prompt
def build_llm_prompt(user_input: str, session: CallSession, missing_slots: list[str]) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT.strip()}]
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
        return 0 <= int(h) <= 23 and 0 <= int(m) <= 59
    except ValueError:
        return False

def parse_local_datetime(date_str: str, time_str: str) -> datetime:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("America/Toronto")
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=LOCAL_TZ)

# Info handler
def handle_info_intent(user_input: str, session: CallSession) -> str:
    call_id = session.call_id
    lowered = user_input.lower()
    if "hours" in lowered or "open" in lowered or "close" in lowered:
        reply = f"We are open from {config.hours.open} to {config.hours.close}."
        log_event(call_id, "info_response", output_data=reply)
        session.add_history("info_response", output_data=reply)
        return reply
    if any(kw in lowered for kw in ["price", "cost", "how much", "rate", "charge"]):
        found = []
        for s in config.services:
            if s.name.lower() in lowered:
                price = s.price or "N/A"
                found.append(f"{s.name}: {price}")
        if found:
            reply = "Pricing: " + "; ".join(found)
        else:
            svc_names = ", ".join([s.name for s in config.services])
            reply = f"Which service are you asking about? Options: {svc_names}"
        log_event(call_id, "pricing_response", output_data=reply)
        session.add_history("pricing_response", output_data=reply)
        return reply
    fallback = "I'm only trained to assist with mechanic shop-related questions."
    log_event(call_id, "fallback_info", output_data=fallback)
    session.add_history("fallback_info", output_data=fallback)
    return fallback

# Core entrypoint
def process_interaction(user_input: str, session: CallSession, io_adapter, max_slot_attempts: int = 2) -> str:
    call_id = session.call_id
    log_event(call_id, "user_input", input_data=user_input)
    intent = classify_intent(user_input)
    log_event(call_id, "intent_classified", input_data=user_input, output_data=intent)

    # Information/pricing
    if intent in ("pricing", "information"):
        return handle_info_intent(user_input, session)
    if intent != "booking":
        fallback = "I'm only trained to assist with mechanic shop-related questions."
        io_adapter.prompt(fallback)
        log_event(call_id, "fallback", output_data=fallback)
        session.add_history("fallback", output_data=fallback)
        persist_call_session(session)
        return fallback

    # 1. Extract slots
    extract_and_prepare(user_input, session, io_adapter, config)
    missing = [s for s in ["service", "date", "time"] if not session.state.get(s)]

    # 2. Clarify
    for slot in missing:
        attempts = 0
        while not session.state.get(slot):
            if attempts >= max_slot_attempts:
                io_adapter.prompt(escalation_message())
                mark_and_log(session, f"failed_clarify_{slot}")
                persist_call_session(session)
                return escalation_message()
            if slot == "service":
                opts = ", ".join(s.name for s in config.services)
                ans = io_adapter.collect(f"Which service would you like to book? Options: {opts}: ")
                if ans:
                    session.update_slot("service", ans.strip().title())
                    session.add_history("clarified_service", input_data=ans)
                    log_event(call_id, "clarified_service", input_data=ans)
            elif slot == "date":
                ans = io_adapter.collect("What date would you like? (YYYY-MM-DD): ")
                if ans:
                    if validate_date_format(ans.strip()):
                        session.update_slot("date", ans.strip())
                        session.add_history("clarified_date", input_data=ans)
                        log_event(call_id, "clarified_date", input_data=ans)
                    else:
                        io_adapter.prompt("❌ Invalid date format. Use YYYY-MM-DD.")
                        session.add_history("date_invalid", input_data=ans)
                        log_event(call_id, "date_invalid", input_data=ans)
            else:  # time
                ans = io_adapter.collect("What time works for you? (HH:MM 24h): ")
                if ans:
                    if validate_time_format(ans.strip()):
                        session.update_slot("time", ans.strip())
                        session.add_history("clarified_time", input_data=ans)
                        log_event(call_id, "clarified_time", input_data=ans)
                    else:
                        io_adapter.prompt("❌ Invalid time format. Use HH:MM in 24h.")
                        session.add_history("time_invalid", input_data=ans)
                        log_event(call_id, "time_invalid", input_data=ans)
            attempts += 1

    # 3. Confirmation
    svc = session.state["service"]
    date = session.state["date"]
    time_slot = session.state["time"]
    paraphrase = f"Just to confirm: you want a {svc} on {date} at {time_slot}. Is that correct?"
    io_adapter.prompt(paraphrase)
    session.add_history("paraphrase_prompt", output_data=paraphrase)
    log_event(call_id, "paraphrase_prompt", output_data=paraphrase)

    reply = io_adapter.collect("> ").strip().lower()
    session.add_history("user_confirmation", input_data=reply)
    log_event(call_id, "user_confirmation", input_data=reply)

    def has_keyword(text, kws):
        return any(kw in text for kw in kws)

    confirmed = False
    if has_keyword(reply, AFFIRMATIVE_KEYWORDS):
        confirmed = True
    elif has_keyword(reply, NEGATIVE_KEYWORDS):
        confirmed = False
    else:
        # fallback to LLM
        prompt_msgs = build_llm_prompt(paraphrase, session, missing_slots=[])
        if not can_call_model():
            io_adapter.prompt("⚠️ Usage limit reached. " + escalation_message())
            log_event(call_id, "usage_limit")
            persist_call_session(session)
            return escalation_message()
        try:
            res = client.chat.completions.create(
                model="gpt-3.5-turbo", messages=prompt_msgs,
                temperature=0.1, max_tokens=100
            )
            usage = getattr(res, "usage", {}) or {}
            pt = usage.get("prompt_tokens", 0)
            ct = usage.get("completion_tokens", 0)
            total = pt + ct
            if total:
                record_usage(total)
                persist_usage(call_id, total)
            llm_text = res.choices[0].message.content.strip().lower()
            log_event(call_id, "llm_confirmation", input_data=paraphrase, output_data=llm_text)
            session.add_history("llm_confirmation", input_data=paraphrase, output_data=llm_text)
            if has_keyword(llm_text, AFFIRMATIVE_KEYWORDS):
                confirmed = True
            elif has_keyword(llm_text, NEGATIVE_KEYWORDS):
                confirmed = False
            else:
                io_adapter.prompt(escalation_message())
                mark_and_log(session, "confirm_unclear")
                persist_call_session(session)
                return escalation_message()
        except Exception as e:
            io_adapter.prompt("⚠️ Error during confirmation. " + escalation_message())
            mark_and_log(session, "confirm_error", extra={"error": str(e)})
            persist_call_session(session)
            return escalation_message()

    if not confirmed:
        io_adapter.prompt("Okay, let's try again.")
        session.add_history("confirm_rejected", output_data=reply)
        log_event(call_id, "confirm_rejected", output_data=reply)
        persist_call_session(session)
        return "Okay, let's try again."

    # 4. Booking
    try:
        dt = parse_local_datetime(session.state["date"], session.state["time"])
    except Exception:
        io_adapter.prompt(escalation_message())
        mark_and_log(session, "parse_error")
        persist_call_session(session)
        return escalation_message()

    # determine duration
    dur = next((s.duration_minutes for s in config.services if s.name.lower() == svc.lower()), 30)
    session.update_slot("duration_minutes", dur)

    conflicts = has_conflict(dt, dur, ics_path=config.calendar.ics_path)
    if conflicts:
        io_adapter.prompt("That slot is unavailable due to a conflict.")
        session.add_history("conflict_detected", extra={"conflicts": conflicts})
        log_event(call_id, "conflict_detected", extra={"conflicts": conflicts})

        alt = suggest_next_slot(
            dt, dur, ics_path=config.calendar.ics_path,
            business_start=dtime(*map(int, config.hours.open.split(":"))),
            business_end=dtime(*map(int, config.hours.close.split(":"))),
            interval_minutes=config.booking_slots.interval_minutes,
            max_lookahead_days=7
        )
        if alt:
            readable = alt.strftime("%Y-%m-%d %H:%M")
            io_adapter.prompt(f"The next available slot is {readable}. Do you want that instead? (yes/no)")
            ans = io_adapter.collect("> ").lower()
            if any(k in ans for k in AFFIRMATIVE_KEYWORDS):
                session.update_slot("date", alt.strftime("%Y-%m-%d"))
                session.update_slot("time", alt.strftime("%H:%M"))
                dt = alt
                session.add_history("accepted_alt", input_data=readable)
                log_event(call_id, "accepted_alt", input_data=readable)
            else:
                io_adapter.prompt(escalation_message())
                mark_and_log(session, "reject_alt")
                persist_call_session(session)
                return escalation_message()
        else:
            io_adapter.prompt(escalation_message())
            mark_and_log(session, "no_alt")
            persist_call_session(session)
            return escalation_message()

    try:
        add_event_to_calendar(
            f"{svc} for {session.caller_number}",
            dt, dur,
            description=f"Booked service: {svc}",
            ics_path=config.calendar.ics_path
        )
        confirmation = f"✅ Appointment confirmed for {svc} on {session.state['date']} at {session.state['time']}."
        io_adapter.prompt(confirmation)
        session.add_history("booking_confirmed", output_data=confirmation)
        log_event(call_id, "booking_confirmed", output_data=session.state)

        # persist appointment & call
        persist_appointment({
            "call_id": session.call_id,
            "service": svc,
            "date": session.state["date"],
            "time": session.state["time"],
            "duration_minutes": dur,
            "created_at": datetime.now().isoformat(),
        })
        persist_call_session(session)

        return confirmation

    except FatalBookingError as e:
        io_adapter.prompt("❌ Failed to finalize booking due to system error. " + escalation_message())
        mark_and_log(session, "final_error", extra={"error": str(e)})
        persist_call_session(session)
        return escalation_message()
    except Exception as e:
        io_adapter.prompt("❌ Failed to finalize booking. " + escalation_message())
        mark_and_log(session, "final_error", extra={"error": str(e)})
        persist_call_session(session)
        return escalation_message()
