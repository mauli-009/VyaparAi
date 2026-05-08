from groq import Groq
from dotenv import load_dotenv
import os
import json
import time

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# llama-3.1-8b-instant  → fast, zero-latency JSON routing & schema tasks
# llama-3.3-70b-versatile → deep reasoning, language generation, suggestions
FAST_ROUTER_MODEL    = "llama-3.1-8b-instant"
# Override via SMART_MODEL env var — lets you swap in openai/gpt-oss-120b or any other model
SMART_STRATEGIST_MODEL = os.getenv("SMART_MODEL", "openai/gpt-oss-120b")


def _strip_fences(content: str) -> str:
    """Remove markdown code fences (```json ... ```) that some models inject."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        # Drop opening fence line
        lines = lines[1:]
        # Drop closing fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
        # Some models write ```json\n{  — strip the word "json" if still present
        if content.lower().startswith("json"):
            content = content[4:].strip()
    return content


def call_llm(prompt: str, model: str = FAST_ROUTER_MODEL, max_retries: int = 2):
    """
    Strict JSON task (intent extraction, schema mapping).
    Returns a parsed Python dict/list. Retries up to max_retries on transient errors.
    """
    last_err: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a data schema analyst. "
                            "Return JSON only. No markdown, no explanation, no commentary. "
                            "Raw JSON that can be passed directly to json.loads()."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )
            raw = response.choices[0].message.content
            content = _strip_fences(raw)
            return json.loads(content)

        except json.JSONDecodeError as e:
            last_err = ValueError(
                f"[LLM] Attempt {attempt + 1}: invalid JSON. "
                f"Raw output: {raw!r}. Error: {e}"
            )
            if attempt < max_retries:
                time.sleep(0.4 * (attempt + 1))

        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))

    raise last_err  # type: ignore[misc]


def call_llm_text(
    prompt: str,
    expect_json: bool = False,
    model: str = SMART_STRATEGIST_MODEL,
    max_retries: int = 2,
):
    """
    Reasoning / language generation task (suggestions, recommendations, translations).
    When expect_json=True behaves like call_llm but on the smart model.
    """
    system_msg = (
        "You are a senior business analyst. "
        "Return JSON only. No markdown, no explanation, no commentary."
        if expect_json
        else (
            "You are a senior business analyst. "
            "Be precise, data-driven, and concise. "
            "Back every claim with numbers from the data."
        )
    )
    last_err: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            raw = response.choices[0].message.content
            content = _strip_fences(raw)

            if expect_json:
                return json.loads(content)
            return content

        except json.JSONDecodeError as e:
            last_err = ValueError(
                f"[LLM_TEXT] Attempt {attempt + 1}: invalid JSON. "
                f"Raw output: {raw!r}. Error: {e}"
            )
            if attempt < max_retries:
                time.sleep(0.4 * (attempt + 1))

        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(1.0 * (attempt + 1))

    raise last_err  # type: ignore[misc]