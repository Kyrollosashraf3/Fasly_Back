"""Permission matrix test for app.core.data.

Runs against an in-memory SQLite database - no PostgreSQL needed:

    python _perm_test.py

Every line prints PASS/FAIL; the process exits 1 if anything failed.
"""

import sys
from datetime import date, datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.data import (
    AttendanceService,
    BoyService,
    ClassService,
    FollowUpService,
    GroupsService,
    TeacherCheckService,
    TeacherService,
    UserService,
    get_user_by_email,
)
from app.db.database import Base
from app.models import (
    Attend,
    Boy,
    FollowUp,
    Group,
    SchoolClass,
    Teacher,
    TeacherCheck,
    User,
)
from app.models.enums import FollowEnum, GenderEnum, RoleEnum
from app.schemas.attend import AttendBulkCreate, AttendCreate, AttendItem
from app.schemas.boy import BoyCreate, BoyUpdate
from app.schemas.follow_up import FollowUpCreate, FollowUpUpdate
from app.schemas.group import GroupAssign
from app.schemas.school_class import SchoolClassCreate
from app.schemas.teacher import TeacherCreate
from app.schemas.teacher_check import TeacherCheckCreate
from app.schemas.attend import AttendUpdate
from app.schemas.user import UserCreate, UserResponse, UserUpdate

# ---------------------------------------------------------------- database
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _enable_fk(dbapi_connection, _record):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")


Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

# -------------------------------------------------------------------- seed
today = date.today()
c1 = SchoolClass(name="1st Primary", grade_number=1, academic_year="2026/2027")
c2 = SchoolClass(name="2nd Primary", grade_number=2, academic_year="2026/2027")
db.add_all([c1, c2])
db.flush()

t1 = Teacher(teacher_name="T1", phone="1", class_id=c1.id)
t_ad = Teacher(teacher_name="ADMIN1", phone="a1", class_id=c1.id)
t3 = Teacher(teacher_name="T3", phone="3", class_id=c2.id)
t_ad2 = Teacher(teacher_name="ADMIN2", phone="a2", class_id=c2.id)
db.add_all([t1, t_ad, t3, t_ad2])
db.flush()


def boy(name, class_id):
    return Boy(
        boy_name=name,
        gender=GenderEnum.MALE,
        birth_date=date(2015, 1, 1),
        class_id=class_id,
    )


b1, b2, b3, b4 = boy("B1", c1.id), boy("B2", c1.id), boy("B3", c1.id), boy("B4", c2.id)
db.add_all([b1, b2, b3, b4])
db.flush()
db.add_all([Group(teacher_id=t1.id, boy_id=b1.id), Group(teacher_id=t1.id, boy_id=b2.id)])
db.commit()

users = {
    "sa": User(email="sa@x.com", password_hash="h", role=RoleEnum.SUPER_ADMIN),
    "ad1": User(email="ad1@x.com", password_hash="h", role=RoleEnum.ADMIN, teacher_id=t_ad.id),
    "ad2": User(email="ad2@x.com", password_hash="h", role=RoleEnum.ADMIN, teacher_id=t_ad2.id),
    "te1": User(email="te1@x.com", password_hash="h", role=RoleEnum.TEACHER, teacher_id=t1.id),
    "us1": User(email="us1@x.com", password_hash="h", role=RoleEnum.USER, boy_id=b1.id),
    "us2": User(email="us2@x.com", password_hash="h", role=RoleEnum.USER, boy_id=b4.id),
}
db.add_all(users.values())
db.commit()


def login(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        email=u.email,
        role=u.role,
        teacher_id=u.teacher_id,
        boy_id=u.boy_id,
        created_at=u.created_at,
    )


L = {name: login(u) for name, u in users.items()}
L["sa"] = login(users["sa"])


def who(k):
    return L[k]


# ------------------------------------------------------------------ harness
results = []


def expect(label, code, fn, read_back=None):
    try:
        fn()
        got, detail = 200, ""
    except HTTPException as exc:
        got, detail = exc.status_code, str(exc.detail)
    except Exception as exc:  # noqa: BLE001
        got, detail = 500, f"{type(exc).__name__}: {exc}"
    ok = got == code
    if read_back is not None and ok:
        try:
            actual = read_back()
            if actual is not None:
                ok = bool(actual)
                if not ok:
                    detail = f"predicate failed: {actual!r}"
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, f"read_back: {type(exc).__name__}: {exc}"
    results.append((label, code, got, ok, detail))
    mark = "PASS" if ok else "FAIL"
    extra = "" if ok else f"  <- expected {code}, got {got} {detail}"
    print(f"[{mark}] {label}{extra}")


