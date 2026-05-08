"""query.py — main query router with natural language summaries"""
from __future__ import annotations
from fastapi import APIRouter, HTTPException, Header
import pandas as pd, os

from app.repositories.dataset_repo import get_dataset
from app.repositories.history_repo import save_history_entry, get_chat_messages
from app.services.intent_service import extract_intent
from app.services.aggregation_service import run_aggregation
from app.services.suggestion_service import generate_suggestions, generate_product_recommendation
from app.services.retrieval_service import run_retrieval
from app.utils.file_utils import download_from_s3
from app.utils.auth_utils import decode_token
from app.models.schemas import QueryRequest

router = APIRouter()

QUERY_TYPE_MAP = {
    "metadata":  "metadata",
    "recommend": "recommendation",
    "suggest":   "both",
    "list":      "list_records",
    "aggregate": "aggregation",
}


def _fmt(v: float, field: str = "") -> str:
    is_fin = any(kw in field.lower() for kw in ["revenue","profit","earning","income","sale","cost","expense","price","spend"])
    if abs(v) >= 1_000_000:
        s = f"{v/1_000_000:.2f}M"; return f"${s}" if is_fin else s
    if abs(v) >= 1_000:
        s = f"{v:,.0f}"; return f"${s}" if is_fin else s
    return f"{v:,.2f}"


def _label(row: dict) -> str:
    return (row.get("period") or row.get("group") or row.get("month") or
            row.get("category") or row.get("region") or row.get("country") or
            next((str(v) for v in row.values() if isinstance(v,str)), "?"))


def _build_summary(question: str, intent: dict, result: dict | None,
                   query_type: str, records: list | None = None) -> str:
    """
    Generate a conversational natural-language answer bubble.
    Template-based (no extra LLM call) — fast.
    """
    field    = (intent.get("field") or "").replace("_"," ")
    metric   = intent.get("metric","sum")
    filters  = intent.get("filters",[])
    group_by = (intent.get("group_by") or "")
    sort_by  = intent.get("sort_by")

    # Build filter context string
    def _filter_str():
        if not filters: return ""
        parts = []
        for f in filters:
            fn  = f.get("field","").replace("_"," ")
            op  = f.get("operator","==")
            val = f.get("value")
            if op == "==":       parts.append(f"in **{val}**")
            elif op == ">":      parts.append(f"where {fn} > **{val}**")
            elif op == ">=":     parts.append(f"where {fn} ≥ **{val}**")
            elif op == "<":      parts.append(f"where {fn} < **{val}**")
            elif op == "<=":     parts.append(f"where {fn} ≤ **{val}**")
            elif op == "between" and isinstance(val,list):
                parts.append(f"where {fn} is between **{val[0]}** and **{val[1]}**")
            elif op == "in" and isinstance(val,list):
                parts.append(f"in **{', '.join(str(v) for v in val)}**")
        return " " + " and ".join(parts) if parts else ""

    fstr = _filter_str()

    # List records
    if query_type == "list_records":
        n = len(records or [])
        if n == 0:
            return f"No records found{fstr}. Try adjusting your filters."
        noun = "record" if n == 1 else "records"
        return f"Found **{n} {noun}**{fstr}. Here they are:"

    if not result:
        return "Here are the results:"

    rows = result.get("results",[])

    if result.get("error"):
        return f"Something went wrong: {result['error']}"

    if not rows:
        return f"No data found{fstr}."

    # Single value (no grouping)
    if len(rows) == 1 and "value" in rows[0] and not group_by:
        val = rows[0]["value"]
        return f"The **{metric}** of **{field}**{fstr} is **{_fmt(val, field)}**."

    # Grouped / ranked
    if rows and group_by:
        gb_display = re.sub(r"\w+\((.+)\)", r"\1", group_by).replace("_"," ")
        sorted_rows = sorted(rows, key=lambda r: r.get("value",0), reverse=(intent.get("order","desc")=="desc"))
        top  = sorted_rows[0]
        top_label = _label(top)
        top_val   = top.get("value",0)

        summary = f"Here's the **{metric} of {field}** by **{gb_display}**{fstr}. "
        if len(sorted_rows) >= 2:
            second = sorted_rows[1]
            summary += (f"**{top_label}** leads with **{_fmt(top_val, field)}**, "
                        f"followed by **{_label(second)}** with **{_fmt(second.get('value',0), field)}**.")
        else:
            summary += f"**{top_label}** has **{_fmt(top_val, field)}**."
        return summary

    return "Here are the results:"


