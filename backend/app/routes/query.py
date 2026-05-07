from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
import pandas as pd
import os

from app.repositories.dataset_repo import get_dataset, add_cleaning_rule
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

    # -- 1. PROACTIVE HEALTH CHECK -----------------------------------------
    if request.question == "__INIT_CHECK__":

        # RACE CONDITION GUARD: data_health key will be absent if this request
        # fires before /mapping has finished its MongoDB write. Return a sentinel
        # so the frontend retries instead of falsely reporting "clean".
        if "data_health" not in dataset:
            return {
                "query_type": "text",
                "result": {"message": "__MAPPING_PENDING__"}
            }

        health = dataset["data_health"]
        miss = health.get("missing", {})
        dups = health.get("duplicates", 0)

        if not miss and dups == 0:
            return {"query_type": "text", "result": {"message": "OK I've analyzed your data. It looks perfectly clean and ready to explore!"}}

        msg = "Data Health Alert\nI scanned your dataset and found some issues:\n"
        for k, v in miss.items():
            msg += f"- `{k}` is missing {v} values.\n"
        if dups > 0:
            msg += f"- Found {dups} duplicate rows.\n"
        msg += "\n*How would you like to handle this?* (e.g. 'Drop duplicates', 'Fill missing prices with average', or 'Ignore and continue')"
        return {"query_type": "text", "result": {"message": msg}}

    s3_path = dataset["file_path"]
    local_path = None
    cleaned_path = None

    try:
        # -- 2. Download the file EXACTLY ONCE --------------------------------
        local_path = get_local_csv(s3_path)
        df = pd.read_csv(local_path)

        # -- 3. APPLY CLEANING RULES IN MEMORY (Non-destructive) --------------
        rules = dataset.get("cleaning_rules", [])
        if rules:
            for r in rules:
                op = r.get("op")
                f = r.get("field")
                if op == "drop_duplicates": df.drop_duplicates(inplace=True)
                elif op == "drop_nulls" and f in df.columns: df.dropna(subset=[f], inplace=True)
                elif op == "fill_mean" and f in df.columns and pd.api.types.is_numeric_dtype(df[f]): df[f].fillna(df[f].mean(), inplace=True)
                elif op == "fill_median" and f in df.columns and pd.api.types.is_numeric_dtype(df[f]): df[f].fillna(df[f].median(), inplace=True)
                elif op == "fill_zero" and f in df.columns: df[f].fillna(0, inplace=True)

            cleaned_path = local_path.replace(".csv", "_cleaned.csv")
            df.to_csv(cleaned_path, index=False)
            local_path = cleaned_path

        # -- 4. Extract column values -----------------------------------------
        column_values = {}
        for actual_col, semantic_key in dataset["semantic_mapping"].items():
            if actual_col in df.columns and df[actual_col].dtype == object:
                column_values[semantic_key] = df[actual_col].dropna().unique().tolist()[:50]

        # -- 5. Fetch Recent Chat History -------------------------------------
        history_text = "No previous history."
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = decode_token(token)
            if user_id and request.chat_id:
                past_messages = get_chat_messages(user_id, request.chat_id)[-4:]
                if past_messages:
                    history_lines = []
                    for msg in past_messages:
                        history_lines.append(f"User: {msg.get('question')}")
                        past_intent = msg.get("response", {}).get("intent", {})
                        history_lines.append(f"AI previously performed action: {past_intent.get('action', 'unknown')} on field: {past_intent.get('field', 'none')} with metric: {past_intent.get('metric', 'none')}")
                    history_text = "\n".join(history_lines)

        # -- 6. Extract intent ------------------------------------------------
        intent = extract_intent(request.question, dataset["semantic_mapping"], column_values, history_text)
        action = intent.get("action", "aggregate")

        frontend_query_type_map = {
            "metadata": "metadata",
            "recommend": "recommendation",
            "suggest": "suggestion",
            "list": "list_records",
            "aggregate": "aggregation",
            "clean": "text"
        }
        frontend_type = frontend_query_type_map.get(action, "aggregation")
        final_response = None

        # -- 7. Route to the correct service ----------------------------------

        if action == "clean":
            rule = intent.get("clean_rule")
            if rule and rule.get("op"):
                add_cleaning_rule(request.file_id, rule)
                final_response = {
                    "intent": intent,
                    "query_type": "text",
                    "result": {"message": f"Data Cleaned! Applied `{rule['op']}` on `{rule['field']}`. Future queries will use the cleaned data. What's next?"}
                }
            else:
                final_response = {"query_type": "text", "result": {"message": "I didn't quite catch how you want to clean it. Try 'Drop duplicates' or 'Fill missing prices with zero'."}}

        elif action == "metadata":
            final_response = {
                "intent": intent,
                "query_type": frontend_type,
                "result": {
                    "columns": dataset.get("columns", []),
                    "column_types": dataset.get("column_types", {})
                }
            }

        elif action == "recommend":
            recommendation = generate_product_recommendation(
                request.question, local_path, dataset["semantic_mapping"], getattr(request, 'language', 'English'), getattr(request, 'complexity', 'Simple')
            )
            final_response = {
                "intent": intent,
                "query_type": frontend_type,
                "recommendation": recommendation
            }

        elif action == "suggest":
            result = run_aggregation(local_path, dataset["semantic_mapping"], intent)
            suggestions = generate_suggestions(
                request.question, intent, result, getattr(request, 'language', 'English'), getattr(request, 'complexity', 'Simple')
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

        # -- 8. Save history if logged in -------------------------------------
        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ")[1]
            user_id = decode_token(token)
            if user_id:
                save_history_entry(user_id, request.file_id, request.chat_id, request.question, final_response)

        return final_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")

    finally:
        # -- 9. Clean up EXACTLY ONCE -----------------------------------------
        if local_path and os.path.exists(local_path):
            os.remove(local_path)
        if cleaned_path and os.path.exists(cleaned_path):
            os.remove(cleaned_path)