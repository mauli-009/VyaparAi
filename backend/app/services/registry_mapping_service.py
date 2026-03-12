from rapidfuzz import fuzz
from app.repositories.semantic_registry_repo import (
    get_all_registry,
    find_by_alias,
    insert_registry_entry
)
from app.services.llm_service import call_llm
import pandas as pd


SIMILARITY_THRESHOLD = 90


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
# LLM disambiguation
# ---------------------------
def llm_disambiguation(column_name, preview_values, candidates):

    prompt = f"""
    You are a dataset schema analyzer.

    Column name:
    {column_name}

    Sample values:
    {preview_values[:5]}

    Candidate semantic keys:
    {candidates}

    Rules:

    1. If a column represents money/amount/transaction value, map it to "revenue".
    2. If a column represents date/time, map it to "transaction_date".
    3. If a column represents location/area, map it to "region".

    Return JSON only.

    Option 1:
    {{ "key": "<candidate_key>" }}

    Option 2:
    {{
    "action":"create_new",
    "key":"<new_key>",
    "description":"<description>",
    "data_type":"numeric | categorical | date"
    }}
    """ 

    return call_llm(prompt)


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
# Select best candidate keys
# ---------------------------
def get_top_candidates(column_name, registry):

    scores = []

    for entry in registry:

        for alias in entry.get("aliases", []):

            score = fuzz.ratio(
                normalize(column_name),
                normalize(alias)
            )

            scores.append((score, entry["key"]))

    scores.sort(reverse=True)

    # top 5 candidates
    return [key for _, key in scores[:5]]


# ---------------------------
# Main mapping function
# ---------------------------
def generate_mapping(df: pd.DataFrame):

    mapping = {}

    registry = get_all_registry()

    for column in df.columns:

        # 1️⃣ exact match
        key = exact_match(column)

        if key:
            mapping[column] = key
            continue


        # 2️⃣ fuzzy match
        key = fuzzy_match(column)

        if key:
            mapping[column] = key
            continue


        # 3️⃣ LLM reasoning

        preview_values = df[column].dropna().tolist()

        candidate_keys = get_top_candidates(column, registry)

        response = llm_disambiguation(
            column,
            preview_values,
            candidate_keys
        )

        if isinstance(response, dict):

            # LLM selected existing key
            if "key" in response and response["key"] in candidate_keys:

                mapping[column] = response["key"]

            # LLM creates new key
            elif response.get("action") == "create_new":

                new_key = normalize(response.get("key", column))

                description = response.get("description", "")

                data_type = response.get(
                    "data_type",
                    infer_data_type(df[column])
                )

                insert_registry_entry(
                    new_key,
                    [normalize(column)],
                    description,
                    data_type
                )

                mapping[column] = new_key

            else:

                mapping[column] = "unknown"

        else:

            mapping[column] = "unknown"

    return mapping