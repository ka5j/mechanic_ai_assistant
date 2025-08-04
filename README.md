# AI Mechanic Receptionist Backend

A production-grade, backend-first AI receptionist tailored for a local mechanic shop.  
It handles appointment booking (service, date, time), availability/conflict resolution, concise clarification, and escalation to human staff when needed. Designed to be modular, cost-aware, auditable, and easily extensible (e.g., future telephony integration).

---

## 🚀 Features

- **Free-form slot extraction + clarification**: Extracts service, date (YYYY-MM-DD), and time (HH:MM 24h) from user input; asks only for missing or ambiguous pieces.  
- **Booking with conflict detection**: Timezone-aware (America/Toronto) calendar integration (.ics) that detects overlaps and suggests the next available slot.  
- **Confirmation flow**: Echoes back interpreted booking for affirmation before finalizing.  
- **Unified escalation**: Consistent behavior when input can’t be resolved — flags the session and surfaces a human handoff message.  
- **Structured session management**: `CallSession` encapsulates call state, collected slots, history, and escalation flag.  
- **Structured logging**: Event-level logs of every decision, input, output, and error.  
- **Deterministic info responses**: Handles common queries like hours and pricing without unnecessary LLM calls.  
- **Prompt engineering built-in**: Bounded system prompt to avoid hallucination, minimal context, clarification policy, and escalation language.  
- **Pluggable I/O via adapter pattern**: Starts with CLI; easily replaceable with telephony/web adapters later.  
- **Test harness support**: Simulate normal, invalid, conflict, and escalation flows.

---

## 🏗️ Architecture Overview

1. **CallSession** — Tracks per-call state, slots (service/date/time), history, and escalation.  
2. **IOAdapter** — Abstracts input/output (e.g., `CLIAdapter` today).  
3. **Slot Extractor** — Deterministically pulls booking info from free-form text and prompts for missing pieces.  
4. **Assistant (LLM + Logic)** — Confirms intent, handles clarification, resolves conflicts, and finalizes bookings.  
5. **Booking Engine / Calendar** — Manages `.ics` calendar, checks conflicts, suggests alternatives, writes appointments.  
6. **Escalation Logic** — Centralized messaging and flagging when flow cannot complete cleanly.  
7. **Structured Logger** — Logs all steps in `data/logs/structured_calls.json` for audit/debug.  

---

##🛠️ Configuration
Edit config/demo_config.json (or provide your own) — key sections:
- **services:** List of services with name, duration_minutes, price, etc.
- **calendar.ics_path:** Path where .ics appointments are stored (default under data/calendar/).
- **booking_slots.interval_minutes:** Granularity for alternative suggestions.
hours.open / hours.close: Business hours for suggestion window.
Escalation and cost guard parameters are inside code and usage guard logic.

---

##📚 Developer Notes
- **Adapters:** Swap CLIAdapter for any input/output medium (HTTP webhook, telephony) without touching core logic.
- **Prompt minimalism:** Only necessary context (missing or confirmed slots + latest utterance) is sent to the model. Full history is retained locally for auditing, not re-sent to reduce cost and drift.
- **Cost guard:** usage_guard prevents runaway OpenAI usage; adjust or extend limits there.
- **Timezone:** All booking logic assumes America/Toronto; internal datetime objects are timezone-aware.