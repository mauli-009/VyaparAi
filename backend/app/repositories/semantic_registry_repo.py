from app.db.database import semantic_registry_collection
from datetime import datetime


def get_all_registry():
    return list(semantic_registry_collection.find({}))


def find_by_alias(alias: str):
    return semantic_registry_collection.find_one(
        {"aliases": alias.lower().strip()}
    )


def find_by_key(key: str):
    return semantic_registry_collection.find_one(
        {"key": key.lower().strip()}
    )


def insert_registry_entry(key: str, aliases: list, description: str, data_type: str):

    semantic_registry_collection.insert_one({
        "key": key.lower().strip(),
        "aliases": [a.lower().strip() for a in aliases],
        "description": description.strip(),
        "data_type": data_type,
        "created_at": datetime.utcnow()
    })


def add_alias_to_key(key: str, new_alias: str):
    semantic_registry_collection.update_one(
        {"key": key.lower().strip()},
        {"$addToSet": {"aliases": new_alias.lower().strip()}}
    )