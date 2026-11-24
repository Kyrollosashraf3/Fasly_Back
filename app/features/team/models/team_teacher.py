"""Team teachers - which servants are assigned to which team.

One row per (team, teacher). Servants with no single class (the church-wide
amin) may be attached; a class servant must belong to the team's class. The
link is checked on write, not trusted from the client.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "team_teachers"


class TeamTeacher(Base):
    """خادم داخل فريق: صف واحد لكل (فريق، خادم)."""

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint(
            "team_id", "teacher_id", name="uq_team_teachers_team_id_teacher_id"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    team_id = Column(
        Integer,
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    teacher_id = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    church = relationship("Church")
    team = relationship("Team", back_populates="teachers")
    teacher = relationship("Teacher", back_populates="team_assignments")

    @property
    def teacher_name(self) -> str | None:
        return self.teacher.teacher_name if self.teacher is not None else None

    @property
    def team_name(self) -> str | None:
        return self.team.team_name if self.team is not None else None

    def __repr__(self) -> str:
        return (
            f"<TeamTeacher id={self.id} team_id={self.team_id} "
            f"teacher_id={self.teacher_id}>"
        )
