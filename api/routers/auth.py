"""Authentication router — POST /auth/login."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from api.models.schemas import LoginRequest, TokenResponse
from api.services.auth import create_access_token, verify_credentials

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    """Exchange email + password for a JWT access token."""
    if not verify_credentials(body.email, body.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token({"sub": body.email})
    return TokenResponse(access_token=token)
