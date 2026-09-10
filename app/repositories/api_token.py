from typing import Optional
from sqlalchemy.orm import Session
from app.models.api_token import ApiToken, ApiTokenUsage
from app.repositories.base import BaseRepository

class ApiTokenRepository(BaseRepository[ApiToken]):
    def get_by_token(self, db: Session, *, token: str) -> Optional[ApiToken]:
        return db.query(self.model).filter(self.model.token == token).first()

    def get_multi_by_user(self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100):
        return db.query(self.model).filter(self.model.user_id == user_id).offset(skip).limit(limit).all()

api_token_repo = ApiTokenRepository(ApiToken)

class ApiTokenUsageRepository(BaseRepository[ApiTokenUsage]):
    def get_multi_by_token(self, db: Session, *, token_id: int, skip: int = 0, limit: int = 100):
        return db.query(self.model).filter(self.model.token_id == token_id).order_by(self.model.used_at.desc()).offset(skip).limit(limit).all()

api_token_usage_repo = ApiTokenUsageRepository(ApiTokenUsage)
