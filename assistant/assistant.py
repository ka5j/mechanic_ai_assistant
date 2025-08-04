# assistant/assistant.py

from openai import OpenAI
from core.config_loader import load_env_variables, load_config
from utils.usage_guard import can_call_model, record_usage
from utils.structured_logger import log_event
from assistant.session import CallSession
from assistant.slot_extractor import extract_and_prepare
from assistant.escalation import escalation_message, mark_and_log
from calendar_integration.ics_writer import has_conflict, suggest_next_slot, add_event_to_calendar
from datetime import datetime, time as dtime
from typing import Optional
from calendar_integration.ics_writer import FatalBookingError

# Load configuration and OpenAI client
env = load_env_variables()
client = OpenAI(api_key=env["OPENAI_API_KEY"])
config = load_config()

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

# Intent helper
def classify_intent(user_input: str) -> str:
    lowered = user_input.lower()
    if any(k in lowered for k in ["book", "appointment", "schedule", "reserve"]):
        return "booking"
    if any(k in lowered for k in ["price", "cost", "how much", "fee", "charge"]):
        return "pricing"
    if any(k in lowered for k in ["what", "when", "hours", "open", "close", "availability"]):
        return "information"
    return "general"

# Confirmation keyword sets
AFFIRMATIVE_KEYWORDS = {"yes", "yep", "correct", "that is right", "sure", "sounds good", "affirmative", "yup", "right"}
NEGATIVE_KEYWORDS = {"no", "nah", "incorrect", "don't", "do not", "nope", "not really", "wrong"}

# Build minimal LLM prompt
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

# Info handler (pricing/hours)
def handle_info_intent(user_input: str, session: CallSession) -> str:
    call_id = session.call_id
    lowered = user_input.lower()
    if "hours" in lowered or "open" in lowered or "close" in lowered:
        open_h = config.hours.open
        close_h = config.hours.close
        reply = f"We are open from {open_h} to {close_h}."
        log_event(call_id, "info_response", output_data=reply)
        session.add_history("info_response", output_data=reply)
        return reply
    if "price" in lowered or "cost" in lowered:
        found = []
        for s in config.services:
            if s.name.lower() in lowered:
                price = s.price if s.price else "N/A"
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

