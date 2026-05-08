"""
aggregation_service.py

Handles all numeric aggregations: single values, categorical breakdowns, and time-series.
"""
from __future__ import annotations

import math
import re

import pandas as pd
from rapidfuzz import fuzz


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    return str(s).lower().replace(" ", "").replace("_", "").replace("-", "").strip()


def _fuzzy_reverse_lookup(
    semantic_key: str,
    reverse_mapping: dict[str, str],
    threshold: int = 68,
) -> str | None:
    """
    Find the actual CSV column that best matches semantic_key.
    Tries exact, then clean-exact, then fuzzy ratio.
    """
    if semantic_key in reverse_mapping:
        return reverse_mapping[semantic_key]

    clean_key = _clean(semantic_key)
    for skey, col in reverse_mapping.items():
        if _clean(skey) == clean_key:
            return col

    best_score, best_col = 0, None
    for skey, col in reverse_mapping.items():
        score = fuzz.ratio(clean_key, _clean(skey))
        if score > best_score:
            best_score, best_col = score, col

    return best_col if best_score >= threshold else None


def force_numeric(series: pd.Series) -> pd.Series:
    """Coerce to numeric; if >50% NaN after first pass, strip dirty chars and retry."""
    result = pd.to_numeric(series, errors="coerce")
    if result.isna().mean() > 0.5:
        cleaned = series.astype(str).apply(
            lambda v: re.sub(r"[^\d.]", "", v.strip())
        )
        result = pd.to_numeric(cleaned, errors="coerce")
    return result


def is_date_field(field: str, series: pd.Series) -> bool:
    date_keywords = ["date", "time", "timestamp", "dt", "day", "month", "year"]
    if any(kw in field.lower() for kw in date_keywords):
        return True
    sample = series.dropna().astype(str).head(5).tolist()
    for val in sample:
        if re.search(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}", val):
            return True
    return False


def safe_float(val) -> float:
    if val is None:
        return 0.0
    try:
        f = float(val)
        return 0.0 if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return 0.0


def _metric_to_pandas(metric: str) -> str:
    return {"sum": "sum", "avg": "mean", "count": "count", "min": "min", "max": "max"}.get(
        metric, "sum"
    )


# ─────────────────────────────────────────────────────────────────
# Filter application
# ─────────────────────────────────────────────────────────────────

