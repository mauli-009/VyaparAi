"""
intent_service.py — complete overhaul
"""
from __future__ import annotations
import json, re
from rapidfuzz import fuzz
from app.services.llm_service import FAST_ROUTER_MODEL, call_llm

SUPPORTED_OPERATORS = ["==","!=",">","<",">=","<=","between","in"]
METADATA_KEYWORDS   = ["columns","colums","coloum","column names","fields","schema","headers","structure","data types","what data","what columns","tell me about"]
FOLLOW_UP_SIGNALS   = ["what about","how about","and for","and in","what if","break it down","only for","just for","also show","now show","compare","vs","versus","drill down","same but","instead","exclude","without","narrow down","focus on"]
METRIC_ALIASES      = {"total":"sum","add up":"sum","mean":"avg","average":"avg","median":"avg","number of":"count","how many":"count","how much":"sum","largest":"max","highest":"max","maximum":"max","lowest":"min","smallest":"min","minimum":"min"}
TIME_PERIODS        = ["day","week","month","quarter","year"]

# Patterns that FORCE action = "list"
_LIST_PATTERNS = [
    r"\bgive me (a )?list\b",
    r"\blist (all |of )\b",
    r"\bshow (me )?all\b",
    r"\bshow (me )?(the )?(all )?(products?|customers?|orders?|items?|users?|clients?|people|records?|entries?|names?)\b",
    r"\bfind (all |me |me all )?(the )?(products?|customers?|orders?|items?|users?|records?|entries?|people|names?)\b",
    r"\bfetch (all |me )?\b",
    r"\bget (me )?(all )?(the )?(products?|customers?|orders?|items?|users?|records?|entries?|names?)\b",
    r"\bnames? of (all )?(the )?\b",
    r"\b(products?|customers?|orders?|items?|users?|clients?|records?|entries?)\s+(who|whose|that|where|with|having)\b",
    r"\b(who|whom) (are|is|were|was) (from|in|at|based|located|living)\b",
    r"\bwhich (products?|customers?|orders?|items?|users?|clients?)\s+(are|have|had|with|where|whose)\b",
    r"\b(customers?|clients?|users?|people)\s+(from|in|at|based in|located in)\b",
]

# Patterns that signal ranking (group_by + sort)
_RANKING_PATTERNS = [
    r"\bwhich\b.{1,50}\bhas(?: the)? (highest|most|best|largest|biggest|maximum|lowest|least|worst|smallest|minimum)\b",
    r"\b(best|worst|top|bottom|highest|lowest|most|least)\b.{1,30}\bby (region|category|product|city|state|country|channel|segment|area|market|zone)\b",
    r"\b(best|worst|top|bottom|highest|lowest|most|least) performing\b",
    r"\btop \d+\b.{1,30}\b(region|category|product|city|state|country|channel)\b",
    r"\b(rank|ranking|ranked)\b",
    r"\b(region|category|product|city|state|country|channel)\b.{1,40}\b(highest|most|best|largest|lowest|least|worst|smallest)\b",
]

def _is_list(q):    return any(re.search(p, q, re.IGNORECASE) for p in _LIST_PATTERNS)
def _is_ranking(q): return any(re.search(p, q, re.IGNORECASE) for p in _RANKING_PATTERNS)

# Patterns that indicate a general knowledge / advisory question NOT requiring data lookup
_GENERAL_PATTERNS = [
    # "usually/usally/normally done/used" — handles common typos
    r"\b(usually|usally|usualy|normaly|normally|typically|typicaly|generaly)\s+(done|used|practiced|implemented|recommended|followed|applied)\b",
    r"\bin\s+general\b",
    r"\bgenerally\s+(speaking|done|used|recommended)?\b",
    r"\bbest\s+pract",
    r"\bstandard\s+(pract|approach|method|procedure)\b",
    r"\bcompanies?\s+(usually|typically|generally|often|tend to|should|can|would)\b",
    r"\bwhat\s+(are|is)\s+(the\s+)?(common|standard|typical|usual|traditional|modern|effective|proven)\s+(ways?|methods?|steps?|strategies?|approaches?|techniques?|practices?|tactics?)\b",
    r"\bhow\s+(do|does|can|should|would)\s+(a\s+)?compan",
    r"\badvice\s+(on|for|about)\b",
    r"\btips?\s+(on|for|about|to)\b",
    r"\bways?\s+to\s+(improve|boost|grow|increase|maximize|optimize|enhance)\b",
    r"\bstrategies?\s+(for|to)\s+(improve|boost|grow|increase|sales|revenue|profit)\b",
    r"\bhow\s+to\s+(improve|increase|boost|grow|maximize|optimize|enhance|drive|expand)\b",
    r"\bwhat\s+(should|can|could|would)\s+(i|we|a\s+business|a\s+company|companies?)\s+(do|focus|consider)\b",
    r"\bwhat\s+(is|are)\s+(the\s+)?(key|main|primary|top|best|important)\s+(factor|driver|reason|cause|element|step)\b",
]

