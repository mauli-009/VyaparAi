import pandas as pd
import re

def clean_string(s):
    """Removes all spaces, underscores, and makes lowercase for perfect fuzzy matching."""
    return str(s).lower().replace(" ", "").replace("_", "").strip()

def run_retrieval(file_path: str, mapping: dict, intent: dict) -> list:
    df = pd.read_csv(file_path)
    
    # 1. Strip invisible BOM characters and spaces from CSV headers
    df.columns = df.columns.str.replace(r'^\xef\xbb\xbf', '', regex=True).str.strip()

    # 2. Extract safely
    filters = intent.get("filters", intent.get("Filters", []))
    limit = intent.get("limit", intent.get("Limit", 15))
    sort_by = intent.get("sort_by", intent.get("Sort_by"))
    order = intent.get("order", intent.get("Order", "desc"))
    
    # NEW: Extract the "select" array to know exactly which columns the user wants
    select_fields = intent.get("select", ["*"]) 

    # Map semantic keys back to actual CSV columns using super-fuzzy matching
    reverse_mapping = {clean_string(v): str(k).strip() for k, v in mapping.items()}
    applied_filters = 0

    op_map = {
        "greater_or_equal": ">=",
        "greater_than": ">",
        "less_or_equal": "<=",
        "less_than": "<",
        "equals": "==",
        "not_equals": "!="
    }

    # 3. Apply Filters Aggressively
    for f in filters:
        semantic_field = str(f.get("field", f.get("Field", "")))
        raw_op = str(f.get("operator", f.get("Operator", ""))).strip().lower()
        operator = op_map.get(raw_op, raw_op)
        value = f.get("value", f.get("Value", ""))

        clean_semantic = clean_string(semantic_field)
        actual_col = reverse_mapping.get(clean_semantic, semantic_field)

        # Fallback: Super fuzzy column match
        if actual_col not in df.columns:
            col_matches = [c for c in df.columns if clean_string(c) == clean_semantic]
            if col_matches:
                actual_col = col_matches[0]
            else:
                continue

        try:
            # NUMERIC MATH
            if operator in [">", "<", ">=", "<="]:
                clean_series = df[actual_col].astype(str).str.replace(r'[$, ]', '', regex=True)
                num_series = pd.to_numeric(clean_series, errors='coerce')
                num_val = float(str(value).replace(',', '').replace('$', '').strip())
                
                if operator == ">": df = df[num_series > num_val]
                elif operator == "<": df = df[num_series < num_val]
                elif operator == ">=": df = df[num_series >= num_val]
                elif operator == "<=": df = df[num_series <= num_val]
                applied_filters += 1
            
            # STRING MATCHING
            else:
                val_str = str(value).strip().lower()
                col_str = df[actual_col].astype(str).str.strip().str.lower()
                
                if operator in ["==", "contains", "in"]:
                    df = df[col_str.str.contains(re.escape(val_str), case=False, na=False)]
                    applied_filters += 1
                elif operator in ["!=", "not_contains"]:
                    df = df[~col_str.str.contains(re.escape(val_str), case=False, na=False)]
                    applied_filters += 1

        except Exception as e:
            print(f"[ERROR] Failed on filter {f}: {e}")

    # 4. Apply Sorting
    if sort_by:
        clean_sort = clean_string(sort_by)
        actual_sort = reverse_mapping.get(clean_sort, sort_by)
        if actual_sort not in df.columns:
            sort_matches = [c for c in df.columns if clean_string(c) == clean_sort]
            if sort_matches: actual_sort = sort_matches[0]
            
        if actual_sort in df.columns:
            df = df.sort_values(by=actual_sort, ascending=(order == "asc"))

    # == NEW: 5. Apply Column Slicing (Drop columns the user didn't ask for) ==
    if not isinstance(select_fields, list):
        select_fields = ["*"]

    # If the user asked for specific fields (not just "*")
    if "*" not in select_fields and len(select_fields) > 0:
        actual_select_cols = []
        for field in select_fields:
            clean_sel = clean_string(field)
            actual_col = reverse_mapping.get(clean_sel, field)
            
            # Fuzzy match fallback for the select columns
            if actual_col not in df.columns:
                col_matches = [c for c in df.columns if clean_string(c) == clean_sel]
                if col_matches: 
                    actual_col = col_matches[0]
            
            # Only add the column if it actually exists in the CSV and isn't a duplicate
            if actual_col in df.columns and actual_col not in actual_select_cols:
                actual_select_cols.append(actual_col)
                
        # If we successfully found the exact columns, slice the dataframe!
        if actual_select_cols:
            df = df[actual_select_cols]

    # 6. Limit and safely clean NaNs
    df = df.head(int(limit))
    df = df.fillna("")
    
    return df.to_dict(orient="records")