def apply_filters(
    df: pd.DataFrame,
    filters: list[dict],
    reverse_mapping: dict[str, str],
) -> pd.DataFrame:
    """Apply all intent filters to the dataframe."""

    # Normalise operator to symbolic form
    _op_norm = {
        "==": "==", "=": "==", "equals": "==", "eq": "==",
        "!=": "!=", "not_equals": "!=", "ne": "!=",
        ">": ">",  "greater_than": ">",  "gt": ">",
        "<": "<",  "less_than": "<",     "lt": "<",
        ">=": ">=","greater_or_equal": ">=","gte": ">=","ge": ">=",
        "<=": "<=","less_or_equal": "<=", "lte": "<=","le": "<=",
    }

    for f in filters:
        field    = str(f.get("field", ""))
        operator = _op_norm.get(str(f.get("operator", "==")).lower().strip(), str(f.get("operator", "==")).lower().strip())
        value    = f.get("value")

        if not field:
            continue

        actual_col = _fuzzy_reverse_lookup(field, reverse_mapping)
        if not actual_col or actual_col not in df.columns:
            print(f"[AGG] Skipping filter — unmapped field: '{field}'")
            continue

        # Date normalisation
        if is_date_field(field, df[actual_col]):
            df[actual_col] = pd.to_datetime(df[actual_col], errors="coerce")

        try:
            # ── String equality (==) ──────────────────────────────
            if operator == "==":
                val_str = str(value).lower().strip()
                df = df[
                    df[actual_col].astype(str).str.lower().str.strip()
                    .str.contains(re.escape(val_str), na=False)
                ]

            # ── String inequality (!=) ────────────────────────────
            elif operator == "!=":
                val_str = str(value).lower().strip()
                df = df[
                    df[actual_col].astype(str).str.lower().str.strip() != val_str
                ]

            # ── Numeric / date comparisons ─────────────────────────
            elif operator in (">", "<", ">=", "<="):
                if is_date_field(field, df[actual_col]):
                    ts = pd.to_datetime(value)
                    if operator == ">":  df = df[df[actual_col] > ts]
                    elif operator == "<": df = df[df[actual_col] < ts]
                    elif operator == ">=": df = df[df[actual_col] >= ts]
                    elif operator == "<=": df = df[df[actual_col] <= ts]
                else:
                    num_series = force_numeric(df[actual_col])
                    num_val = float(str(value).replace(",", "").replace("$", "").strip())
                    if operator == ">":  df = df[num_series > num_val]
                    elif operator == "<": df = df[num_series < num_val]
                    elif operator == ">=": df = df[num_series >= num_val]
                    elif operator == "<=": df = df[num_series <= num_val]

            # ── Between ───────────────────────────────────────────
            elif operator == "between":
                if isinstance(value, (list, tuple)) and len(value) == 2:
                    start, end = value
                    if is_date_field(field, df[actual_col]):
                        df = df[
                            (df[actual_col] >= pd.to_datetime(start))
                            & (df[actual_col] <= pd.to_datetime(end))
                        ]
                    else:
                        num = force_numeric(df[actual_col])
                        df = df[(num >= float(start)) & (num <= float(end))]

            # ── In (membership) ───────────────────────────────────
            elif operator == "in":
                if isinstance(value, (list, tuple)) and len(value) > 0:
                    lowered = [str(v).lower().strip() for v in value]
                    col_lower = df[actual_col].astype(str).str.lower().str.strip()
                    df = df[col_lower.isin(lowered)]
                elif isinstance(value, str):
                    # If LLM returned a string instead of list, treat as ==
                    val_str = value.lower().strip()
                    df = df[
                        df[actual_col].astype(str).str.lower().str.strip()
                        .str.contains(re.escape(val_str), na=False)
                    ]

        except Exception as e:
            print(f"[AGG] Filter error on field='{field}', op='{operator}', val={value!r}: {e}")

    return df


# ─────────────────────────────────────────────────────────────────
# Time period grouping
# ─────────────────────────────────────────────────────────────────

def add_period_column(df: pd.DataFrame, date_col: str, period: str) -> pd.DataFrame:
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    # Access .dt ONCE on the Series — do NOT nest inside a lambda that also calls .dt
    col = df[date_col]
    if period == "day":
        df["__group__"] = col.dt.strftime("%Y-%m-%d")
    elif period == "week":
        df["__group__"] = col.dt.strftime("%Y-W%W")
    elif period == "month":
        df["__group__"] = col.dt.to_period("M").astype(str)
    elif period == "quarter":
        df["__group__"] = col.dt.to_period("Q").astype(str)
    elif period == "year":
        df["__group__"] = col.dt.year.astype(str)
    else:
        df["__group__"] = col.dt.to_period("M").astype(str)  # default: monthly

    return df


def _parse_time_group_by(group_by: str) -> tuple[str, str] | None:
    """
    Parse "month(transaction_date)" → ("month", "transaction_date").
    Also handles bare "transaction_date" → ("month", "transaction_date").
    Returns None if not a time expression.
    """
    g = group_by.lower().strip()

    # Format: "period(field)"
    m = re.match(r"^(\w+)\((.+)\)$", g)
    if m:
        period, inner_field = m.group(1), m.group(2)
        if period in ("day", "week", "month", "quarter", "year"):
            return period, inner_field

    # Bare date field — default to monthly
    if any(kw in g for kw in ["date", "time", "timestamp"]):
        return "month", g

    return None


# ─────────────────────────────────────────────────────────────────
# Single metric application
# ─────────────────────────────────────────────────────────────────

def apply_metric(series: pd.Series, metric: str) -> float:
    numeric = force_numeric(series)
    ops = {
        "sum":   lambda s: s.sum(),
        "avg":   lambda s: s.mean(),
        "count": lambda s: float(series.count()),  # count non-null of original
        "min":   lambda s: s.min(),
        "max":   lambda s: s.max(),
    }
    fn = ops.get(metric)
    if fn is None:
        raise ValueError(f"Unsupported metric: '{metric}'")
    return fn(numeric)


