import hashlib
import random
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from .config import get_settings
from .database import Base, SessionLocal, engine, get_db
from .models import Contact, FriendRequest, InviteUse, Message, Status, User
from .realtime import manager
from .schemas import FriendRequestIn, LoginIn, MessageIn, MessageOut, ProfilePatch, RegisterIn, UserOut
from .security import create_session, csrf_for, current_user, hash_password, require_csrf, session_user_id, verify_password

settings = get_settings()
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="DKL Chat API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def public_user(user: User, viewer_id: int | None = None):
    status = Status.offline if user.status == Status.invisible and viewer_id != user.id else user.status
    return {"id": user.id, "dkl_number": user.dkl_number, "username": user.username, "display_name": user.display_name, "status": status, "status_message": user.status_message, "theme": user.theme}


def unique_dkl(db: Session) -> str:
    for _ in range(20):
        number = str(random.SystemRandom().randint(10_000_000, 99_999_999))
        if not db.scalar(select(User.id).where(User.dkl_number == number)):
            return number
    raise HTTPException(503, "Keine DKL-Nummer verfügbar")


def are_contacts(db: Session, a: int, b: int) -> bool:
    return db.scalar(select(Contact.id).where(Contact.owner_id == a, Contact.contact_id == b, Contact.blocked.is_(False))) is not None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/register", response_model=UserOut)
