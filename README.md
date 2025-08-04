# AI Mechanic Assistant (Backend)

This is the official backend for a production-grade AI assistant designed for mechanic shops.

### Features:
- Simulates customer calls via CLI
- Modular assistant logic
- Appointment booking with calendar sync
- SMS reminders and data storage
- Full debugging and test mode

## Usage & Budget Guard

To protect your OpenAI credit (e.g., the $5 cap), the assistant includes a simple **usage guard** that tracks approximate token usage locally. It:

- Estimates cost per request and blocks further API calls if you approach the hard threshold (default $4.50).  
- Stores usage in: `data/usage/usage.json`  
- Prevents runaway spend during demos or development.

### Resetting Usage

If you want to reset the tracked usage (e.g., after refilling credit or for a fresh demo), delete or reset the file:

```bash
rm data/usage/usage.json

---

To run:
```bash
python3 main.py
