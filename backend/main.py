from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
from backend.database import engine
from backend.models import Base



load_dotenv()

# Base.metadata.drop_all(engine)
Base.metadata.create_all(bind=engine) 

app = FastAPI(title="Equity RAG API")

origins = os.getenv("ALLOWED_ORIGINS")
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .routes import auth,documents,conversations
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(conversations.router)
