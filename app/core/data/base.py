from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.user import UserResponse


class BaseService:
    def __init__(self, db: Session, current_user: UserResponse):
        pass


class AdminService(BaseService):
    def __init__(self, db: Session, current_user: UserResponse):
        pass


class ClassScopedService(BaseService):
    def resolve_class(self, class_name):
        pass


class PersonCheckService(ClassScopedService):
    def _not_found(self, person_id: int) -> HTTPException:
        pass

    def _resolve_person(self, person_id: int):
        pass

    def _find_existing(self, person_id: int, action_date: date):
        pass

    def after_upsert(self, person_id: int, record) -> None:
        pass

    def _upsert(
        self,
        person_id: int,
        person_name: str | None,
        class_name,
        action_date: date,
        attend,
        note: str | None = None,
        **flags,
    ):
        pass

    def _flags_of(self, item) -> dict:
        pass

    def create(self, data):
        pass

    def create_bulk(self, data) -> list:
        pass

    def get(self, record_id: int):
        pass

    def list(self, class_name=None, action_date: date | None = None) -> list:
        pass

    def update(self, record_id: int, data):
        pass

    def delete(self, record_id: int) -> None:
        pass
