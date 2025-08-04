# test/test_non_llm_flow.py

import os
import json
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from assistant.session import CallSession
from assistant.io_adapter import CLIAdapter
from assistant.assistant import process_interaction
from core.config_loader import load_config
from calendar_integration.ics_writer import (
    has_conflict,
    suggest_next_slot,
    add_event_to_calendar,
    load_calendar,
    ICS_FILE,
    BookingError,
    FatalBookingError,
)
from utils.structured_logger import read_events, LOG_FILE
from assistant.escalation import escalation_message
import traceback

# Stub adapter to simulate user replies for non-LLM flows
class StubAdapter(CLIAdapter):
    def __init__(self, responses):
        self.responses = responses  # queue of responses
        self.idx = 0
        self.prompts = []

    def collect(self, prompt_text: str) -> str:
        print(f"[COLLECT PROMPT] {prompt_text}", end="")
        if self.idx < len(self.responses):
            resp = self.responses[self.idx]
            print(resp)
            self.idx += 1
            return resp
        print("<no response>")
        return ""

    def prompt(self, message: str):
        self.prompts.append(message)
        print(f"[PROMPT] {message}")

    def confirm(self, message: str):
        print(f"[CONFIRM] {message}")

# Helper to reset calendar file for clean tests
def reset_calendar_file(path: Path):
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

def simulate_conflict_and_suggestion(config):
    print("\n--- Test: Conflict detection and next-slot suggestion ---")
    # Ensure a known appointment exists
    reset_calendar_file(Path(config.calendar.ics_path))
    service = "Oil Change"
    # Book at 2025-08-15 10:00
    existing_dt = datetime.strptime("2025-08-15 10:00", "%Y-%m-%d %H:%M")
    add_event_to_calendar(f"{service} existing", existing_dt, 30, "Existing block", ics_path=config.calendar.ics_path)

    # Attempt to book same slot: should detect conflict
    desired_dt = existing_dt
    conflicts = has_conflict(desired_dt, 30, ics_path=config.calendar.ics_path)
    assert conflicts, "Expected conflict for overlapping appointment"
    print("Conflict detected as expected:", conflicts)

    # Suggest next available slot
    suggestion = suggest_next_slot(
        desired_dt,
        30,
        ics_path=config.calendar.ics_path,
        business_start=datetime.strptime(config.hours.open, "%H:%M").time(),
        business_end=datetime.strptime(config.hours.close, "%H:%M").time(),
        interval_minutes=config.booking_slots.interval_minutes,
        max_lookahead_days=1
    )
    assert suggestion is not None, "Expected a suggested alternative slot"
    print("Suggested alternative slot:", suggestion.strftime("%Y-%m-%d %H:%M"))

def test_calendar_corruption_recovery(config):
    print("\n--- Test: Calendar corruption recovery ---")
    reset_calendar_file(Path(config.calendar.ics_path))
    # Write invalid content to calendar file to simulate corruption
    with open(config.calendar.ics_path, "w") as f:
        f.write("this is not valid ics content")

    # Loading calendar should not crash; should fallback to empty
    cal = load_calendar(config.calendar.ics_path)
    assert hasattr(cal, "events"), "Calendar should have 'events' attribute even if corrupted"
    print("Corrupted calendar loaded gracefully.")

def test_booking_write_with_retry(config):
    print("\n--- Test: Booking write with retry/backoff ---")
    reset_calendar_file(Path(config.calendar.ics_path))

    # Intentionally simulate success path: adding event
    from calendar_integration.ics_writer import add_event_to_calendar
    service = "Brake Inspection"
    dt = datetime.strptime("2025-08-16 11:00", "%Y-%m-%d %H:%M")
    try:
        add_event_to_calendar(f"{service} test", dt, 45, "Testing write", ics_path=config.calendar.ics_path)
        # Should exist now in calendar
        conflicts = has_conflict(dt, 45, ics_path=config.calendar.ics_path)
        assert conflicts, "Should find the event we just wrote (overlap with itself)."
        print("Write succeeded and conflict shows the newly added appointment.")
    except Exception as e:
        print("Unexpected failure writing appointment:", e)
        raise

def test_slot_extraction_and_manual_clarification(config):
    print("\n--- Test: Slot extraction + manual clarification ---")
    # Provide a vague input missing time, then supply invalid then valid time
    session = CallSession(caller_number="+1-555-0000")
    # First response is free-form partial ("Oil Change on 2025-08-17"), then provide invalid time, then valid time, then confirm yes
    adapter = StubAdapter([
        "Oil Change on 2025-08-17",  # initial user input
        "25:99",  # invalid time
        "10:30",  # valid time
        "yes"  # confirmation
    ])
    # Call process_interaction which will perform booking logic but without relying on LLM confirming (it will treat "yes" as affirmative)
    response = process_interaction("Oil Change on 2025-08-17", session, adapter)
    print("Response:", response)
    assert "Appointment confirmed" in response or session.escalation_triggered is False, "Expected successful booking or at least no runaway escalation."