import re

def _history(user_id, chat_id):
    try:
        past = get_chat_messages(user_id, chat_id)[-3:]
        return [{"question": m.get("question",""), "intent": m.get("response",{}).get("intent",{})} for m in past]
    except: return []


@router.post("/query")
def query_dataset(request: QueryRequest, authorization: str = Header(None)):
    dataset = get_dataset(request.file_id)
    if not dataset:
        raise HTTPException(404, "Dataset not found.")
    if not dataset.get("semantic_mapping"):
        raise HTTPException(400, "Mapping not generated. Call /mapping first.")

    local_path = None
    try:
        local_path = download_from_s3(dataset["file_path"])
        df = pd.read_csv(local_path)

        # Column values for filter resolution
        col_vals = {}
        for col, skey in dataset["semantic_mapping"].items():
            if col in df.columns and df[col].dtype == object:
                col_vals[skey] = df[col].dropna().unique().tolist()[:50]

        # History
        chat_history = []
        user_id = None
        if authorization and authorization.startswith("Bearer "):
            tok = authorization.split(" ")[1]
            user_id = decode_token(tok)
            if user_id and request.chat_id:
                chat_history = _history(user_id, request.chat_id)

        # Intent
        if getattr(request, "intent_override", None):
            intent = request.intent_override
        else:
            intent = extract_intent(
                request.question, dataset["semantic_mapping"],
                col_vals, chat_history
            )

        action     = intent.get("action","aggregate")
        query_type = QUERY_TYPE_MAP.get(action,"aggregation")
        final: dict

        if action == "general":
            # Pure conversational answer — no data query, just LLM response
            from app.services.llm_service import call_llm_text
            answer = call_llm_text(
                f"""You are a helpful business analyst assistant for small and medium enterprises.
Answer the following business question clearly and practically. The user is a business owner or manager.

Question: "{request.question}"

Provide 4-6 specific, actionable points. Use simple language. Back each point with a brief explanation.
Format as a flowing response — not just bullet points. Be direct and useful.""",
                expect_json=False,
            )
            final = {"intent": intent, "query_type": "general", "summary": answer}

        elif action == "metadata":
            result = {"columns": dataset.get("columns",[]), "column_types": dataset.get("column_types",{})}
            summary = "Here's your dataset schema:"
            final = {"intent": intent, "query_type": query_type, "result": result, "summary": summary}

        elif action == "recommend":
            rec = generate_product_recommendation(request.question, local_path, dataset["semantic_mapping"], request.language, request.complexity)
            top = rec.get("top_pick","")
            summary = f"Here are your product recommendations. Best long-term pick: **{top}**." if top else "Here are the ranked product recommendations:"
            final = {"intent": intent, "query_type": query_type, "recommendation": rec, "summary": summary}

        elif action == "suggest":
            # Safely run aggregation — if field is missing/invalid, continue with empty result
            try:
                result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
            except Exception as exc:
                print(f"[QUERY] suggest aggregation failed: {exc}")
                result = {"results": []}
            # If aggregation errored (field not found etc.), still generate suggestions from question alone
            if result.get("error") or not result.get("results"):
                result = {"results": []}
            suggestions = generate_suggestions(request.question, intent, result, request.language, request.complexity)
            summary = _build_summary(request.question, intent, result, "aggregation") if result.get("results") else "Here are AI-powered business recommendations based on your question:"
            final = {"intent": intent, "query_type": "both" if result.get("results") else "suggestion", "result": result, "suggestions": suggestions, "summary": summary}

        elif action == "list":
            records = run_retrieval(local_path, dataset["semantic_mapping"], intent)
            summary = _build_summary(request.question, intent, None, "list_records", records)
            final = {"intent": intent, "query_type": query_type, "records": records, "summary": summary}

        else:  # aggregate
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
            summary = _build_summary(request.question, intent, result, "aggregation")
            final = {"intent": intent, "query_type": query_type, "result": result, "summary": summary}

        if user_id:
            save_history_entry(user_id, request.file_id, request.chat_id, request.question, final)

        return final

    except HTTPException:
        raise
    except Exception as exc:
        import traceback; traceback.print_exc()
        raise HTTPException(500, f"Query failed: {exc}")
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)