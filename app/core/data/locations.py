"""Save the GPS point of a boy's house onto ``boys`` itself.

Two doors into the same columns:

* a servant / amin standing in front of the house saves a point for that boy;
* a boy logged into his own account saves his point with ``/boys/me``.

If the caller also sends ``status`` (the existing ``FollowEnum``), a follow-up
row is written in the same transaction - the follow-up type has always lived
on ``follow_ups.status``, never on the boy's coordinates.
"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Query

from app.core.data.base import BaseService
from app.core.data.common import commit, ensure_boy_access, get_or_404
from app.models.boy import Boy
from app.models.enums import RoleEnum
from app.models.follow_up import FollowUp
from app.schemas.location import BoyLocationResponse, LocationRecord


class BoyLocationService(BaseService):
    """write: any staff member for a boy in scope | a boy for himself
    read : the same scopes as ``BoyService`` (a boy only sees his own point)
    """

    # -------------------------------------------------------------- helpers
    def _boy(self, boy_id: int) -> Boy:
        boy = get_or_404(self.db, Boy, boy_id, "Boy")
        ensure_boy_access(self.db, self.user, boy)
        return boy

    def _query(self, boy_id: int) -> Query:
        self._boy(boy_id)  # permission check before the read
        return self.db.query(Boy).filter(Boy.id == boy_id)

    @staticmethod
    def _response(boy: Boy, follow_up_id: int | None = None) -> BoyLocationResponse:
        return BoyLocationResponse(
            boy_id=boy.id,
            boy_name=boy.boy_name,
            latitude=boy.latitude,
            longitude=boy.longitude,
            updated_at=boy.updated_at,
            follow_up_id=follow_up_id,
        )

    # ---------------------------------------------------------------- writes
    def record(self, boy_id: int | None, data: LocationRecord) -> BoyLocationResponse:
        """Write the point onto ``boys`` and optionally log one follow-up.

        ``boy_id=None`` means the caller is the boy himself. A boy account can
        only ever save its own coordinates; it never writes a follow-up row.
        """
        if boy_id is None:
            if self.user.role != RoleEnum.USER or self.user.boy_id is None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This route is only for a boy's own account.",
                )
            boy_id = self.user.boy_id

        boy = self._boy(boy_id)
        boy.latitude = data.latitude
        boy.longitude = data.longitude

        follow_up = None
        if data.status is not None and self.user.role != RoleEnum.USER:
            teacher_id = self.user.teacher_id or boy.teacher_id
            if teacher_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "This boy has no servant group, so a follow-up cannot "
                        "be logged. Save the location first, then assign a servant."
                    ),
                )
            follow_up = FollowUp(
                teacher_id=teacher_id,
                boy_id=boy.id,
                class_id=boy.class_id,  # historical snapshot, as everywhere else
                action_date=date.today(),
                status=data.status,
                note=data.note,
                recorded_by=self.user_id,
            )
            self.db.add(follow_up)

        self.db.flush()  # updated_at + follow-up id are available before commit
        result = self._response(boy, follow_up.id if follow_up is not None else None)
        commit(
            self.db,
            f"Boy location save boy={boy.id} by user={self.user_id}"
            + (f" follow_up={follow_up.id}" if follow_up is not None else ""),
        )
        return result

    # ----------------------------------------------------------------- reads
    def current(self, boy_id: int) -> BoyLocationResponse | None:
        boy = self._query(boy_id).first()
        if boy is None or boy.latitude is None or boy.longitude is None:
            return None
        return self._response(boy)