# Core interaction entrypoint
def process_interaction(user_input: str, session: CallSession, io_adapter, max_slot_attempts: int = 2) -> str:
    call_id = session.call_id
    log_event(call_id, "user_input", input_data=user_input)
    intent = classify_intent(user_input)
    log_event(call_id, "intent_classified", input_data=user_input, output_data=intent)

    if intent in ("pricing", "information"):
        return handle_info_intent(user_input, session)

    if intent != "booking":
        fallback = "I'm only trained to assist with mechanic shop-related questions."
        io_adapter.prompt(fallback)
        log_event(call_id, "fallback", output_data=fallback)
        session.add_history("fallback", output_data=fallback)
        return fallback

    # 1. Extract and clarify slots
    slots = extract_and_prepare(user_input, session, io_adapter, config)
    missing = [s for s in ["service", "date", "time"] if not session.state.get(s)]

    # 2. Clarify missing slots
    for slot_name in missing:
        attempts = 0
        while not session.state.get(slot_name):
            if attempts >= max_slot_attempts:
                io_adapter.prompt(escalation_message())
                mark_and_log(session, f"failed_clarify_{slot_name}")
                return escalation_message()
            if slot_name == "service":
                services_list = ", ".join([s.name for s in config.services])
                answer = io_adapter.collect(f"Which service would you like to book? Options: {services_list}: ")
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

    # 3. Paraphrase and confirm deterministically first
    service = session.state.get("service")
    date = session.state.get("date")
    time_slot = session.state.get("time")
    paraphrase = f"Just to confirm: you want a {service} on {date} at {time_slot}. Is that correct?"
    io_adapter.prompt(paraphrase)
    session.add_history("paraphrase_confirmation_prompt", output_data=paraphrase)
    log_event(call_id, "paraphrase_confirmation_prompt", output_data=paraphrase)

    user_reply = io_adapter.collect("> ").strip().lower()
    session.add_history("user_confirmation_reply", input_data=user_reply)
    log_event(call_id, "user_confirmation_reply", input_data=user_reply)

    def contains_keyword(text: str, keywords: set[str]) -> bool:
        return any(kw in text for kw in keywords)

    confirmed = False
    if contains_keyword(user_reply, AFFIRMATIVE_KEYWORDS):
        confirmed = True
    elif contains_keyword(user_reply, NEGATIVE_KEYWORDS):
        confirmed = False
    else:
        # Ambiguous: fallback to LLM confirmation
        confirmation_text = paraphrase
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
            llm_reply = response.choices[0].message.content.strip().lower()
            log_event(call_id, "llm_confirmation_reply", input_data=confirmation_text, output_data=llm_reply)
            session.add_history("llm_confirmation_reply", input_data=confirmation_text, output_data=llm_reply)

            if contains_keyword(llm_reply, AFFIRMATIVE_KEYWORDS):
                confirmed = True
            elif contains_keyword(llm_reply, NEGATIVE_KEYWORDS):
                confirmed = False
            else:
                io_adapter.prompt(escalation_message())
                mark_and_log(session, "confirmation_unclear_after_llm", extra={"llm_reply": llm_reply})
                return escalation_message()
        except Exception as e:
            io_adapter.prompt("⚠️ Error during confirmation. " + escalation_message())
            mark_and_log(session, "confirmation_llm_error", extra={"error": str(e)})
            return escalation_message()

    if not confirmed:
        io_adapter.prompt("Okay, let's try again.")
        session.add_history("confirmation_rejected", output_data=user_reply)
        log_event(call_id, "confirmation_rejected", output_data=user_reply)
        return "Okay, let's try again."

    # 4. Proceed to booking (slots confirmed)
    try:
        desired_dt = parse_local_datetime(session.state["date"], session.state["time"])
    except Exception:
        io_adapter.prompt(escalation_message())
        mark_and_log(session, "parse_error")
        return escalation_message()

    # Determine duration
    duration = 30
    for s in config.services:
        if s.name.lower() == service.lower():
            duration = s.duration_minutes
            break
    session.update_slot("duration_minutes", duration)

    # Conflict detection
    conflicts = has_conflict(desired_dt, duration, ics_path=config.calendar.ics_path)
    if conflicts:
        io_adapter.prompt("That slot is unavailable due to a conflict.")
        session.add_history("conflict_detected", extra={"conflicts": conflicts})
        log_event(call_id, "conflict_detected", extra={"conflicts": conflicts})

        interval = config.booking_slots.interval_minutes
        suggestion = suggest_next_slot(
            desired_dt,
            duration,
            ics_path=config.calendar.ics_path,
            business_start=dtime(int(config.hours.open.split(":")[0]), int(config.hours.open.split(":")[1])),
            business_end=dtime(int(config.hours.close.split(":")[0]), int(config.hours.close.split(":")[1])),
            interval_minutes=interval,
            max_lookahead_days=7
        )
        if suggestion:
            readable = suggestion.strftime("%Y-%m-%d %H:%M")
            io_adapter.prompt(f"The next available slot is {readable}. Do you want that instead? (yes/no)")
            accept = io_adapter.collect("> ").lower()
            if any(k in accept for k in AFFIRMATIVE_KEYWORDS):
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
        
        # Finalize booking
    try:
        title = f"{service} for {session.caller_number}"
        description = f"Booked service: {service}"
        add_event_to_calendar(title, desired_dt, duration, description, ics_path=config.calendar.ics_path)
        confirmation = f"✅ Appointment confirmed for {service} on {session.state['date']} at {session.state['time']}."
        io_adapter.prompt(confirmation)
        session.add_history("booking_confirmed", output_data={"service": service, "datetime": desired_dt.isoformat()})
        log_event(call_id, "booking_confirmed", output_data=session.state)
        return confirmation
    except FatalBookingError as e:
        io_adapter.prompt("❌ Failed to finalize booking due to system error. " + escalation_message())
        mark_and_log(session, "finalization_error", extra={"error": str(e)})
        return escalation_message()
    except Exception as e:
        io_adapter.prompt("❌ Failed to finalize booking. " + escalation_message())
        mark_and_log(session, "finalization_error", extra={"error": str(e)})
        return escalation_message()
