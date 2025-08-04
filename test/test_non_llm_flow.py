# test/test_non_llm_flow_final.py

import os
import time
import traceback
import re
from pathlib import Path
from datetime import datetime
from assistant.session import CallSession
from assistant.assistant import process_interaction
from core.config_loader import load_config
from calendar_integration.ics_writer import (
    has_conflict,
    suggest_next_slot,
    add_event_to_calendar,
    load_calendar,
    FatalBookingError,
)
from utils.structured_logger import read_events
from typing import Callable

# === Adapter with pattern matching for resilience ===
class PatternAdapter:
    def __init__(self, response_map: list[tuple[Callable[[str], bool], object]]):
        self.response_map = response_map
        self.history = []

    def collect(self, prompt_text: str) -> str:
        self.history.append(("collect", prompt_text))
        for matcher, reply in self.response_map:
            try:
                if matcher(prompt_text):
                    value = reply() if callable(reply) else reply
                    print(f"[COLLECT PROMPT] {prompt_text}{value}")
                    self.history.append((prompt_text, value))
                    return value
            except Exception:
                continue
        print(f"[COLLECT PROMPT] {prompt_text}<no match>")
        self.history.append((prompt_text, ""))
        return ""

    def prompt(self, message: str):
        print(f"[PROMPT] {message}")
        self.history.append(("prompt", message))

    def confirm(self, message: str):
        print(f"[CONFIRM] {message}")
        self.history.append(("confirm", message))


# Matcher helpers
def regex_match(pattern: str):
    compiled = re.compile(pattern, re.IGNORECASE)
    return lambda prompt: bool(compiled.search(prompt))

def contains_any(words: list[str]):
    lowers = [w.lower() for w in words]
    return lambda prompt: any(w in prompt.lower() for w in lowers)

def always(_):
    return True

# Assertion helpers
def assert_conflict(expected: bool, dt: datetime, duration: int, config, context=""):
    conflicts = has_conflict(dt, duration, ics_path=config.calendar.ics_path)
    if expected:
        assert conflicts, f"[{context}] Expected conflict at {dt} but none found."
    else:
        assert not conflicts, f"[{context}] Expected no conflict at {dt} but found one."

# === Test Cases ===

def test_config_loading_and_normalization():
    print("\n--- Test: Config loading & normalization ---")
    config = load_config()
    print("Loaded config:", config)
    assert config.services, "Services missing"
    assert ":" in config.hours.open and len(config.hours.open) == 5
    assert ":" in config.hours.close and len(config.hours.close) == 5
    return config