def S(svc, key):
    return svc(db, who(key))


def schema(fn):
    """Build a payload the way FastAPI would: a bad payload -> 422."""
    try:
        return fn()
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ============================================================ ATTENDANCE
att = AttendanceService

expect("attendance: sa lists every class", 200, lambda: S(att, "sa").list(),
       read_back=lambda: len(S(att, "sa").list()) >= 0)
expect("attendance: ad1 sees only his class", 200, lambda: S(att, "ad1").list(),
       read_back=lambda: all(r.class_id == c1.id for r in S(att, "ad1").list()))
expect("attendance: te1 sees only his group's boys", 200, lambda: S(att, "te1").list(),
       read_back=lambda: all(r.boy_id in (b1.id, b2.id) for r in S(att, "te1").list()))
expect("attendance: us1 sees only his own rows", 200, lambda: S(att, "us1").list(),
       read_back=lambda: all(r.boy_id == b1.id for r in S(att, "us1").list()))

expect("attendance: sa writes anywhere", 200,
       lambda: S(att, "sa").create(AttendCreate(boy_id=b4.id, present=True)))
expect("attendance: ad1 writes in his class", 200,
       lambda: S(att, "ad1").create(AttendCreate(boy_id=b3.id, present=True)))
expect("attendance: te1 writes for his group", 200,
       lambda: S(att, "te1").create(AttendCreate(boy_id=b2.id, present=True)))
expect("attendance: te1 denied a boy outside his group", 403,
       lambda: S(att, "te1").create(AttendCreate(boy_id=b3.id, present=True)))
expect("attendance: te1 denied another class", 403,
       lambda: S(att, "te1").create(AttendCreate(boy_id=b4.id, present=True)))
expect("attendance: ad2 denied ad1's class", 403,
       lambda: S(att, "ad2").create(AttendCreate(boy_id=b1.id, present=True)))
expect("attendance: boy login denied write", 403,
       lambda: S(att, "us1").create(AttendCreate(boy_id=b1.id, present=True)))
expect("attendance: bulk write by ad1", 200,
       lambda: S(att, "ad1").create_bulk(AttendBulkCreate(
           items=[AttendItem(boy_id=b1.id, present=True),
                  AttendItem(boy_id=b2.id)])))
expect("attendance: unknown boy -> 404", 404,
       lambda: S(att, "sa").create(AttendCreate(boy_id=99999, present=True)))

expect("attendance: us1 denied update even of his own row", 403,
       lambda: S(att, "us1").update(
           db.query(Attend).filter(Attend.boy_id == b1.id).first().id,
           AttendUpdate(present=False),
       ))
expect("attendance: ad1 can update", 200,
       lambda: S(att, "ad1").update(
           db.query(Attend).filter(Attend.boy_id == b1.id).first().id,
           AttendUpdate(present=False),
       ))
expect("attendance: ad2 cannot read ad1's row", 404,
       lambda: S(att, "ad2").get(db.query(Attend).filter(Attend.boy_id == b1.id).first().id))

# =============================================================== BOYS
boys = BoyService

expect("boys: sa sees everyone", 200, lambda: S(boys, "sa").list(),
       read_back=lambda: len(S(boys, "sa").list()) == 4)
expect("boys: ad1 sees his class", 200, lambda: S(boys, "ad1").list(),
       read_back=lambda: len(S(boys, "ad1").list()) == 3)
expect("boys: te1 sees his group only", 200, lambda: S(boys, "te1").list(),
       read_back=lambda: len(S(boys, "te1").list()) == 2)
expect("boys: us1 sees only himself", 200, lambda: S(boys, "us1").list(),
       read_back=lambda: len(S(boys, "us1").list()) == 1)
expect("boys: ad2 asking for ad1's class -> 403", 403,
       lambda: S(boys, "ad2").list(class_id=c1.id))
expect("boys: ad2 reading ad1's boy -> 404", 404,
       lambda: S(boys, "ad2").get(b1.id))

expect("boys: sa writes", 200,
       lambda: S(boys, "sa").create(BoyCreate(
           boy_name="B5", gender=GenderEnum.MALE, birth_date=date(2014, 5, 5),
           class_id=c2.id)))
expect("boys: ad1 writes in his class", 200,
       lambda: S(boys, "ad1").create(BoyCreate(
           boy_name="B6", gender=GenderEnum.MALE, birth_date=date(2014, 5, 5),
           class_id=c1.id)))
expect("boys: ad1 denied another class", 403,
       lambda: S(boys, "ad1").create(BoyCreate(
           boy_name="B7", gender=GenderEnum.MALE, birth_date=date(2014, 5, 5),
           class_id=c2.id)))
