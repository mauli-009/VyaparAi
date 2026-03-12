from app.db.database import db
from datetime import datetime

registry_collection = db["semantic_registry"]

def get_all_registry():
    return list(registry_collection.find({}))

def find_by_alias(alias):
    return registry_collection.find_one({
        "aliases": alias
    })

def insert_registry_entry(key, aliases, description, data_type):
    registry_collection.insert_one({
        "key": key,
        "aliases": aliases,
        "description": description,
        "data_type": data_type,
        "created_at": datetime.utcnow()
    })