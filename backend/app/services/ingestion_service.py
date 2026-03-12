import pandas as pd

def extract_metadata(file_path):
    df = pd.read_csv(file_path)

    columns = df.columns.tolist()

    column_types = {}
    for col in df.columns:
        column_types[col] = str(df[col].dtype)

    # Convert preview rows to JSON-safe types (avoid numpy types)
    preview_rows = df.head(5).astype(object).where(df.head(5).notna(), None).to_dict(orient="records")

    return {
        "columns": columns,
        "column_types": column_types,
        "preview_rows": preview_rows
    }