expect("boys: te1 denied write", 403,
       lambda: S(boys, "te1").create(BoyCreate(
           boy_name="B8", gender=GenderEnum.MALE, birth_date=date(2014, 5, 5),
           class_id=c1.id)))
expect("boys: us1 denied write", 403,
       lambda: S(boys, "us1").create(BoyCreate(
           boy_name="B9", gender=GenderEnum.MALE, birth_date=date(2014, 5, 5),
           class_id=c1.id)))
expect("boys: te1 denied update", 403,
       lambda: S(boys, "te1").update(b1.id, BoyUpdate(note="x")))
expect("boys: ad1 cannot move a boy to another class", 403,
       lambda: S(boys, "ad1").update(b1.id, BoyUpdate(class_id=c2.id)))
expect("boys: ad1 can rename", 200,
       lambda: S(boys, "ad1").update(b1.id, BoyUpdate(boy_name="B1-renamed")))
expect("boys: ad1 delete with history -> 409", 409,
       lambda: S(boys, "ad1").delete(b1.id))

# ============================================================ TEACHERS
tch = TeacherService

expect("teachers: sa sees everyone", 200, lambda: S(tch, "sa").list(),
       read_back=lambda: len(S(tch, "sa").list()) == 4)
expect("teachers: ad1 sees his class", 200, lambda: S(tch, "ad1").list(),
       read_back=lambda: len(S(tch, "ad1").list()) == 2)
expect("teachers: te1 sees only himself", 200, lambda: S(tch, "te1").list(),
       read_back=lambda: len(S(tch, "te1").list()) == 1)
expect("teachers: boy login denied", 403, lambda: S(tch, "us1").list())
expect("teachers: ad2 reading ad1's servant -> 404", 404,
       lambda: S(tch, "ad2").get(t1.id))

T2_ID = None


def _set_t2(rec):
    global T2_ID
    T2_ID = rec.id
    return rec


expect("teachers: ad1 creates in his class", 200,
       lambda: _set_t2(S(tch, "ad1").create(TeacherCreate(
           teacher_name="T2", phone="2", class_id=c1.id))))
expect("teachers: ad1 denied another class", 403,
       lambda: S(tch, "ad1").create(TeacherCreate(
           teacher_name="T4", phone="4", class_id=c2.id)))
expect("teachers: te1 denied write", 403,
       lambda: S(tch, "te1").create(TeacherCreate(
           teacher_name="T5", phone="5", class_id=c1.id)))
expect("teachers: duplicate name in same class -> 409", 409,
       lambda: S(tch, "ad1").create(TeacherCreate(
           teacher_name="T2", phone="2", class_id=c1.id)))

# ========================================================== FOLLOW-UPS
fu = FollowUpService

expect("followups: us1 denied write", 403,
       lambda: S(fu, "us1").create(FollowUpCreate(
           teacher_id=t1.id, boy_id=b1.id, status=FollowEnum.CALL)))
expect("followups: te1 logs his own boy", 200,
       lambda: S(fu, "te1").create(FollowUpCreate(
           teacher_id=t1.id, boy_id=b1.id, status=FollowEnum.CALL)))
expect("followups: te1 denied a boy outside his group", 403,
       lambda: S(fu, "te1").create(FollowUpCreate(
           teacher_id=t1.id, boy_id=b3.id, status=FollowEnum.CALL)))
expect("followups: te1 denied another servant", 403,
       lambda: S(fu, "te1").create(FollowUpCreate(
           teacher_id=t3.id, boy_id=b4.id, status=FollowEnum.CALL)))
expect("followups: ad1 denied another class", 403,
       lambda: S(fu, "ad1").create(FollowUpCreate(
           teacher_id=t3.id, boy_id=b4.id, status=FollowEnum.CALL)))
expect("followups: ad1 can log for his servant", 200,
       lambda: S(fu, "ad1").create(FollowUpCreate(
           teacher_id=t1.id, boy_id=b3.id, status=FollowEnum.VISIT)))
expect("followups: cross-class pair -> 400", 400,
       lambda: S(fu, "sa").create(FollowUpCreate(
           teacher_id=t1.id, boy_id=b4.id, status=FollowEnum.CALL)))
expect("followups: unknown servant -> 404", 404,
       lambda: S(fu, "sa").create(FollowUpCreate(
           teacher_id=99999, boy_id=b1.id, status=FollowEnum.CALL)))

expect("followups: te1 sees only his own", 200, lambda: S(fu, "te1").list(),
       read_back=lambda: all(r.teacher_id == t1.id for r in S(fu, "te1").list()))
