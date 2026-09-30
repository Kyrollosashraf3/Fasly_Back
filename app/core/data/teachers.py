from app.core.data.base import ClassScopedService
from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate


class TeacherService(ClassScopedService):
    def create(self, data: TeacherCreate) -> Teacher:
        pass

    def add_list(self, items: list[TeacherCreate]) -> dict:
        pass

    def get(self, teacher_id: int) -> Teacher:
        pass

    def list(self, class_name=None) -> list[Teacher]:
        pass

    def update(self, teacher_id: int, data: TeacherUpdate) -> Teacher:
        pass

    def delete(self, teacher_id: int) -> None:
        pass
