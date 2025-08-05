#!/usr/bin/env python3
import os
import sys
import tempfile
import re
from pathlib import Path

# 1) (Optional) isolate data in a fresh temp dir
# import shutil
# TEST_DATA = tempfile.mkdtemp(prefix="llm_test_")
# os.environ["DATA_DIR"] = str(TEST_DATA)

# 2) Dummy API key for load_env_variables()
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# 3) Make project importable
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

import assistant.assistant as A
from assistant.assistant import llm_confirm, process_interaction, UsageLimitError
from assistant.session import CallSession
from assistant.escalation import escalation_message

# --- Helpers ---

class FakeResponse:
    """Mimic an OpenAI chat completion response."""
    def __init__(self, text, pt=1, ct=1):
        self.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": text})()})
        ]
        self.usage = {"prompt_tokens": pt, "completion_tokens": ct}

class PatternAdapter:
    """
    Fake io_adapter for process_interaction:
     - prompt(text): no-op
     - collect(prompt_text): return fn() for first matching regex
    """
    def __init__(self, patterns):
        self.patterns = [(re.compile(p), fn) for p, fn in patterns]
    def prompt(self, text):
        pass
    def collect(self, prompt_text):
        for pat, fn in self.patterns:
            if pat.search(prompt_text):
                return fn()
        return ""

def print_header(title: str):
    print(f"\n---- {title} ----\n")

def assert_true(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)

# --- Runner ---

def run_all():
    print("\n=== Starting LLM-Flow Tests ===\n")

    # Ensure token quota logic sees unlimited
    import utils.usage_guard as UG
    UG.can_call_model = lambda: True
    A.can_call_model  = lambda: True

    # --- Test 1: llm_confirm YES / NO ---
    print_header("LLM_CONFIRM: YES / NO")
    for reply, expect in [("Yes, please", True), ("No, thanks", False)]:
        A.client.chat.completions.create = lambda **k: FakeResponse(reply, pt=2, ct=3)
        sess = CallSession("+111")
        res = llm_confirm("Confirm booking", sess)
        print(f"Reply='{reply}' -> {res}")
        assert_true(res is expect, f"Expected {expect} for '{reply}'")

    # --- Test 2: llm_confirm UNCLEAR ---
    print_header("LLM_CONFIRM: UNCLEAR")
    A.client.chat.completions.create = lambda **k: FakeResponse("Maybe", pt=1, ct=1)
    res = llm_confirm("Confirm booking", CallSession("+222"))
    print(f"Reply='Maybe' -> {res}")
    assert_true(res is None, "Expected None for unclear reply")

    # --- Test 3: llm_confirm USAGE LIMIT ---
    print_header("LLM_CONFIRM: USAGE LIMIT")
    UG.can_call_model = lambda: False
    A.can_call_model  = lambda: False
    try:
        llm_confirm("Confirm booking", CallSession("+333"))
        raise AssertionError("Expected UsageLimitError")
    except UsageLimitError:
        print("Caught UsageLimitError as expected")
    # restore
    UG.can_call_model = lambda: True
    A.can_call_model  = lambda: True

    # --- Test 4: llm_confirm API ERROR ---
    print_header("LLM_CONFIRM: API ERROR")
    def raise_err(**k): raise RuntimeError("API down")
    A.client.chat.completions.create = raise_err
    try:
        llm_confirm("Confirm booking", CallSession("+444"))
        raise AssertionError("Expected RuntimeError")
    except RuntimeError as e:
        print("Caught RuntimeError as expected:", e)

    # --- Test 5: PROCESS_INTERACTION: YES -> BOOKING (pre-seed + skip extractor) ---
    print_header("PROCESS_INTERACTION: YES -> BOOKING")
    A.client.chat.completions.create = lambda **k: FakeResponse("Yes", pt=1, ct=2)
    UG.can_call_model = lambda: True
    A.can_call_model  = lambda: True

    # Patch out slot extraction
    A.extract_and_prepare = lambda *args, **kwargs: None

    # Pre-seed session:
    session = CallSession("+555")
    session.update_slot("service", "Oil Change")
    session.update_slot("date",    "2025-08-25")
    session.update_slot("time",    "11:00")

    # Adapter: "yes" to both paraphrase and final prompt
    adapter = PatternAdapter([
        (r"Just to confirm", lambda: "yes"),
        (r"^>",              lambda: "yes"),
    ])

    resp = process_interaction("Book appointment", session, adapter)
    print("process_interaction resp:", resp)
    assert_true("Appointment confirmed" in resp,
                "Expected booking with LLM fallback")

    # --- Test 6: PROCESS_INTERACTION: NO -> RETRY ---
    print_header("PROCESS_INTERACTION: NO -> RETRY")
    A.client.chat.completions.create = lambda **k: FakeResponse("No", pt=1, ct=1)

    A.extract_and_prepare = lambda *args, **kwargs: None
    session = CallSession("+666")
    session.update_slot("service", "Oil Change")
    session.update_slot("date",    "2025-08-26")
    session.update_slot("time",    "12:00")

    adapter = PatternAdapter([
        (r"Just to confirm", lambda: "yes"),
        (r"^>",              lambda: "no"),
    ])
    resp = process_interaction("Book appointment", session, adapter)
    print("process_interaction resp:", resp)
    assert_true("Okay, let's try again." in resp,
                "Expected retry when LLM says No")

    # --- Test 7: PROCESS_INTERACTION: UNCLEAR -> ESCALATION ---
    print_header("PROCESS_INTERACTION: UNCLEAR -> ESCALATION")
    A.client.chat.completions.create = lambda **k: FakeResponse("Hmm", pt=1, ct=1)

    A.extract_and_prepare = lambda *args, **kwargs: None
    session = CallSession("+777")
    session.update_slot("service", "Oil Change")
    session.update_slot("date",    "2025-08-27")
    session.update_slot("time",    "13:00")

    adapter = PatternAdapter([
        (r"Just to confirm", lambda: "yes"),
        (r"^>",              lambda: "maybe"),
    ])
    resp = process_interaction("Book appointment", session, adapter)
    print("process_interaction resp:", resp)
    assert_true(escalation_message() in resp,
                "Expected escalation when LLM unclear")

    print("\n---ALL LLM TESTS PASSED---\n")

if __name__ == "__main__":
    run_all()
