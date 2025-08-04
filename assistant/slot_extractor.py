# assistant/slot_extractor.py

import re
from assistant.session import CallSession
from typing import Tuple, Dict, Any
from datetime import datetime
import difflib

# Helper normalization
def normalize_text(s: str) -> str:
    s = s.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)  # remove punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s

def service_similarity(a: str, b: str) -> float:
    """
    Rough similarity: token subset shortcut, then combination of token overlap and sequence matcher ratio.
    """
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    a_tokens = set(a_norm.split())
    b_tokens = set(b_norm.split())

    # Short-circuit: if service name tokens are subset of user input tokens, high confidence
    if a_tokens and a_tokens.issubset(b_tokens):
        return 1.0

    # Token overlap
    if not a_tokens or not b_tokens:
        token_score = 0.0
    else:
        token_score = len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))

    # Sequence similarity
    seq_score = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()

    # Weighted combination (heavy on token overlap)
    return 0.8 * token_score + 0.2 * seq_score

DATE_REGEX = re.compile(
    r"(?P<year>20\d{2})[-/](?P<month>0[1-9]|1[0-2])[-/](?P<day>0[1-9]|[12]\d|3[01])"
)
TIME_REGEX = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")  # HH:MM 24h

def extract_service(text: str, config) -> str | None:
    lowered = text.lower()
    best = None
    best_score = 0.0
    for svc in config.services:
        score = service_similarity(svc.name, lowered)
        if score > best_score:
            best_score = score
            best = svc.name
    if best_score >= 0.5:
        return best
    return None

def extract_date(text: str) -> str | None:
    m = DATE_REGEX.search(text)
    if m:
        try:
            y = int(m.group("year"))
            mo = int(m.group("month"))
            d = int(m.group("day"))
            dt = datetime(year=y, month=mo, day=d)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return None
    return None

def extract_time(text: str) -> str | None:
    m = TIME_REGEX.search(text)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"
    return None

def extract_and_prepare(user_input: str, session: CallSession, io_adapter, config) -> Dict[str, Any]:
    extracted = {}

    if not session.state.get("service"):
        svc = extract_service(user_input, config)
        if svc:
            session.update_slot("service", svc)
            session.add_history("extracted_service", input_data=svc)
            extracted["service"] = svc

    if not session.state.get("date"):
        dt = extract_date(user_input)
        if dt:
            session.update_slot("date", dt)
            session.add_history("extracted_date", input_data=dt)
            extracted["date"] = dt

    if not session.state.get("time"):
        tm = extract_time(user_input)
        if tm:
            session.update_slot("time", tm)
            session.add_history("extracted_time", input_data=tm)
            extracted["time"] = tm

    return extracted
