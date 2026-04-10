from groq import Groq
from dotenv import load_dotenv
import os
import json

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

# Fix: Use a valid Groq-supported model name
MODEL = "openai/gpt-oss-120b"

def call_llm(prompt: str):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "You are a data schema analyst. Return JSON only. No markdown, no explanation, just raw JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON. Raw response: {content!r}. Error: {e}")

def call_llm_text(prompt: str, expect_json: bool = False):
    """
    Call LLM for text or JSON responses.
    Use expect_json=True when the prompt asks for a JSON array/object (e.g. suggestions).
    Use expect_json=False for plain text responses.
    """
    system_msg = (
        "You are a senior business analyst. Return JSON only. No markdown, no explanation."
        if expect_json
        else "You are a senior business analyst. Be concise and data-driven."
    )

    response = client.chat.completions.create(
        model=MODEL,
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