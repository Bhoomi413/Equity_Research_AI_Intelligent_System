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
    conversations = relationship("Conversation", back_populates="owner", cascade="all, delete-orphan")


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
    conversations = relationship("Conversation", back_populates="document", cascade="all, delete-orphan")



class Conversation(Base):
    __tablename__ = "conversations"
 
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    company_name = Column(String(255), nullable=True)   # denormalised for convenience
    title = Column(String(255), nullable=True)           # first few words of first question
    created_at=Column(DateTime(timezone=True), server_default=func.now())
    updated_at=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
 
    owner= relationship("User", back_populates="conversations")
    document = relationship("Document", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
 
 
class Message(Base):
    __tablename__ = "messages"
 
    id = Column(Integer, primary_key=True, index=True)
    conversation_id =Column(Integer,ForeignKey("conversations.id"),nullable=False)
    role = Column(String(10), nullable=False)    #"user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
 
    conversation = relationship("Conversation", back_populates="messages")