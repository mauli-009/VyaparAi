from app.services.llm_service import call_llm

SUPPORTED_METRICS = ["sum", "avg", "count"]

SUPPORTED_OPERATORS = [
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "greater_or_equal",
    "less_or_equal",
    "between"
]


def extract_intent(question: str, semantic_mapping: dict) -> dict:
    # Get unique semantic fields (not raw column names)
    semantic_fields = list(set(semantic_mapping.values()))

    prompt = f"""
You are an analytics intent extractor.

User question:
"{question}"

Available semantic fields:
{semantic_fields}

Supported metrics:
{SUPPORTED_METRICS}

Supported operators:
{SUPPORTED_OPERATORS}

Convert the user question into structured analytics intent.

Return JSON in this exact structure:

{{
  "metric": "sum | avg | count",
  "field": "<semantic_field>",
  "group_by": "month(transaction_date)" or null,
  "filters": [
    {{
      "field": "<semantic_field>",
      "operator": "<operator>",
      "value": "<value>"
    }}
  ]
}}

RULES:

1. The "field" MUST be one of the available semantic fields.

2. If the user asks for revenue/sales/amount but the dataset only has "price",
choose "price".

Example:

User question:
total revenue

Available fields:
["price","rating","category"]

Return:

{{
 "metric":"sum",
 "field":"price",
 "group_by": null,
 "filters":[]
}}

3. Detect DATE filters.

Example:

User question:
revenue between 2023-01-01 and 2023-03-01

Return:

{{
 "metric":"sum",
 "field":"price",
 "group_by": null,
 "filters":[
   {{
     "field":"transaction_date",
     "operator":"between",
     "value":["2023-01-01","2023-03-01"]
   }}
 ]
}}

4. Detect CATEGORY filters.

Example:

User question:
average rating for category electronics

Return:

{{
 "metric":"avg",
 "field":"rating",
 "group_by": null,
 "filters":[
   {{
     "field":"category",
     "operator":"equals",
     "value":"electronics"
   }}
 ]
}}

5. Only use semantic fields.

6. If no filters exist return empty list.

7. JSON only. No markdown. No explanation.
"""

    intent = call_llm(prompt)

    if not isinstance(intent, dict):
        raise ValueError(f"Intent extraction returned non-dict: {intent}")

    # defaults
    intent.setdefault("metric", "count")
    intent.setdefault("field", semantic_fields[0] if semantic_fields else "unknown")
    intent.setdefault("group_by", None)
    intent.setdefault("filters", [])

    # fallback mapping for common synonyms
    fallback_map = {
        "revenue": "price",
        "sales": "price",
        "amount": "price"
    }

    if intent["field"] not in semantic_fields:
        if intent["field"] in fallback_map and fallback_map[intent["field"]] in semantic_fields:
            intent["field"] = fallback_map[intent["field"]]

    return intent