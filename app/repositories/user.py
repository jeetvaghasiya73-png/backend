from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User
from app.repositories.base import BaseRepository

class UserRepository(BaseRepository[User]):
    def get_by_username(self, db: Session, *, username: str) -> Optional[User]:
        return db.query(self.model).filter(self.model.username == username).first()

user_repo = UserRepository(User)
