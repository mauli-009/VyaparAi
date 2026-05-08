import uuid
from app.services.llm_service import call_llm, FAST_ROUTER_MODEL

def generate_dynamic_layout(semantic_mapping: dict) -> list:
    semantic_fields = list(set(semantic_mapping.values()))
    
    prompt = f"""
You are an expert Business Intelligence dashboard architect.
I have a dataset with the following available semantic columns:
{semantic_fields}

Design a starter dashboard with exactly 6 widgets that make logical business sense for this specific data. 
Infer what the data is about (e.g., sales, HR, server logs) and pick the best KPIs.

REQUIREMENTS:
1. Widget 1: A single high-level metric (type: "metric")
2. Widget 2: Another single high-level metric (type: "metric")
3. Widget 3: A trend over time (type: "line_chart") - MUST use a date column for group_by.
4. Widget 4: A categorical breakdown (type: "bar_chart") - MUST use a string/category column for group_by.
5. Widget 5: A distribution (type: "pie_chart") - MUST use a string/category column for group_by.
6. Widget 6: A list of top records (type: "list") - action MUST be "list", select top 3-4 columns.

Return a JSON array of exactly 6 objects in this format:
[
  {{
    "id": "generate-a-unique-string",
    "type": "metric | line_chart | bar_chart | pie_chart | list",
    "title": "Human readable title (e.g., Total Revenue)",
    "grid_position": {{ "w": 2, "h": 1 }}, // metrics are w:1 h:1, charts are w:2 h:2
    "intent": {{
      "action": "aggregate", // or "list"
      "metric": "sum | avg | count", 
      "field": "column_name",
      "filters": [],
      "group_by": "column_name" // or null for metrics/lists
    }}
  }}
]

RULES:
- ONLY use the columns provided. Do NOT invent columns.
- Return raw JSON array only. No markdown.
"""
    
    # We use the fast 8B model because this is strict JSON structural generation
    try:
        layout = call_llm(prompt, model=FAST_ROUTER_MODEL)
        # Ensure unique IDs just in case the LLM gets lazy
        for widget in layout:
            widget["id"] = f"widget-{uuid.uuid4().hex[:8]}"
        return layout
    except Exception as e:
        print(f"[DASHBOARD ERROR] Failed to generate layout: {e}")
        return []