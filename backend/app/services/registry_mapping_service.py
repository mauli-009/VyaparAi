from rapidfuzz import fuzz
from app.repositories.semantic_registry_repo import (
    get_all_registry,
    find_by_alias,
    find_by_key,
    insert_registry_entry,
    add_alias_to_key
)
from app.services.llm_service import call_llm
import pandas as pd
import re


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
FUZZY_THRESHOLD = 75   # token_sort_ratio score to accept a fuzzy match


# ─────────────────────────────────────────────
# Normalize
# "product_name" / "Product Name" / "product-name" → "product name"
# ─────────────────────────────────────────────
def normalize(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


# ─────────────────────────────────────────────
# Step 1 — Exact alias match
# Fastest path. Hits if column was seen before.
# ─────────────────────────────────────────────
def exact_match(column_name: str):
    entry = find_by_alias(normalize(column_name))
    if entry:
        return entry["key"]
    return None


# ─────────────────────────────────────────────
# Step 2 — Fuzzy match
# Scores against BOTH aliases AND the key itself.
# Scoring against the key is a safety net for sparse registry entries
# that have very few aliases yet — the key name is often the best
# descriptive string to match against in that case.
# e.g. new entry "battery_capacity" with only 1 alias:
#      "bat cap" vs alias "battery capacity" → 58 ❌
#      "bat cap" vs key   "battery capacity" → 58 (same, but ensures it's checked)
# ─────────────────────────────────────────────
def fuzzy_match(column_name: str, registry: list):
    best_score = 0
    best_key = None

    for entry in registry:
        key = entry["key"]
        normalized_col = normalize(column_name)

        # score against the key itself first (safety net for sparse entries)
        key_score = fuzz.token_sort_ratio(normalized_col, normalize(key))
        if key_score > best_score:
            best_score = key_score
            best_key = key

        # score against every alias
        for alias in entry.get("aliases", []):
            score = fuzz.token_sort_ratio(normalized_col, normalize(alias))
            if score > best_score:
                best_score = score
                best_key = key

    if best_score >= FUZZY_THRESHOLD:
        return best_key, best_score

    return None, best_score


# ─────────────────────────────────────────────
# Top unique candidate keys for LLM context
# Scores against BOTH key and aliases, deduped per key
# ─────────────────────────────────────────────
def get_top_candidates(column_name: str, registry: list) -> list:
    scores = {}  # key → best score across key name + all aliases

    for entry in registry:
        key = entry["key"]
        normalized_col = normalize(column_name)

        # score against the key itself
        key_score = fuzz.token_sort_ratio(normalized_col, normalize(key))
        scores[key] = key_score

        # score against every alias, keep highest
        for alias in entry.get("aliases", []):
            score = fuzz.token_sort_ratio(normalized_col, normalize(alias))
            if score > scores[key]:
                scores[key] = score

    sorted_keys = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [k for k, _ in sorted_keys[:5]]


# ─────────────────────────────────────────────
# Data type inference
# ─────────────────────────────────────────────
def infer_data_type(series: pd.Series) -> str:
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    # detect date-like strings
    sample = series.dropna().astype(str).head(10).tolist()
    for val in sample:
        if re.search(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}", val):
            return "date"
    return "categorical"


# ─────────────────────────────────────────────
# Step 3 — LLM disambiguation
#
# KEY DESIGN: sample values are the primary signal.
# The LLM sees actual data (e.g. ["Portronics Konnect", "boAt Rockerz"])
# so it can correctly resolve ambiguous/abbreviated column names
# WITHOUT any hardcoded abbreviation maps.
#
# e.g. column "pr_name" with values ["Portronics Konnect", "boAt Rockerz"]
#      → LLM correctly returns {"key": "product_name"}
# ─────────────────────────────────────────────
def llm_disambiguation(
    column_name: str,
    preview_values: list,
    candidates: list,
    data_type: str,
    all_keys: list
):
    prompt = f"""
You are a dataset schema analyst. Your job is to map a raw CSV column to the correct semantic key.

COLUMN NAME: "{column_name}"
DATA TYPE: {data_type}
SAMPLE VALUES (most important signal — use these to understand what the column actually contains):
{preview_values[:8]}

TOP FUZZY CANDIDATE KEYS (use as a starting point):
{candidates}

ALL AVAILABLE SEMANTIC KEYS (use if candidates don't fit):
{all_keys}

INSTRUCTIONS:
- The sample values are your most important clue. Use them first.
- If sample values look like product/item names → pick "product_name"
- If sample values look like descriptions/long text → pick "product_description"
- If sample values look like prices (numbers) → pick "discounted_price_numeric" or "actual_price_numeric"
- If sample values look like dates → pick "transaction_date"
- If sample values look like category names → pick "category"
- If sample values look like usernames/people names → pick "user_name"
- If sample values look like IDs/codes → pick "user_id" or "product_id"
- If sample values look like review/feedback text → pick "review_text"
- If sample values look like URLs/links → pick "product_link"
- Only use "create_new" if the column represents something genuinely not covered
  by ANY key in the full keys list above.

Return JSON only. No markdown. No explanation.

Option 1 — map to existing key:
{{"key": "<existing_key_from_all_keys>"}}

Option 2 — create new key (only if truly nothing fits):
{{"action": "create_new", "key": "<snake_case_key>", "description": "<one sentence describing what this column represents>", "data_type": "numeric | categorical | date"}}
"""

    return call_llm(prompt)


# ─────────────────────────────────────────────
# Safe insert — prevents duplicate keys
# If key already exists → just add new alias
# If key is new → create full entry
# ─────────────────────────────────────────────
def safe_insert(new_key: str, column_name: str, description: str, data_type: str):
    existing = find_by_key(new_key)
    if existing:
        add_alias_to_key(new_key, normalize(column_name))
    else:
        insert_registry_entry(
            key=new_key,
            aliases=[normalize(column_name)],
            description=description,
            data_type=data_type
        )


# ─────────────────────────────────────────────
# Main mapping pipeline
#
# For each column:
#   1. Exact match   → free, instant, deterministic
#   2. Fuzzy match   → free, handles small variations
#   3. LLM           → handles abbreviations + semantics using sample values
#
# Feedback loop: every successful match saves the column as an alias
# so the next dataset with the same column hits exact match instantly.
# ─────────────────────────────────────────────
def generate_mapping(df: pd.DataFrame) -> dict:

    mapping = {}
    registry = get_all_registry()
    all_keys = list({entry["key"] for entry in registry})

    for column in df.columns:

        # ── Step 1: Exact alias match ──────────────────────────────────
        key = exact_match(column)
        if key:
            mapping[column] = key
            continue

        # ── Step 2: Fuzzy match ────────────────────────────────────────
        key, best_score = fuzzy_match(column, registry)
        if key:
            mapping[column] = key
            # Feedback loop — save alias so next time hits Step 1
            add_alias_to_key(key, normalize(column))
            continue

        # ── Step 3: LLM with sample values ────────────────────────────
        preview_values = df[column].dropna().tolist()
        data_type = infer_data_type(df[column])
        candidate_keys = get_top_candidates(column, registry)

        response = llm_disambiguation(
            column_name=column,
            preview_values=preview_values,
            candidates=candidate_keys,
            data_type=data_type,
            all_keys=all_keys
        )

        if not isinstance(response, dict):
            # LLM returned garbage — use best fuzzy candidate
            mapping[column] = candidate_keys[0] if candidate_keys else "unknown"
            continue

        # LLM picked an existing key
        if "key" in response:
            chosen_key = response["key"]

            if chosen_key in all_keys:
                mapping[column] = chosen_key
                # Feedback loop — save alias so next time hits Step 1
                add_alias_to_key(chosen_key, normalize(column))
            else:
                # LLM hallucinated a key that doesn't exist
                # Fall back to best fuzzy candidate
                mapping[column] = candidate_keys[0] if candidate_keys else "unknown"

        # LLM wants to create a brand new key
        elif response.get("action") == "create_new":
            new_key = normalize(response.get("key", column)).replace(" ", "_")
            description = response.get("description", "")
            inferred_type = response.get("data_type", data_type)

            safe_insert(new_key, column, description, inferred_type)
            mapping[column] = new_key

            # Update local state so later columns in this same CSV
            # can match against this newly created key without a DB round trip
            all_keys.append(new_key)
            registry.append({"key": new_key, "aliases": [normalize(column)]})

        else:
            mapping[column] = candidate_keys[0] if candidate_keys else "unknown"

    return mapping