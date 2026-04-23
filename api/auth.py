"""JWT 认证 - 仅依赖 PyJWT + 标准库"""
import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta

import jwt

SECRET_KEY = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
ALGORITHM = "HS256"
EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "168"))  # 7天

PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
    ).hex()
    return f"{salt}${key}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        salt, stored_key = hashed.split("$", 1)
        key = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS
        ).hex()
        return secrets.compare_digest(key, stored_key)
    except (ValueError, AttributeError):
        return False


def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(hours=EXPIRE_HOURS)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
