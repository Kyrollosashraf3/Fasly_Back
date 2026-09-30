from app.core.data.base import ClassScopedService
from app.models.boy import Boy
from app.schemas.boy import BoyCreate, BoyUpdate


class BoyService(ClassScopedService):
    def create(self, data: BoyCreate) -> Boy:
        pass

    def add_list(self, items: list[BoyCreate]) -> dict:
        pass

    def get(self, boy_id: int) -> Boy:
        pass

    def list(self, class_name=None, issue_flag: bool | None = None) -> list[Boy]:
        pass

    def update(self, boy_id: int, data: BoyUpdate) -> Boy:
        pass

    def delete(self, boy_id: int) -> None:
        pass
