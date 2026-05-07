from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import os
from app.repositories.dataset_repo import get_dataset, update_mapping
from app.services.registry_mapping_service import generate_mapping
from app.utils.file_utils import download_from_s3
from app.models.schemas import MappingRequest

router = APIRouter()

@router.post("/mapping")
def map_columns(request: MappingRequest):
    dataset = get_dataset(request.file_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Download CSV from R2 to a temp local file
    local_path = None
    try:
        local_path = download_from_s3(dataset["file_path"])
        df = pd.read_csv(local_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read CSV from R2: {str(e)}")
    finally:
        if local_path and os.path.exists(local_path):
            os.remove(local_path)

    # Generate the semantic mapping
    try:
        mapping = generate_mapping(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Mapping generation failed: {str(e)}")

    # Extract Metadata for Lightning-Fast Queries
    columns = []
    column_types = {}
    column_values = {}
    data_health = {}
    
    try:
        columns = df.columns.tolist()
        column_types = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # Get up to 50 unique values for each categorical field based on the new mapping
        for actual_col, semantic_key in mapping.items():
            if actual_col in df.columns and df[actual_col].dtype == object:
                column_values[semantic_key] = df[actual_col].dropna().unique().tolist()[:50]
                
        # 🔥 THE FIX: Strip Numpy data types so PyMongo doesn't crash!
        missing_counts = df.isnull().sum()
        
        # Force every key to a string and every value to a native Python int
        missing_dict = {str(k): int(v) for k, v in missing_counts[missing_counts > 0].items()}
        
        # Force duplicates to a native Python int
        duplicates = int(df.duplicated().sum())
        
        data_health = {
            "missing": missing_dict,
            "duplicates": duplicates
        }
    except Exception as e:
        print(f"[Warning] Metadata extraction failed, skipping: {str(e)}")

    # Update MongoDB with mapping AND the new metadata safely
    update_mapping(request.file_id, mapping, columns, column_types, column_values, data_health)

    return {
        "file_id": request.file_id,
        "semantic_mapping": mapping,
        "data_health": data_health,
        "message": "Mapping & metadata generated successfully"
    }