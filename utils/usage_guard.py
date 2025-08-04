# utils/usage_guard.py

import json
from pathlib import Path

USAGE_FILE = Path("data/usage/usage.json")
USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)

# Rough cost assumptions (adjust to current pricing)
COST_PER_1K_TOKENS = 0.002  # example: $0.002 per 1k tokens for gpt-3.5
HARD_LIMIT_DOLLARS = 4.50   # stop before $5

def load_usage():
    if USAGE_FILE.exists():
        with open(USAGE_FILE, "r") as f:
            return json.load(f)
    return {"tokens": 0, "cost": 0.0}

def save_usage(usage):
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)

def can_call_model(additional_tokens=0):
    usage = load_usage()
    projected_tokens = usage["tokens"] + additional_tokens
    projected_cost = projected_tokens / 1000 * COST_PER_1K_TOKENS
    return projected_cost <= HARD_LIMIT_DOLLARS

def record_usage(tokens_used):
    usage = load_usage()
    usage["tokens"] += tokens_used
    usage["cost"] = usage["tokens"] / 1000 * COST_PER_1K_TOKENS
    save_usage(usage)
