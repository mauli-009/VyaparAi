import pandas as pd
import math
import re


# ─────────────────────────────────────────────────────────────────
# Force numeric — strips dirty chars at runtime
# Fallback for CSVs with ₹, %, commas in numeric columns
# "₹1,099" → 1099.0   "64%" → 64.0   "24,269" → 24269.0
# ─────────────────────────────────────────────────────────────────
def force_numeric(series: pd.Series) -> pd.Series:
    result = pd.to_numeric(series, errors="coerce")
    # if more than 50% NaN, strip dirty chars and retry
    if result.isna().mean() > 0.5:
        cleaned = series.astype(str).apply(
            lambda v: re.sub(r"[^\d.]", "", v.strip())
        )
        result = pd.to_numeric(cleaned, errors="coerce")
    return result


# ─────────────────────────────────────────────────────────────────
# Detect if a field is date-typed
# Checks BOTH the semantic field name AND actual sample values
# so columns like "saleDate" mapped to "transaction_date" work correctly
# ─────────────────────────────────────────────────────────────────
def is_date_field(field: str, series: pd.Series) -> bool:
    date_keywords = ["date", "time", "timestamp", "dt", "day", "month", "year"]
    if any(kw in field.lower() for kw in date_keywords):
        return True
    # scan actual values for date-like patterns
    sample = series.dropna().astype(str).head(5).tolist()
    for val in sample:
        if re.search(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}", val):
            return True
    return False


# ─────────────────────────────────────────────────────────────────
# Apply all filters to dataframe
# Supports: equals, not_equals, greater_than, less_than,
#           greater_or_equal, less_or_equal, between (date + numeric)
# ─────────────────────────────────────────────────────────────────
def apply_filters(df: pd.DataFrame, filters: list, reverse_mapping: dict) -> pd.DataFrame:

    for f in filters:

        field    = f.get("field")
        operator = f.get("operator")
        value    = f.get("value")

        if field not in reverse_mapping:
            continue

        actual_column = reverse_mapping[field]

        if actual_column not in df.columns:
            continue

        # ── Date conversion (checks name AND sample values) ───────
        if is_date_field(field, df[actual_column]):
            df[actual_column] = pd.to_datetime(df[actual_column], errors="coerce")

        # ── equals (substring match, regex-safe) ──────────────────
        if operator == "equals":
            value = str(value).lower().strip()
            df = df[
                df[actual_column]
                .astype(str)
                .str.lower()
                .str.contains(re.escape(value), na=False)
            ]

        # ── not_equals ────────────────────────────────────────────
        elif operator == "not_equals":
            df = df[
                df[actual_column]
                .astype(str)
                .str.lower()
                .str.strip()
                != str(value).lower().strip()
            ]

        # ── greater_than ──────────────────────────────────────────
        elif operator == "greater_than":
            if is_date_field(field, df[actual_column]):
                df = df[df[actual_column] > pd.to_datetime(value)]
            else:
                df = df[force_numeric(df[actual_column]) > float(value)]

        # ── less_than ─────────────────────────────────────────────
        elif operator == "less_than":
            if is_date_field(field, df[actual_column]):
                df = df[df[actual_column] < pd.to_datetime(value)]
            else:
                df = df[force_numeric(df[actual_column]) < float(value)]

        # ── greater_or_equal ──────────────────────────────────────
        elif operator == "greater_or_equal":
            if is_date_field(field, df[actual_column]):
                df = df[df[actual_column] >= pd.to_datetime(value)]
            else:
                df = df[force_numeric(df[actual_column]) >= float(value)]

        # ── less_or_equal ─────────────────────────────────────────
        elif operator == "less_or_equal":
            if is_date_field(field, df[actual_column]):
                df = df[df[actual_column] <= pd.to_datetime(value)]
            else:
                df = df[force_numeric(df[actual_column]) <= float(value)]

        # ── between (date range or numeric range) ─────────────────
        elif operator == "between":
            if isinstance(value, (list, tuple)) and len(value) == 2:
                start, end = value

                if is_date_field(field, df[actual_column]):
                    start = pd.to_datetime(start)
                    end   = pd.to_datetime(end)
                    df = df[
                        (df[actual_column] >= start) &
                        (df[actual_column] <= end)
                    ]
                else:
                    df = df[
                        (force_numeric(df[actual_column]) >= float(start)) &
                        (force_numeric(df[actual_column]) <= float(end))
                    ]

    return df


# ─────────────────────────────────────────────────────────────────
# Apply metric to a series
# ─────────────────────────────────────────────────────────────────
def apply_metric(series: pd.Series, metric: str):
    numeric = force_numeric(series)

    if metric == "sum":
        return numeric.sum()
    elif metric == "avg":
        return numeric.mean()
    elif metric == "count":
        return float(series.count())
    elif metric == "min":
        return numeric.min()
    elif metric == "max":
        return numeric.max()
    else:
        raise ValueError(f"Unsupported metric: '{metric}'")


# ─────────────────────────────────────────────────────────────────
# Map metric names to pandas agg function names
# ─────────────────────────────────────────────────────────────────
def _metric_to_pandas(metric: str) -> str:
    mapping = {
        "sum":   "sum",
        "avg":   "mean",
        "count": "count",
        "min":   "min",
        "max":   "max",
    }
    if metric not in mapping:
        raise ValueError(f"Unsupported metric: '{metric}'")
    return mapping[metric]


