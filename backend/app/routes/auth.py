from fastapi import APIRouter, HTTPException, Header
from app.db.database import users_collection
from app.utils.auth_utils import hash_password, verify_password, create_token, decode_token
from app.repositories.history_repo import get_user_chats, get_chat_messages, delete_chat
from app.models.schemas import AuthRequest
from datetime import datetime

router = APIRouter()


@router.post("/register")
def register(request: AuthRequest):
    if users_collection.find_one({"email": request.email}):
        raise HTTPException(status_code=400, detail="Email already registered.")

    user_id = users_collection.insert_one({
        "email":      request.email,
        "password":   hash_password(request.password),
        "created_at": datetime.utcnow(),
    }).inserted_id

    token = create_token(str(user_id), request.email)
    return {"token": token, "email": request.email}


@router.post("/login")
def login(request: AuthRequest):
    user = users_collection.find_one({"email": request.email})
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    token = create_token(str(user["_id"]), request.email)
    return {"token": token, "email": request.email}


def _require_user(authorization: str | None) -> str:
    """Extract and validate bearer token. Returns user_id or raises 401."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized.")
    token   = authorization.split(" ")[1]
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")
    return user_id


@router.get("/chats")
def get_chats(authorization: str = Header(None)):
    user_id = _require_user(authorization)
    return {"chats": get_user_chats(user_id)}


@router.get("/chats/{chat_id}")
def get_chat_history(chat_id: str, authorization: str = Header(None)):
    user_id  = _require_user(authorization)
    messages = get_chat_messages(user_id, chat_id)
    return {"messages": messages}


@router.delete("/chats/{chat_id}")
def delete_chat_history(chat_id: str, authorization: str = Header(None)):
    """
    Permanently delete all messages in a chat.
    Called by the frontend trash-icon button.
    """
    user_id = _require_user(authorization)
    deleted = delete_chat(user_id, chat_id)
    return {"deleted": deleted, "chat_id": chat_id}