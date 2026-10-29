import hashlib
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from fastapi import Cookie, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from .config import get_settings
from .database import get_db
from .models import User

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="dkl-session-v1")


def create_session(user_id: int) -> str:
    return serializer().dumps({"uid": user_id})


def session_user_id(token: str, max_age: int = 60 * 60 * 24 * 30) -> int:
    try:
        return int(serializer().loads(token, max_age=max_age)["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Sitzung ungültig")


def csrf_for(token: str) -> str:
    return hashlib.sha256((token + get_settings().secret_key).encode()).hexdigest()


def current_user(dkl_session: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    if not dkl_session:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")
    user = db.get(User, session_user_id(dkl_session))
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")
    return user


def require_csrf(request: Request, x_csrf_token: str | None = Header(default=None), dkl_session: str | None = Cookie(default=None)):
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (not dkl_session or x_csrf_token != csrf_for(dkl_session)):
        raise HTTPException(status_code=403, detail="CSRF-Prüfung fehlgeschlagen")