# ─────────────────────────────────────────────────────────────────
# Safe float — converts NaN/Inf to 0
# ─────────────────────────────────────────────────────────────────
def safe_float(val) -> float:
    if val is None:
        return 0.0
    f = float(val)
    if math.isnan(f) or math.isinf(f):
        return 0.0
    return f


# ─────────────────────────────────────────────────────────────────
# Group by time period helper
# ─────────────────────────────────────────────────────────────────
def add_period_column(df: pd.DataFrame, date_col: str, period: str) -> pd.DataFrame:
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    if period == "day":
        df["__group__"] = df[date_col].dt.strftime("%Y-%m-%d")
    elif period == "week":
        df["__group__"] = df[date_col].dt.strftime("%Y-W%W")
    elif period == "month":
        df["__group__"] = df[date_col].dt.to_period("M").astype(str)
    elif period == "year":
        df["__group__"] = df[date_col].dt.year.astype(str)
    else:
        df["__group__"] = df[date_col].dt.to_period("M").astype(str)

    return df


# ─────────────────────────────────────────────────────────────────
# Main aggregation runner
# ─────────────────────────────────────────────────────────────────
def run_aggregation(file_path: str, semantic_mapping: dict, intent: dict) -> dict:

    df = pd.read_csv(file_path)

    # reverse_mapping: semantic_key → actual CSV column name
    reverse_mapping = {v: k for k, v in semantic_mapping.items()}

    metric   = intent.get("metric", "count")
    field    = intent.get("field")
    group_by = intent.get("group_by")
    top_n    = intent.get("top_n")
    filters  = intent.get("filters", [])

    available_fields = list(reverse_mapping.keys())

    # ── Validate metric field ─────────────────────────────────────
    if field not in reverse_mapping:
        return {
            "error": f"Semantic field '{field}' not found in this dataset's mapping.",
            "available_fields": available_fields
        }

    actual_column = reverse_mapping[field]

    if actual_column not in df.columns:
        return {
            "error": f"Column '{actual_column}' not found in CSV.",
            "available_columns": df.columns.tolist()
        }

    # ── Validate group_by field exists in this dataset ────────────
    if group_by:
        is_time_group = "transaction_date" in group_by
        is_cat_group  = group_by in reverse_mapping

        if is_time_group:
            date_col = reverse_mapping.get("transaction_date")
            if not date_col or date_col not in df.columns:
                return {
                    "error": f"Cannot group by '{group_by}' — dataset has no transaction_date column.",
                    "available_fields": available_fields
                }
        elif not is_cat_group:
            return {
                "error": f"Cannot group by '{group_by}' — field not mapped in this dataset.",
                "available_fields": available_fields
            }

    # ── Validate filter fields ────────────────────────────────────
    invalid_filter_fields = [
        f.get("field") for f in filters
        if f.get("field") not in reverse_mapping
    ]
    if invalid_filter_fields:
        return {
            "error": f"Filter field(s) {invalid_filter_fields} not found in dataset mapping.",
            "available_fields": available_fields
        }

    # ── Apply filters ─────────────────────────────────────────────
    df = apply_filters(df, filters, reverse_mapping)

    if df.empty:
        return {"results": [], "message": "No rows match the given filters."}

    # ══════════════════════════════════════════════════════════════
    # GROUP BY — time period (day / week / month / year)
    # ══════════════════════════════════════════════════════════════
    if group_by and "transaction_date" in group_by:

        period   = group_by.split("(")[0]
        date_col = reverse_mapping.get("transaction_date")

        df = add_period_column(df, date_col, period)
        df[actual_column] = force_numeric(df[actual_column])

        try:
            result = df.groupby("__group__")[actual_column].agg(_metric_to_pandas(metric))
        except Exception as e:
            return {"error": f"Aggregation failed: {str(e)}"}

        output = [
            {"period": idx, "period_type": period, "value": safe_float(val)}
            for idx, val in result.items()
        ]

        if top_n:
            output = sorted(output, key=lambda x: x["value"], reverse=True)[:top_n]

        return {"results": output, "group_by": group_by}

    # ══════════════════════════════════════════════════════════════
    # GROUP BY — categorical field (region / category / product_name)
    # ══════════════════════════════════════════════════════════════
    elif group_by and group_by in reverse_mapping:

        group_col = reverse_mapping[group_by]
        df[actual_column] = force_numeric(df[actual_column])

        try:
            result = df.groupby(group_col)[actual_column].agg(_metric_to_pandas(metric))
        except Exception as e:
            return {"error": f"Aggregation failed: {str(e)}"}

        output = [
            {"group": str(idx), "value": safe_float(val)}
            for idx, val in result.items()
        ]

        output = sorted(output, key=lambda x: x["value"], reverse=True)
        if top_n:
            output = output[:top_n]

        return {"results": output, "group_by": group_by}

    # ══════════════════════════════════════════════════════════════
    # NO GROUP BY — single aggregated value
    # ══════════════════════════════════════════════════════════════
    else:

        try:
            value = apply_metric(df[actual_column], metric)
        except ValueError as e:
            return {"error": str(e)}

        return {"results": [{"value": safe_float(value)}]}