from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from langchain_community.vectorstores import FAISS
import pickle

from ..database import *
from ..oauth2 import *
from ..schemas import *
from ..models import *
from backend.rag.rag import handle_userinput

router = APIRouter(tags=['Query'])


@router.post("/query")
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
        ).first()
    )
    if not doc_record:
        raise HTTPException(
            status_code=403,
            detail="Document not found or you don't have access to it",
        )
 
    kb_path=doc_record.kb_path
 
    try:
        # embeddings=GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        # vectorstore=FAISS.load_local(kb_path, embeddings, allow_dangerous_deserialization=True)
        from langchain_huggingface import HuggingFaceEmbeddings
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
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