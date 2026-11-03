from dotenv import load_dotenv

load_dotenv(".env")

from app.db.database import SessionLocal
from app.core.data.task_values import TaskValueService
from app.schemas.task_value import TaskValueCreate
from app.models.user import User
from app.models.teacher import Teacher
from app.models.enums import RoleEnum

db = SessionLocal()
teacher = db.query(Teacher).filter(Teacher.class_id == 5).first()
user = db.query(User).filter(User.teacher_id == teacher.id, User.role == RoleEnum.TEACHER).first()
print("teacher", teacher.id, "user", user.id, user.role)

for task_id in (10, 8):
    for boy_id in (259, 330):
        try:
            rec = TaskValueService(db, user).create(
                TaskValueCreate(task_id=task_id, boy_id=boy_id, received=False)
            )
            print("OK  task", task_id, "boy", boy_id, "-> id", rec.id)
        except Exception as exc:
            print("ERR task", task_id, "boy", boy_id, "->", type(exc).__name__, exc)
        db.rollback()
db.close()
