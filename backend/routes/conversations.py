from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from langchain_community.vectorstores import FAISS
import pickle

from ..database import *
from ..oauth2 import *
from ..schemas import *
from ..models import *
from backend.rag.rag import handle_userinput,get_vectorstore
from backend.utils.cache_manager import vectorstore_cache
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS



router = APIRouter(tags=['Query'])

 
embeddings_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

@router.post("/conversations")
def create_conversation(
    payload: NewConversationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # confirm document belongs to this user
    doc = db.query(Document).filter(
        Document.id == payload.document_id,
        Document.user_id == current_user.id,
    ).first()
 
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
 
    conversation = Conversation(
        user_id=current_user.id,
        document_id=doc.id,
        company_name=doc.company_name,
        title=None,  #set on first query
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
 
    return {
        "id": conversation.id,
        "document_id": doc.id,
        "company_name": doc.company_name,
        "title": conversation.title,
        "created_at": str(conversation.created_at),
    }
 
 
 
@router.get("/conversations/my")
def list_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    return [
        {
            "id": c.id,
            "document_id": c.document_id,
            "company_name": c.company_name,
            "title": c.title or "New conversation",
            "created_at": str(c.created_at),
            "updated_at": str(c.updated_at),
        }
        for c in conversations
    ]
 
 
 
@router.get("/conversations/{conversation_id}")
def get_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
 
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
 
    messages = [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": str(m.created_at),
        }
        for m in conversation.messages
    ]
 
    return {
        "id": conversation.id,
        "document_id": conversation.document_id,
        "company_name": conversation.company_name,
        "title": conversation.title or "New conversation",
        "messages": messages,
        "created_at": str(conversation.created_at),
        "updated_at": str(conversation.updated_at),
    }
 
 
 
@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
 
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
 
    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted", "conversation_id": conversation_id}
 
 
 
@router.post("/conversations/{conversation_id}/query")
def query_in_conversation(
    conversation_id: int,
    payload: QueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
 
    #confirm conversation belongs to this user
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id,
    ).first()
 
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
 
    #confirm document still exists and belongs to this user — ownership check
    doc = db.query(Document).filter(
        Document.id == conversation.document_id,
        Document.user_id == current_user.id,
    ).first()
 
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")


#build unique cache key: scoped to user_id and file_hash (to handle versioning)
    cache_key= f"user_{current_user.id}:{doc.file_hash}"
    kb_path=doc.kb_path

    # Check RAM 
    cached_data = vectorstore_cache.get(cache_key)

    if cached_data:
        print(f"[RAM Cache Hit] Loaded vectorstore from RAM for key: {cache_key}")
        vectorstore, text_chunks = cached_data
    else:
        print(f"[RAM Cache Miss] Loading vectorstore from disk for path: {kb_path}")
        try:
            vectorstore = FAISS.load_local(
                kb_path, 
                embeddings_model, 
                allow_dangerous_deserialization=True
            )

            chunks_file = os.path.join(kb_path, "chunks.pkl")
            with open(chunks_file, "rb") as f:
                text_chunks = pickle.load(f)

            for chunk_id, chunk in enumerate(text_chunks):
                chunk.metadata["chunk_id"] = chunk_id

            # Store in RAM cache
            vectorstore_cache.put(cache_key, (vectorstore, text_chunks))

        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to load document embeddings: {str(e)}"
            )

 
    # fetch last 5 messages for query rewrite context
    last_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(5)
        .all()
    )
    # reverse so oldest is first — chronological order for the rewrite prompt
    history = [
        {"role": m.role, "content": m.content}
        for m in reversed(last_messages)
    ]
 
    # kb_path = doc.kb_path
    # try:
    #     from langchain_community.embeddings import HuggingFaceEmbeddings
    #     from langchain_community.vectorstores import FAISS
 
    #     embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    #     vectorstore = FAISS.load_local(kb_path, embeddings, allow_dangerous_deserialization=True)
 
    #     chunks_file = os.path.join(kb_path, "chunks.pkl")
    #     with open(chunks_file, "rb") as f:
    #         text_chunks = pickle.load(f)
 
    #     for chunk_id, chunk in enumerate(text_chunks):
    #         chunk.metadata["chunk_id"] = chunk_id
 
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=f"Failed to load document embeddings: {str(e)}")
 
    # run RAG with history
    try:
        result = handle_userinput(
            payload.question,
            vectorstore,
            doc.company_name or "",
            text_chunks,
            conversation_history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
 
    # save user message
    user_msg = Message(
        conversation_id=conversation_id,
        role="user",
        content=payload.question,
    )
    db.add(user_msg)
 
    assistant_msg = Message(
        conversation_id=conversation_id,
        role="assistant",
        content=result["content"],
    )
    db.add(assistant_msg)
 
    # setting conversation title from first question if not set yet
    if not conversation.title:
        words = payload.question.strip().split()
        title_words = " ".join(words[:6])
        company = doc.company_name or ""
        conversation.title = f"{title_words} — {company}" if company else title_words
 
    # update updated_at so conversation rises to top
    conversation.updated_at = datetime.now(timezone.utc)
 
    db.commit()
 
    return {
        "content": result["content"],
        "citations": result["citations"],
        "conversation_id": conversation_id,
        "title": conversation.title,
    }
 