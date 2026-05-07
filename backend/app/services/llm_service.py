from groq import Groq
from dotenv import load_dotenv
import os
import json

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# Fix: Use a valid Groq-supported model name
FAST_ROUTER_MODEL = "llama-3.1-8b-instant"           # Blazing fast for JSON routing & schema mapping
SMART_STRATEGIST_MODEL = "openai/gpt-oss-120b" # Your heavy-duty model for reasoning & translation

def call_llm(prompt: str, model: str = FAST_ROUTER_MODEL):
    """Used for strict JSON tasks like intent extraction and mapping."""
    response = client.chat.completions.create(
        model=model, # 👈 Use the passed-in model
        messages=[
            {"role": "system", "content": "You are a data schema analyst. Return JSON only. No markdown, no explanation, just raw JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON. Raw response: {content!r}. Error: {e}")


def call_llm_text(prompt: str, expect_json: bool = False, model: str = SMART_STRATEGIST_MODEL):
    """Used for deep reasoning, suggestions, and language translation."""
    system_msg = (
        "You are a senior business analyst. Return JSON only. No markdown, no explanation."
        if expect_json
        else "You are a senior business analyst. Be concise and data-driven."
    )

    response = client.chat.completions.create(
        model=model, # 👈 Use the passed-in model
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    content = response.choices[0].message.content.strip()

    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    if expect_json:
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM did not return valid JSON. Raw: {content!r}. Error: {e}")

    return content