# Data-anchor words — if present, the question IS about the dataset even with general phrasing
_DATA_ANCHORS = [
    "my data", "this data", "the data", "dataset", "in my", "our", "this csv",
    "my company", "my store", "my business", "my sales", "this company",
]

def _is_general(question: str) -> bool:
    """True when the question asks for general knowledge not tied to the loaded dataset."""
    q = question.lower().strip()
    if any(anchor in q for anchor in _DATA_ANCHORS):
        return False  # Explicitly about their data — not general
    return any(re.search(p, q, re.IGNORECASE) for p in _GENERAL_PATTERNS)

def _clean(s):
    return str(s).lower().replace(" ","").replace("_","").replace("-","").strip()

def _fuzzy(field, fields, threshold=68):
    if not field: return None
    if field in fields: return field
    cf = _clean(field)
    for sf in fields:
        if _clean(sf) == cf: return sf
    best, bm = 0, None
    for sf in fields:
        s = fuzz.ratio(cf, _clean(sf))
        if s > best: best, bm = s, sf
    return bm if best >= threshold else None

def _norm_groupby(gb, fields):
    if not gb: return None
    g = str(gb).strip().lower()
    for period in TIME_PERIODS:
        if g.startswith(f"{period}(") and g.endswith(")"):
            inner = g[len(period)+1:-1]
            m = _fuzzy(inner, fields, 60)
            if m: return f"{period}({m})"
        if g in (period, f"{period}ly", f"by {period}"):
            df = _fuzzy("transaction_date", fields, 60)
            if df: return f"{period}({df})"
    if any(kw in g for kw in ["date","time","timestamp"]):
        m = _fuzzy(g, fields, 55)
        if m: return f"month({m})"
    return _fuzzy(g, fields, 70)

def _norm_op(op):
    m = {"equals":"==","eq":"==","=":"==","not_equals":"!=","ne":"!=","greater_than":">","gt":">","less_than":"<","lt":"<","greater_or_equal":">=","gte":">=","less_or_equal":"<=","lte":"<="}
    return m.get(str(op).lower().strip(), str(op).lower().strip())

def _fix(intent, fields):
    if intent.get("field") and intent.get("action") in ("aggregate","suggest"):
        m = _fuzzy(intent["field"], fields)
        if m: intent["field"] = m
    intent["group_by"] = _norm_groupby(intent.get("group_by"), fields)
    if intent.get("sort_by"):
        intent["sort_by"] = _fuzzy(str(intent["sort_by"]), fields)
    clean = []
    for f in intent.get("filters",[]):
        fk = str(f.get("field",""))
        if not fk: continue
        m = _fuzzy(fk, fields, 52)
        if m: f["field"] = m
        f["operator"] = _norm_op(f.get("operator","=="))
        clean.append(f)
    intent["filters"] = clean
    intent.setdefault("filters",[])
    intent.setdefault("select",["*"])
    if not isinstance(intent.get("select"),list): intent["select"] = ["*"]
    # Guard: limit can be None if LLM returned null explicitly
    if not intent.get("limit"): intent["limit"] = 20
    intent.setdefault("order","desc")
    intent.setdefault("suggested_charts",[])
    if intent.get("group_by") and not intent.get("suggested_charts"):
        g = str(intent["group_by"]).lower()
        if any(p in g for p in ["month","week","year","day","quarter","date","time"]):
            intent["suggested_charts"] = ["line_chart","bar_chart"]
        else:
            intent["suggested_charts"] = ["bar_chart","pie_chart"]
    rm = str(intent.get("metric","sum")).lower().strip()
    intent["metric"] = METRIC_ALIASES.get(rm, rm)
    if intent["metric"] not in ("sum","avg","count","min","max"): intent["metric"] = "sum"
    return intent

def _is_followup(q, hist):
    if not hist: return False
    if any(sig in q.lower() for sig in FOLLOW_UP_SIGNALS): return True
    if len(q.split()) <= 4: return True
    return False