expect("followups: us1 sees only his own", 200, lambda: S(fu, "us1").list(),
       read_back=lambda: all(r.boy_id == b1.id for r in S(fu, "us1").list()))
expect("followups: us1 denied update even of her own row", 403,
       lambda: S(fu, "us1").update(
           db.query(FollowUp).filter(FollowUp.boy_id == b1.id).first().id,
           FollowUpUpdate(note="x"),
       ))
expect("followups: te1 can update his own row", 200,
       lambda: S(fu, "te1").update(
           db.query(FollowUp).filter(FollowUp.boy_id == b1.id).first().id,
           FollowUpUpdate(note="x"),
       ))
expect("followups: ad2 cannot see ad1's rows", 200, lambda: S(fu, "ad2").list(),
       read_back=lambda: all(r.class_id == c2.id for r in S(fu, "ad2").list()))
expect("followups: ad2 reading ad1's row -> 404", 404,
       lambda: S(fu, "ad2").get(
           db.query(FollowUp).filter(FollowUp.class_id == c1.id).first().id))
expect("followups: us1 delete denied", 403,
       lambda: S(fu, "us1").delete(
           db.query(FollowUp).filter(FollowUp.boy_id == b1.id).first().id))

# ====================================================== TEACHER CHECKS
tc = TeacherCheckService

expect("checks: boy login denied read", 403, lambda: S(tc, "us1").list())
expect("checks: te1 sees only his own", 200, lambda: S(tc, "te1").list(),
       read_back=lambda: all(r.teacher_id == t1.id for r in S(tc, "te1").list()))
expect("checks: ad1 writes", 200,
       lambda: S(tc, "ad1").create(TeacherCheckCreate(
           teacher_id=t1.id, attend=True, prepare=True, liturgy=True, follow=True)))
expect("checks: te1 denied write", 403,
       lambda: S(tc, "te1").create(TeacherCheckCreate(
           teacher_id=t1.id, attend=True, prepare=True, liturgy=True, follow=True)))
expect("checks: ad1 denied another class", 403,
       lambda: S(tc, "ad1").create(TeacherCheckCreate(
           teacher_id=t3.id, attend=True, prepare=True, liturgy=True, follow=True)))
expect("checks: sa writes anywhere", 200,
       lambda: S(tc, "sa").create(TeacherCheckCreate(
           teacher_id=t3.id, attend=True, prepare=True, liturgy=True, follow=True)))
expect("checks: ad2 cannot read ad1's row", 404,
       lambda: S(tc, "ad2").get(
           db.query(TeacherCheck).filter(TeacherCheck.class_id == c1.id).first().id))
expect("checks: boy login denied write", 403,
       lambda: S(tc, "us1").create(TeacherCheckCreate(
           teacher_id=t1.id, attend=True, prepare=True, liturgy=True, follow=True)))

# =============================================================== GROUPS
gr = GroupsService

expect("groups: boy login denied read", 403, lambda: S(gr, "us1").list())
expect("groups: te1 sees his own group", 200, lambda: S(gr, "te1").list(),
       read_back=lambda: len(S(gr, "te1").list()["groups"]) == 1)
expect("groups: ad1 sees his class", 200, lambda: S(gr, "ad1").list(),
       read_back=lambda: len(S(gr, "ad1").list()["groups"]) == 3)
expect("groups: sa sees everyone", 200, lambda: S(gr, "sa").list(),
       read_back=lambda: len(S(gr, "sa").list()["groups"]) == 5)

expect("groups: ad1 assigns", 200,
       lambda: S(gr, "ad1").assign(t1.id, [b3.id]))
expect("groups: te1 denied assign", 403,
       lambda: S(gr, "te1").assign(t1.id, [b3.id]))
expect("groups: ad1 denied another class's boy", 403,
       lambda: S(gr, "ad1").assign(t1.id, [b4.id]))
expect("groups: ad1 denied another class's servant", 403,
       lambda: S(gr, "ad1").assign(t3.id, [b3.id]))
expect("groups: unknown servant -> 404", 404,
       lambda: S(gr, "sa").assign(99999, [b3.id]))
expect("groups: sa unassigns", 200, lambda: S(gr, "sa").unassign([b3.id]))
expect("groups: te1 denied unassign", 403, lambda: S(gr, "te1").unassign([b3.id]))

# =============================================================== USERS
us = UserService

expect("users: sa sees all", 200, lambda: S(us, "sa").list_users(),
       read_back=lambda: len(S(us, "sa").list_users()) == 6)
