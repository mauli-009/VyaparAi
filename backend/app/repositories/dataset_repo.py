from app.db.database import datasets_collection
from datetime import datetime


def create_dataset(dataset_data):
    dataset_data["created_at"] = datetime.utcnow()
    datasets_collection.insert_one(dataset_data)


def get_dataset(file_id: str):
    return datasets_collection.find_one({"file_id": file_id})


def update_mapping(file_id: str, mapping: dict):
    datasets_collection.update_one(
        {"file_id": file_id},
        {"$set": {"semantic_mapping": mapping}}
    )