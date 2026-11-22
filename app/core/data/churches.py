"""Churches (الكنائس) - the tenant anchor of the whole platform.

Only the platform owner (``super_admin``) creates, suspends or removes a
church. Every other login may read its own church record - the one row it is
pinned to - and nothing else.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.core.data.base import BaseService
from app.core.data.common import (
    commit,
    deny,
    ensure_unique,
    get_or_404,
)
from app.models.church import Church
from app.models.enums import RoleEnum
from app.schemas.church import ChurchCreate, ChurchUpdate


class ChurchService(BaseService):
    """Read : owner all churches | everyone else only their own church.
    Write: platform owner only.
    """

    def query(self):
        # The church list is the owner's tenant directory, so it deliberately
        # ignores ``selected_church_id``: the header filter must keep offering
        # every church even while the owner is looking at one of them.
        query = self.db.query(Church)
        if self.user.role == RoleEnum.SUPER_ADMIN:
            return query
        if self.user.church_id is None:
            return query.filter(Church.id.in_([]))
        return query.filter(Church.id == self.user.church_id)

    def list(self) -> list[Church]:
        return self.query().order_by(Church.name).all()

    def get(self, church_id: int) -> Church:
        church = self.query().filter(Church.id == church_id).first()
        if church is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Church {church_id} not found.",
            )
        return church

    def _ensure_owner(self) -> None:
        if self.user.role != RoleEnum.SUPER_ADMIN:
            deny("Only the platform owner can manage churches.")

    def create(self, data: ChurchCreate) -> Church:
        self._ensure_owner()
        name = data.name.strip()
        ensure_unique(self.db, Church, "name", name, label="Church")
        church = Church(
            name=name,
            region=data.region,
            address=data.address,
            phone=data.phone,
            phone_2=data.phone_2,
            is_active=data.is_active,
            expiry_date=data.expiry_date,
        )
        self.db.add(church)
        commit(self.db, f"Church create name={name}")
        return church

    def update(self, church_id: int, data: ChurchUpdate) -> Church:
        self._ensure_owner()
        church = get_or_404(self.db, Church, church_id, "Church")
        if "name" in data.model_fields_set and data.name is not None:
            name = data.name.strip()
            ensure_unique(
                self.db, Church, "name", name, exclude_id=church_id, label="Church"
            )
            church.name = name
        for field in (
            "region",
            "address",
            "phone",
            "phone_2",
            "is_active",
            "expiry_date",
        ):
            if field in data.model_fields_set:
                setattr(church, field, getattr(data, field))
        commit(self.db, f"Church update id={church_id}")
        return church

    def delete(self, church_id: int) -> None:
        self._ensure_owner()
        church = get_or_404(self.db, Church, church_id, "Church")
        # Every tenant table references churches with ON DELETE RESTRICT, so a
        # church holding any data cannot be removed. Give a clear answer rather
        # than leaking a raw IntegrityError.
        from sqlalchemy.exc import IntegrityError

        try:
            self.db.delete(church)
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This church still has classes, people or other data. "
                    "Remove those first, then delete the church."
                ),
            )
