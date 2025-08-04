#!/usr/bin/env python3
import os
import sys
import shutil
import re
from pathlib import Path
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

# 1) Ensure OPENAI key present (though we won’t call OpenAI here)
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# 2) Make project root importable
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

# 3) Imports from your application
from assistant.assistant import process_interaction
from assistant.session   import CallSession
from assistant.escalation import escalation_message
from calendar_integration.ics_writer import (
    add_event_to_calendar,
    has_conflict,
    suggest_next_slot,
    load_calendar,
)
from utils.structured_logger import read_events

# --- Helpers ---

class PatternAdapter:
    """
    Mocks the io_adapter interface:
      - prompt(text) is ignored,
      - collect(prompt_text) returns canned answers based on regex patterns.
    """
    def __init__(self, patterns):
        # patterns: list of (regex_pattern, fn_returning_answer)
        self.patterns = [(re.compile(p), fn) for p, fn in patterns]

    def prompt(self, text):
        pass

    def collect(self, prompt_text):
        for pat, fn in self.patterns:
            if pat.search(prompt_text):
                return fn()
        return ""

def wipe_data(root: Path):
    """
    Delete the entire `data/` directory so production code can re-create it.
    """
    data_dir = root / "data"
    if data_dir.exists():
        shutil.rmtree(data_dir)

def print_header(title: str):
    print(f"\n---- {title} ----\n")

def assert_true(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)

# --- Test cases ---

def test_config_loading(config):
    print_header("Config loading & normalization")
    print("Loaded config:", config)
    assert_true(bool(config.services), "services must be defined")
    assert_true(hasattr(config.hours, "open"), "hours.open missing")
    assert_true(hasattr(config.hours, "close"), "hours.close missing")

def test_calendar_conflict_and_suggestion(config):
    print_header("Calendar conflict & suggestion")
    base = datetime(2025,8,15,10,0, tzinfo=ZoneInfo("America/Toronto"))
    add_event_to_calendar("EXIST", base, 30, "BLOCK", ics_path=config.calendar.ics_path)
    conflicts = has_conflict(base, 30, ics_path=config.calendar.ics_path)
    print("Conflicts:", conflicts)
    assert_true(conflicts, "Expected a conflict")
    suggestion = suggest_next_slot(
        base, 30,
        ics_path=config.calendar.ics_path,
        business_start=dtime(*map(int, config.hours.open.split(":"))),
        business_end  =dtime(*map(int, config.hours.close.split(":"))),
        interval_minutes=config.booking_slots.interval_minutes,
        max_lookahead_days=7
    )
    print("Suggestion:", suggestion)
    assert_true(suggestion and suggestion != base, "Bad suggestion")

def test_calendar_corruption_and_recovery(config):
    print_header("Calendar corruption & recovery")
    ics = config.calendar.ics_path
    # write garbage
    ics.write_text("NOT A VALID ICS")
    # load_calendar should not throw
    load_calendar(ics)
    # and has_conflict should return False
    ok = not has_conflict(
        datetime(2025,8,15,10,0, tzinfo=ZoneInfo("America/Toronto")),
        30,
        ics_path=ics
    )
    print("No conflict on corrupt:", ok)
    assert_true(ok, "Expected no conflict on corrupted file")

def test_calendar_write_resilience(config):
    print_header("Calendar write resilience")
    base = datetime(2025,8,16,11,0, tzinfo=ZoneInfo("America/Toronto"))
    add_event_to_calendar("A", base, 30, "D", ics_path=config.calendar.ics_path)
    add_event_to_calendar("B", base, 30, "D", ics_path=config.calendar.ics_path)
    print("Double-write succeeded")

