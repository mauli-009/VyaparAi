import pandas as pd
from app.services.llm_service import call_llm_text


# ─────────────────────────────────────────────
# General business suggestions (for "both" / "suggestion" queries)
# ─────────────────────────────────────────────
def generate_suggestions(question: str, intent: dict, result: dict, language: str = "English", complexity: str = "Executive") -> list:
    results = result.get("results", [])
    if not results:
        return []

    result_summary = _summarize_result(intent, results)
    field = intent.get("field", "").replace("_", " ")
    metric = intent.get("metric", "")

    prompt = f"""
You are a senior business strategist.

User asked: "{question}"
Metric: {metric} of {field}
Data:
{result_summary}

LANGUAGE & COMPLEXITY SETTINGS:
- Output Language: {language}
- Explanation Style: {complexity}
- CRITICAL RULE: If the style is "Simple", DO NOT omit any details, metrics, or numbers. You must explain the exact same data using easier-to-understand terms and analogies.
- CRITICAL RULE 2: Ensure ALL JSON keys remain exactly as written below in English. ONLY translate the content values.

Generate exactly 3 business suggestions. Each must be:
- Based directly on the actual numbers
- Specific — mention real values from the data
- Include a step-by-step execution plan
- Include expected impact with estimated numbers

Return a JSON array of exactly 3 objects:
[
  {{
    "title": "5-8 word title",
    "insight": "1-2 sentences on what the data shows",
    "action": "Core recommendation in 1 sentence",
    "execution_plan": [
      "Step 1: specific action with timeline",
      "Step 2: specific action with timeline",
      "Step 3: specific action with timeline"
    ],
    "expected_impact": "Specific outcome with estimated numbers",
    "priority": "high | medium | low"
  }}
]

JSON only. No markdown.
"""

    try:
        suggestions = call_llm_text(prompt, expect_json=True)
        if isinstance(suggestions, list):
            return suggestions[:3]
        return []
    except Exception:
        return []


