import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from collections import Counter
from datetime import date

from dotenv import load_dotenv

load_dotenv(".env")

import httpx

from app.core.auth.security import create_access_token
from app.db.database import SessionLocal
from app.models.follow_up import FollowUp
from app.models.group import Group
from app.models.teacher import Teacher
from app.models.user import User

BASE = "http://127.0.0.1:9002"

db = SessionLocal()
# a servant login whose teacher row is class 4, and one of his own group's boys
servant_user = None
for u, t in (
    db.query(User, Teacher)
    .join(Teacher, Teacher.id == User.teacher_id)
    .filter(User.role == "teacher", Teacher.class_id == 4)
    .all()
):
    boy_id = db.query(Group.boy_id).filter(Group.teacher_id == t.id).scalar()
    if boy_id:
        servant_user, servant_teacher, tested_boy = u, t, boy_id
        break
print("servant:", servant_user.id, "teacher", servant_teacher.id, "boy", tested_boy)

other = db.query(Teacher).filter(Teacher.class_id == 4, Teacher.id != servant_teacher.id).first()
print("other servant of the class:", other.id, other.teacher_name)

probe = FollowUp(
    boy_id=tested_boy,
    teacher_id=other.id,
    action_date=date.today(),
    status="visit",
    note="__probe__ سجل من خادم تاني",
)
db.add(probe)
db.commit()
probe_id = probe.id
db.close()

try:
    with httpx.Client(base_url=BASE, timeout=20) as c:
        h = {"Authorization": f"Bearer {create_access_token(str(servant_user.id))}"}
        r = c.get(f"/dashboard/boys/{tested_boy}", headers=h)
        print("profile:", r.status_code)
        fups = r.json()["followups"]
        print("rows:", len(fups), Counter(f["teacher_id"] for f in fups))
        print("payload:", [f for f in fups][:4])
finally:
    db = SessionLocal()
    db.query(FollowUp).filter(FollowUp.id == probe_id).delete()
    db.commit()
    print("probe deleted; follow-up rows left:", db.query(FollowUp).count())
    db.close()
