from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
import hashlib
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from backend.rag.rag import handle_userinput,load_pdf, get_text_chunks, get_vectorstore
from fastapi.security import OAuth2PasswordRequestForm
from dotenv import load_dotenv
import os
import pickle
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from backend.database import get_db, engine
from backend.models import Base, User, Document
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

from backend.rag.rag import load_pdf, get_text_chunks, handle_userinput, get_vectorstore

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Equity RAG API")

origins = os.getenv("ALLOWED_ORIGINS")
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#pydantic schemas
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
 
 
#auth routes
@app.post("/auth/register", status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    # make sure username and email are not taken
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
 
    new_user=User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "Account created successfully", "username": new_user.username}
 
 
@app.post("/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user=db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token=create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}
 
 
@app.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}
 
 
#document routes
@app.post("/documents/upload")
def upload_document(
    file: UploadFile = File(...),
    company_name: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pdf_bytes=file.file.read()
 
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
 
    file_hash=hashlib.sha256(pdf_bytes).hexdigest()
 
    #per user folder so userA can never access userB embeddings
    kb_path=os.path.join("knowledgebase", f"user_{current_user.id}", file_hash)
 
    #check if this user already uploaded this exact file
    existing = (
        db.query(Document)
        .filter(Document.user_id == current_user.id, Document.file_hash == file_hash)
        .first()
    )
    if existing:
        return {
            "message": "File already uploaded before",
            "hash_exists": True,
            "file_hash": file_hash,
            "kb_path": existing.kb_path,
            "filename": existing.filename,
        }
 
    #save PDF to disk
    os.makedirs("UploadedPDF", exist_ok=True)
    save_path = os.path.join("UploadedPDF", file.filename)
    with open(save_path, "wb") as f:
        f.write(pdf_bytes)
 
    exists = bool(existing)

    #create kb folder 
    os.makedirs(kb_path, exist_ok=True)
    import traceback
    try:
        print("STEP 1")
        raw_docs = load_pdf(save_path, company_name)
        print("STEP 2")
        text_chunks = get_text_chunks(raw_docs)
        print("STEP 3")
        vectorstore=get_vectorstore(text_chunks, exists, kb_path )
        print("STEP 4")
    except Exception as e:
        traceback.print_exc()
    doc = Document(
        user_id=current_user.id,
        filename=file.filename,
        company_name=company_name if company_name else None,
        file_hash=file_hash,
        kb_path=kb_path,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
 
    return {
        "message": "File uploaded successfully",
        "hash_exists": False,
        "file_hash": file_hash,
        "kb_path": kb_path,
        "filename": file.filename,
    }
 

 
 
@app.get("/documents/my")
def list_my_documents(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    docs=db.query(Document).filter(Document.user_id == current_user.id).all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "company_name": d.company_name,
            "file_hash": d.file_hash,
            "uploaded_at": str(d.uploaded_at),
        }
        for d in docs
    ]
 
 
@app.post("/query")
def query_document(
    payload: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
 
    doc_record= (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.file_hash == payload.file_hash,
        )
        .first()
    )
    if not doc_record:
        raise HTTPException(
            status_code=403,
            detail="Document not found or you don't have access to it",
        )
 
    kb_path=doc_record.kb_path
 
    try:
        embeddings=GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        vectorstore=FAISS.load_local(kb_path, embeddings, allow_dangerous_deserialization=True)
 
        chunks_file=os.path.join(kb_path, "chunks.pkl")
        with open(chunks_file, "rb") as f:
            text_chunks = pickle.load(f)
 
 #moved to rag.py because semantic docs were loaded from faiss index and didn't saved the chunk id
        # for chunk_id, chunk in enumerate(text_chunks):
        #     chunk.metadata["chunk_id"] = chunk_id
 
        result= handle_userinput(
            payload.question,
            vectorstore,
            payload.company_name,
            text_chunks,
        )
        return result
 
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")