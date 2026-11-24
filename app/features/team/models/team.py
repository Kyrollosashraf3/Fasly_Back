"""Team (فريق) - a named group of boys and servants inside one class.

A team belongs to exactly one church and one class. The name only has to be
unique inside that pair: two classes (or two churches) may both have a team
called "فريق النور". Membership lives in the two link tables, never on this
row, so a boy/servant can be added or removed without rewriting the team.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "teams"


class Team(Base):
    """A named class group (church_id + class_id + team_name)."""

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint(
            "church_id",
            "class_id",
            "team_name",
            name="uq_teams_church_id_class_id_team_name",
        ),
        Index("ix_teams_church_id_class_id", "church_id", "class_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    team_name = Column(String(100), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    church = relationship("Church")
    class_ = relationship("SchoolClass", back_populates="teams")
    members = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )
    teachers = relationship(
        "TeamTeacher", back_populates="team", cascade="all, delete-orphan"
    )

    # Display helpers - response schemas read these without extra joins.
    @property
    def member_count(self) -> int:
        return len(self.members)

    @property
    def teacher_count(self) -> int:
        return len(self.teachers)

    @property
    def class_name(self) -> str | None:
        return self.class_.name if self.class_ is not None else None

    def __repr__(self) -> str:
        return (
            f"<Team id={self.id} name={self.team_name!r} "
            f"class_id={self.class_id} church_id={self.church_id}>"
        )
