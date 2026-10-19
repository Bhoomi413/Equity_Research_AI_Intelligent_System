from fastapi import APIRouter, Depends, status, HTTPException, Response
from fastapi.security.oauth2 import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import shutil
from backend.utils.cache_manager import vectorstore_cache

from ..database import *
from ..oauth2 import *
from ..schemas import *
from ..models import *


router = APIRouter(tags=['Authentication'])

@router.post("/auth/register", status_code=201)
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
 
 
@router.post("/auth/login", response_model=TokenResponse)
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
 
 
@router.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return {"username": current_user.username, "email": current_user.email}


@router.post("/auth/change-password")
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password not correct")
 
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
 
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message":"Password changed successfully"}
 
 
 
@router.delete("/auth/delete-account")
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    vectorstore_cache.clear_user_cache(user_id)
    print("DELETED ALL THE ASSOCIATED DATA")
    
    #delete all disk files for this user
    user_pdf_dir = os.path.join("UploadedPDF", f"user_{user_id}")
    user_kb_dir = os.path.join("knowledgebase", f"user_{user_id}")
 
    try:
        if os.path.exists(user_pdf_dir):
            shutil.rmtree(user_pdf_dir)
        if os.path.exists(user_kb_dir):
            shutil.rmtree(user_kb_dir)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user files: {str(e)}")
 
    # delete user from DB — cascade deletes documents, conversations, messages
    db.delete(current_user)
    db.commit()
 
    return {"message": "Account and all associated data deleted successfully"}
 