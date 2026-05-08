"""
dashboard_service.py

Generates a 9-widget executive dashboard layout tailored to the uploaded dataset.
Fully defensive: handles LLM quirks, missing keys, wrong types, partial responses.
"""
import uuid
import json
from app.services.llm_service import call_llm, FAST_ROUTER_MODEL


_NUMERIC_HINTS = {
    "revenue", "profit", "sales", "cost", "price", "units", "quantity",
    "amount", "count", "total", "avg", "rate", "score", "rating",
    "discount", "margin", "percent", "number", "num", "qty", "value",
    "income", "expense", "tax", "fee", "salary", "wage", "commission",
}


def _looks_numeric(field: str) -> bool:
    lower = field.lower().replace("_", " ")
    return any(h in lower for h in _NUMERIC_HINTS)


def _safe_int(v, default: int) -> int:
    try:
        return int(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def _sanitise_widget(
    raw: dict,
    numeric_fields: list,
    cat_fields: list,
    all_fields: list,
) -> dict | None:
    """
    Validate and repair a single widget dict from the LLM.
    Returns None only if the widget is completely unsalvageable.
    """
    if not isinstance(raw, dict):
        return None

    # --- type ---
    wtype = str(raw.get("type", "metric")).lower().strip()
    if wtype not in ("metric", "bar_chart", "line_chart", "pie_chart", "list"):
        wtype = "metric"

    title = str(raw.get("title") or "KPI").strip() or "KPI"

    # --- grid_position ---
    gp    = raw.get("grid_position") or {}
    gp    = gp if isinstance(gp, dict) else {}
    dw    = 1 if wtype == "metric" else 2
    dh    = 1 if wtype == "metric" else 2
    grid_position = {
        "w": _safe_int(gp.get("w"), dw),
        "h": _safe_int(gp.get("h"), dh),
    }

    # --- intent ---
    intent_raw = raw.get("intent") or {}
    if not isinstance(intent_raw, dict):
        intent_raw = {}

    action = str(intent_raw.get("action") or "aggregate").lower().strip()
    if action not in ("aggregate", "list"):
        action = "list" if wtype == "list" else "aggregate"

    metric = str(intent_raw.get("metric") or "sum").lower().strip()
    if metric not in ("sum", "avg", "count", "min", "max"):
        metric = "count" if action == "list" else "sum"

    # Validate field exists in the dataset
    field = intent_raw.get("field")
    if field not in all_fields:
        field = numeric_fields[0] if numeric_fields else (all_fields[0] if all_fields else None)
    if not field:
        return None  # Cannot render any widget without a field

    # Validate group_by
    group_by = intent_raw.get("group_by")
    if group_by is not None:
        group_by = str(group_by).strip() or None
    if group_by:
        # Time expressions are always fine
        is_time_expr = any(p in group_by.lower() for p in ("(", "month", "year", "week", "day", "quarter"))
        if not is_time_expr:
            if group_by not in all_fields:
                group_by = cat_fields[0] if cat_fields else None

    sort_by = intent_raw.get("sort_by")
    if sort_by and sort_by not in all_fields:
        sort_by = None

    filters = intent_raw.get("filters") or []
    if not isinstance(filters, list):
        filters = []

    order = str(intent_raw.get("order") or "desc").lower()
    if order not in ("asc", "desc"):
        order = "desc"

    select = intent_raw.get("select") or ["*"]
    if not isinstance(select, list) or not select:
        select = ["*"]

    intent = {
        "action":          action,
        "metric":          metric,
        "field":           field,
        "filters":         filters,
        "group_by":        group_by,
        "sort_by":         sort_by,
        "order":           order,
        "limit":           _safe_int(intent_raw.get("limit"), 10),
        "select":          select,
        "suggested_charts": [],
    }

    return {
        "id":            f"widget-{uuid.uuid4().hex[:8]}",
        "type":          wtype,
        "title":         title,
        "grid_position": grid_position,
        "intent":        intent,
    }


def generate_dynamic_layout(semantic_mapping: dict) -> list:
    """
    Generate a 9-widget executive dashboard layout.
    Never raises — returns [] on total failure.
    """
    if not semantic_mapping:
        print("[DASHBOARD] Empty semantic mapping — nothing to generate.")
        return []

    all_fields     = list(set(semantic_mapping.values()))
    numeric_fields = [f for f in all_fields if _looks_numeric(f)]
    cat_fields     = [f for f in all_fields if f not in numeric_fields]

    if not all_fields:
        return []

    num_example  = numeric_fields[0] if numeric_fields else all_fields[0]
    cat_example  = cat_fields[0]     if cat_fields     else all_fields[0]
    date_fields  = [f for f in all_fields
                    if any(kw in f.lower() for kw in ("date", "time", "timestamp", "dt"))]
    date_example = date_fields[0] if date_fields else None
    date_group   = f"month({date_example})" if date_example else "null"

    prompt = f"""You are a Business Intelligence dashboard designer for SME analytics.

Dataset fields:
  Numeric  (sum/avg/min/max targets): {numeric_fields}
  Category (group_by targets):        {cat_fields}
  All fields: {all_fields}

Return a JSON array of exactly 9 widget objects. Use this exact structure per widget:

{{
  "id": "w1",
  "type": "metric",
  "title": "Total Revenue",
  "grid_position": {{"w": 1, "h": 1}},
  "intent": {{
    "action": "aggregate",
    "metric": "sum",
    "field": "{num_example}",
    "filters": [],
    "group_by": null,
    "sort_by": null,
    "order": "desc",
    "limit": 10,
    "select": ["*"]
  }}
}}

REQUIRED 9 WIDGETS IN ORDER:
1. type:metric,     w:1 -- Sum of main revenue/sales/profit field. title like "Total Revenue"
2. type:metric,     w:1 -- Count of all records OR avg of an important numeric. title like "Total Orders"
3. type:metric,     w:1 -- Another KPI: max single value, or sum of cost, or avg price
4. type:line_chart, w:2 -- Revenue trend over time. group_by: {date_group}. If no date column use bar_chart on a category instead
5. type:bar_chart,  w:2 -- Sum or count grouped by {cat_example} (or best category field). title like "Revenue by Category"
6. type:pie_chart,  w:1 -- Distribution by region/segment/channel. title like "Sales by Region"
7. type:bar_chart,  w:2 -- DIFFERENT category from widget 5 (use sub_category/city/channel/ship_mode). title like "Orders by City"
8. type:metric,     w:1 -- Avg of a useful numeric field. title like "Avg Order Value"
9. type:list,       w:2 -- Top records. action must be "list". select 3-4 important column names. title like "Top Orders"

STRICT RULES:
- Only use field names from the lists above. Never invent or guess fields.
- field for sum/avg/min/max MUST be from the Numeric list.
- group_by MUST be from the Category list OR a time expression like month(fieldname).
- group_by must NEVER be a numeric field.
- Widget 9: action must be "list" not "aggregate".
- Widgets 5 and 7 must use DIFFERENT category fields.
- Return a raw JSON array only. No markdown. No explanation. No code fences."""

    raw_output = None
    try:
        raw_output = call_llm(prompt, model=FAST_ROUTER_MODEL)

        # Handle LLM wrapping the array in an object
        if isinstance(raw_output, dict):
            for key in ("layout", "widgets", "dashboard", "data", "result", "items"):
                if isinstance(raw_output.get(key), list):
                    raw_output = raw_output[key]
                    break
            else:
                # Fallback: take the first list value
                for v in raw_output.values():
                    if isinstance(v, list):
                        raw_output = v
                        break

        if not isinstance(raw_output, list):
            print(f"[DASHBOARD] LLM returned unexpected type {type(raw_output)} — got: {str(raw_output)[:300]}")
            return []

        layout = []
        for idx, raw_widget in enumerate(raw_output):
            clean = _sanitise_widget(raw_widget, numeric_fields, cat_fields, all_fields)
            if clean is not None:
                layout.append(clean)
            else:
                print(f"[DASHBOARD] Widget {idx} dropped (unsalvageable): {raw_widget}")

        print(f"[DASHBOARD] Generated {len(layout)}/{len(raw_output)} valid widgets.")
        return layout

    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[DASHBOARD] Layout generation failed: {exc}")
        if raw_output is not None:
            try:
                print(f"[DASHBOARD] Raw output snippet: {json.dumps(raw_output, default=str)[:500]}")
            except Exception:
                pass
        return []