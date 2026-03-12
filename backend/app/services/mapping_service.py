from app.services.llm_service import call_llm

INTERNAL_SCHEMA = [
    "transaction_date",
    "revenue",
    "expense",
    "profit",
    "loss",
    "product",
    "region",
    "quantity",
    "customer_id",
    "unknown"
]

def generate_mapping(columns, column_types, preview_rows):

    prompt = f"""
Given the following dataset:


Columns:
{columns}

Column Types:
{column_types}

Preview Rows:
{preview_rows}

Map each column to ONE of the following categories:

{INTERNAL_SCHEMA}

Rules:
- Return JSON only.
- Every column must be mapped.
- If unsure, return "unknown".
"""

    mapping = call_llm(prompt)

    return mapping