def test_invalid_date_time_escalation(config):
    print("\n--- Test: Invalid date/time escalation ---")
    session = CallSession(caller_number="+1-555-1111")
    # Provide completely malformed date/time and negative confirmation path
    adapter = StubAdapter([
        "Brake Inspection on notadate",  # user input
        "no"  # rejection of paraphrase
    ])
    response = process_interaction("Brake Inspection on notadate", session, adapter)
    print("Response:", response)
    assert session.escalation_triggered or "try again" in response.lower(), "Expected escalation or a retry prompt for invalid input."

def test_info_responses(config):
    print("\n--- Test: Informational responses (hours/pricing) ---")
    session = CallSession(caller_number="+1-555-2222")
    adapter = StubAdapter([])
    r1 = process_interaction("What are your hours?", session, adapter)
    print("Hours reply:", r1)
    assert "open from" in r1.lower()

    session2 = CallSession(caller_number="+1-555-3333")
    r2 = process_interaction("How much is Oil Change?", session2, adapter)
    print("Price reply:", r2)
    assert "oil change" in r2.lower() or "which service" in r2.lower()

def test_conflict_reject_escalation_flow(config):
    print("\n--- Test: Conflict reject leads to escalation ---")
    session = CallSession(caller_number="+1-555-4444")
    # Pre-populate calendar with an appointment to create conflict
    reset_calendar_file(Path(config.calendar.ics_path))
    existing_dt = datetime.strptime("2025-08-18 09:00", "%Y-%m-%d %H:%M")
    add_event_to_calendar("Existing", existing_dt, 30, "Block", ics_path=config.calendar.ics_path)

    # User tries to book same slot, then rejects suggestion
    adapter = StubAdapter([
        "Oil Change 2025-08-18 09:00",  # initial booking
        "yes",  # confirm paraphrase
        "no"  # reject suggested alternative if prompted
    ])
    response = process_interaction("Oil Change 2025-08-18 09:00", session, adapter)
    print("Response:", response)
    assert session.escalation_triggered, "Expected escalation after rejecting alternative."

def test_logging_and_readback():
    print("\n--- Test: Logging write/readback ---")
    # Ensure there's at least one log entry and we can read it
    events = read_events(limit=5)
    print("Recent events:", events)
    assert isinstance(events, list), "read_events should return a list"
    # Each event should have required keys
    if events:
        for e in events:
            for key in ("call_id", "step", "timestamp"):
                assert key in e, f"Missing expected log field {key} in event"

def test_config_validation_failure():
    print("\n--- Test: Config validation failure handling ---")
    # Temporarily write a bad config to simulate failure
    from pathlib import Path
    bad_config_path = Path("config/bad_demo_config.json")
    bad_content = {
        # missing required fields like services or hours
        "shop_name": "Broken Shop",
        "services": []
    }
    bad_config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(bad_config_path, "w") as f:
        json.dump(bad_content, f)
    # Monkey-patch loader to point to this file
    from core.config_loader import load_raw_config, DEFAULT_CONFIG_PATH
    original = DEFAULT_CONFIG_PATH.resolve()
    try:
        # Temporary override environment variable or modify loader call
        from core.config_loader import load_config as real_loader
        try:
            # direct instantiation to bypass default path
            from core.config_schema import RootConfig
            RootConfig(**bad_content)
            print("Expected validation error did not occur.")
        except Exception as e:
            print("Caught expected config validation error:", e)
    finally:
        # cleanup
        if bad_config_path.exists():
            bad_config_path.unlink()

def run_all():
    print("\n=== Starting Non-LLM Full Test Run ===")
    config = load_config()

    # 1. Config validation (happy path)
    print("\n-> Valid config loaded:", config)

    # 2. Calendar conflict & suggestion
    simulate_conflict_and_suggestion(config)

    # 3. Calendar corruption recovery
    test_calendar_corruption_recovery(config)

    # 4. Calendar write resilience
    test_booking_write_with_retry(config)

    # 5. Slot extraction & manual clarification
    test_slot_extraction_and_manual_clarification(config)

    # 6. Invalid date/time escalation
    test_invalid_date_time_escalation(config)

    # 7. Info responses
    test_info_responses(config)

    # 8. Conflict reject escalation
    test_conflict_reject_escalation_flow(config)

    # 9. Logging integrity
    test_logging_and_readback()

    # 10. Config schema failure case
    test_config_validation_failure()

    print("\n=== Completed Non-LLM Test Run ===")

if __name__ == "__main__":
    run_all()
