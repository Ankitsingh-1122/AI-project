"""Password hashing (scrypt) and JWT helpers - no external crypto deps."""

import hashlib
import hmac
import os
import time
import uuid

import jwt

from .config import settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt|" + salt.hex() + "|" + digest.hex()


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt_hex, digest_hex = stored.split("|")
        if algo != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def create_access_token(user_id: int, role: str) -> tuple[str, str]:
    """Returns (token, jti)."""
    jti = uuid.uuid4().hex
    expire = int(time.time()) + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "exp": expire,
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


# In-memory logout blacklist (jti -> expiry). Fine for demo; swap for
# Redis/DB token store in production.
_blacklist: dict[str, float] = {}


def blacklist_token(jti: str, exp: int):
    _blacklist[jti] = exp
    # opportunistic cleanup
    now = time.time()
    for k in [k for k, v in _blacklist.items() if v < now]:
        _blacklist.pop(k, None)


def is_blacklisted(jti: str) -> bool:
    return _blacklist.get(jti, 0) > time.time()
