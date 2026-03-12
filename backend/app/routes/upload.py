from fastapi import APIRouter, UploadFile, File, HTTPException
from app.utils.file_utils import generate_file_id, save_uploaded_file
from app.services.ingestion_service import extract_metadata
from app.repositories.dataset_repo import create_dataset

router = APIRouter()

@router.post("/upload")
def upload_csv(file: UploadFile = File(...)):
    # Validate file type
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    file_id = generate_file_id()
    file_path = save_uploaded_file(file, file_id)

    try:
        metadata = extract_metadata(file_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse CSV: {str(e)}")

    dataset_data = {
        "file_id": file_id,
        "file_path": file_path,
        "columns": metadata["columns"],
        "column_types": metadata["column_types"],
        "preview_rows": metadata["preview_rows"],
        "semantic_mapping": None
    }

    create_dataset(dataset_data)

    return {
        "file_id": file_id,
        "columns": metadata["columns"],
        "preview_rows": metadata["preview_rows"]
    }