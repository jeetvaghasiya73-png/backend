from datetime import timedelta
from sqlalchemy.orm import Session
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.repositories.user import user_repo
from app.models.user import User

class AuthService:
    def authenticate(self, db: Session, *, username: str, password: str) -> User | None:
        user = user_repo.get_by_username(db, username=username)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_user_tokens(self, user: User) -> dict:
        extra = {
            "username": user.username,
            "is_superadmin": user.is_superadmin,
        }
        access_token = create_access_token(subject=user.id, extra_claims=extra)
        refresh_token = create_refresh_token(subject=user.id)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    def refresh_token(self, db: Session, *, refresh_token: str) -> dict | None:
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
            
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
            
        try:
            user_id = int(user_id_str)
        except ValueError:
            return None
            
        user = user_repo.get(db, id=user_id)
        if not user or not user.is_active:
            return None
            
        # Re-issue new access token and optional new refresh token
        new_access_token = create_access_token(subject=user.id)
        new_refresh_token = create_refresh_token(subject=user.id)
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

auth_service = AuthService()