# ─────────────────────────────────────────────
# Product / category recommendation
# (for "which product should I choose" type queries)
# ─────────────────────────────────────────────
def generate_product_recommendation(
    question: str,
    file_path: str,
    semantic_mapping: dict,
    language: str = "English",
    complexity: str = "Executive",
) -> dict:
    """
    Reads the actual CSV, computes per-product metrics,
    ranks them, and returns structured recommendations.
    """

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return {"error": f"Could not read data: {str(e)}"}

    # Find the product/category column and revenue/profit column from mapping
    reverse = {v: k for k, v in semantic_mapping.items()}

    product_col = _find_col(reverse, ["item_type", "product", "product_name", "category", "item"])
    revenue_col = _find_col(reverse, ["total_revenue", "revenue", "price", "sales"])
    profit_col  = _find_col(reverse, ["total_profit", "profit"])
    units_col   = _find_col(reverse, ["units_sold", "quantity", "units"])

    if not product_col:
        return {"error": "No product or category column found in the dataset."}

    if product_col not in df.columns:
        return {"error": f"Column '{product_col}' not found in CSV."}

    # Build per-product stats
    group = df.groupby(product_col)
    stats = {}

    if revenue_col and revenue_col in df.columns:
        df[revenue_col] = pd.to_numeric(df[revenue_col], errors="coerce")
        stats["total_revenue"] = group[revenue_col].sum()
        stats["avg_revenue"]   = group[revenue_col].mean()

    if profit_col and profit_col in df.columns:
        df[profit_col] = pd.to_numeric(df[profit_col], errors="coerce")
        stats["total_profit"] = group[profit_col].sum()

    if units_col and units_col in df.columns:
        df[units_col] = pd.to_numeric(df[units_col], errors="coerce")
        stats["total_units"] = group[units_col].sum()

    stats["order_count"] = group.size()

    if not stats:
        return {"error": "No numeric columns found to rank products."}

    summary_df = pd.DataFrame(stats).fillna(0)

    # Normalize and compute a composite score
    for col in summary_df.columns:
        col_max = summary_df[col].max()
        if col_max > 0:
            summary_df[f"_norm_{col}"] = summary_df[col] / col_max
        else:
            summary_df[f"_norm_{col}"] = 0

    norm_cols = [c for c in summary_df.columns if c.startswith("_norm_")]
    summary_df["score"] = summary_df[norm_cols].mean(axis=1) * 100

    summary_df = summary_df.sort_values("score", ascending=False)

    # Build readable product data for LLM
    products_text = ""
    for product, row in summary_df.head(10).iterrows():
        line = f"\n  Product: {product} | Score: {row['score']:.1f}/100"
        if "total_revenue" in row: line += f" | Revenue: {row['total_revenue']:,.0f}"
        if "total_profit"  in row: line += f" | Profit: {row['total_profit']:,.0f}"
        if "total_units"   in row: line += f" | Units: {row['total_units']:,.0f}"
        if "order_count"   in row: line += f" | Orders: {row['order_count']:,.0f}"
        products_text += line

    prompt = f"""
You are a senior business analyst. A user asked: "{question}"

Here are the top products ranked by a composite score (revenue + profit + units + orders):
{products_text}

LANGUAGE & COMPLEXITY SETTINGS:
- Output Language: {language}
- Explanation Style: {complexity}
- CRITICAL RULE: If the style is "Simple", DO NOT omit any details, metrics, or numbers. You must explain the exact same data using easier-to-understand terms and analogies.
- CRITICAL RULE 2: Ensure ALL JSON keys remain exactly as written below in English. ONLY translate the content values.

Here are the top products ranked by a composite score (revenue + profit + units + orders):
{products_text}

Based on this data, provide:
1. The TOP 3 recommended products with full reasoning
2. For each product, explain WHY it's recommended using the actual numbers
3. A suggestion on what to do with the #1 product

Return JSON:
{{
  "ranked_products": [
    {{
      "rank": 1,
      "product": "<name>",
      "score": <number>,
      "why": "2-3 sentences explaining why this product is recommended using actual numbers",
      "long_term_outlook": "1-2 sentences on long-term potential",
      "suggested_action": "Specific action to take for this product",
      "execution_plan": [
        "Step 1: specific action with timeline",
        "Step 2: specific action with timeline",
        "Step 3: specific action with timeline"
      ],
      "priority": "high | medium | low"
    }}
  ],
  "top_pick": "<product name>",
  "top_pick_reason": "1 sentence summary of why this is the best long-term choice"
}}

JSON only. No markdown.
"""

    try:
        result = call_llm_text(prompt, expect_json=True)
        if isinstance(result, dict):
            # Also attach raw stats for frontend display
            result["raw_stats"] = summary_df.head(10)[
                [c for c in summary_df.columns if not c.startswith("_norm_")]
            ].reset_index().to_dict(orient="records")
            return result
        return {"error": "LLM returned unexpected format"}
    except Exception as e:
        return {"error": str(e)}


def _find_col(reverse_mapping: dict, candidates: list):
    """Find the first matching actual column from a list of semantic key candidates."""
    for key in candidates:
        if key in reverse_mapping:
            return reverse_mapping[key]
    return None


def _summarize_result(intent: dict, results: list) -> str:
    if len(results) == 1 and "value" in results[0]:
        field = intent.get("field", "value").replace("_", " ")
        metric = intent.get("metric", "")
        val = results[0]["value"]
        filters = intent.get("filters", [])
        filter_str = ""
        if filters:
            filter_str = " for " + ", ".join(f"{f['field']} = {f['value']}" for f in filters)
        return f"{metric} of {field}{filter_str} = {val:,.2f}"

    values = [r.get("value", 0) for r in results]
    total = sum(values)
    avg = total / len(values) if values else 0
    lines = [
        f"Total: {total:,.2f} | Average: {avg:,.2f} | "
        f"Max: {max(values):,.2f} | Min: {min(values):,.2f}",
        "", "Breakdown:"
    ]
    sorted_rows = sorted(results, key=lambda r: r.get("value", 0), reverse=True)
    for row in sorted_rows[:20]:
        label = (
            row.get("month") or row.get("category") or row.get("region")
            or row.get("group") or next((v for v in row.values() if isinstance(v, str)), "?")
        )
        pct = (row.get("value", 0) / total * 100) if total > 0 else 0
        lines.append(f"  {label}: {row.get('value', 0):,.2f} ({pct:.1f}%)")

    return "\n".join(lines)