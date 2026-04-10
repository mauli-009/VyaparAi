from app.services.llm_service import call_llm

SUPPORTED_METRICS = ["sum", "avg", "count"]

SUPPORTED_OPERATORS = [
    "equals", "not_equals", "greater_than", "less_than",
    "greater_or_equal", "less_or_equal", "between"
]

SUGGESTION_KEYWORDS = [
    "suggest", "suggestion", "recommend", "recommendation",
    "what should", "strategy", "advice", "tip", "improve",
    "opportunity", "plan", "how can i", "should i"
]

RECOMMENDATION_KEYWORDS = [
    "which product", "what product", "best product", "top product",
    "which item", "what item", "which category", "what category",
    "long term", "next month", "next quarter", "invest in",
    "focus on", "choose", "pick", "select", "prioritize",
    "what to sell", "which to sell", "worth selling"
]

AGGREGATION_KEYWORDS = [
    "total", "sum", "average", "avg", "count", "how many",
    "how much", "trend", "breakdown", "show me", "what is",
    "revenue", "profit", "sales", "units", "cost"
]


def detect_query_type(question: str) -> str:
    """
    Returns:
    - "aggregation"    → user wants a number/table
    - "suggestion"     → user wants general advice
    - "recommendation" → user wants product/category ranking with reasons
    - "both"           → user wants number + suggestions
    """
    q = question.lower().strip()

    is_recommendation = any(kw in q for kw in RECOMMENDATION_KEYWORDS)
    is_suggestion = any(kw in q for kw in SUGGESTION_KEYWORDS)
    is_aggregation = any(kw in q for kw in AGGREGATION_KEYWORDS)

    if is_recommendation:
        return "recommendation"
    if is_suggestion and is_aggregation:
        return "both"
    if is_suggestion:
        return "suggestion"
    return "aggregation"


def extract_intent(question: str, semantic_mapping: dict, column_values: dict = {}) -> dict:
    semantic_fields = list(set(semantic_mapping.values()))

    values_section = ""
    if column_values:
        values_section = "\nActual values present in each categorical field (use EXACTLY one of these as filter values):\n"
        for field, vals in column_values.items():
            values_section += f'  "{field}": {vals}\n'

    prompt = f"""
You are an analytics intent extractor.

User question:
"{question}"

Available semantic fields:
{semantic_fields}
{values_section}
Supported metrics: {SUPPORTED_METRICS}
Supported operators: {SUPPORTED_OPERATORS}

Convert the user question into structured analytics intent.

Return JSON:
{{
  "metric": "sum | avg | count",
  "field": "<semantic_field>",
  "group_by": "month(transaction_date)" or null,
  "filters": []
}}

RULES:
1. "field" MUST be one of the available semantic fields.
2. Filter values MUST be copied EXACTLY from the actual values list above.
3. JSON only. No markdown. No explanation.
"""

    intent = call_llm(prompt)

    if not isinstance(intent, dict):
        raise ValueError(f"Intent extraction returned non-dict: {intent}")

    intent.setdefault("metric", "count")
    intent.setdefault("field", semantic_fields[0] if semantic_fields else "unknown")
    intent.setdefault("group_by", None)
    intent.setdefault("filters", [])

    fallback_map = {"revenue": "price", "sales": "price", "amount": "price"}
    if intent["field"] not in semantic_fields:
        if intent["field"] in fallback_map and fallback_map[intent["field"]] in semantic_fields:
            intent["field"] = fallback_map[intent["field"]]

    intent["query_type"] = detect_query_type(question)

    return intent