@limiter.limit("5/minute")
def register(request: Request, data: RegisterIn, response: Response, db: Session = Depends(get_db)):
    code_hash = hashlib.sha256(data.invite_code.encode()).hexdigest()
    if data.invite_code not in settings.invites or db.scalar(select(InviteUse.id).where(InviteUse.code_hash == code_hash)):
        raise HTTPException(400, "Einladungscode ungültig oder bereits verwendet")
    user = User(dkl_number=unique_dkl(db), username=data.username.lower(), display_name=data.display_name.strip(), password_hash=hash_password(data.password), status=Status.online)
    db.add(user)
    try:
        db.flush()
        db.add(InviteUse(code_hash=code_hash, used_by=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Benutzername bereits vergeben")
    set_session(response, user.id)
    return user


def set_session(response: Response, user_id: int):
    token = create_session(user_id)
    response.set_cookie("dkl_session", token, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=2592000, path="/")
    response.set_cookie("dkl_csrf", csrf_for(token), httponly=False, secure=settings.cookie_secure, samesite="lax", max_age=2592000, path="/")


@app.post("/api/auth/login", response_model=UserOut)
@limiter.limit("10/minute")
def login(request: Request, data: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(or_(User.username == data.login.lower(), User.dkl_number == data.login)))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Anmeldedaten ungültig")
    user.status = Status.online
    db.commit()
    set_session(response, user.id)
    return user


@app.post("/api/auth/logout", dependencies=[Depends(require_csrf)])
async def logout(response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.status = Status.offline
    db.commit()
    response.delete_cookie("dkl_session", path="/")
    response.delete_cookie("dkl_csrf", path="/")
    await manager.broadcast({"type": "presence", "user_id": user.id, "status": "offline"})
    return {"ok": True}


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return public_user(user, user.id)


@app.patch("/api/me", dependencies=[Depends(require_csrf)])
async def update_me(data: ProfilePatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    await manager.broadcast({"type": "presence", "user_id": user.id, "status": "offline" if user.status == Status.invisible else user.status.value})
    return public_user(user, user.id)


@app.get("/api/users/search")
def search_user(dkl_number: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    found = db.scalar(select(User).where(User.dkl_number == dkl_number))
    if not found or found.id == user.id:
        raise HTTPException(404, "Benutzer nicht gefunden")
    return public_user(found, user.id)


@app.get("/api/contacts")
def contacts(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Contact, User).join(User, User.id == Contact.contact_id).where(Contact.owner_id == user.id, Contact.blocked.is_(False))).all()
    return [{**public_user(other, user.id), "group_name": relation.group_name} for relation, other in rows]


@app.get("/api/friends/requests")
def requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(FriendRequest, User).join(User, User.id == FriendRequest.sender_id).where(FriendRequest.recipient_id == user.id)).all()
    return [{"request_id": req.id, "user": public_user(sender, user.id), "created_at": req.created_at} for req, sender in rows]


@app.post("/api/friends/requests", dependencies=[Depends(require_csrf)])
async def request_friend(data: FriendRequestIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    recipient = db.scalar(select(User).where(User.dkl_number == data.dkl_number))
    if not recipient or recipient.id == user.id:
        raise HTTPException(404, "Benutzer nicht gefunden")
    if are_contacts(db, user.id, recipient.id):
        raise HTTPException(409, "Bereits als Kontakt hinzugefügt")
    db.add(FriendRequest(sender_id=user.id, recipient_id=recipient.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Anfrage bereits gesendet")
    await manager.send(recipient.id, {"type": "friend_request", "from": public_user(user, recipient.id)})
    return {"ok": True}


@app.post("/api/friends/requests/{request_id}/accept", dependencies=[Depends(require_csrf)])
async def accept_friend(request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    req = db.scalar(select(FriendRequest).where(FriendRequest.id == request_id, FriendRequest.recipient_id == user.id))
    if not req:
        raise HTTPException(404, "Anfrage nicht gefunden")
    db.add_all([Contact(owner_id=user.id, contact_id=req.sender_id), Contact(owner_id=req.sender_id, contact_id=user.id)])
    sender_id = req.sender_id
    db.delete(req)
    db.commit()
    await manager.send(sender_id, {"type": "friend_accepted", "user": public_user(user, sender_id)})
    return {"ok": True}


@app.delete("/api/friends/requests/{request_id}", dependencies=[Depends(require_csrf)])
def reject_friend(request_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    req = db.scalar(select(FriendRequest).where(FriendRequest.id == request_id, FriendRequest.recipient_id == user.id))
    if not req:
        raise HTTPException(404, "Anfrage nicht gefunden")
    db.delete(req)
    db.commit()
    return {"ok": True}


@app.get("/api/messages/{contact_id}", response_model=list[MessageOut])
def message_history(contact_id: int, before: int | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not are_contacts(db, user.id, contact_id):
        raise HTTPException(403, "Kein Zugriff auf diese Unterhaltung")
    condition = or_(and_(Message.sender_id == user.id, Message.recipient_id == contact_id), and_(Message.sender_id == contact_id, Message.recipient_id == user.id))
    query = select(Message).where(condition)
    if before:
        query = query.where(Message.id < before)
    return list(reversed(db.scalars(query.order_by(Message.id.desc()).limit(50)).all()))


@app.post("/api/messages/{contact_id}", response_model=MessageOut, dependencies=[Depends(require_csrf)])
@limiter.limit("60/minute")
async def send_message(request: Request, contact_id: int, data: MessageIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not are_contacts(db, user.id, contact_id):
        raise HTTPException(403, "Kein Zugriff auf diese Unterhaltung")
    message = Message(sender_id=user.id, recipient_id=contact_id, body=data.body.strip())
    db.add(message)
    db.commit()
    payload = MessageOut.model_validate(message).model_dump(mode="json")
    await manager.send(contact_id, {"type": "message", "message": payload})
    return message


@app.websocket("/api/ws")
async def websocket(socket: WebSocket):
    token = socket.cookies.get("dkl_session")
    if not token:
        await socket.close(code=4401)
        return
    try:
        user_id = session_user_id(token)
    except HTTPException:
        await socket.close(code=4401)
        return
    db = SessionLocal()
    user = db.get(User, user_id)
    if not user:
        db.close()
        await socket.close(code=4401)
        return
    await manager.connect(user_id, socket)
    user.status = Status.online if user.status == Status.offline else user.status
    db.commit()
    await manager.broadcast({"type": "presence", "user_id": user_id, "status": "offline" if user.status == Status.invisible else user.status.value}, exclude=user_id)
    try:
        while True:
            event = await socket.receive_json()
            if event.get("type") in {"typing", "nudge"}:
                target = int(event.get("to", 0))
                if are_contacts(db, user_id, target):
                    await manager.send(target, {"type": event["type"], "from": user_id, "active": bool(event.get("active", True))})
    except WebSocketDisconnect:
        manager.disconnect(user_id, socket)
    finally:
        if user_id not in manager.connections:
            user.status = Status.offline
            db.commit()
            await manager.broadcast({"type": "presence", "user_id": user_id, "status": "offline"})
        db.close()

