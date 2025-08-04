#!/usr/bin/env python3
import os
import sys
import shutil
import tempfile
import re
from pathlib import Path

# 1) Isolate DATA_DIR in a fresh temp dir
TEST_DATA = tempfile.mkdtemp(prefix="llm_test_")
os.environ["DATA_DIR"] = TEST_DATA

# 2) Dummy API key
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
    """Mimic OpenAI .chat.completions.create response."""
    def __init__(self, text, pt=1, ct=1):
        self.choices = [
            type("Choice", (), {"message": type("Msg", (), {"content": text})()})
        ]
        self.usage = {"prompt_tokens": pt, "completion_tokens": ct}

class PatternAdapter:
    def __init__(self, patterns):
        self.patterns = [(re.compile(p), fn) for p, fn in patterns]
    def prompt(self, text): pass
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

    # stub quota logic
    import utils.usage_guard as UG
    UG.can_call_model = lambda: True
    A.can_call_model  = lambda: True

    # 1) LLM_CONFIRM: YES / NO
    print_header("LLM_CONFIRM: YES / NO")
    for reply, expect in [("Yes, please", True), ("No, thanks", False)]:
        A.client.chat.completions.create = lambda **k: FakeResponse(reply, pt=2, ct=3)
        sess = CallSession("+111")
        res = llm_confirm("Confirm booking", sess)
        print(f"Reply='{reply}' → {res}")
        assert_true(res is expect, f"Expected {expect}")

    # 2) LLM_CONFIRM: UNCLEAR
    print_header("LLM_CONFIRM: UNCLEAR")
    A.client.chat.completions.create = lambda **k: FakeResponse("Maybe", pt=1, ct=1)
    assert_true(llm_confirm("Confirm booking", CallSession("+222")) is None,
                "Expected None")

    # 3) LLM_CONFIRM: USAGE LIMIT
    print_header("LLM_CONFIRM: USAGE LIMIT")
    UG.can_call_model = lambda: False
    A.can_call_model  = lambda: False
    try:
        llm_confirm("Confirm booking", CallSession("+333"))
        raise AssertionError("Expected UsageLimitError")
    except UsageLimitError:
        print("Caught UsageLimitError")

    # restore
    UG.can_call_model = lambda: True
    A.can_call_model  = lambda: True

    # 4) LLM_CONFIRM: API ERROR
    print_header("LLM_CONFIRM: API ERROR")
    def raise_err(**k): raise RuntimeError("API down")
    A.client.chat.completions.create = raise_err
    try:
        llm_confirm("Confirm booking", CallSession("+444"))
        raise AssertionError("Expected RuntimeError")
    except RuntimeError as e:
        print("Caught RuntimeError:", e)

    # 5) PROCESS_INTERACTION: ambiguous → LLM YES → booking
    print_header("PROCESS_INTERACTION: YES → BOOKING")
    A.client.chat.completions.create = lambda **k: FakeResponse("Yes", pt=1, ct=2)
    adapter = PatternAdapter([(r"Would you like", lambda: "no")])
    resp = process_interaction(
        "I want to book Oil Change on 2025-08-25 at 11:00",
        CallSession("+555"), adapter
    )
    print("Resp:", resp)
    assert_true("✅ Appointment confirmed" in resp,
                "Expected booking confirmation")

    # 6) PROCESS_INTERACTION: LLM NO → retry
    print_header("PROCESS_INTERACTION: NO → RETRY")
    A.client.chat.completions.create = lambda **k: FakeResponse("No", pt=1, ct=1)
    resp = process_interaction(
        "I want to book Oil Change on 2025-08-26 at 12:00",
        CallSession("+666"), adapter
    )
    print("Resp:", resp)
    assert_true("Okay, let's try again." in resp,
                "Expected retry")

    # 7) PROCESS_INTERACTION: UNCLEAR → escalation
    print_header("PROCESS_INTERACTION: UNCLEAR → ESCALATE")
    A.client.chat.completions.create = lambda **k: FakeResponse("Hmm", pt=1, ct=1)
    resp = process_interaction(
        "I want to book Oil Change on 2025-08-27 at 13:00",
        CallSession("+777"), adapter
    )
    print("Resp:", resp)
    assert_true(escalation_message() in resp,
                "Expected escalation")

    print("\n✅ ALL LLM TESTS PASSED ✅\n")

if __name__ == "__main__":
    run_all()
