from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username= Column(String(50), unique=True, nullable=False, index=True)
    email= Column(String(100), unique=True, nullable=False)
    hashed_password= Column(String(255), nullable=False)
    created_at= Column(DateTime(timezone=True), server_default=func.now())

    # relationship to uploaded docs
    documents=relationship("Document", back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id= Column(Integer, primary_key=True, index=True)
    user_id= Column(Integer, ForeignKey("users.id"), nullable=False)
    filename= Column(String(255), nullable=False)
    company_name= Column(String(255), nullable=True)
    file_hash= Column(String(64), nullable=False)         
    kb_path= Column(String(512), nullable=False)          
    uploaded_at= Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="documents")