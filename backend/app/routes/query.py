from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import pandas as pd
import os

from app.repositories.dataset_repo import get_dataset
from app.repositories.history_repo import save_history_entry, get_chat_messages
from app.services.intent_service import extract_intent
from app.services.aggregation_service import run_aggregation
from app.services.suggestion_service import generate_suggestions, generate_product_recommendation
from app.utils.file_utils import download_from_s3
from app.utils.auth_utils import decode_token
from app.services.retrieval_service import run_retrieval
from app.models.schemas import QueryRequest

router = APIRouter()

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
    local_path = None
    
    try:
        # ── 1. Download the file EXACTLY ONCE ──────────────────────────────
        local_path = get_local_csv(s3_path)
        df = pd.read_csv(local_path)
        
        # ── 2. Extract column values ───────────────────────────────────────
        column_values = {}
        for actual_col, semantic_key in dataset["semantic_mapping"].items():
            if actual_col in df.columns and df[actual_col].dtype == object:
                column_values[semantic_key] = df[actual_col].dropna().unique().tolist()[:50]

        # 👇 3. Fetch Recent Chat History ───────────────────────────────────
        history_text = "No previous history."
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = decode_token(token)
            if user_id and request.chat_id:
                # Grab the last 4 interactions (to save tokens)
                past_messages = get_chat_messages(user_id, request.chat_id)[-4:]
                if past_messages:
                    history_lines = []
                    for msg in past_messages:
                        history_lines.append(f"User: {msg.get('question')}")
                        past_intent = msg.get("response", {}).get("intent", {})
                        past_action = past_intent.get("action", "unknown")
                        past_metric = past_intent.get("metric", "none")
                        past_field = past_intent.get("field", "none")
                        
                        history_lines.append(f"AI previously performed action: {past_action} on field: {past_field} with metric: {past_metric}")
                    history_text = "\n".join(history_lines)

        
        # ── 4. Extract intent ──────────────────────────────────────────────
        intent = extract_intent(request.question, dataset["semantic_mapping"], column_values)
        action = intent.get("action", "aggregate")
        
        frontend_query_type_map = {
            "metadata": "metadata",
            "recommend": "recommendation",
            "suggest": "suggestion",
            "list": "list_records",
            "aggregate": "aggregation"
        }
        frontend_type = frontend_query_type_map.get(action, "aggregation")
        final_response = None

        # ── 4. Route to the correct service ────────────────────────────────
        if action == "metadata":
            final_response = {
                "intent": intent,
                "query_type": frontend_type,
                "result": {
                    "columns": dataset.get("columns", []),
                    "column_types": dataset.get("column_types", {})
                }
            }

        elif action == "recommend":
            # 👇 Add request.language and request.complexity
            recommendation = generate_product_recommendation(
                request.question, local_path, dataset["semantic_mapping"], request.language, request.complexity
            )
            final_response = {
                "intent": intent,
                "query_type": frontend_type,
                "recommendation": recommendation
            }

        elif action == "suggest":
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
            # 👇 Add request.language and request.complexity
            suggestions = generate_suggestions(
                request.question, intent, result, request.language, request.complexity
            )
            final_response = {
                "intent": intent,
                "query_type": frontend_type,
                "suggestions": suggestions
            }
            
        elif action == "list":
            records = run_retrieval(local_path, dataset["semantic_mapping"], intent)
            final_response = {
                "intent": intent,
                "query_type": frontend_type,
                "records": records
            }

        else:  # action == "aggregate"
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
            final_response = {
                "intent": intent,
                "query_type": frontend_type,
                "result": result
            }

        # ── 5. Save history if logged in ───────────────────────────────────
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = decode_token(token)
            if user_id:
                save_history_entry(user_id, request.file_id, request.chat_id, request.question, final_response)
                
        return final_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

    finally:
        # ── 6. Clean up EXACTLY ONCE ───────────────────────────────────────
        if local_path and os.path.exists(local_path):
            os.remove(local_path)