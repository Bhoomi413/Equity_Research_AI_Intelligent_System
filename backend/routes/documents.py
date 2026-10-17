from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
import hashlib
from sqlalchemy.orm import Session

from ..database import *
from ..oauth2 import *
from ..schemas import *
from ..models import *
from backend.rag.rag import load_pdf, get_text_chunks, handle_userinput, get_vectorstore

router = APIRouter(tags=['Documents'])


@router.post("/documents/upload")
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
            "document_id": existing.id,

        }
 
    #save PDF to disk
    user_pdf_dir =os.path.join("UploadedPDF",f"user_{current_user.id}",file_hash)
    os.makedirs(user_pdf_dir, exist_ok=True)
    safe_filename = os.path.basename(file.filename) #to prevent path traversal attack
    save_path = os.path.join(user_pdf_dir,safe_filename)
    with open(save_path, "wb") as f:
        f.write(pdf_bytes)
  
    #create kb folder 
    os.makedirs(kb_path, exist_ok=True)
    import traceback
    try:
        print("STEP 1")
        raw_docs = load_pdf(save_path, company_name)
        print("STEP 2")
        text_chunks = get_text_chunks(raw_docs)
        print("STEP 3")
        get_vectorstore(text_chunks, False, kb_path )
        print("STEP 4")
    except Exception as e:
        traceback.print_exc()
        import shutil
        if os.path.exists(user_pdf_dir):
            shutil.rmtree(user_pdf_dir)   # remove orphaned PDF
        if os.path.exists(kb_path):
            shutil.rmtree(kb_path)         #remove partial knowledgebase
        raise HTTPException(status_code=500, detail="Document processing failed")
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
        "document_id": doc.id,

    }
 

 
 
@router.get("/documents/my")
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

@router.delete("/delete/document/{document_id}")
def delete_document(document_id:int,current_user:User=Depends(get_current_user), db:Session=Depends(get_db)):
    doc=db.query(Document).filter(Document.user_id==current_user.id,Document.id==document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    file_hash=doc.file_hash
    user_pdf_dir= os.path.join("UploadedPDF", f"user_{current_user.id}", file_hash)
    kb_path=doc.kb_path

    try:
        import shutil
        if os.path.exists(user_pdf_dir):
                shutil.rmtree(user_pdf_dir)   # remove orphaned PDF
        if os.path.exists(kb_path):
                shutil.rmtree(kb_path)         #remove partial knowledgebase
        db.delete(doc)
        db.commit()

        return {
            "message": "Document deleted successfully","document_id": document_id
          }
    
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500,detail="Failed to delete document")


@router.get("/documents/download/{document_id}")
def download_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.user_id == current_user.id,
    ).first()
 
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
 
    # build the pdf path from stored info
    safe_filename = os.path.basename(doc.filename)
    pdf_path = os.path.join("UploadedPDF", f"user_{current_user.id}", doc.file_hash, safe_filename)
 
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF file not found on disk")
 
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=doc.filename,
    )


