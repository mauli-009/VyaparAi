import pandas as pd


def apply_filters(df: pd.DataFrame, filters: list, reverse_mapping: dict) -> pd.DataFrame:

    for f in filters:

        field = f.get("field")
        operator = f.get("operator")
        value = f.get("value")

        if field not in reverse_mapping:
            continue

        actual_column = reverse_mapping[field]

        if actual_column not in df.columns:
            continue

        # convert date column
        if "date" in field:
            df[actual_column] = pd.to_datetime(df[actual_column], errors="coerce")

        # equals
        if operator == "equals":

            value = str(value).lower().strip()

            df = df[
                df[actual_column]
                .astype(str)
                .str.lower()
                .str.contains(value, na=False)
            ]
        # not equals
        elif operator == "not_equals":

            df = df[
                df[actual_column]
                .astype(str)
                .str.lower()
                .str.strip()
                != str(value).lower().strip()
            ]

        # greater than
        elif operator == "greater_than":

            df = df[
                pd.to_numeric(df[actual_column], errors="coerce") > float(value)
            ]

        # less than
        elif operator == "less_than":

            df = df[
                pd.to_numeric(df[actual_column], errors="coerce") < float(value)
            ]

        # greater or equal
        elif operator == "greater_or_equal":

            df = df[
                pd.to_numeric(df[actual_column], errors="coerce") >= float(value)
            ]

        # less or equal
        elif operator == "less_or_equal":

            df = df[
                pd.to_numeric(df[actual_column], errors="coerce") <= float(value)
            ]

        # between (date or numeric)
        elif operator == "between":

            if isinstance(value, (list, tuple)) and len(value) == 2:

                start, end = value

                if "date" in field:

                    start = pd.to_datetime(start)
                    end = pd.to_datetime(end)

                    df = df[
                        (df[actual_column] >= start) &
                        (df[actual_column] <= end)
                    ]

                else:

                    df = df[
                        (pd.to_numeric(df[actual_column], errors="coerce") >= float(start)) &
                        (pd.to_numeric(df[actual_column], errors="coerce") <= float(end))
                    ]

    return df


def run_aggregation(file_path: str, semantic_mapping: dict, intent: dict) -> dict:

    df = pd.read_csv(file_path)

    reverse_mapping = {v: k for k, v in semantic_mapping.items()}

    metric = intent.get("metric")
    field = intent.get("field")
    group_by = intent.get("group_by")
    filters = intent.get("filters", [])

    if field not in reverse_mapping:
        return {
            "error": f"Semantic field '{field}' not found in mapping. Available: {list(reverse_mapping.keys())}"
        }

    actual_column = reverse_mapping[field]

    if actual_column not in df.columns:
        return {
            "error": f"Column '{actual_column}' not found in CSV. Available columns: {df.columns.tolist()}"
        }

    # apply filters
    df = apply_filters(df, filters, reverse_mapping)

    if df.empty:
        return {"results": [], "message": "No rows match the given filters."}

    # group by month
    if group_by == "month(transaction_date)":

        date_col = reverse_mapping.get("transaction_date")

        if not date_col or date_col not in df.columns:
            return {"error": "transaction_date field not available for grouping"}

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")

        df = df.dropna(subset=[date_col])

        df["__month__"] = df[date_col].dt.to_period("M").astype(str)

        numeric_col = pd.to_numeric(df[actual_column], errors="coerce")

        df[actual_column] = numeric_col

        if metric == "sum":
            result = df.groupby("__month__")[actual_column].sum()

        elif metric == "avg":
            result = df.groupby("__month__")[actual_column].mean()

        elif metric == "count":
            result = df.groupby("__month__")[actual_column].count()

        else:
            return {"error": f"Unsupported metric: '{metric}'"}

        output = [{"month": idx, "value": float(val)} for idx, val in result.items()]

        return {"results": output}

    # no grouping
    else:

        numeric_col = pd.to_numeric(df[actual_column], errors="coerce")

        if metric == "sum":
            value = numeric_col.sum()

        elif metric == "avg":
            value = numeric_col.mean()

        elif metric == "count":
            value = float(df[actual_column].count())

        else:
            return {"error": f"Unsupported metric: '{metric}'"}

        return {"results": [{"value": float(value)}]}