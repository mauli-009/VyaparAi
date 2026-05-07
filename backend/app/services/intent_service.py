from app.services.llm_service import FAST_ROUTER_MODEL, call_llm

SUPPORTED_OPERATORS = [
    "equals", "not_equals", "greater_than", "less_than",
    "greater_or_equal", "less_or_equal", "between",
    "==", "!=", ">", "<", ">=", "<=", "in"
]

# Updated with common typos to ensure metadata fast-path works
METADATA_KEYWORDS = [
    "columns", "colums", "coloum", "column names", "fields", "schema", "headers", 
    "structure", "data types", "what data is in"
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

LIST_KEYWORDS = [
    "list", "show me all", "show all", "find all", "details of",
    "give me all", "fetch", "which rows", "all records", "all products", "links"
]

def detect_action(question: str) -> str | None:
    """
    Returns the core action or None if unsure.
    """
    q = question.lower().strip()

    if any(kw in q for kw in METADATA_KEYWORDS): return "metadata"
    if any(kw in q for kw in RECOMMENDATION_KEYWORDS): return "recommend"
    if any(kw in q for kw in SUGGESTION_KEYWORDS): return "suggest"
    if any(kw in q for kw in LIST_KEYWORDS) and not any(kw in q for kw in AGGREGATION_KEYWORDS): return "list"
    if any(kw in q for kw in AGGREGATION_KEYWORDS): return "aggregate"
        
    return None

def extract_intent(question: str, semantic_mapping: dict, column_values: dict = {}, chat_history: str = "") -> dict:
    semantic_fields = list(set(semantic_mapping.values()))

    # 1. Fast Path for Metadata
    heuristic_action = detect_action(question)
    if heuristic_action == "metadata":
        return {
            "action": "metadata",
            "select": ["*"],
            "filters": [],
            "group_by": None,
            "sort_by": None,
            "order": "desc",
            "limit": 10
        }

    # 2. Prepare dynamic values
    values_section = ""
    if column_values:
        values_section = "\nActual values present in categorical fields (use EXACTLY one of these as filter values):\n"
        for field, vals in column_values.items():
            values_section += f'  "{field}": {vals}\n'

    # 3. Universal Schema Prompt
    # 3. Universal Schema Prompt
    prompt = f"""
You are an advanced data query router.
User question: "{question}"

Recent Chat History Context:
{chat_history}

Available columns: {semantic_fields}
{values_section}
Supported operators: {SUPPORTED_OPERATORS}

You must convert the user's question into this EXACT JSON structure. Do NOT change the keys.

{{
  "action": "aggregate" | "list" | "metadata" | "suggest" | "recommend",
  "select": ["column_name_1"],
  "metric": "sum | avg | count", 
  "field": "column_name",
  "filters": [ {{"field": "column_name", "operator": "==", "value": "xyz"}} ],
  "group_by": "column_name" or null,
  "sort_by": "column_name" or null,
  "order": "desc" | "asc",
  "limit": 10,
  "suggested_charts": []
}}

RULES FOR CHARTS & GROUPING:
- Valid chart types: "bar_chart", "pie_chart", "line_chart", "scatter_chart".
- CRITICAL: NEVER use continuous numerical columns (like price, rating) for "group_by". "group_by" MUST be categorical.
- CONVERSATIONAL MEMORY: If the user asks a follow-up question (e.g., "What about Houston?"), you MUST KEEP the same "action", "metric", and "field" from the 'Recent Chat History' and ONLY update the "filters". Do NOT switch to "list" unless explicitly asked.
- EXPLICIT OVERRIDE: If the user explicitly asks for a specific chart type...
"""

    intent = call_llm(prompt, model=FAST_ROUTER_MODEL)

    if not isinstance(intent, dict):
        raise ValueError(f"Intent extraction returned non-dict: {intent}")

    # 4. Smart Merging Logic
    llm_action = intent.get("action")

    if heuristic_action == "metadata":
        final_action = "metadata"
    elif heuristic_action == "list" and llm_action == "aggregate":
        final_action = "list"
    else:
        final_action = llm_action or heuristic_action or "aggregate"

    intent["action"] = final_action

    # 5. Backward Compatibility Safety Net
    if final_action == "aggregate":
        metric = intent.get("metric")
        field = intent.get("field")
        
        # Extract from select array (e.g. "avg(rating)") if LLM forgot
        select_fields = intent.get("select", [])
        if select_fields and isinstance(select_fields[0], str) and "(" in select_fields[0]:
            try:
                parsed_metric = select_fields[0].split("(")[0].strip().lower()
                parsed_field = select_fields[0].split("(")[1].replace(")", "").strip()
                
                if not metric or str(metric).lower() == "none": metric = parsed_metric
                if not field or str(field).lower() == "none": field = parsed_field
            except Exception:
                pass

        # Final sanitization
        if not metric or str(metric).lower() == "none": 
            metric = "count"
        if not field or str(field).lower() == "none" or field == "*": 
            field = semantic_fields[0] if semantic_fields else "unknown"

        # Fuzzy match the field to guarantee it exists in mapping
        clean_field = str(field).lower().replace(" ", "").replace("_", "")
        matched_field = None
        for sf in semantic_fields:
            if str(sf).lower().replace(" ", "").replace("_", "") == clean_field:
                matched_field = sf
                break

        intent["metric"] = metric
        intent["field"] = matched_field or field

    intent.setdefault("select", ["*"])
    if not isinstance(intent.get("select"), list):
        intent["select"] = ["*"]
        
    intent.setdefault("filters", [])
    intent.setdefault("limit", 15)

    return intent