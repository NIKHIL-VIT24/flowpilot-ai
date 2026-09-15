from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db
from .models import User

password_hash = PasswordHash.recommended()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(password: str) -> str: return password_hash.hash(password)
def verify_password(password: str, hashed: str) -> bool: return password_hash.verify(password, hashed)

def create_token(user_id: int):
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm="HS256")

def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)):
    cred = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        uid = int(payload.get("sub"))
    except Exception:
        raise cred
    user = db.get(User, uid)
    if not user: raise cred
    return user