expect("users: ad1 sees his class's accounts", 200, lambda: S(us, "ad1").list_users(),
       read_back=lambda: all(
           u.id in (users["ad1"].id, users["te1"].id, users["us1"].id)
           for u in S(us, "ad1").list_users()))
expect("users: te1 sees only his own", 200, lambda: S(us, "te1").list_users(),
       read_back=lambda: [u.id for u in S(us, "te1").list_users()] == [users["te1"].id])
expect("users: us1 sees only his own", 200, lambda: S(us, "us1").list_users(),
       read_back=lambda: [u.id for u in S(us, "us1").list_users()] == [users["us1"].id])

expect("users: ad1 creates an account for his servant", 200,
       lambda: S(us, "ad1").create_user(UserCreate(
           email="new@x.com", password="password1", role=RoleEnum.TEACHER,
           teacher_id=T2_ID)))
expect("users: second login for the same servant -> 409", 409,
       lambda: S(us, "ad1").create_user(UserCreate(
           email="dupe@x.com", password="password1", role=RoleEnum.TEACHER,
           teacher_id=t1.id)))
expect("users: ad1 cannot create a super admin", 403,
       lambda: S(us, "ad1").create_user(UserCreate(
           email="evil@x.com", password="password1", role=RoleEnum.SUPER_ADMIN)))
expect("users: sa creates a super admin", 200,
       lambda: S(us, "sa").create_user(UserCreate(
           email="sa2@x.com", password="password1", role=RoleEnum.SUPER_ADMIN)))
expect("users: boy login cannot create", 403,
       lambda: S(us, "us1").create_user(UserCreate(
           email="z@x.com", password="password1", role=RoleEnum.TEACHER,
           teacher_id=T2_ID)))
expect("users: ad1 denied another class's servant", 403,
       lambda: S(us, "ad1").create_user(UserCreate(
           email="x@x.com", password="password1", role=RoleEnum.TEACHER,
           teacher_id=t3.id)))
expect("users: te1 denied create", 403,
       lambda: S(us, "te1").create_user(UserCreate(
           email="y@x.com", password="password1", role=RoleEnum.TEACHER,
           teacher_id=T2_ID)))
expect("users: role/link mismatch -> 422", 422,
       lambda: S(us, "sa").create_user(schema(lambda: UserCreate(
           email="bad@x.com", password="password1", role=RoleEnum.USER,
           teacher_id=t1.id))))
expect("users: duplicate email -> 409", 409,
       lambda: S(us, "sa").create_user(UserCreate(
           email="new@x.com", password="password1", role=RoleEnum.TEACHER,
           teacher_id=t1.id)))
expect("users: ad1 cannot delete his own account", 400,
       lambda: S(us, "ad1").delete_user(users["ad1"].id))
expect("users: ad1 cannot escalate to super_admin", 403,
       lambda: S(us, "ad1").update_user(users["te1"].id,
                                        UserUpdate(role=RoleEnum.SUPER_ADMIN)))
expect("users: lookup by email", 200,
       lambda: get_user_by_email(db, "  TE1@X.COM "),
       read_back=lambda: get_user_by_email(db, "TE1@x.com").id == users["te1"].id)

# ============================================================== CLASSES
cls = ClassService

expect("classes: any login may read", 200, lambda: S(cls, "us1").list(),
       read_back=lambda: len(S(cls, "us1").list()) == 2)
expect("classes: boy login denied write", 403,
       lambda: S(cls, "us1").create(SchoolClassCreate(
           name="X", grade_number=3, academic_year="2026/2027")))
expect("classes: te1 denied write", 403,
       lambda: S(cls, "te1").create(SchoolClassCreate(
           name="X", grade_number=3, academic_year="2026/2027")))
expect("classes: ad1 can create", 200,
       lambda: S(cls, "ad1").create(SchoolClassCreate(
           name="3rd Primary", grade_number=3, academic_year="2026/2027")))
expect("classes: sa can create", 200,
       lambda: S(cls, "sa").create(SchoolClassCreate(
           name="4th Primary", grade_number=4, academic_year="2026/2027")))
expect("classes: delete class with servants -> 409", 409,
       lambda: S(cls, "sa").delete(c1.id))
empty = db.query(SchoolClass).filter(SchoolClass.name == "4th Primary").first()
expect("classes: delete empty class", 200, lambda: S(cls, "sa").delete(empty.id))

# ---------------------------------------------------------------- report
failed = [r for r in results if not r[3]]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
if failed:
    print("\nFAILURES:")
    for label, want, got, _ok, detail in failed:
        print(f"  - {label}: expected {want}, got {got} {detail}")
    sys.exit(1)
print("ALL PERMISSION CHECKS PASSED")
