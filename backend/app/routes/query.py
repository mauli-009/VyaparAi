from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.repositories.dataset_repo import get_dataset
from app.services.intent_service import extract_intent
from app.services.aggregation_service import run_aggregation

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

    try:
        intent = extract_intent(request.question, dataset["semantic_mapping"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent extraction failed: {str(e)}")

    try:
        result = run_aggregation(
            dataset["file_path"],
            dataset["semantic_mapping"],
            intent
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Aggregation failed: {str(e)}")

    return {
        "intent": intent,
        "result": result
    }