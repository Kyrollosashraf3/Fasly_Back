"""Class catalogue (الفصول) - the anchor every permission scope resolves to."""

from fastapi import HTTPException, status

from app.core.data.base import AdminService
from app.core.data.common import get_or_404
from app.models.boy import Boy
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.schemas.school_class import SchoolClassCreate, SchoolClassUpdate


def _norm(label: str) -> str:
    """Case/whitespace-insensitive form of a class label typed in a cell."""
    return " ".join(str(label).split()).lower()


class ClassService(AdminService):
    """Reads are open to every login (a grade label leaks nothing); only the
    amin or the super admin may create / rename / retire a class.
    """

    def _query(self):
        return self.db.query(SchoolClass)

    def create(self, data: SchoolClassCreate) -> SchoolClass:
        self._ensure_write()
        school_class = SchoolClass(
            name=data.name.strip(),
            academic_year=data.academic_year,
        )
        self.db.add(school_class)
        self._commit(f"Class create name={data.name}")
        return school_class

    def get(self, class_id: int) -> SchoolClass:
        return get_or_404(self.db, SchoolClass, class_id, "Class")

    def list(self):
        return (
            self._query()
            .order_by(SchoolClass.academic_year.desc(), SchoolClass.id)
            .all()
        )

    def label_lookup(self) -> dict[str, int]:
        """Normalized class label -> id, so a spreadsheet's ``class_name``
        column can become ``class_id``.

        Only the classes this login may *write into* are offered (super admin:
        every class, amin: his own), so an import can never point at a class
        the caller is not allowed to fill.
        """
        writable = [
            row
            for row in self.list()
            if self.scope.is_super_admin or row.id == self.scope.class_id
        ]
        lookup: dict[str, int] = {}
        for school_class in writable:
            lookup.setdefault(_norm(school_class.name), school_class.id)
        return lookup

    def update(self, class_id: int, data: SchoolClassUpdate) -> SchoolClass:
        school_class = self.get(class_id)
        self._ensure_write()
        updates = data.model_dump(exclude_unset=True)
        if "name" in updates:
            updates["name"] = updates["name"].strip()
        for field, value in updates.items():
            setattr(school_class, field, value)
        self._commit(f"Class update id={class_id}")
        return school_class

    def delete(self, class_id: int) -> None:
        school_class = self.get(class_id)
        self._ensure_write()
        # RESTRICT refuses while servants or boys still belong to it
        has_boys = self.db.query(Boy.id).filter(Boy.class_id == class_id).first()
        has_teachers = (
            self.db.query(Teacher.id).filter(Teacher.class_id == class_id).first()
        )
        if has_boys is not None or has_teachers is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Move the class's servants and boys out first.",
            )
        self.db.delete(school_class)
        self._commit(f"Class delete id={class_id}")
