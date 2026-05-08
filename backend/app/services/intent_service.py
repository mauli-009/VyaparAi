"""
intent_service.py

Responsibilities
────────────────
1. Classify the user's question into an action (aggregate / list / suggest / recommend / metadata)
2. Extract all parameters needed by downstream services
3. Validate every field name against the actual semantic mapping (fuzzy-matched)
4. Maintain conversation context for follow-up questions
"""
from __future__ import annotations

import json
from rapidfuzz import fuzz

from app.services.llm_service import FAST_ROUTER_MODEL, call_llm


# ─────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────

SUPPORTED_OPERATORS = [
    "==", "!=", ">", "<", ">=", "<=",
    "between", "in",
]

METADATA_KEYWORDS = [
    "columns", "colums", "coloum", "column names", "fields",
    "schema", "headers", "structure", "data types",
    "what data", "what columns", "tell me about",
]

# Words that strongly indicate a follow-up question
FOLLOW_UP_SIGNALS = [
    "what about", "how about", "and for", "and in", "what if",
    "break it down", "show same", "filter by", "only for", "just for",
    "also show", "now show", "compare", "vs", "versus",
    "drill down", "same but", "instead", "exclude",
    "without", "narrow down", "focus on",
]

# Synonym normalization for metric words
METRIC_ALIASES: dict[str, str] = {
    "total":   "sum",
    "add up":  "sum",
    "mean":    "avg",
    "average": "avg",
    "median":  "avg",  # approximate — pandas median not supported yet
    "number of": "count",
    "how many": "count",
    "how much": "sum",
    "largest":  "max",
    "highest":  "max",
    "top":      "max",
    "lowest":   "min",
    "smallest": "min",
    "bottom":   "min",
}

TIME_PERIODS = ["day", "week", "month", "quarter", "year"]


# ─────────────────────────────────────────────────────────────────
# Field normalisation helpers
# ─────────────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    """Strip spaces, underscores, lowercase — for fuzzy comparison."""
    return str(s).lower().replace(" ", "").replace("_", "").replace("-", "").strip()


def _fuzzy_match_field(
    field: str,
    semantic_fields: list[str],
    threshold: int = 68,
) -> str | None:
    """
    Return the best-matching semantic key, or None if score < threshold.
    Tries exact → clean-exact → fuzzy in order.
    """
    if not field:
        return None

    # 1. Exact match
    if field in semantic_fields:
        return field

    clean_f = _clean(field)

    # 2. Clean-exact match (handles "totalRevenue" == "total_revenue")
    for sf in semantic_fields:
        if _clean(sf) == clean_f:
            return sf

    # 3. Fuzzy match
    best_score, best_match = 0, None
    for sf in semantic_fields:
        score = fuzz.ratio(clean_f, _clean(sf))
        if score > best_score:
            best_score, best_match = score, sf

    return best_match if best_score >= threshold else None


def _normalize_group_by(
    group_by: str | None,
    semantic_fields: list[str],
) -> str | None:
    """
    Normalize whatever the LLM returned for group_by to one of:
      • "month(transaction_date)"  /  "year(…)"  etc.  ← time grouping
      • A valid semantic key                            ← categorical grouping
      • None                                            ← can't resolve
    """
    if not group_by:
        return None

    g = str(group_by).strip().lower()

    # Already well-formed:  "month(transaction_date)"
    for period in TIME_PERIODS:
        if g.startswith(f"{period}(") and g.endswith(")"):
            # Make sure the inner field exists
            inner = g[len(period) + 1 : -1]
            matched_inner = _fuzzy_match_field(inner, semantic_fields, threshold=60)
            if matched_inner:
                return f"{period}({matched_inner})"

    # Plain time period keyword: "month", "monthly", "week", "year", …
    for period in TIME_PERIODS:
        if g == period or g == f"{period}ly" or g == f"by {period}":
            date_field = _fuzzy_match_field("transaction_date", semantic_fields, threshold=60)
            if date_field:
                return f"{period}({date_field})"

    # "date" / "order_date" / "transaction_date" with no period → default monthly
    if any(kw in g for kw in ["date", "time", "timestamp"]):
        matched = _fuzzy_match_field(g, semantic_fields, threshold=55)
        if matched:
            return f"month({matched})"

    # Categorical field — fuzzy match
    return _fuzzy_match_field(g, semantic_fields, threshold=70)


