from app.db.database import history_collection
from datetime import datetime


def save_history_entry(user_id: str, file_id: str, chat_id: str, question: str, response: dict):
    try:
        result = history_collection.insert_one({
            "user_id":    user_id,
            "file_id":    file_id,
            "chat_id":    chat_id,
            "question":   question,
            "query_type": response.get("query_type", "aggregation"),
            "response":   response,
            "created_at": datetime.utcnow(),
        })
        return str(result.inserted_id)
    except Exception as exc:
        print(f"[HISTORY] save failed: {exc}")
        return None


def get_user_chats(user_id: str) -> list[dict]:
    """
    Returns unique chats for the sidebar.
    Title = first question asked in that chat.
    """
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$sort":  {"created_at": 1}},
        {
            "$group": {
                "_id":        "$chat_id",
                "title":      {"$first": "$question"},
                "file_id":    {"$first": "$file_id"},
                "updated_at": {"$last":  "$created_at"},
            }
        },
        {"$sort": {"updated_at": -1}},
    ]
    chats = list(history_collection.aggregate(pipeline))
    for c in chats:
        c["chat_id"] = c.pop("_id")
    return chats


def get_chat_messages(user_id: str, chat_id: str) -> list[dict]:
    """Returns all messages for a chat in chronological order."""
    entries = list(
        history_collection
        .find({"user_id": user_id, "chat_id": chat_id})
        .sort("created_at", 1)
    )
    for e in entries:
        e["_id"] = str(e["_id"])
    return entries


def delete_chat(user_id: str, chat_id: str) -> bool:
    """
    Permanently deletes all messages belonging to a chat.
    Returns True if any documents were deleted.
    """
    try:
        result = history_collection.delete_many(
            {"user_id": user_id, "chat_id": chat_id}
        )
        return result.deleted_count > 0
    except Exception as exc:
        print(f"[HISTORY] delete failed: {exc}")
        return False