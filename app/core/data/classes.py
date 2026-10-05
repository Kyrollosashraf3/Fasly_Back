"""Class catalogue (الفصول) - the anchor every permission scope resolves to."""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import (
    apply_update,
    commit,
    get_or_404,
    my_class_id,
    normalise_name,
)
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.school_class import SchoolClass
from app.models.teacher import Teacher
from app.schemas.school_class import SchoolClassCreate, SchoolClassUpdate


class ClassService(BaseService):
    """Reads are open to every login (a grade label leaks nothing); only the
    class amin or the super admin may create / rename / retire a class.
    """


    def query(self) -> Query:
        return self.db.query(SchoolClass)

    def list(self) -> list[SchoolClass]:
        return (
            self.query()
            .order_by(SchoolClass.academic_year.desc(), SchoolClass.id)
            .all()
        )

    def get(self, class_id: int) -> SchoolClass:
        return get_or_404(self.db, SchoolClass, class_id, "Class")

    def create(self, data: SchoolClassCreate) -> SchoolClass:
        self.ensure_manager()
        school_class = SchoolClass(
            name=data.name.strip(), academic_year=data.academic_year
        )
        self.db.add(school_class)
        commit(self.db, f"Class create name={data.name}")
        return school_class

    def update(self, class_id: int, data: SchoolClassUpdate) -> SchoolClass:
        school_class = self.get(class_id)
        self.ensure_manager()
        apply_update(school_class, data, strip=("name",))
        commit(self.db, f"Class update id={class_id}")
        return school_class

    def delete(self, class_id: int) -> None:
        school_class = self.get(class_id)
        self.ensure_manager()
        # A class still holding servants or boys is refused by the RESTRICT
        # foreign keys; this message says why before the driver does.
        occupied = (
            self.db.query(Boy.id).filter(Boy.class_id == class_id).first()
            or self.db.query(Teacher.id)
            .filter(Teacher.class_id == class_id)
            .first()
        )
        if occupied is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Move the class's servants and boys out first.",
            )
        self.db.delete(school_class)
        commit(self.db, f"Class delete id={class_id}")

    def label_lookup(self) -> dict[str, int]:
        """Normalized class label -> id, so a spreadsheet's ``class_name``
        column can become a ``class_id``.

        Only the classes this login may *write into* are offered (super admin:
        every class, amin: his own), so an import can never point at a class
        the caller is not allowed to fill.
        """
        mine = my_class_id(self.db, self.user)
        return {
            normalise_name(row.name): row.id
            for row in self.list()
            if mine is None or row.id == mine
        }