def _normalize_operator(op: str) -> str:
    """Normalise operator string to the canonical symbolic form."""
    mapping = {
        "equals":           "==",
        "eq":               "==",
        "=":                "==",
        "not_equals":       "!=",
        "ne":               "!=",
        "neq":              "!=",
        "greater_than":     ">",
        "gt":               ">",
        "less_than":        "<",
        "lt":               "<",
        "greater_or_equal": ">=",
        "gte":              ">=",
        "ge":               ">=",
        "less_or_equal":    "<=",
        "lte":              "<=",
        "le":               "<=",
    }
    return mapping.get(str(op).lower().strip(), str(op).lower().strip())


def _validate_and_fix_intent(intent: dict, semantic_fields: list[str]) -> dict:
    """
    Post-process the raw LLM output:
    • Fuzzy-match field / group_by / filter fields to real semantic keys
    • Normalize operators
    • Ensure required keys have sane defaults
    """
    # Fix metric field
    raw_field = intent.get("field")
    if raw_field and intent.get("action") in ("aggregate", "suggest"):
        matched = _fuzzy_match_field(str(raw_field), semantic_fields)
        if matched:
            intent["field"] = matched

    # Fix group_by
    intent["group_by"] = _normalize_group_by(intent.get("group_by"), semantic_fields)

    # Fix sort_by
    if intent.get("sort_by"):
        matched = _fuzzy_match_field(str(intent["sort_by"]), semantic_fields)
        intent["sort_by"] = matched  # None if unresolvable → ignored downstream

    # Fix filters — use a lower threshold (55) so short geographic/categorical words
    # like "region", "category", "country" don't get dropped
    clean_filters: list[dict] = []
    for f in intent.get("filters", []):
        field_key = str(f.get("field", ""))
        if not field_key:
            continue
        matched = _fuzzy_match_field(field_key, semantic_fields, threshold=55)
        if matched:
            f["field"] = matched
            f["operator"] = _normalize_operator(f.get("operator", "=="))
            clean_filters.append(f)
        else:
            # Keep the filter in the intent even if unresolvable, for display transparency
            # Aggregation service will log & skip it gracefully
            f["operator"] = _normalize_operator(f.get("operator", "=="))
            clean_filters.append(f)

    intent["filters"] = clean_filters

    # Ensure defaults
    intent.setdefault("filters", [])
    intent.setdefault("select", ["*"])
    if not isinstance(intent.get("select"), list):
        intent["select"] = ["*"]
    intent.setdefault("limit", 15)
    intent.setdefault("order", "desc")
    intent.setdefault("suggested_charts", [])

    # Auto-add chart suggestions when group_by is set but LLM forgot charts
    if intent.get("group_by") and not intent.get("suggested_charts"):
        g = str(intent["group_by"]).lower()
        if any(p in g for p in ["month", "week", "year", "day", "quarter", "date", "time"]):
            intent["suggested_charts"] = ["line_chart", "bar_chart"]
        else:
            intent["suggested_charts"] = ["bar_chart", "pie_chart"]

    # Normalize metric aliases (in case LLM or heuristic wrote "total" instead of "sum")
    raw_metric = str(intent.get("metric", "sum")).lower().strip()
    intent["metric"] = METRIC_ALIASES.get(raw_metric, raw_metric)

    # Validate metric is one of the supported values
    if intent["metric"] not in ("sum", "avg", "count", "min", "max"):
        intent["metric"] = "sum"

    return intent


def _is_follow_up(question: str, chat_history: list[dict]) -> bool:
    """Heuristic: is this question a continuation of the previous one?"""
    if not chat_history:
        return False
    q = question.lower().strip()
    if any(sig in q for sig in FOLLOW_UP_SIGNALS):
        return True
    # Very short questions (≤ 5 tokens, no explicit aggregation keyword) are likely follow-ups
    if len(q.split()) <= 4:
        return True
    return False


# ─────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────

