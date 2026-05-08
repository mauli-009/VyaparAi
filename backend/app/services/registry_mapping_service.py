from rapidfuzz import fuzz
from app.repositories.semantic_registry_repo import (
    get_all_registry,
    find_by_alias,
    find_by_key,
    insert_registry_entry,
    add_alias_to_key
)
from app.services.llm_service import FAST_ROUTER_MODEL, call_llm
import pandas as pd


# High enough to catch abbreviations like "regn"→"region"
# but low enough to avoid false matches between similar columns
SIMILARITY_THRESHOLD = 80

# These generic keys are BANNED from registry
# They caused Total Cost / Total Profit to all map to "revenue"
BANNED_GENERIC_KEYS = {"revenue", "expense", "profit", "loss", "price", "cost", "amount"}


def normalize(text: str):
    return text.lower().strip()


# ---------------------------
# Exact alias match
# ---------------------------
def exact_match(column_name: str):
    alias = normalize(column_name)
    entry = find_by_alias(alias)
    if entry:
        return entry["key"]
    return None


# ---------------------------
# Fuzzy match against aliases
# ---------------------------
def fuzzy_match(column_name: str):
    registry = get_all_registry()
    best_score = 0
    best_key = None

    for entry in registry:
        # Skip banned generic keys during fuzzy match
        if entry.get("key") in BANNED_GENERIC_KEYS:
            continue

        for alias in entry.get("aliases", []):
            score = fuzz.ratio(
                normalize(column_name),
                normalize(alias)
            )
            if score > best_score:
                best_score = score
                best_key = entry["key"]

    if best_score >= SIMILARITY_THRESHOLD:
        return best_key

    return None


# ---------------------------
# Data type inference
# ---------------------------
def infer_data_type(series):
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    return "categorical"


# ---------------------------
# Batch LLM mapping — all columns at once
# ---------------------------
def llm_batch_mapping(columns_info: list) -> dict:
    columns_block = ""
    for item in columns_info:
        columns_block += f"""
  - Column: "{item['column_name']}"
    Type: {item['dtype']}
    Sample values: {item['sample_values'][:5]}
"""

    prompt = f"""
You are a dataset schema analyzer. Map each column to a unique semantic key.

Columns to map:
{columns_block}

STRICT RULES:

1. Every column MUST get a UNIQUE semantic key. No two columns can share the same key.

2. Derive the key directly from the column name using snake_case.
   Examples:
   - "Total Revenue"      → "total_revenue"
   - "Total Cost"         → "total_cost"
   - "Total Profit"       → "total_profit"
   - "Order Date"         → "transaction_date"
   - "Ship Date"          → "ship_date"
   - "Order ID"           → "order_id"
   - "Units Sold"         → "units_sold"
   - "Unit Price"         → "unit_price"
   - "Unit Cost"          → "unit_cost"
   - "Sales Channel"      → "sales_channel"
   - "Order Priority"     → "order_priority"
   - "Item Type"          → "item_type"
   - "Region"             → "region"
   - "Country"            → "country"
   - "Actual Price"       → "actual_price"
   - "Discounted Price"   → "discounted_price"
   - "Rating Count"       → "rating_count"
   - "Review Count"       → "review_count"
   - "Discount Percent"   → "discount_percent"

3. NEVER use generic keys like "revenue", "cost", "profit", "price", "expense", "amount" alone.
   Always use the FULL specific snake_case key from the column name:
   - "Total Revenue" → "total_revenue"   NOT "revenue"
   - "Total Cost"    → "total_cost"      NOT "cost"
   - "Total Profit"  → "total_profit"    NOT "profit"
   - "Unit Price"    → "unit_price"      NOT "price"

4. NEVER append technical suffixes to keys. These are all FORBIDDEN:
   - _numeric, _num, _value, _val, _col, _field, _data, _clean, _processed, _raw
   Example: "Actual Price" → "actual_price" NOT "actual_price_numeric"

5. Exception — use a shorter key ONLY when the column name itself is already generic
   and it's the ONLY column of that type:
   - A column literally named "Revenue" (no prefix) → "revenue" is acceptable
   - A single date column → "transaction_date"

6. NEVER assign the same key to two different columns.

7. Return a flat JSON object. JSON only. No markdown. No explanation.

Example output:
{{
  "Region": "region",
  "Country": "country",
  "Item Type": "item_type",
  "Sales Channel": "sales_channel",
  "Order Priority": "order_priority",
  "Order Date": "transaction_date",
  "Order ID": "order_id",
  "Ship Date": "ship_date",
  "Units Sold": "units_sold",
  "Unit Price": "unit_price",
  "Unit Cost": "unit_cost",
  "Total Revenue": "total_revenue",
  "Total Cost": "total_cost",
  "Total Profit": "total_profit",
  "Actual Price": "actual_price",
  "Discounted Price": "discounted_price"
}}
"""

    return call_llm(prompt, model=FAST_ROUTER_MODEL)


# ---------------------------
# Registry learning
# ---------------------------
def learn(column: str, key: str, series: pd.Series):
    """
    If key already exists in registry → add column name as alias.
    If key does not exist → create a new registry entry.
    Never creates a duplicate document.
    Never stores banned generic keys.
    """
    # Don't pollute registry with generic keys
    if key in BANNED_GENERIC_KEYS:
        return

    alias = normalize(column)
    existing = find_by_key(key)

    if existing:
        # Key exists — add alias if not already present
        if alias not in [a.lower().strip() for a in existing.get("aliases", [])]:
            add_alias_to_key(key, alias)
    else:
        # Brand new key — insert fresh entry
        insert_registry_entry(
            key,
            [alias],
            f"Auto-mapped from column: {column}",
            infer_data_type(series)
        )


# ---------------------------
# Main mapping function
# ---------------------------
def generate_mapping(df: pd.DataFrame):

    used_keys = []
    final_mapping = {}

    # --- Phase 1: exact + fuzzy match from registry (fast, no LLM) ---
    unresolved_columns = []

    for column in df.columns:

        # 1. Exact alias match
        key = exact_match(column)
        if key and key not in used_keys:
            final_mapping[column] = key
            used_keys.append(key)
            learn(column, key, df[column])
            continue

        # 2. Fuzzy match
        key = fuzzy_match(column)
        if key and key not in used_keys:
            final_mapping[column] = key
            used_keys.append(key)
            learn(column, key, df[column])
            continue

        # Could not resolve — send to LLM
        unresolved_columns.append(column)

    # --- Phase 2: batch LLM for unresolved columns only ---
    if unresolved_columns:

        columns_info = [
            {
                "column_name": col,
                "sample_values": df[col].dropna().tolist(),
                "dtype": str(df[col].dtype)
            }
            for col in unresolved_columns
        ]

        llm_mapping = llm_batch_mapping(columns_info)

        if not isinstance(llm_mapping, dict):
            llm_mapping = {}

        for column in unresolved_columns:
            key = llm_mapping.get(column)

            # Safety: if LLM gave a duplicate or nothing, fall back to snake_case
            if not key or key in used_keys:
                key = normalize(column).replace(" ", "_")
                if key in used_keys:
                    key = f"{key}_{len(used_keys)}"

            final_mapping[column] = key
            used_keys.append(key)

            # Learn: add alias to existing key OR create new entry
            learn(column, key, df[column])

    return final_mapping