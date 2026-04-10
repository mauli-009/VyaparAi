from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
from app.repositories.dataset_repo import get_dataset
from app.services.intent_service import extract_intent
from app.services.aggregation_service import run_aggregation
from app.services.suggestion_service import generate_suggestions, generate_product_recommendation

router = APIRouter()

class QueryRequest(BaseModel):
    file_id: str
    question: str

@router.post("/query")
def query_dataset(request: QueryRequest):
    dataset = get_dataset(request.file_id)

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if not dataset.get("semantic_mapping"):
        raise HTTPException(status_code=400, detail="Mapping not generated. Call /mapping first.")

    # Build actual unique values for categorical columns
    column_values = {}
    try:
        df = pd.read_csv(dataset["file_path"])
        for actual_col, semantic_key in dataset["semantic_mapping"].items():
            if actual_col in df.columns and df[actual_col].dtype == object:
                column_values[semantic_key] = df[actual_col].dropna().unique().tolist()[:50]
    except Exception:
        column_values = {}

    try:
        intent = extract_intent(request.question, dataset["semantic_mapping"], column_values)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent extraction failed: {str(e)}")

    query_type = intent.pop("query_type", "aggregation")

    # ── Product / category recommendation ─────────────────────────────
    if query_type == "recommendation":
        try:
            recommendation = generate_product_recommendation(
                request.question,
                dataset["file_path"],
                dataset["semantic_mapping"]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Recommendation failed: {str(e)}")

        return {
            "intent": intent,
            "query_type": "recommendation",
            "recommendation": recommendation
        }

    # ── Suggestion only ────────────────────────────────────────────────
    if query_type == "suggestion":
        try:
            result = run_aggregation(dataset["file_path"], dataset["semantic_mapping"], intent)
        except Exception:
            result = {"results": []}

        try:
            suggestions = generate_suggestions(request.question, intent, result)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Suggestion generation failed: {str(e)}")

        return {
            "intent": intent,
            "query_type": "suggestion",
            "suggestions": suggestions
        }

    # ── Aggregation only ───────────────────────────────────────────────
    if query_type == "aggregation":
        try:
            result = run_aggregation(dataset["file_path"], dataset["semantic_mapping"], intent)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")

        return {
            "intent": intent,
            "query_type": "aggregation",
            "result": result
        }

    # ── Both: number + suggestions ─────────────────────────────────────
    try:
        result = run_aggregation(dataset["file_path"], dataset["semantic_mapping"], intent)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")

    suggestions = []
    try:
        if result.get("results") and not result.get("error"):
            suggestions = generate_suggestions(request.question, intent, result)
    except Exception:
        suggestions = []

    return {
        "intent": intent,
        "query_type": "both",
        "result": result,
        "suggestions": suggestions
    }