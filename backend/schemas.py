from pydantic import BaseModel, EmailStr
from typing import Optional


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
 
 
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
 
 
class QueryRequest(BaseModel):
    question: str
    company_name: str
    file_hash: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class NewConversationRequest(BaseModel):
    document_id: int
 
class QueryRequest(BaseModel):
    question: str