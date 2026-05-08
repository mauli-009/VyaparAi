"""
query.py

Main query router — downloads data, extracts intent, dispatches to the
correct service, saves history, returns a unified response to the frontend.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Header
import pandas as pd
import os

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

# ── Query type → frontend label mapping ──────────────────────────
# "both" = return aggregation numbers AND AI suggestions together
QUERY_TYPE_MAP: dict[str, str] = {
    "metadata":  "metadata",
    "recommend": "recommendation",
    "suggest":   "both",         # ← aggregation data + suggestion cards
    "list":      "list_records",
    "aggregate": "aggregation",
    "chat":      "chat",         # ← ADD THIS LINE
}


def _build_history_context(user_id: str, chat_id: str) -> list[dict]:
    """
    Return the last 3 conversation turns as structured dicts:
      [{"question": str, "intent": dict}, ...]

    This gives the intent LLM full context for resolving follow-up questions.
    """
    try:
        past = get_chat_messages(user_id, chat_id)[-3:]
        return [
            {
                "question": msg.get("question", ""),
                "intent":   msg.get("response", {}).get("intent", {}),
            }
            for msg in past
        ]
    except Exception as exc:
        print(f"[QUERY] Could not load history: {exc}")
        return []


def _get_column_values(df: pd.DataFrame, semantic_mapping: dict) -> dict:
    """
    Build a {semantic_key: [sample values]} dict for categorical columns.
    Used by the intent LLM to resolve filter values accurately.
    """
    column_values: dict[str, list] = {}
    for actual_col, semantic_key in semantic_mapping.items():
        if actual_col in df.columns and df[actual_col].dtype == object:
            column_values[semantic_key] = (
                df[actual_col].dropna().unique().tolist()[:50]
            )
    return column_values


# ─────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────

@router.post("/query")
def query_dataset(request: QueryRequest, authorization: str = Header(None)):

    # ── 1. Load dataset metadata ──────────────────────────────────
    dataset = get_dataset(request.file_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    if not dataset.get("semantic_mapping"):
        raise HTTPException(
            status_code=400,
            detail="Semantic mapping not yet generated. Call /mapping first.",
        )

    local_path: str | None = None

    try:
        # ── 2. Download CSV exactly once ──────────────────────────
        local_path = download_from_s3(dataset["file_path"])
        df = pd.read_csv(local_path)

        # ── 3. Build column-values context ────────────────────────
        column_values = _get_column_values(df, dataset["semantic_mapping"])

        # ── 4. Build structured chat history ──────────────────────
        chat_history: list[dict] = []
        user_id: str | None = None

        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = decode_token(token)
            if user_id and request.chat_id:
                chat_history = _build_history_context(user_id, request.chat_id)

        # ── 5. Extract intent ─────────────────────────────────────
        if getattr(request, "intent_override", None):
            # Dashboard fast-path: bypass LLM entirely
            intent = request.intent_override
        else:
            intent = extract_intent(
                question        = request.question,
                semantic_mapping= dataset["semantic_mapping"],
                column_values   = column_values,
                chat_history    = chat_history,
            )

        action     = intent.get("action", "aggregate")
        query_type = QUERY_TYPE_MAP.get(action, "aggregation")

        # ── 6. Route to service ───────────────────────────────────
        final_response: dict

        if action == "metadata":
            final_response = {
                "intent":     intent,
                "query_type": query_type,
                "result": {
                    "columns":      dataset.get("columns", []),
                    "column_types": dataset.get("column_types", {}),
                },
            }

        elif action == "recommend":
            recommendation = generate_product_recommendation(
                request.question,
                local_path,
                dataset["semantic_mapping"],
                request.language,
                request.complexity,
            )
            final_response = {
                "intent":         intent,
                "query_type":     query_type,
                "recommendation": recommendation,
            }

        elif action == "suggest":
            # Always run aggregation first so the LLM has actual numbers
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
            suggestions = generate_suggestions(
                request.question,
                intent,
                result,
                request.language,
                request.complexity,
            )
            final_response = {
                "intent":      intent,
                "query_type":  "both",   # Front-end renders data table + suggestion cards
                "result":      result,
                "suggestions": suggestions,
            }

        elif action == "list":
            records = run_retrieval(local_path, dataset["semantic_mapping"], intent)
            final_response = {
                "intent":     intent,
                "query_type": query_type,
                "records":    records,
            }

        # ── Conversational Chat ────────────────────────────────────────────
        elif action == "chat":
            from app.services.llm_service import call_llm_text
            
            chat_prompt = (
                f"You are QueryMind, a helpful AI data analyst. "
                f"The user asked a general question: '{request.question}'. "
                f"Respond concisely and naturally. If they ask about your capabilities, "
                f"mention you can aggregate metrics, create charts, give business suggestions, "
                f"and recommend products based on their uploaded CSV data."
            )
            
            reply = call_llm_text(chat_prompt, expect_json=False)
            final_response = {
                "intent": intent,
                "query_type": query_type,  # ← CHANGE THIS from frontend_type to query_type
                "result": {"message": reply}
            }

        else:  # aggregate (default)
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
            final_response = {
                "intent":     intent,
                "query_type": query_type,
                "result":     result,
            }

        # ── 7. Persist to history ─────────────────────────────────
        if user_id:
            save_history_entry(
                user_id,
                request.file_id,
                request.chat_id,
                request.question,
                final_response,
            )

        return final_response

    except HTTPException:
        raise

    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Query processing failed: {str(exc)}",
        )

    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)