def extract_intent(
    question: str,
    semantic_mapping: dict,
    column_values: dict | None = None,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Parameters
    ──────────
    question        : Raw user question
    semantic_mapping: {actual_csv_col: semantic_key}
    column_values   : {semantic_key: [sample values]}  — for accurate filter values
    chat_history    : List of {"question": str, "intent": dict} from previous turns

    Returns
    ───────
    Validated intent dict ready for aggregation / retrieval / suggestion services.
    """
    column_values = column_values or {}
    chat_history  = chat_history  or []

    semantic_fields = list(set(semantic_mapping.values()))

    # ── Fast path: metadata ──────────────────────────────────────
    q_lower = question.lower().strip()
    if any(kw in q_lower for kw in METADATA_KEYWORDS):
        return {
            "action":   "metadata",
            "select":   ["*"],
            "filters":  [],
            "group_by": None,
            "sort_by":  None,
            "order":    "desc",
            "limit":    10,
            "metric":   "count",
            "field":    semantic_fields[0] if semantic_fields else "unknown",
            "suggested_charts": [],
        }

    # ── Build column values section (cap at 15 fields to keep prompt lean) ──
    values_section = ""
    if column_values:
        values_section = (
            "\nActual values in categorical columns "
            "(use EXACTLY these strings in filter values — do NOT paraphrase):\n"
        )
        for field, vals in list(column_values.items())[:15]:
            values_section += f'  "{field}": {vals[:10]}\n'

    # ── Build structured history section ────────────────────────
    history_section = ""
    follow_up_instruction = ""

    if chat_history:
        history_section = (
            "\nConversation history (oldest → newest). "
            "Use this to resolve follow-up questions:\n"
        )
        for i, turn in enumerate(chat_history[-3:], 1):
            history_section += (
                f"\n  Turn {i}:\n"
                f"    User: \"{turn.get('question', '')}\"\n"
                f"    Intent: {json.dumps(turn.get('intent', {}))}\n"
            )

        if _is_follow_up(question, chat_history):
            prev_intent = chat_history[-1].get("intent", {})
            follow_up_instruction = f"""
⚠️  FOLLOW-UP DETECTED — The user's question appears to be a continuation.
Previous resolved intent:
{json.dumps(prev_intent, indent=2)}

Rules for follow-ups:
1. INHERIT action, metric, field, group_by UNCHANGED unless the user explicitly changes them.
2. ONLY update filters (or group_by) based on what the user newly specified.
3. NEVER switch action from "aggregate" to "list" unless the user says "show me records" / "list".
"""

    # ── Prompt ────────────────────────────────────────────────────
    # Build a ranked field list: numeric fields first (likely aggregation targets)
    numeric_hint = ""
    if column_values is not None:
        # Numeric fields are those NOT in column_values (no categorical samples = numeric)
        numeric_fields = [f for f in semantic_fields if f not in column_values]
        categorical_fields = [f for f in semantic_fields if f in column_values]
        numeric_hint = f"\nNumeric fields (sum/avg/min/max candidates): {numeric_fields}\nCategorical fields (group_by/filter candidates): {categorical_fields}\n"

    prompt = f"""You are an expert data query router for a business analytics platform serving SMEs.

User question: "{question}"
{follow_up_instruction}
{history_section}
All available semantic fields: {semantic_fields}
{numeric_hint}
{values_section}

Classify the question and return this EXACT JSON (all keys required):

{{
  "action":           "aggregate | list | metadata | suggest | recommend | chat",
  "metric":           "sum | avg | count | min | max",
  "field":            "<semantic_field_name>",
  "filters":          [{{"field": "<name>", "operator": "== | != | > | < | >= | <= | between | in", "value": "<scalar or [list]>"}}],
  "group_by":         "<semantic_field | month(date_field) | year(date_field) | null>",
  "sort_by":          "<semantic_field | null>",
  "order":            "desc | asc",
  "limit":            15,
  "select":           ["<field1>", "<field2>"],
  "suggested_charts": ["bar_chart | pie_chart | line_chart | scatter_chart"]
}}

══════════ ACTION ROUTING ══════════
"aggregate" → numeric questions: totals, averages, counts, trends, breakdowns, rankings
"list"      → fetch actual rows: "show me records", "list", "find all", "details of"
"suggest"   → business strategy / advice based on data: "what should I do", "how can I improve"
"recommend" → best product/category to focus on: "which product is best", "what to invest in"
"metadata"  → column names, data structure: "what columns", "schema"
"chat"      → conversational questions, greetings, or questions not related to querying the data (e.g., "hi", "what can you do?")

══════════ FINANCIAL VOCABULARY — CRITICAL ══════════
Map user's business intent to the correct field TYPE:

• "earned / made / revenue / income / how much did I get / sales"
  → PREFER fields containing: revenue, profit, earnings, sales, income, total
  → AVOID fields containing: unit_price, actual_price, discounted_price, price, rate
  (those are PER-UNIT prices, NOT aggregate revenue)

• "spent / cost / expense / how much did it cost me"
  → PREFER fields containing: cost, expense, spending, cogs

• "price of a product / unit price / how much does X cost"
  → PREFER fields containing: price, rate, unit_price, mrp

• "profit / margin / net / bottom line"
  → PREFER fields containing: profit, margin, net, earnings

• "how many / count of / number of"
  → metric = "count", field = any column (usually an ID or name column)

PRIORITY ORDER when multiple candidates exist:
  total_revenue > revenue > total_sales > sales > net_revenue
  total_profit  > profit  > net_profit  > margin
  total_cost    > cost    > unit_cost

══════════ LOCATION / CATEGORICAL FILTER PATTERNS ══════════
• "in [location]" / "for [location]" / "from [location]"
  → add a filter: find the best matching field from categorical fields
  → example: "in west region" → {{"field": "region", "operator": "==", "value": "West"}}
• "in [month/year]" → add a date filter, not a categorical filter
• "for [product/category]" → add a category filter

══════════ AGGREGATION RULES ══════════
• metric   → MUST be one of: sum, avg, count, min, max
• field    → MUST be numeric for sum/avg/min/max; pick from Numeric fields list above
• count    → field can be any column (counts non-null rows)
• group_by → MUST be categorical or a time expression — NEVER a numeric/price field
• Time grouping: "month(field_name)", "year(field_name)", "week(field_name)"
• "trend / monthly / over time" → group_by time expression + suggested_charts ["line_chart"]
• "breakdown / by region / by category" → categorical group_by + suggested_charts ["bar_chart"]
• "distribution / share / proportion" → suggested_charts ["pie_chart"]
• "top N" → sort_by = field, order = "desc", limit = N

══════════ FILTER RULES ══════════
• String equality:  {{"field":"region","operator":"==","value":"North America"}}
• Multiple values:  {{"field":"category","operator":"in","value":["Electronics","Books"]}}
• Numeric range:    {{"field":"revenue","operator":"between","value":[1000,5000]}}
• ALWAYS use exact value strings from the categorical values section above
• NEVER leave filters empty when the user specifies a location, category, or time period

══════════ FIELD VALIDATION ══════════
• ONLY use field names from "All available semantic fields" list above
• Never invent field names — if uncertain, pick the closest match
• For sum/avg, the field MUST be a numeric field (from Numeric fields list)

Return raw JSON only. No markdown. No explanation."""

    # ── Call LLM ─────────────────────────────────────────────────
    intent = call_llm(prompt, model=FAST_ROUTER_MODEL)

    if not isinstance(intent, dict):
        raise ValueError(f"Intent extraction returned non-dict: {intent}")

    # ── Validate and fix all field names ─────────────────────────
    intent = _validate_and_fix_intent(intent, semantic_fields)

    # ── Ensure action is valid ────────────────────────────────────
    valid_actions = {"aggregate", "list", "metadata", "suggest", "recommend", "chat"}
    if intent.get("action") not in valid_actions:
        intent["action"] = "aggregate"

    # ── For aggregate: guarantee metric + field are present ───────
    if intent["action"] == "aggregate":
        if not intent.get("field") or intent["field"] not in semantic_fields:
            # Pick the first numeric-looking field as fallback
            intent["field"] = semantic_fields[0] if semantic_fields else "unknown"
        if not intent.get("metric"):
            intent["metric"] = "sum"

    return intent