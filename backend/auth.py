from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import os
 
from backend.database import get_db
from backend.models import User

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 30
 
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
 
 
def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)
 
 
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
 
 
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode=data.copy()
    expire=datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"]=expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
 
 
def decode_token(token: str) -> Optional[str]:
    """Returns username from token or None if invalid."""
    try:
        payload=jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str=payload.get("sub")
        return username
    except JWTError:
        return None
 
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    username=decode_token(token)
    if username is None:
        raise credentials_exception
 
    user=db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user
 