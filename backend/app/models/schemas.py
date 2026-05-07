from pydantic import BaseModel
from typing import Optional

class AuthRequest(BaseModel):
    email: str
    password: str

class MappingRequest(BaseModel):
    file_id: str

class QueryRequest(BaseModel):
    file_id: str
    question: str
    chat_id: Optional[str] = None
    file_name: Optional[str] = None
    language: Optional[str] = "English" 
    complexity: Optional[str] = "Executive" 