def extract_intent(question, semantic_mapping, column_values=None, chat_history=None):
    column_values = column_values or {}
    chat_history  = chat_history  or []
    fields = list(set(semantic_mapping.values()))
    q_lower = question.lower().strip()

    # Fast path: metadata
    if any(kw in q_lower for kw in METADATA_KEYWORDS):
        return {"action":"metadata","select":["*"],"filters":[],"group_by":None,"sort_by":None,"order":"desc","limit":10,"metric":"count","field":fields[0] if fields else "unknown","suggested_charts":[]}

    # Fast path: general knowledge question — no data query needed
    if _is_general(question):
        return {"action":"general","field":None,"filters":[],"group_by":None,"sort_by":None,"metric":None,"limit":0,"select":[],"suggested_charts":[]}

    is_list    = _is_list(question)
    is_rank    = _is_ranking(question) and not is_list
    num_fields = [f for f in fields if f not in column_values]
    cat_fields = [f for f in fields if f in column_values]

    # Values section
    val_sec = ""
    if column_values:
        val_sec = "\nCategorical column sample values (use EXACTLY these for filter values):\n"
        for f,v in list(column_values.items())[:15]:
            val_sec += f'  "{f}": {v[:8]}\n'

    # History section
    hist_sec = ""
    fu_hint  = ""
    if chat_history:
        hist_sec = "\nConversation history:\n"
        for i,t in enumerate(chat_history[-3:],1):
            hist_sec += f"  Turn {i}: \"{t.get('question','')}\" → {json.dumps(t.get('intent',{}))}\n"
        if _is_followup(question, chat_history):
            prev = chat_history[-1].get("intent",{})
            fu_hint = f"\n⚠️ FOLLOW-UP: Inherit unchanged fields from: {json.dumps(prev)}\nOnly update what changed.\n"

    # Override hints
    override = ""
    if is_list:
        override = """
🚨 LIST OVERRIDE — action MUST be "list". User wants individual records NOT numbers.
• The condition (whose X > Y, from city, with attribute) → goes into filters
• select → entity/name column + filter column + 1-2 relevant columns
• NEVER use "aggregate". NEVER compute sum/avg/count.
• "customers from Seattle" → select:["customer_name","city"], filters:[{city=="Seattle"}]
• "products whose sales > 300" → select:["product_name","units_sold"], filters:[{units_sold>300}]
• "list of product names" → select:["product_name"], filters:[]
"""
    elif is_rank:
        override = """
🏆 RANKING — User wants to compare groups, NOT a single total.
• action:"aggregate", group_by=the category (region/product/category), sort_by=metric, order="desc", limit=10
• "which region has highest sales" → group_by:"region", sort_by:"total_revenue", order:"desc", limit:10
• Add "bar_chart" to suggested_charts
"""

    prompt = f"""You are an expert data query router for a business analytics platform serving SMEs.

User question: "{question}"
{override}{fu_hint}{hist_sec}
All semantic fields: {fields}
Numeric fields (sum/avg targets): {num_fields}
Categorical fields (group_by/filter targets): {cat_fields}
{val_sec}

Return this EXACT JSON:
{{
  "action":           "aggregate | list | metadata | suggest | recommend",
  "metric":           "sum | avg | count | min | max",
  "field":            "<semantic_field>",
  "filters":          [{{"field":"<f>","operator":"== | != | > | < | >= | <= | between | in","value":"<scalar or [list]>"}}],
  "group_by":         "<semantic_field | month(date_field) | null>",
  "sort_by":          "<semantic_field | null>",
  "order":            "desc | asc",
  "limit":            20,
  "select":           ["<col1>","<col2>"],
  "suggested_charts": ["bar_chart | pie_chart | line_chart | scatter_chart"]
}}

ACTION:
• aggregate → numeric totals, averages, trends, breakdowns, rankings
• list       → fetch records: "give me a list", "show all", "find products that", "customers from X"
• suggest    → business advice: "what should I do", "how to improve"
• recommend  → best product/category: "which product is best long term"
• metadata   → schema/column info

FINANCIAL VOCABULARY:
• "earned/made/revenue/income" → prefer: total_revenue, profit, sales, earnings (NOT unit_price/actual_price)
• "spent/cost/expense"         → prefer: total_cost, cost, expense
• "price" (per-unit)           → prefer: unit_price, actual_price, mrp
• Small filter values (< 10k, no $): likely units/quantity NOT revenue

SELECT for list queries:
• Always include the entity/name column + filter column + context columns
• "customers from Seattle" → ["customer_name","city","state"] NOT just ["city"]
• "products whose sales > 300" → ["product_name","units_sold","category"]
• NEVER return just the filter column alone

FILTER RULES:
• "more than X but less than Y" → operator:"between", value:[X,Y]
• "from Seattle" → field:city_field, operator:"==", value:"Seattle"
• "whose sales > 300" → field:units_sold_field, operator:">", value:300
• Use EXACT values from the categorical values section above

RANKING — "which X has highest Y":
• group_by=X, sort_by=Y_field, order="desc", limit=10, bar_chart

TIME TRENDS:
• "monthly/trend/over time" → group_by="month(date_field)", line_chart

Return raw JSON only. No markdown."""

    intent = call_llm(prompt, model=FAST_ROUTER_MODEL)
    if not isinstance(intent, dict):
        raise ValueError(f"Intent returned non-dict: {intent}")

    intent = _fix(intent, fields)

    # Validate action
    if intent.get("action") not in {"aggregate","list","metadata","suggest","recommend"}:
        intent["action"] = "aggregate"

    # Hard override: list
    if is_list and intent.get("action") == "aggregate":
        intent["action"] = "list"
        intent.pop("metric", None)
        intent.pop("group_by", None)
        intent["suggested_charts"] = []

    # Hard override: ranking needs group_by
    if is_rank and intent.get("action") == "aggregate" and not intent.get("group_by"):
        if cat_fields:
            intent["group_by"] = cat_fields[0]
        if not intent.get("sort_by") and intent.get("field"):
            intent["sort_by"] = intent["field"]
        if not intent.get("suggested_charts"):
            intent["suggested_charts"] = ["bar_chart"]

    # Aggregate sanity
    if intent["action"] == "aggregate":
        if not intent.get("field") or intent["field"] not in fields:
            intent["field"] = num_fields[0] if num_fields else fields[0]
        intent.setdefault("metric", "sum")

    return intent