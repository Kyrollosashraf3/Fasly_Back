from datetime import date

from sqlalchemy import Column, Date, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.database import Base

TABLE = "tasks"


class Task(Base):
    """مسابقة واحدة داخل فصل: اسمها ومكافأتها بالطايو.

    ``value`` عدد الطايو التي يستحقها الولد لما يسمع المسابقة (مثلاً حفظ
    اصحاح 4 من انجيل مرقس = 50 طايو). القيمة تبقى هنا وحدها: كل تسميع يُقرأ
    طايوه من مسابقته، فتعديلها يحرّك كل المستحقات المسجّلة عليها.

    ``class_id`` يلمح الفصل لحظة الإنشاء ولا يتغيّر عند نقل الصفوف لاحقًا،
    زي الرحلات بالظبط.
    """

    __tablename__ = TABLE

    id = Column(Integer, primary_key=True, index=True)
    church_id = Column(
        Integer,
        ForeignKey("churches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    task_name = Column(String(200), nullable=False, index=True)
    value = Column(Integer, nullable=False, default=0)
    class_id = Column(
        Integer,
        ForeignKey("classes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_at = Column(Date, nullable=False, default=date.today, index=True)
    status = Column(String(20), nullable=False, default='active', index=True)

    # Relationships
    church = relationship("Church")
    class_ = relationship("SchoolClass", back_populates="tasks")
    task_values = relationship("TaskValue", back_populates="task")

    def __repr__(self) -> str:
        return (
            f"<Task id={self.id} name={self.task_name!r} "
            f"class_id={self.class_id} value={self.value}>"
        )
