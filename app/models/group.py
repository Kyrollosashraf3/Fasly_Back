"""Group assignment payloads (servant follow-up groups)."""

from app.db.database import Base

class Group(Base):

    __tablename__ = "groups"

    class_id= Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    teacher_id= Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    boy_id= Column(Integer, ForeignKey("boys.id", ondelete="CASCADE"), nullable=False)
     

