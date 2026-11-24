"""Team membership - which boys belong to which team.

One row per (team, boy). ``church_id`` is copied from the team so the usual
church-first scope applies here too, exactly like ``groups``. The class is not
stored: it is reachable through the team and is validated when the link is
written.
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

TABLE = "team_members"


class TeamMember(Base):
    """ولد داخل فريق: صف واحد لكل (فريق، ولد)."""

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint("team_id", "boy_id", name="uq_team_members_team_id_boy_id"),
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
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    church = relationship("Church")
    team = relationship("Team", back_populates="members")
    boy = relationship("Boy", back_populates="team_memberships")

    @property
    def boy_name(self) -> str | None:
        return self.boy.boy_name if self.boy is not None else None

    @property
    def team_name(self) -> str | None:
        return self.team.team_name if self.team is not None else None

    def __repr__(self) -> str:
        return f"<TeamMember id={self.id} team_id={self.team_id} boy_id={self.boy_id}>"
