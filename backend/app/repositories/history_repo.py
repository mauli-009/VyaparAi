from app.db.database import db
from datetime import datetime

history_collection = db["history"]

def save_history_entry(user_id: str, file_id: str, chat_id: str, question: str, response: dict):
    try:
        result = history_collection.insert_one({
            "user_id": user_id,
            "file_id": file_id,
            "chat_id": chat_id,  # <-- NEW: Grouping ID
            "question": question,
            "query_type": response.get("query_type", "aggregation"),
            "response": response,
            "created_at": datetime.utcnow()
        })
        return str(result.inserted_id)
    except Exception as e:
        print(f"[HISTORY] Failed to save: {e}")
        return None

def get_user_chats(user_id: str):
    """Gets unique chats for the sidebar, titled by the first question asked."""
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$sort": {"created_at": 1}},  # Sort oldest first to grab the first question
        {"$group": {
            "_id": "$chat_id",
            "title": {"$first": "$question"},
            "file_id": {"$first": "$file_id"},
            "updated_at": {"$last": "$created_at"}
        }},
        {"$sort": {"updated_at": -1}}  # Show newest chats at the top
    ]
    chats = list(history_collection.aggregate(pipeline))
    for c in chats:
        c["chat_id"] = c.pop("_id")
    return chats

def get_chat_messages(user_id: str, chat_id: str):
    """Gets all back-and-forth messages for a specific chat."""
    entries = list(
        history_collection
        .find({"user_id": user_id, "chat_id": chat_id})
        .sort("created_at", 1)  # Chronological order
    )
    for e in entries:
        e["_id"] = str(e["_id"])
    return entries