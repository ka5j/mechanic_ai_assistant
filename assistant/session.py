# assistant/session.py

from datetime import datetime
import uuid

class CallSession:
    def __init__(self, call_id: str | None = None, caller_number: str = "", mode: str = "customer"):
        self.call_id = call_id or str(uuid.uuid4())
        self.caller_number = caller_number
        self.mode = mode  # "customer" or "debug"
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.state = {}  # e.g., {"service": "...", "date": "...", "time": "..."}
        self.history = []  # chronological list of interactions
        self.escalation_triggered = False

    def update_slot(self, key: str, value):
        self.state[key] = value
        self.touch()

    def add_history(self, step: str, input_data=None, output_data=None, extra: dict | None = None):
        entry = {
            "step": step,
            "input": input_data,
            "output": output_data,
            "extra": extra or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.history.append(entry)
        self.touch()

    def touch(self):
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        return {
            "call_id": self.call_id,
            "caller_number": self.caller_number,
            "mode": self.mode,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "state": self.state,
            "history": self.history,
            "escalation_triggered": self.escalation_triggered,
        }
