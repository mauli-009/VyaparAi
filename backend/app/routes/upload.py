from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import pandas as pd
from app.utils.file_utils import generate_file_id, save_uploaded_file_locally, upload_to_s3
from app.services.ingestion_service import extract_metadata
from app.repositories.dataset_repo import create_dataset
from app.services.registry_mapping_service import generate_mapping

router = APIRouter()

@router.post("/upload")
def upload_csv(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    file_id = generate_file_id()
    local_file_path = save_uploaded_file_locally(file, file_id)

    # Extract metadata and generate semantic mapping silently
    try:
        metadata = extract_metadata(local_file_path)
        
        df = pd.read_csv(local_file_path)
        mapping = generate_mapping(df)
    except Exception as e:
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        raise HTTPException(status_code=422, detail=f"Could not parse or map CSV: {str(e)}")

    # Upload to Cloudflare R2
    try:
        s3_path = upload_to_s3(local_file_path, file_id)
    except Exception as e:
        if os.path.exists(local_file_path):
            os.remove(local_file_path)
        raise HTTPException(status_code=500, detail=f"Cloudflare Upload failed: {str(e)}")

    # Clean up local file
    if os.path.exists(local_file_path):
        os.remove(local_file_path)

    # Save to MongoDB
    dataset_data = {
        "file_id": file_id,
        "file_path": s3_path,
        "columns": metadata["columns"],
        "column_types": metadata["column_types"],
        "preview_rows": metadata["preview_rows"],
        "semantic_mapping": mapping  # Saves the generated mapping to the DB
    }

    create_dataset(dataset_data)

    return {
        "file_id": file_id,
        "columns": metadata["columns"],
        "preview_rows": metadata["preview_rows"],
        "message": "File uploaded and mapped successfully"
    }