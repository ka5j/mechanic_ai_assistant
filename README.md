# Mechanic AI Assistant (CLI Backend)

**Mechanic AI Assistant** is a fully modular backend system that simulates a professional automotive shop receptionist. It intelligently guides customers through the booking process, answers service-related questions, handles schedule conflicts, and stores appointments in a real calendar file — all via a clean, terminal-based interface. Built with future-proofing in mind, this backend is ready to integrate with phone systems (like Twilio) and real calendar services (like Google Calendar) when desired.

---

## Features

- Intelligent appointment booking via natural conversation
- Supports multiple service categories with customizable durations
- Real-time availability detection using `.ics` calendar files
- Built-in OpenAI assistant for slot-filling and conversation flow
- Escalates to human staff when needed
- Modular I/O layer for CLI, Twilio, or web interfaces
- Logging and cost guard monitoring for production-readiness

---

## Demo (CLI Walkthrough)

```bash
$ python main.py
🔧 AI Receptionist CLI
─────────────────────────────────
👉 New call! Enter customer phone number:
> 4165551234

🤖 Hi there! What’s your name?
> Krish

🤖 Great, Krish! What service do you need today?
> Oil change

🤖 When would you like to book it?
> Tomorrow at 2pm

📅 Checking availability...
⚠️ That time is unavailable. How about:
  - Tomorrow at 3:00 PM
  - Tomorrow at 4:00 PM
> 3:00 PM

✅ Appointment confirmed for Oil Change at 3:00 PM tomorrow.
📆 Added to the shop calendar.
```

---

## 🏗️ Architecture Overview

```
mechanic_ai_assistant/
│
├── main.py                     # Entry point for the assistant CLI
├── assistant/                  # Orchestrates LLM-based conversation logic
│
├── core/                       # Business logic
│
├── io_adapters/                # Interface layer (CLI for now, Twilio-ready)
│
├── calendar_integration/       # Read/write calendar logic via .ics files
│
├── config/                     # System and business configuration
│
├── secrets/                    # Stores environment variables (excluded from repo)
│
├── data/                       # Persistent calendar data (appointments.ics)
│
├── test/                       # Unit tests and simulation utilities
│
├── requirements.txt            # Python dependencies
└── README.md                   # You're here!
```

---

## ⚙️ Setup Instructions

### 1. Clone the repo

### 4. Run the CLI assistant

```bash
python main.py
```

---

## 📅 Calendar Integration

Appointments are stored in a local `.ics` file (`appointments.ics`) using iCalendar format. This allows easy viewing in apps like:

- Google Calendar (import `.ics`)
- Outlook
- Apple Calendar

📌 The assistant automatically:
- Checks for overlapping bookings
- Suggests next available time slots
- Honors configurable business hours

---

## 🤖 AI Assistant Capabilities

The assistant uses OpenAI's GPT API under the hood to:

- Interpret vague user input (e.g., "next Friday around 4")
- Extract intent and fill required booking fields
- Re-prompt or escalate when information is missing
- Maintain natural dialogue throughout the session

You can customize:
- Business hours
- Available services and durations
- LLM prompt behavior
- Escalation conditions

---

## 🧩 Extensibility

This backend is built to support:

| Feature              | Status      | Description                                                  |
|----------------------|-------------|--------------------------------------------------------------|
| CLI I/O              | ✅ Complete | Fully working demo environment                               |
| Twilio voice/SMS     | 🔜 Planned  | Drop-in adapter coming soon                                  |
| Google Calendar Sync | 🔜 Planned  | Swap .ics file for real cloud calendar integration           |
| WebSocket/Chat       | Optional    | Can easily be added via `io_adapters` abstraction            |

All future interfaces will use the same core logic — no duplication or branching logic.

---

## 🧪 Testing

Run unit tests with:

```bash
pytest
```

> 💡 You are encouraged to add more test cases for slot filling, conflict resolution, and calendar write failures.

---

## 📈 Logging and Monitoring

- Key actions are logged to stdout
- Escalation events and LLM usage are tracked
- A **cost guard** monitors excessive API usage and prevents runaway billing

---

## 🚧 Known Limitations

- `.ics` file access is not thread-safe (future versions will address concurrency)
- No input validation for ambiguous user inputs like "next next Tuesday"
- No retry logic for LLM/API failures
- Session state is not persisted if the process is restarted mid-call

---

## 💡 Future Plans

- ✅ Voice integration with Twilio
- ✅ Google Calendar adapter (real-time sync)
- ✅ Booking confirmation via SMS
- ✅ Dynamic service pricing and durations
- ✅ Persistent session handling
- ✅ Web dashboard for admins

---

## 🧠 Built With

- 🧠 OpenAI GPT-3.5 (LLM assistant)
- 🕘 `ics` Python package for calendar handling
- 🧪 `pytest` for testing
- 🛠️ Built from scratch in pure Python with clean architecture

---

## 🧑‍💻 Author

**Krish Ahuja**  
Built as a foundation for a production-grade AI receptionist for mechanic shops and service-based businesses.

---

## 📜 License

This project is under the MIT License — feel free to fork, modify, and extend as needed.
