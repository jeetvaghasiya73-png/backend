from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Body
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dependencies.database import get_db
from app.dependencies.auth import get_current_user
from app.services.auth import auth_service
from app.schemas.user import Token, UserOut, UserCreate, LoginRequest
from app.models.user import User
from app.middleware.rate_limit import record_failed_attempt, clear_failed_attempts, get_ip

router = APIRouter()


def _require_admin_user(user, ip: str):
    """
    After authentication, ensure the user is an active admin.
    Non-admin accounts must not receive dashboard tokens.
    """
    if not user:
        record_failed_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.is_active:
        record_failed_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated",
        )
    if not user.is_admin:
        # Don't reveal that the account exists but isn't admin
        record_failed_attempt(ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )


def _set_refresh_cookie(response: Response, refresh_token: str):
    """Attach secure HttpOnly cookie for refresh_token."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=False, # Allowed over local & proxy TLS
        path="/api/v1/auth",
        max_age=7 * 24 * 60 * 60 # 7 days
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/login", response_model=Token)
def login(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
):
    """
    Standard OAuth2 compatible token login (form-based).
    Rate-limited: 5 failures per 60 s per IP.
    """
    ip = get_ip(request)
    user = auth_service.authenticate(db, username=form_data.username, password=form_data.password)
    _require_admin_user(user, ip)
    clear_failed_attempts(ip)
    tokens = auth_service.create_user_tokens(user)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return tokens


@router.post("/login/json", response_model=Token)
def login_json(
    request: Request,
    response: Response,
    user_in: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    JSON-based credentials login.
    Rate-limited: 5 failures per 60 s per IP.
    Only admin users can receive tokens.
    """
    ip = get_ip(request)
    user = auth_service.authenticate(db, username=user_in.username, password=user_in.password)
    _require_admin_user(user, ip)
    clear_failed_attempts(ip)
    tokens = auth_service.create_user_tokens(user)
    _set_refresh_cookie(response, tokens["refresh_token"])
    return tokens


@router.post("/refresh", response_model=Token)
def refresh_token(
    request: Request,
    response: Response,
    body: Optional[RefreshTokenRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Re-issue access and refresh tokens using HTTP-only cookie or payload.
    """
    token_str = request.cookies.get("refresh_token") or (body.refresh_token if body else None)
    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token cookie or payload",
        )

    tokens = auth_service.refresh_token(db, refresh_token=token_str)
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    _set_refresh_cookie(response, tokens["refresh_token"])
    return tokens


@router.post("/logout")
def logout(response: Response):
    """
    Clear HTTP-only refresh token cookie.
    """
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
def read_users_me(
    current_user: User = Depends(get_current_user),
):
    """
    Get current user profile.
    """
    return current_user