def test_booking_flow_seeded_slots(config):
    print_header("Booking flow (seeded slots) + confirm")
    import assistant.assistant as A

    # 1) Patch calendar path
    A.config.calendar.ics_path = config.calendar.ics_path

    # 2) Seed the session with all required slots
    session = CallSession("+1555000001")
    session.update_slot("service", "Brake Inspection")
    session.update_slot("date",    "2025-08-19")
    session.update_slot("time",    "14:00")

    # 3) Adapter: answer “yes” both to the paraphrase and to the "> " prompt
    adapter = PatternAdapter([
        (r"Just to confirm", lambda: "yes"),  # for paraphrase prompt
        (r"^>",               lambda: "yes"),  # for the "> " confirmation collect
    ])

    # 4) Use any booking keyword to enter the booking path
    user_input = "I want to book Brake Inspection on 2025-08-19 at 14:00"
    resp = process_interaction(user_input, session, adapter)

    print("Response:", resp)
    assert_true(
        "✅ Appointment confirmed" in resp,
        f"Expected booking confirmation, got: {resp}"
    )

    # 5) Finally, verify that the .ics calendar now holds the event
    from datetime import datetime
    from zoneinfo import ZoneInfo

    dt = datetime(2025, 8, 19, 14, 0, tzinfo=ZoneInfo("America/Toronto"))
    assert_true(
        has_conflict(dt, 30, ics_path=config.calendar.ics_path),
        "Calendar event not written"
    )



def test_conflict_accept_suggestion(config):
    print_header("Conflict then accept suggestion")
    # inline imports needed only for this test
    import assistant.assistant as A
    from calendar_integration.ics_writer import add_event_to_calendar, has_conflict
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    # 1) Patch calendar path
    A.config.calendar.ics_path = config.calendar.ics_path

    # 2) Prevent re-extraction of slots (we’ve pre-seeded them)
    A.extract_and_prepare = lambda *args, **kwargs: None

    # 3) Seed an existing event at 10:00
    base = datetime(2025, 8, 20, 10, 0, tzinfo=ZoneInfo("America/Toronto"))
    add_event_to_calendar("EXIST", base, 30, "BLOCK", ics_path=config.calendar.ics_path)

    # 4) Pre-seed the session with the conflicting slot
    session = CallSession("+1555000002")
    session.update_slot("service", "Oil Change")
    session.update_slot("date",    "2025-08-20")
    session.update_slot("time",    "10:00")

    # 5) Adapter answers “yes” to both paraphrase, suggestion, and final "> " prompt
    adapter = PatternAdapter([
        (r"Just to confirm",            lambda: "yes"),
        (r"The next available slot is", lambda: "yes"),
        (r"^>",                         lambda: "yes"),
    ])

    # 6) Use any booking-keyword input
    resp = process_interaction("Book appointment", session, adapter)
    print("Response:", resp)

    # 7) Assert the booking confirmation came through
    assert_true(
        "✅ Appointment confirmed" in resp,
        f"Suggestion acceptance failed, got: {resp}"
    )

    # 8) Finally, verify the new (10:30) slot is in the calendar
    alt = base + timedelta(minutes=config.booking_slots.interval_minutes)
    conflict = has_conflict(alt, 30, ics_path=config.calendar.ics_path)
    assert_true(
        conflict,
        f"Alternate slot {alt} was not added"
    )



def test_conflict_reject_suggestion(config):
    print_header("Conflict then reject suggestion => escalate")
    import assistant.assistant as A
    from calendar_integration.ics_writer import add_event_to_calendar, has_conflict
    from assistant.escalation import escalation_message
    from assistant.session import CallSession
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    # 1) Patch calendar path
    A.config.calendar.ics_path = config.calendar.ics_path

    # 2) Prevent re‐extraction (we seed slots manually)
    A.extract_and_prepare = lambda *args, **kwargs: None

    # 3) Seed an existing 9:00 event
    base = datetime(2025, 8, 21, 9, 0, tzinfo=ZoneInfo("America/Toronto"))
    add_event_to_calendar("EXIST", base, 30, "BLOCK", ics_path=config.calendar.ics_path)

    # 4) Pre‐seed session with conflicting slot
    session = CallSession("+1555000003")
    session.update_slot("service", "Oil Change")
    session.update_slot("date",    "2025-08-21")
    session.update_slot("time",    "09:00")

    # 5) Adapter: confirm paraphrase, then reject suggestion
    adapter = PatternAdapter([
        (r"Just to confirm",            lambda: "yes"),
        (r"The next available slot is", lambda: "no"),
    ])

    # 6) Kick off booking
    resp = process_interaction("Book appointment for Oil Change on 2025-08-21 at 09:00",
                               session, adapter)
    print("Response:", resp)

    # 7) It should escalate
    assert_true(
        escalation_message() in resp,
        f"Expected escalation on reject, got: {resp}"
    )


