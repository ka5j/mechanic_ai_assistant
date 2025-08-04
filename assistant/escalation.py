# assistant/escalation.py

from utils.structured_logger import log_event

def escalation_message():
    return "I'm having trouble completing that booking. I can transfer you to a human staff member for help."

def mark_and_log(session, reason: str, extra: dict = None):
    """
    Marks session as escalated and logs the reason.
    """
    session.escalation_triggered = True
    payload = {"reason": reason}
    if extra:
        payload.update(extra)
    log_event(session.call_id, "escalation", extra=payload)