# ─────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────

def run_aggregation(file_path: str, semantic_mapping: dict, intent: dict) -> dict:
    df = pd.read_csv(file_path)
    # Strip BOM / whitespace from CSV headers
    df.columns = df.columns.str.strip().str.lstrip("\ufeff")

    # semantic_key → actual CSV column
    reverse_mapping: dict[str, str] = {v: k for k, v in semantic_mapping.items()}
    available_fields = list(reverse_mapping.keys())

    metric   = intent.get("metric", "count")
    field    = intent.get("field")
    group_by = intent.get("group_by")
    filters  = intent.get("filters", [])
    top_n    = intent.get("top_n")

    # ── Validate metric field ─────────────────────────────────────
    actual_column = _fuzzy_reverse_lookup(field, reverse_mapping)
    if not actual_column:
        return {
            "error": f"Field '{field}' not found in this dataset. "
                     f"Available: {available_fields}",
            "available_fields": available_fields,
        }
    if actual_column not in df.columns:
        return {
            "error": f"Column '{actual_column}' not found in CSV. "
                     f"CSV columns: {df.columns.tolist()}",
        }

    # ── Apply filters ─────────────────────────────────────────────
    df = apply_filters(df, filters, reverse_mapping)

    if df.empty:
        return {"results": [], "message": "No rows match the given filters."}

    # ═════════════════════════════════════════════════════════════
    # TIME-BASED GROUP BY
    # ═════════════════════════════════════════════════════════════
    time_parsed = _parse_time_group_by(group_by) if group_by else None

    if time_parsed:
        period, inner_field = time_parsed

        # Resolve actual date column via fuzzy lookup
        date_col = _fuzzy_reverse_lookup(inner_field, reverse_mapping, threshold=55)
        if not date_col:
            # Try finding any date-looking column
            for skey, col in reverse_mapping.items():
                if is_date_field(skey, df[col]):
                    date_col = col
                    break

        if not date_col or date_col not in df.columns:
            return {
                "error": f"Cannot group by time — no date column found in mapping.",
                "available_fields": available_fields,
            }

        df = add_period_column(df, date_col, period)
        df[actual_column] = force_numeric(df[actual_column])

        try:
            result = df.groupby("__group__")[actual_column].agg(_metric_to_pandas(metric))
        except Exception as e:
            return {"error": f"Time aggregation failed: {str(e)}"}

        output = [
            {"period": str(idx), "period_type": period, "value": safe_float(val)}
            for idx, val in result.sort_index().items()
        ]

        # Apply top_n after sort by value if requested
        if top_n:
            output = sorted(output, key=lambda x: x["value"], reverse=True)[: int(top_n)]

        return {"results": output, "group_by": group_by}

    # ═════════════════════════════════════════════════════════════
    # CATEGORICAL GROUP BY
    # ═════════════════════════════════════════════════════════════
    elif group_by:
        group_col = _fuzzy_reverse_lookup(group_by, reverse_mapping)
        if not group_col or group_col not in df.columns:
            return {
                "error": f"Cannot group by '{group_by}' — not found in dataset.",
                "available_fields": available_fields,
            }

        df[actual_column] = force_numeric(df[actual_column])

        try:
            result = df.groupby(group_col)[actual_column].agg(_metric_to_pandas(metric))
        except Exception as e:
            return {"error": f"Categorical aggregation failed: {str(e)}"}

        output = sorted(
            [{"group": str(idx), "value": safe_float(val)} for idx, val in result.items()],
            key=lambda x: x["value"],
            reverse=True,
        )
        if top_n:
            output = output[: int(top_n)]

        return {"results": output, "group_by": group_by}

    # ═════════════════════════════════════════════════════════════
    # NO GROUP BY — single aggregated value
    # ═════════════════════════════════════════════════════════════
    else:
        try:
            value = apply_metric(df[actual_column], metric)
        except ValueError as e:
            return {"error": str(e)}

        return {"results": [{"value": safe_float(value)}]}