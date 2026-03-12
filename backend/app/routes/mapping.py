from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
from app.repositories.dataset_repo import get_dataset, update_mapping
from app.services.registry_mapping_service import generate_mapping

router = APIRouter()

class MappingRequest(BaseModel):
    file_id: str

@router.post("/mapping")
def map_columns(request: MappingRequest):
    dataset = get_dataset(request.file_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        df = pd.read_csv(dataset["file_path"])
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read CSV file: {str(e)}")

    try:
        mapping = generate_mapping(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mapping generation failed: {str(e)}")

    update_mapping(request.file_id, mapping)

    return {
        "file_id": request.file_id,
        "semantic_mapping": mapping,
        "message": "Mapping generated successfully"
    }