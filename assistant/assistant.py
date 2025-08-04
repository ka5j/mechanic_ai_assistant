# assistant/assistant.py

from openai import OpenAI
from utils.call_logger import log_interaction
from core.config_loader import load_env_variables
from utils.usage_guard import can_call_model, record_usage

# Load config & OpenAI client
config = load_env_variables()
client = OpenAI(api_key=config["OPENAI_API_KEY"])

SYSTEM_PROMPT = """
You are a smart, strict, and professional AI receptionist for a mechanic shop.
Only answer questions related to services, prices, timing, appointment booking,
and car-related general info. If someone asks something off-topic, say:
"I'm only trained to assist with mechanic shop-related questions."

Be polite, fast, accurate, and never make up prices or services.
If the question is too complex or uncertain, say:
"I’ll connect you to a human right away."
"""

def get_faq_response(user_input: str, full_config: dict) -> str | None:
    for question, answer in full_config.get("faq", {}).items():
        if user_input.lower().strip() == question.lower().strip():
            return answer
    return None

def get_service_response(user_input: str, full_config: dict) -> str | None:
    services = full_config.get("services", [])
    for service in services:
        if service["name"].lower() in user_input.lower():
            return (
                f"🔧 {service['name']}:\n"
                f"{service['description']}\n"
                f"💵 Price: {service.get('price','N/A')}\n"
                f"⏱ Duration: {service.get('duration_minutes','N/A')} minutes"
            )
    return None

def run_assistant(user_input: str, full_config: dict) -> str:
    """
    First checks for FAQ/service shortcuts; otherwise queries OpenAI with budget guard.
    """
    # 1. FAQ exact match
    faq_resp = get_faq_response(user_input, full_config)
    if faq_resp:
        log_interaction("faq_match", {"input": user_input, "response": faq_resp})
        return faq_resp

    # 2. Service keyword match
    service_resp = get_service_response(user_input, full_config)
    if service_resp:
        log_interaction("service_match", {"input": user_input, "response": service_resp})
        return service_resp

    # 3. OpenAI fallback with usage guard
    estimated_prompt_tokens = len(user_input.split())  # rough proxy
    if not can_call_model(estimated_prompt_tokens):
        msg = "⚠️ Budget limit reached. Cannot process further requests right now."
        log_interaction("usage_blocked", {"input": user_input, "reason": "budget_exceeded"})
        return msg

    try:
        response = client.chat.completions.create(
            model=config["OPENAI_MODEL"],
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.3,
            max_tokens=300
        )

        # Record usage
        usage_info = getattr(response, "usage", None)
        if usage_info:
            prompt_tokens = usage_info.get("prompt_tokens", 0)
            completion_tokens = usage_info.get("completion_tokens", 0)
            total = prompt_tokens + completion_tokens
            record_usage(total)
        else:
            reply_text = response.choices[0].message.content.strip()
            record_usage(len(reply_text.split()))

        reply = response.choices[0].message.content.strip()
        log_interaction("ai_response", {"input": user_input, "response": reply})
        return reply

    except Exception as e:
        error_message = f"⚠️ Assistant error: {str(e)}"
        log_interaction("error", {"input": user_input, "error": str(e)})
        return error_message
