from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import pandas as pd
import os

from app.repositories.dataset_repo import get_dataset
from app.repositories.history_repo import save_history_entry
from app.services.intent_service import extract_intent
from app.services.aggregation_service import run_aggregation
from app.services.suggestion_service import generate_suggestions, generate_product_recommendation
from app.utils.file_utils import download_from_s3
from app.utils.auth_utils import decode_token
from app.services.retrieval_service import run_retrieval

router = APIRouter()

class QueryRequest(BaseModel):
    file_id: str
    question: str
    chat_id: str | None = None
    file_name: str | None = None

def get_local_csv(s3_path: str) -> str:
    return download_from_s3(s3_path)

@router.post("/query")
def query_dataset(request: QueryRequest, authorization: str = Header(None)):
    dataset = get_dataset(request.file_id)

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.get("semantic_mapping"):
        raise HTTPException(status_code=400, detail="Mapping not generated. Call /mapping first.")

    s3_path = dataset["file_path"]

    # ── Extract column values ──────────────────────────────────────────
    column_values = {}
    local_path = None
    try:
        local_path = get_local_csv(s3_path)
        df = pd.read_csv(local_path)
        for actual_col, semantic_key in dataset["semantic_mapping"].items():
            if actual_col in df.columns and df[actual_col].dtype == object:
                column_values[semantic_key] = df[actual_col].dropna().unique().tolist()[:50]
    except Exception:
        column_values = {}
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)

    # ── Extract intent ─────────────────────────────────────────────────
    try:
        intent = extract_intent(request.question, dataset["semantic_mapping"], column_values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent extraction failed: {str(e)}")

    # Map the new Universal Schema "action" to the frontend's expected "query_type"
    action = intent.get("action", "aggregate")
    
    # Translate actions to keep frontend React code completely unbroken
    frontend_query_type_map = {
        "metadata": "metadata",
        "recommend": "recommendation",
        "suggest": "suggestion",
        "list": "list_records",
        "aggregate": "aggregation"
    }
    frontend_type = frontend_query_type_map.get(action, "aggregation")
    
    final_response = None

    # ── Metadata (Schema/Columns) ──────────────────────────────────────
    if action == "metadata":
        final_response = {
            "intent": intent,
            "query_type": frontend_type,
            "result": {
                "columns": dataset.get("columns", []),
                "column_types": dataset.get("column_types", {})
            }
        }

    # ── Recommendation ─────────────────────────────────────────────────
    elif action == "recommend":
        local_path = None
        try:
            local_path = get_local_csv(s3_path)
            recommendation = generate_product_recommendation(
                request.question, local_path, dataset["semantic_mapping"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
        final_response = {
            "intent": intent,
            "query_type": frontend_type,
            "recommendation": recommendation
        }

    # ── Suggestion ─────────────────────────────────────────────────────
    elif action == "suggest":
        local_path = None
        try:
            local_path = get_local_csv(s3_path)
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
        except Exception:
            result = {"results": []}
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
        try:
            suggestions = generate_suggestions(request.question, intent, result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Suggestion failed: {str(e)}")
        final_response = {
            "intent": intent,
            "query_type": frontend_type,
            "suggestions": suggestions
        }
        
    # ── List Records / Retrieval ───────────────────────────────────────
    elif action == "list":
        local_path = None
        try:
            local_path = get_local_csv(s3_path)
            records = run_retrieval(local_path, dataset["semantic_mapping"], intent)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
                
        final_response = {
            "intent": intent,
            "query_type": frontend_type,
            "records": records
        }

    # ── Aggregation ────────────────────────────────────────────────────
    else:  # action == "aggregate"
        local_path = None
        try:
            local_path = get_local_csv(s3_path)
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")
        finally:
            if local_path and os.path.exists(local_path):
                os.remove(local_path)
        final_response = {
            "intent": intent,
            "query_type": frontend_type,
            "result": result
        }

    # ── Save to history if logged in ───────────────────────────────────
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        user_id = decode_token(token)
        if user_id:
            save_history_entry(user_id, request.file_id, request.chat_id, request.question, final_response)
            
    return final_response