from app.services.llm_service import call_llm

SUPPORTED_METRICS = ["sum", "avg", "count", "min", "max"]

SUPPORTED_OPERATORS = [
    "equals",
    "not_equals",
    "greater_than",
    "less_than",
    "greater_or_equal",
    "less_or_equal",
    "between"
]

SUPPORTED_GROUP_BY = [
    "day(transaction_date)",
    "week(transaction_date)",
    "month(transaction_date)",
    "year(transaction_date)",
    "category",
    "region",
    "product_name",
    "user_name",
]


def extract_intent(question: str, semantic_mapping: dict) -> dict:

    # unique semantic fields available in this dataset
    semantic_fields = list(set(semantic_mapping.values()))

    # only include group_by options relevant to this dataset
    available_group_by = [
        g for g in SUPPORTED_GROUP_BY
        if any(f in g for f in semantic_fields) or g in semantic_fields
    ]

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

Supported group_by values:
{available_group_by}

Convert the user question into a structured analytics intent.

Return JSON in this EXACT structure:

{{
  "metric": "sum | avg | count | min | max",
  "field": "<semantic_field>",
  "group_by": "<group_by_value> or null",
  "top_n": <integer or null>,
  "filters": [
    {{
      "field": "<semantic_field>",
      "operator": "<operator>",
      "value": "<value or [start, end] for between>"
    }}
  ]
}}

═══════════════════════════════
RULES
═══════════════════════════════

RULE 1 — field must be a valid semantic field.
Always pick from the available semantic fields list.
If user asks for revenue/sales/profit/amount → pick the closest price field available.

RULE 2 — DATE RANGE FILTERS.
If user mentions "between date1 and date2" or "from date1 to date2":
- Use operator "between" with value as a list: ["date1", "date2"]
- Always use "transaction_date" semantic field for date filters
- Dates must be in YYYY-MM-DD format

Example:
User: total sales between 2024-01-01 and 2024-03-31
→
{{
  "metric": "sum",
  "field": "discounted_price_numeric",
  "group_by": null,
  "top_n": null,
  "filters": [
    {{
      "field": "transaction_date",
      "operator": "between",
      "value": ["2024-01-01", "2024-03-31"]
    }}
  ]
}}

RULE 3 — MULTIPLE FILTERS (date + category combined).
Always include ALL filters the user mentions.

Example:
User: total revenue for electronics between 2024-01-01 and 2024-06-30
→
{{
  "metric": "sum",
  "field": "discounted_price_numeric",
  "group_by": null,
  "top_n": null,
  "filters": [
    {{
      "field": "category",
      "operator": "equals",
      "value": "electronics"
    }},
    {{
      "field": "transaction_date",
      "operator": "between",
      "value": ["2024-01-01", "2024-06-30"]
    }}
  ]
}}

RULE 4 — GROUP BY TIME PERIOD OR CATEGORY.
- "month by month" / "monthly"  → "month(transaction_date)"
- "day by day" / "daily"        → "day(transaction_date)"
- "week by week" / "weekly"     → "week(transaction_date)"
- "year by year" / "yearly"     → "year(transaction_date)"
- "by category"                 → "category"
- "by product"                  → "product_name"
- "by region"                   → "region"

Example:
User: total sales month by month in 2024
→
{{
  "metric": "sum",
  "field": "discounted_price_numeric",
  "group_by": "month(transaction_date)",
  "top_n": null,
  "filters": [
    {{
      "field": "transaction_date",
      "operator": "between",
      "value": ["2024-01-01", "2024-12-31"]
    }}
  ]
}}

RULE 5 — TOP N.
If user says "top 5", "top 10", "best N", "highest N" → set top_n to that integer.
Always pair top_n with a relevant group_by.

Example:
User: top 5 products by total sales
→
{{
  "metric": "sum",
  "field": "discounted_price_numeric",
  "group_by": "product_name",
  "top_n": 5,
  "filters": []
}}

RULE 6 — MIN / MAX.
- "highest", "maximum", "most expensive" → metric: "max"
- "lowest", "minimum", "cheapest"        → metric: "min"

Example:
User: what is the highest rated product
→
{{
  "metric": "max",
  "field": "rating",
  "group_by": null,
  "top_n": null,
  "filters": []
}}

RULE 7 — PRODUCT NAME FILTER.
If user mentions a specific product, brand, or model name:
- ALWAYS use "product_name" as filter field
- NEVER use "product_description"

RULE 8 — JSON only. No markdown. No explanation.
"""

    intent = call_llm(prompt)

    if not isinstance(intent, dict):
        raise ValueError(f"Intent extraction returned non-dict: {intent}")

    # ── Defaults ─────────────────────────────────────────────────────
    intent.setdefault("metric", "count")
    intent.setdefault("field", semantic_fields[0] if semantic_fields else "unknown")
    intent.setdefault("group_by", None)
    intent.setdefault("top_n", None)
    intent.setdefault("filters", [])

    # ── Fallback synonyms for metric field ───────────────────────────
    fallback_map = {
        "revenue": "discounted_price_numeric",
        "sales":   "discounted_price_numeric",
        "profit":  "discounted_price_numeric",
        "amount":  "discounted_price_numeric",
        "price":   "discounted_price_numeric",
    }
    if intent["field"] not in semantic_fields:
        fallback = fallback_map.get(intent["field"])
        if fallback and fallback in semantic_fields:
            intent["field"] = fallback
        elif semantic_fields:
            intent["field"] = semantic_fields[0]

    # ── Fix common LLM mistakes in filter fields ─────────────────────
    filter_field_corrections = {
        "product_description": "product_name",
        "description":         "product_name",
        "date":                "transaction_date",
        "order_date":          "transaction_date",
        "purchase_date":       "transaction_date",
    }
    for f in intent.get("filters", []):
        wrong_field = f.get("field")
        if wrong_field in filter_field_corrections:
            corrected = filter_field_corrections[wrong_field]
            if corrected in semantic_fields:
                f["field"] = corrected

    # ── Validate group_by ─────────────────────────────────────────────
    if intent["group_by"] and intent["group_by"] not in SUPPORTED_GROUP_BY:
        intent["group_by"] = None

    # ── Validate top_n ────────────────────────────────────────────────
    if intent["top_n"] is not None:
        try:
            intent["top_n"] = int(intent["top_n"])
        except (ValueError, TypeError):
            intent["top_n"] = None

    return intent