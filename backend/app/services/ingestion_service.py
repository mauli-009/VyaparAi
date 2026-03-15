import pandas as pd
import re


# ─────────────────────────────────────────────────────────────────
# Check if a series has a string-like dtype
# Catches both legacy "object" and newer pandas "StringDtype"
# ─────────────────────────────────────────────────────────────────
def is_string_dtype(series: pd.Series) -> bool:
    return series.dtype == object or pd.api.types.is_string_dtype(series)


# ─────────────────────────────────────────────────────────────────
# Detect dirty numeric column
#
# A column is dirty numeric if:
#   1. Values are mostly parseable as numbers after stripping symbols
#   2. Values have non-numeric characters (₹, %, ,)
#   3. At least 60% of characters in original values are digits
#      ← This prevents ID columns like "B07JW9H4J1" from being cleaned
#
# Correctly cleans:  "₹399"   "₹1,099"  "64%"   "24,269"
# Correctly skips:   "B07JW9H4J1"  "B098NS6PVG"  (product IDs)
#                    "Wayona Nylon" "Electronics"  (text)
# ─────────────────────────────────────────────────────────────────
def looks_dirty_numeric(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(10).tolist()
    if not sample:
        return False

    numeric_after_strip = 0
    has_dirt = 0

    for val in sample:
        val = val.strip()
        stripped = re.sub(r"[^\d.]", "", val)

        if stripped and re.match(r"^\d+\.?\d*$", stripped):
            # Check digit ratio of original value
            # "₹1,099" → 4 digits out of 6 chars = 0.66  ✅ dirty numeric
            # "B07JW9H4J1" → 5 digits out of 10 chars = 0.50 ❌ alphanumeric ID
            # "64%" → 2 digits out of 3 chars = 0.66  ✅ dirty numeric
            digit_ratio = sum(c.isdigit() for c in val) / len(val)
            if digit_ratio >= 0.6:
                numeric_after_strip += 1

        # has non-numeric characters at all
        if re.search(r"[^\d.\s]", val):
            has_dirt += 1

    return (
        numeric_after_strip >= len(sample) * 0.7 and
        has_dirt >= len(sample) * 0.5
    )


# ─────────────────────────────────────────────────────────────────
# Clean a single dirty numeric value
# Strips currency symbols, commas, percent signs → float
#
# "₹1,099" → 1099.0
# "64%"    → 64.0
# "24,269" → 24269.0
# ─────────────────────────────────────────────────────────────────
def clean_numeric_value(val) -> float | None:
    if pd.isna(val):
        return None
    cleaned = re.sub(r"[^\d.]", "", str(val).strip())
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────
# Scan all columns and clean dirty numeric ones
# Returns cleaned dataframe + list of which columns were cleaned
# ─────────────────────────────────────────────────────────────────
def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    cleaned_columns = []

    for col in df.columns:
        if is_string_dtype(df[col]) and looks_dirty_numeric(df[col]):
            df[col] = df[col].apply(clean_numeric_value)
            cleaned_columns.append(col)

    return df, cleaned_columns


# ─────────────────────────────────────────────────────────────────
# Main entry point called by upload route
# ─────────────────────────────────────────────────────────────────
def extract_metadata(file_path: str) -> dict:
    df = pd.read_csv(file_path)

    # ── Auto-clean dirty numeric columns ─────────────────────────
    # e.g. "₹399" → 399.0, "64%" → 64.0, "24,269" → 24269.0
    # ID columns like "B07JW9H4J1" are correctly skipped
    # Cleaned CSV saved back to disk so aggregation reads clean data
    df, cleaned_columns = clean_dataframe(df)

    if cleaned_columns:
        df.to_csv(file_path, index=False)

    # ── Extract metadata ──────────────────────────────────────────
    columns = df.columns.tolist()

    column_types = {col: str(df[col].dtype) for col in df.columns}

    preview_rows = (
        df.head(5)
        .astype(object)
        .where(df.head(5).notna(), None)
        .to_dict(orient="records")
    )

    return {
        "columns": columns,
        "column_types": column_types,
        "preview_rows": preview_rows,
        "cleaned_columns": cleaned_columns
    }