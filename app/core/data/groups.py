from app.core.data.base import ClassScopedService


def _pct(present: int, total: int) -> float:
    pass


def _class_value(value):
    pass


class GroupsService(ClassScopedService):
    def assign(self, teacher_id: int, boy_ids: list[int]) -> dict:
        pass

    def unassign(self, boy_ids: list[int]) -> dict:
        pass

    def _find_exact(
        self,
        model,
        name_field: str,
        name: str,
        class_name,
        label: str,
    ):
        pass

    def assign_import(self, rows: list[dict]) -> dict:
        pass

    def _scope_classes(self, class_name) -> list[str]:
        pass

    def _scope_query(self, query, model, classes: list[str]):
        pass

    def _boys_in(self, classes: list[str]) -> list[object]:
        pass

    def _teachers_in(self, classes: list[str]) -> list[object]:
        pass

    def _boy_summary(self, boy, attends_by_boy: dict, fu_by_boy: dict) -> dict:
        pass

    def list_groups(
        self,
        class_name=None,
        teacher_id: int | None = None,
    ) -> dict:
        pass
