from sqlalchemy.orm import Session

from app.core.data.base import BaseService
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


def get_user_by_mail(db: Session, mail: str) -> User | None:
    pass


class UserService(BaseService):
    def create_user(self, data: UserCreate) -> User:
        pass

    def get_user(self, user_id: int) -> User:
        pass

    def update_user(self, user_id: int, data: UserUpdate) -> User:
        pass

    def list_users(self) -> list[User]:
        pass

    def delete_user(self, user_id: int) -> None:
        pass
