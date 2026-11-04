from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import bearer, extract_token, get_current_user
from ..models import Team, User
from ..schemas import LoginIn, RegisterIn
from ..security import blacklist_token, create_access_token, decode_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalars(select(User).where(User.email == body.email)).first():
        raise HTTPException(409, "Email already registered")
    if db.scalars(select(User).where(User.name == body.name)).first():
        raise HTTPException(409, "Name already used")
    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token, _ = create_access_token(user.id, user.role)
    return {"user": user_out(user), "access_token": token, "token_type": "bearer"}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalars(select(User).where(User.email == body.email)).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(401, "Invalid email or password")
    token, _ = create_access_token(user.id, user.role)
    return {"user": user_out(user), "access_token": token, "token_type": "bearer"}


@router.post("/logout")
def logout(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    user: User = Depends(get_current_user),
):
    """Blacklist the presented token's jti until its natural expiry.

    Works for both header and cookie auth (same extraction as get_current_user).
    """
    token = extract_token(request, creds)
    if token:
        payload = decode_token(token)
        if payload:
            blacklist_token(payload.get("jti", ""), int(payload.get("exp", 0)))
    return {"detail": "Logged out"}


@router.get("/me")
def me(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    out = user_out(user)
    if user.role == "team":
        team = db.scalars(select(Team).where(Team.user_id == user.id)).first()
        out["team_id"] = team.id if team else None
    return out
