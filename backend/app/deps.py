import base64
import time

import httpx
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User
from .security import decode_token, is_blacklisted

bearer = HTTPBearer(auto_error=False)
COOKIE_NAME = "civic_token"
CUSTOM_HEADER = "X-Civic-Token"

# token -> (valid_until_epoch, local_user_id). Supabase access tokens are
# opaque to us (signed with the project's JWT secret), so we validate them
# by asking Supabase, then cache the result until the token's exp.
_supabase_cache: dict[str, tuple[float, int]] = {}
_VALID_ROLES = {"citizen", "team", "admin"}


def extract_token(request: Request, creds: HTTPAuthorizationCredentials | None) -> str | None:
    """Token from any of the three channels the frontend sends on:

    1. `Authorization: Bearer <t>`  (standard REST)
    2. `X-Civic-Token: <t>`         (custom header — most proxies don't strip it)
    3. `civic_token` cookie         (browser attaches automatically)

    Proxied deployments (e.g. preview sandboxes) may strip some of these;
    accepting all three guarantees at least one channel always survives.
    """
    if creds is not None and creds.credentials:
        return creds.credentials
    custom = request.headers.get(CUSTOM_HEADER)
    if custom:
        return custom
    return request.cookies.get(COOKIE_NAME)


def _jwt_exp_unverified(token: str) -> float | None:
    """Read `exp` from a JWT payload WITHOUT verifying the signature.
    Safe: the signature is verified by Supabase itself in /auth/v1/user."""
    try:
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = __import__("json").loads(base64.urlsafe_b64decode(payload_b64))
        return float(payload.get("exp"))
    except Exception:
        return None


def _supabase_resolve(token: str, db: Session) -> User | None:
    """Validate a Supabase access token (via Supabase' /auth/v1/user) and
    map it to a local user — creating the local record on first login.

    Existing local accounts keep their role/team: the mapping is by email,
    so e.g. a user registered in Supabase with a demo email inherits that
    account. New Supabase users start as citizens unless their account
    metadata carries role=team (set on registration).
    """
    now = time.time()
    hit = _supabase_cache.get(token)
    if hit and hit[0] > now:
        user = db.get(User, hit[1])
        return user
    if hit:  # expired cache entry — evict
        _supabase_cache.pop(token, None)

    try:
        resp = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": settings.SUPABASE_PUBLISHABLE_KEY,
            },
            timeout=10,
        )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None

    try:
        profile = resp.json()
        email = (profile.get("email") or "").strip().lower()
        meta = profile.get("user_metadata") or {}
    except ValueError:
        return None
    if not email:
        return None

    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        role = meta.get("role")
        user = User(
            name=str(meta.get("name") or email.split("@")[0]).strip()[:120] or "New user",
            email=email,
            hashed_password="supabase-managed",  # password lives in Supabase
            role=role if role in _VALID_ROLES else "citizen",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    exp = _jwt_exp_unverified(token)
    valid_until = min(exp, now + 600) if exp else now + 300
    _supabase_cache[token] = (valid_until, user.id)
    # keep the cache bounded (demo scale)
    if len(_supabase_cache) > 500:
        _supabase_cache.clear()
        _supabase_cache[token] = (valid_until, user.id)
    return user


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = extract_token(request, creds)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = decode_token(token)
    if payload is not None:
        if is_blacklisted(payload.get("jti", "")):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")
        user = db.get(User, int(payload["sub"]))
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer exists")
        return user
    # Not one of our local JWTs — accept a Supabase Auth access token.
    user = _supabase_resolve(token, db)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def require_role(*roles: str):
    def checker(user: User = Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Requires role: {' or '.join(roles)}",
            )
        return user

    return checker
