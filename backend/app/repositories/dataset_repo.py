from app.db.database import datasets_collection
from datetime import datetime

def create_dataset(dataset_data):
    dataset_data["created_at"] = datetime.utcnow()
    datasets_collection.insert_one(dataset_data)

def get_dataset(file_id: str):
    return datasets_collection.find_one({"file_id": file_id})

def update_mapping(file_id: str, mapping: dict, columns: list = None, column_types: dict = None, column_values: dict = None):
    # Always update the semantic mapping
    update_data = {
        "semantic_mapping": mapping
    }
    
    # Conditionally add the new metadata if it was passed
    if columns is not None:
        update_data["columns"] = columns
    if column_types is not None:
        update_data["column_types"] = column_types
    if column_values is not None:
        update_data["column_values"] = column_values

    # Send the update to MongoDB
    datasets_collection.update_one(
        {"file_id": file_id},
        {"$set": update_data}
    )