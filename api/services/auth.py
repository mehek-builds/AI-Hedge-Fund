"""JWT authentication for single-user PEAD API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from loguru import logger
from passlib.context import CryptContext

# ---------------------------------------------------------------------------
# Config from env
# ---------------------------------------------------------------------------

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@pead.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")
JWT_SECRET = os.environ.get("JWT_SECRET", "insecure-default-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


# ---------------------------------------------------------------------------
# Credential verification
# ---------------------------------------------------------------------------


def verify_credentials(email: str, password: str) -> bool:
    """Verify email and plaintext password against env-configured admin credentials."""
    email_ok = email.lower().strip() == ADMIN_EMAIL.lower().strip()
    # Support both plaintext and bcrypt-hashed password in env
    if ADMIN_PASSWORD.startswith("$2b$") or ADMIN_PASSWORD.startswith("$2a$"):
        password_ok = pwd_context.verify(password, ADMIN_PASSWORD)
    else:
        password_ok = password == ADMIN_PASSWORD
    return email_ok and password_ok


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """Decode JWT and return the subject (email). Raises 401 on failure."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub: Optional[str] = payload.get("sub")
        if sub is None:
            raise credentials_exception
    except JWTError as exc:
        logger.debug(f"JWT decode error: {exc}")
        raise credentials_exception
    return sub