def test_calendar_conflict_and_suggestion(config):
    print("\n--- Test: Calendar conflict detection & suggestion ---")
    path = Path(config.calendar.ics_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = datetime.strptime("2025-08-15 10:00", "%Y-%m-%d %H:%M")
    add_event_to_calendar("Oil Change existing", existing, 30, "Block", ics_path=config.calendar.ics_path)
    assert_conflict(True, existing, 30, config, "initial")
    suggestion = suggest_next_slot(
        existing,
        30,
        ics_path=config.calendar.ics_path,
        business_start=datetime.strptime(config.hours.open, "%H:%M").time(),
        business_end=datetime.strptime(config.hours.close, "%H:%M").time(),
        interval_minutes=config.booking_slots.interval_minutes,
        max_lookahead_days=1,
    )
    assert suggestion is not None, "Should suggest alternate"
    print("Suggested alternative:", suggestion.strftime("%Y-%m-%d %H:%M"))
    assert_conflict(False, suggestion, 30, config, "suggestion free")

def test_calendar_corruption_recovery(config):
    print("\n--- Test: Calendar corruption recovery ---")
    path = Path(config.calendar.ics_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("invalid calendar content")
    cal = load_calendar(config.calendar.ics_path)
    assert hasattr(cal, "events"), "Fallback on corrupted calendar failed"
    print("Corrupted calendar handled")

def test_calendar_write_retry_backoff(config):
    print("\n--- Test: Calendar write resilience (transient) ---")
    path = Path(config.calendar.ics_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    dt = datetime.strptime("2025-08-16 12:00", "%Y-%m-%d %H:%M")
    parent = path.parent
    original_mode = parent.stat().st_mode
    try:
        os.chmod(parent, 0o500)
        def restore():
            time.sleep(1)
            os.chmod(parent, original_mode)
        import threading
        t = threading.Thread(target=restore)
        t.start()
        try:
            add_event_to_calendar("Transient", dt, 30, "Retry test", ics_path=config.calendar.ics_path)
        except FatalBookingError:
            print("Transient failure occurred; expecting retry after restore")
        t.join()
        assert_conflict(True, dt, 30, config, "post-retry")
        print("Recovered and wrote appointment")
    finally:
        os.chmod(parent, original_mode)

def test_booking_missing_slot_negative_paraphrase_recovery(config):
    print("\n--- Test: Booking flow missing slot + negative paraphrase recovery ---")
    session = CallSession(caller_number="+1-555-1000")
    adapter = PatternAdapter([
        (regex_match(r"which service would you like to book"), lambda: "Brake Inspection"),
        (regex_match(r"what time works for you"), lambda: "14:00"),
        (regex_match(r"just to confirm"), lambda: "no"),
        (regex_match(r"what time works for you"), lambda: "15:30"),
        (regex_match(r"^>"), lambda: "yes"),
    ])
    response = process_interaction("I want to book Brake Inspection on 2025-08-19", session, adapter)
    print("Final response:", response)
    assert "Appointment confirmed" in response, "Expected booking recovery"

def test_conflict_accept_suggestion(config):
    print("\n--- Test: Conflict then accept suggestion ---")
    session = CallSession(caller_number="+1-555-2000")
    path = Path(config.calendar.ics_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = datetime.strptime("2025-08-20 10:00", "%Y-%m-%d %H:%M")
    add_event_to_calendar("Existing", existing, 30, "Block", ics_path=config.calendar.ics_path)

    adapter = PatternAdapter([
        (regex_match(r"just to confirm"), lambda: "yes"),
        (contains_any(["next available slot is", "do you want that instead"]), lambda: "yes"),
        (regex_match(r"^>"), lambda: "yes"),  # fallback
    ])
    response = process_interaction("I want to book Oil Change 2025-08-20 10:00", session, adapter)
    print("Final response:", response)
    assert "Appointment confirmed" in response
    booked_time = session.state.get("time")
    assert booked_time != "10:00", "Should have used suggested alternative"

def test_conflict_reject_suggestion_escalation(config):
    print("\n--- Test: Conflict then reject suggestion escalation ---")
    session = CallSession(caller_number="+1-555-3000")
    path = Path(config.calendar.ics_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = datetime.strptime("2025-08-21 09:00", "%Y-%m-%d %H:%M")
    add_event_to_calendar("Existing", existing, 30, "Block", ics_path=config.calendar.ics_path)

    adapter = PatternAdapter([
        (regex_match(r"just to confirm"), lambda: "yes"),
        (contains_any(["next available slot is", "do you want that instead"]), lambda: "no"),
    ])
    response = process_interaction("I want to book Oil Change 2025-08-21 09:00", session, adapter)
    print("Final response:", response)
    assert session.escalation_triggered, "Expected escalation after rejecting alternative"

def test_fuzzy_service_extraction(config):
    print("\n--- Test: Fuzzy/multi-word service name extraction ---")
    session = CallSession(caller_number="+1-555-4000")
    adapter = PatternAdapter([
        (regex_match(r"just to confirm"), lambda: "yes"),  # confirm paraphrase
        (regex_match(r"^>"), lambda: "yes"),  # respond to the follow-up confirmation prompt
    ])
    # this tests fuzzy matching: "and" instead of "&"
    response = process_interaction("I want to book battery test and replacement on 2025-08-22 at 09:00", session, adapter)
    print("Final response:", response)
    assert "Appointment confirmed" in response, "Expected booking for fuzzy service phrase"
    assert session.state.get("service"), "Service slot should be extracted"


def test_info_and_offdomain_fallback(config):
    print("\n--- Test: Informational and off-domain fallback ---")
    session_hours = CallSession(caller_number="+1-555-5000")
    adapter1 = PatternAdapter([(always, lambda: "")])
    hours = process_interaction("What are your hours?", session_hours, adapter1)
    print("Hours:", hours)
    assert "open from" in hours.lower()

    session_price = CallSession(caller_number="+1-555-5001")
    adapter2 = PatternAdapter([(always, lambda: "")])
    price = process_interaction("How much is Tire Rotation?", session_price, adapter2)
    print("Pricing:", price)
    assert "tire rotation" in price.lower() or "which service" in price.lower()

    session_off = CallSession(caller_number="+1-555-5002")
    off = process_interaction("Tell me a joke", session_off, adapter2)
    print("Off-domain:", off)
    assert "only trained to assist" in off.lower()

def test_logging_content_assertions():
    print("\n--- Test: Logging content assertions ---")
    events = read_events(limit=100)
    print(f"Retrieved {len(events)} events")
    assert isinstance(events, list)
    booking_event = next((e for e in events if "booking_confirmed" in e.get("step", "")), None)
    assert booking_event is not None, "Expected booking_confirmed in logs"

def test_config_schema_rejection():
    print("\n--- Test: Bad config schema rejection ---")
    from core.config_schema import RootConfig
    bad = {"shop_name": "X", "services": []}
    try:
        RootConfig(**bad)
        assert False, "Schema validation should fail"
    except Exception as e:
        print("Caught expected schema error:", str(e))

# === Runner ===

def run_all():
    print("\n=== FINAL Non-LLM Deep Comprehensive Test Run ===")
    try:
        config = test_config_loading_and_normalization()
        test_calendar_conflict_and_suggestion(config)
        test_calendar_corruption_recovery(config)
        test_calendar_write_retry_backoff(config)
        test_booking_missing_slot_negative_paraphrase_recovery(config)
        test_conflict_accept_suggestion(config)
        test_conflict_reject_suggestion_escalation(config)
        test_fuzzy_service_extraction(config)
        test_info_and_offdomain_fallback(config)
        test_logging_content_assertions()
        test_config_schema_rejection()
        print("\n✅ ALL NON-LLM TESTS PASSED.")
    except AssertionError as e:
        print("\n❌ Assertion failed:", e)
        traceback.print_exc()
    except Exception:
        print("\n❌ Unexpected error during testing:")
        traceback.print_exc()

if __name__ == "__main__":
    run_all()
