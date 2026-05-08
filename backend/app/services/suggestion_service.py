"""
suggestion_service.py

Generates AI-powered business suggestions and product/category recommendations
using the smart LLM model.
"""
from __future__ import annotations

import pandas as pd
from app.services.llm_service import call_llm_text


# ─────────────────────────────────────────────────────────────────
# General business suggestions  (action = "suggest")
# ─────────────────────────────────────────────────────────────────

def generate_suggestions(
    question: str,
    intent: dict,
    result: dict,
    language: str = "English",
    complexity: str = "Executive",
) -> list:
    results = result.get("results", [])
    if not results:
        return []

    result_summary = _summarize_result(intent, results)
    field  = intent.get("field", "").replace("_", " ")
    metric = intent.get("metric", "")

    prompt = f"""You are a senior business strategist advising a small/medium enterprise owner.

User's business question: "{question}"
Metric analysed: {metric} of {field}

Data summary:
{result_summary}

OUTPUT LANGUAGE: {language}
EXPLANATION STYLE: {complexity}

CRITICAL RULES:
1. Every suggestion MUST reference specific numbers from the data above.
2. If style is "Simple", use plain language + analogies, but keep ALL numbers.
3. ALL JSON keys must remain in English. Only translate values/text fields.
4. Be actionable — vague advice is useless to an SME owner.

Generate exactly 3 prioritised business suggestions. Return a JSON array:
[
  {{
    "title":          "5-8 word punchy title",
    "insight":        "What the data specifically reveals (1-2 sentences, cite numbers)",
    "action":         "The single most important action to take right now",
    "execution_plan": [
      "Step 1: [specific action] by [timeline]",
      "Step 2: [specific action] by [timeline]",
      "Step 3: [specific action] by [timeline]"
    ],
    "expected_impact": "Quantified outcome: e.g. 'Estimated 15-20% revenue uplift in 90 days'",
    "priority":        "high | medium | low"
  }}
]

Order by priority (high first). JSON only. No markdown."""

    try:
        suggestions = call_llm_text(prompt, expect_json=True)
        if isinstance(suggestions, list):
            return suggestions[:3]
        return []
    except Exception as exc:
        print(f"[SUGGEST] Failed: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────
# Product / category recommendation  (action = "recommend")
# ─────────────────────────────────────────────────────────────────

def generate_product_recommendation(
    question: str,
    file_path: str,
    semantic_mapping: dict,
    language: str = "English",
    complexity: str = "Executive",
) -> dict:
    """
    Reads the CSV, computes composite per-product scores,
    and asks the LLM for ranked recommendations.
    """
    try:
        df = pd.read_csv(file_path)
    except Exception as exc:
        return {"error": f"Could not read data: {exc}"}

    reverse = {v: k for k, v in semantic_mapping.items()}

    product_col = _find_col(reverse, ["item_type", "product", "product_name", "category", "item", "item_name"])
    revenue_col = _find_col(reverse, ["total_revenue", "revenue", "price", "sales", "gross_sales"])
    profit_col  = _find_col(reverse, ["total_profit", "profit", "net_profit", "margin"])
    units_col   = _find_col(reverse, ["units_sold", "quantity", "units", "qty"])

    if not product_col:
        return {"error": "No product or category column found in the dataset."}
    if product_col not in df.columns:
        return {"error": f"Column '{product_col}' not found in CSV."}

    # ── Per-product stats ─────────────────────────────────────────
    group = df.groupby(product_col)
    stats: dict[str, pd.Series] = {"order_count": group.size()}

    def add_numeric_stat(col: str | None, key_prefix: str) -> None:
        if col and col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            stats[f"total_{key_prefix}"] = group[col].sum()
            stats[f"avg_{key_prefix}"]   = group[col].mean()

    add_numeric_stat(revenue_col, "revenue")
    add_numeric_stat(profit_col,  "profit")
    add_numeric_stat(units_col,   "units")

    if len(stats) <= 1:
        return {"error": "No numeric columns found to rank products."}

    summary_df = pd.DataFrame(stats).fillna(0)

    # ── Composite score (normalised mean across all stats) ─────────
    for col in list(summary_df.columns):
        col_max = summary_df[col].max()
        summary_df[f"_n_{col}"] = summary_df[col] / col_max if col_max > 0 else 0.0

    norm_cols = [c for c in summary_df.columns if c.startswith("_n_")]
    summary_df["score"] = summary_df[norm_cols].mean(axis=1) * 100
    summary_df = summary_df.sort_values("score", ascending=False)

    # ── Format for LLM ────────────────────────────────────────────
    products_text = ""
    for product, row in summary_df.head(10).iterrows():
        line = f"\n  • {product} | Score: {row['score']:.1f}/100"
        if "total_revenue" in row: line += f" | Revenue: {row['total_revenue']:,.0f}"
        if "total_profit"  in row: line += f" | Profit:  {row['total_profit']:,.0f}"
        if "total_units"   in row: line += f" | Units:   {row['total_units']:,.0f}"
        if "order_count"   in row: line += f" | Orders:  {row['order_count']:,.0f}"
        products_text += line

    prompt = f"""You are a senior business analyst advising an SME owner.

User question: "{question}"

Products ranked by composite score (revenue + profit + units + order volume):
{products_text}

OUTPUT LANGUAGE: {language}
EXPLANATION STYLE: {complexity}

CRITICAL RULES:
1. Cite actual numbers (score, revenue, profit) in every "why" explanation.
2. If style is "Simple", use analogies but keep all numbers.
3. ALL JSON keys stay in English — only translate text values.
4. Be specific about WHY each product ranks where it does.

Return the top 3 products. JSON:
{{
  "ranked_products": [
    {{
      "rank": 1,
      "product": "<name>",
      "score": <number>,
      "why": "2-3 sentences citing actual numbers explaining the ranking",
      "long_term_outlook": "Trend / sustainability analysis in 1-2 sentences",
      "suggested_action": "Single most important action for this product",
      "execution_plan": [
        "Step 1: [action] by [timeline]",
        "Step 2: [action] by [timeline]",
        "Step 3: [action] by [timeline]"
      ],
      "priority": "high | medium | low"
    }}
  ],
  "top_pick": "<product name>",
  "top_pick_reason": "One sentence on why this is the best long-term bet"
}}

JSON only. No markdown."""

    try:
        result = call_llm_text(prompt, expect_json=True)
        if isinstance(result, dict):
            # Attach raw stats for transparency in the frontend
            display_cols = [c for c in summary_df.columns if not c.startswith("_n_")]
            result["raw_stats"] = (
                summary_df.head(10)[display_cols]
                .reset_index()
                .to_dict(orient="records")
            )
            return result
        return {"error": "LLM returned unexpected format"}
    except Exception as exc:
        return {"error": str(exc)}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _find_col(reverse_mapping: dict, candidates: list[str]) -> str | None:
    for key in candidates:
        if key in reverse_mapping:
            return reverse_mapping[key]
    return None


def _summarize_result(intent: dict, results: list) -> str:
    """
    Build a human-readable data summary for LLM context.
    Handles single values, time-series ("period" key), and categorical ("group" key).
    """
    field  = intent.get("field", "value").replace("_", " ")
    metric = intent.get("metric", "")

    # ── Single value ──────────────────────────────────────────────
    if len(results) == 1 and "value" in results[0]:
        val     = results[0]["value"]
        filters = intent.get("filters", [])
        filter_str = (
            " (filtered by " + ", ".join(
                f"{f['field']} {f['operator']} {f['value']}" for f in filters
            ) + ")"
            if filters else ""
        )
        return f"{metric} of {field}{filter_str} = {val:,.2f}"

    # ── Multi-row (time or categorical) ───────────────────────────
    values = [r.get("value", 0) for r in results]
    total  = sum(values)
    avg    = total / len(values) if values else 0

    lines = [
        f"Total: {total:,.2f} | Average per group: {avg:,.2f} | "
        f"Max: {max(values):,.2f} | Min: {min(values):,.2f}",
        "",
        "Breakdown (top 20 shown):",
    ]

    sorted_rows = sorted(results, key=lambda r: r.get("value", 0), reverse=True)
    for row in sorted_rows[:20]:
        # Support "period", "group", "month", "category", "region" label keys
        label = (
            row.get("period")
            or row.get("group")
            or row.get("month")
            or row.get("category")
            or row.get("region")
            or next((v for v in row.values() if isinstance(v, str)), "?")
        )
        val = row.get("value", 0)
        pct = (val / total * 100) if total > 0 else 0
        lines.append(f"  {label}: {val:,.2f} ({pct:.1f}%)")

    return "\n".join(lines)