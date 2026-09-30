from app.core.data.base import PersonCheckService


class AttendanceService(PersonCheckService):
    def after_upsert(self, person_id: int, record) -> None:
        pass