def test_fuzzy_service_extraction(config):
    print_header("Fuzzy/multi-word service extraction")
    import assistant.assistant as A
    from calendar_integration.ics_writer import has_conflict
    from assistant.session import CallSession
    from datetime import datetime
    from zoneinfo import ZoneInfo

    # 1) Patch calendar path
    A.config.calendar.ics_path = config.calendar.ics_path

    # 2) Prevent extractor from clearing our pre-seeded slots
    A.extract_and_prepare = lambda *args, **kwargs: None

    # 3) Pre-seed session with fuzzy service name
    session = CallSession("+1555000004")
    session.update_slot("service", "Battery Test & Replacement")
    session.update_slot("date",    "2025-08-22")
    session.update_slot("time",    "09:00")

    # 4) Adapter: reply "yes" to paraphrase and final collect
    adapter = PatternAdapter([
        (r"Just to confirm", lambda: "yes"),
        (r"^>",               lambda: "yes"),
    ])

    # 5) Kick off with a booking-intent phrase
    resp = process_interaction(
        "I’d like to book battery test and replacement on 2025-08-22 at 09:00",
        session,
        adapter
    )
    print("Response:", resp)

    # 6) Assert it confirmed
    assert_true(
        "✅ Appointment confirmed" in resp,
        f"Fuzzy extraction failed, got: {resp}"
    )

    # 7) Verify the calendar has that appointment
    dt = datetime(2025, 8, 22, 9, 0, tzinfo=ZoneInfo("America/Toronto"))
    assert_true(
        has_conflict(dt, 30, ics_path=config.calendar.ics_path),
        "Fuzzy-service calendar entry missing"
    )


def test_info_and_offdomain(config):
    print_header("Informational & off-domain fallback")
    session = CallSession("+1555000005")
    adapter = PatternAdapter([])

    hrs = process_interaction("What are your hours?", session, adapter)
    print("Hours:", hrs)
    assert_true("open" in hrs.lower(), "Hours query failed")

    price = process_interaction("How much is Tire Rotation?", session, adapter)
    print("Pricing:", price)
    assert_true("tire rotation" in price.lower(), "Pricing query failed")

    off = process_interaction("Tell me a joke", session, adapter)
    print("Off-domain:", off)
    assert_true("only trained to assist" in off.lower(),
                "Off-domain fallback failed")

def test_logging_content(config):
    print_header("Logging assertions")
    events = read_events()
    print(f"Logged events: {len(events)}")
    assert_true(len(events) >= 1, "Expected at least one log event")

def test_bad_config_schema():
    print_header("Bad config schema rejection")
    from core.config_schema import RootConfig
    try:
        RootConfig(**{"shop_name": "X", "services": []})
        raise AssertionError("Schema should have rejected")
    except Exception as e:
        print("Caught expected error:", e)

# --- Runner ---

def run_all():
    root = PROJECT_ROOT
    # wipe old data
    wipe_data(root)

    # load config once
    import assistant.assistant as A
    config = A.config

    # run tests
    test_config_loading(config)
    test_calendar_conflict_and_suggestion(config)
    test_calendar_corruption_and_recovery(config)
    test_calendar_write_resilience(config)
    test_booking_flow_seeded_slots(config)
    test_conflict_accept_suggestion(config)
    test_conflict_reject_suggestion(config)
    test_fuzzy_service_extraction(config)
    test_info_and_offdomain(config)
    test_logging_content(config)
    test_bad_config_schema()

    print("\n✅ ALL NON-LLM TESTS PASSED ✅\n")

if __name__ == "__main__":
    run_all()
