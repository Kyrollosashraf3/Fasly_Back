from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "task_values"


class TaskValue(Base):
    """تسميع ولد واحد لمسابقة واحدة: مين سمّعله، وإمتى، وهل استلم الطايو.

    ``(task_id, boy_id)`` هو هوية السجل - المسابقة تُسمع مرة واحدة، فالتسميع
    التاني لنفس الولد مرفوض.

    ``class_id`` لقطة من فصل الولد لحظة التسجيل، حتى تبقى المستحقات صحيحة
    تاريخيًا بعد نقل الأولاد بين الفصول.

    ``created_by`` الخادم اللي سمّع الولد (مرجع إلى جدول الخدام).

    ``received`` استلام الطايو: يُعلم عليها عند التسميع أو من صفحة المستحقات.
    """

    __tablename__ = TABLE
    __table_args__ = (
        UniqueConstraint("task_id", "boy_id", name="uq_task_values_task_id_boy_id"),
        Index("ix_task_values_task_id_received", "task_id", "received"),
    )

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_id = Column(
        Integer,
        ForeignKey("tasks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    boy_id = Column(
        Integer,
        ForeignKey("boys.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    action_date = Column(Date, nullable=False, index=True)
    received = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_by = Column(
        Integer,
        ForeignKey("teachers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    class_ = relationship("SchoolClass", back_populates="task_values")
    task = relationship("Task", back_populates="task_values")
    boy = relationship("Boy", back_populates="task_values")
    teacher = relationship("Teacher", back_populates="task_values")

    # Display helpers - the response shapes read these without extra joins.
    @property
    def boy_name(self) -> str | None:
        return self.boy.boy_name if self.boy else None

    @property
    def task_name(self) -> str | None:
        return self.task.task_name if self.task else None

    @property
    def task_value(self) -> int:
        """الطايو المستحقة على هذا التسميع: تُقرأ من المسابقة نفسها."""
        return self.task.value if self.task is not None else 0

    @property
    def created_by_name(self) -> str | None:
        """اسم الخادم اللي سمّع الولد."""
        return self.teacher.teacher_name if self.teacher else None

    def __repr__(self) -> str:
        return (
            f"<TaskValue id={self.id} task_id={self.task_id} "
            f"boy_id={self.boy_id} received={self.received}>"
        )
