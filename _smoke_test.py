"""End-to-end smoke test against the real PostgreSQL database.

Run from back_fasly/:  python _smoke_test.py

DESTRUCTIVE: it truncates every table first, so it wipes any existing data.
It refuses to run unless you explicitly opt in:

    set FASLY_SMOKE_RESET=1 && python _smoke_test.py
"""

import os
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.db.database import Base, SessionLocal, engine
from app.main import app

# --- clean slate -------------------------------------------------------
if os.environ.get("FASLY_SMOKE_RESET") != "1":
    raise SystemExit(
        "Refusing to run: this test DROPS AND RECREATES every table.\n"
        "Re-run with FASLY_SMOKE_RESET=1 if you are OK losing the data."
    )
Base.metadata.drop_all(bind=engine)

# --- last friday, so the dashboard's Friday filter has data -------------
today = date.today()
last_friday = today - timedelta(days=(today.weekday() - 4) % 7)
if last_friday > today:
    last_friday -= timedelta(days=7)
# oldest -> newest
FRIDAYS = sorted([last_friday - timedelta(days=7 * i) for i in range(5)])
NEWEST, PREV = FRIDAYS[-1], FRIDAYS[-2]

passed = 0
failed = []


def check(label, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed.append(label)
        print(f"  FAIL  {label} {extra}")


def call(method, path, **kw):
    r = getattr(client, method)(path, **kw)
    return r


with TestClient(app) as client:  # triggers lifespan -> init_db + bootstrap
    print("\n== health ==")
    r = call("get", "/")
    check("GET / -> 200", r.status_code == 200, r.text)

    print("\n== auth ==")
    r = call("post", "/auth/login", data={"username": "admin.kero@fasly.com", "password": "kero0244"})
    check("bootstrap admin login -> 200", r.status_code == 200, r.text)
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    r = call("post", "/auth/login", data={"username": "admin.kero@fasly.com", "password": "wrong"})
    check("bad password -> 401", r.status_code == 401)

    r = call("get", "/auth/me", headers=H)
    check("GET /auth/me -> 200", r.status_code == 200, r.text)
    check("admin role is admin", r.json()["role"] == "admin", r.text)
    admin_id = r.json()["id"]
    check("id is an integer", isinstance(admin_id, int), r.text)

    r = call("get", "/boys", headers={})
    check("no token -> 401", r.status_code == 401)

    # register an amin locked to class 3
    r = call("post", "/auth/register", headers=H, json={
        "user_name": "Amin Three", "mail": "amin3@fasly.com",
        "password": "secret123", "role": "user", "class_name": "3",
    })
    check("register amin -> 201", r.status_code == 201, r.text)
    amin_id = r.json()["id"]

    r = call("post", "/auth/register", headers=H, json={
        "user_name": "Amin Three", "mail": "dup@fasly.com",
        "password": "secret123", "role": "user", "class_name": "3",
    })
    check("duplicate user_name -> 400", r.status_code == 400, r.text)

    r = call("post", "/auth/login", data={"username": "amin3@fasly.com", "password": "secret123"})
    check("amin login -> 200", r.status_code == 200, r.text)
    H_amin = {"Authorization": f"Bearer {r.json()['access_token']}"}

    print("\n== teachers ==")
    t_ids = {}
    for name, cls in [("Mark", "3"), ("Peter", "5")]:
        r = call("post", "/teachers", headers=H, json={"teacher_name": name, "phone": "0100", "class_name": cls, "duty": "class servant"})
        check(f"create teacher {name} -> 201", r.status_code == 201, r.text)
        t_ids[name] = r.json()["id"]
    check("teacher id is int", isinstance(t_ids["Mark"], int))

    r = call("get", "/teachers", headers=H)
    check("list teachers (admin) -> 2", r.status_code == 200 and len(r.json()) == 2, r.text)

    r = call("get", "/teachers", headers=H_amin)
    check("list teachers (amin class 3) -> 1", r.status_code == 200 and len(r.json()) == 1, r.text)

    r = call("get", f"/teachers/{t_ids['Peter']}", headers=H_amin)
    check("amin reading class 5 teacher -> 403", r.status_code == 403, r.text)

    r = call("patch", f"/teachers/{t_ids['Mark']}", headers=H, json={"phone": "0111"})
    check("patch teacher -> 200", r.status_code == 200 and r.json()["phone"] == "0111", r.text)

    print("\n== boys ==")
    b_ids = {}
    for name, cls in [("Omar", "3"), ("Mona", "3"), ("Sara", "5")]:
        r = call("post", "/boys", headers=H, json={
            "boy_name": name, "gender": "m", "age": 12, "class_name": cls,
            "phone": "0122", "issue_flag": name == "Sara",
        })
        check(f"create boy {name} -> 201", r.status_code == 201, r.text)
        b_ids[name] = r.json()["id"]

    r = call("get", "/boys?class_name=3", headers=H)
    check("filter boys by class -> 2", r.status_code == 200 and len(r.json()) == 2, r.text)

    r = call("get", "/boys?issue_flag=true", headers=H)
    check("filter boys by issue_flag -> 1", r.status_code == 200 and len(r.json()) == 1, r.text)

    r = call("get", "/boys", headers=H_amin)
    check("amin sees only class 3 -> 2", r.status_code == 200 and len(r.json()) == 2, r.text)

    r = call("post", "/boys", headers=H_amin, json={"boy_name": "Hacked", "class_name": "5"})
    check("amin creating in class 5 -> 403", r.status_code == 403, r.text)

    r = call("post", "/boys", headers=H, json={"boy_name": "Omar", "class_name": "3"})
    check("duplicate boy_name -> 400", r.status_code == 400, r.text)

    print("\n== attendance (upsert) ==")
    r = call("post", "/attendance", headers=H, json={
        "boy_id": b_ids["Omar"], "attend": "y", "action_date": NEWEST.isoformat(), "note": "first friday",
    })
    check("create attend -> 201", r.status_code == 201, r.text)
    rec = r.json()
    check("boy_name denormalized", rec["boy_name"] == "Omar", r.text)
    check("class_name denormalized", rec["class_name"] == "3", r.text)
    check("recorded_by stamped", rec["recorded_by"] == admin_id, r.text)
    check("attend value stored as 'y'", rec["attend"] == "y", r.text)
    check("action_date is ISO string", rec["action_date"] == NEWEST.isoformat(), r.text)
    attend_id = rec["id"]

    r = call("post", "/attendance", headers=H, json={
        "boy_id": b_ids["Omar"], "attend": "n", "action_date": NEWEST.isoformat(), "note": "changed",
    })
    check("re-save same (boy,date) upserts -> 201", r.status_code == 201, r.text)
    check("upsert returned same row id", r.json()["id"] == attend_id, r.text)
    check("upsert overwrote attend to n", r.json()["attend"] == "n", r.text)

    r = call("get", f"/attendance/{b_ids['Omar']}/x", headers=H)
    check("unknown route id -> 404-ish", r.status_code == 404, r.text)

    r = call("get", "/attendance?class_name=3&action_date=" + NEWEST.isoformat(), headers=H)
    check("list attendance by class+date -> 1", r.status_code == 200 and len(r.json()) == 1, r.text)

    print("\n== attendance bulk ==")
    r = call("post", "/attendance/bulk", headers=H, json={
        "class_name": "3",
        "action_date": PREV.isoformat(),
        "items": [
            {"boy_id": b_ids["Omar"], "attend": "y"},
            {"boy_id": b_ids["Mona"], "attend": "n", "note": "sick"},
        ],
    })
    check("bulk attend -> 201 len 2", r.status_code == 201 and len(r.json()) == 2, r.text)

    r = call("post", "/attendance/bulk", headers=H, json={
        "class_name": "3", "action_date": PREV.isoformat(),
        "items": [{"boy_id": b_ids["Omar"], "attend": "y"}, {"boy_id": b_ids["Omar"], "attend": "n"}],
    })
    check("duplicate rows in bulk -> 400", r.status_code == 400, r.text)

    print("\n== teacher checks ==")
    r = call("post", "/teacher-checks", headers=H, json={
        "teacher_id": t_ids["Mark"], "attend": "y", "action_date": NEWEST.isoformat(),
        "prepare_flag": True, "liturgy_flag": True, "follow_flag": False,
    })
    check("create teacher check -> 201", r.status_code == 201, r.text)
    check("flags stored", r.json()["prepare_flag"] is True and r.json()["liturgy_flag"] is True, r.text)

    r = call("post", "/teacher-checks/bulk", headers=H, json={
        "class_name": "3", "action_date": PREV.isoformat(),
        "items": [{"teacher_id": t_ids["Mark"], "attend": "y", "prepare_flag": True}],
    })
    check("bulk teacher check -> 201", r.status_code == 201 and len(r.json()) == 1, r.text)

    print("\n== follow ups ==")
    r = call("post", "/follow-ups", headers=H, json={
        "teacher_id": t_ids["Mark"], "boy_id": b_ids["Omar"],
        "action_date": NEWEST.isoformat(), "status": "whatsapp", "note": "asked about him",
    })
    check("create follow-up -> 201", r.status_code == 201, r.text)
    fu_id = r.json()["id"]
    check("teacher_name denormalized", r.json()["teacher_name"] == "Mark", r.text)
    check("boy_name denormalized", r.json()["boy_name"] == "Omar", r.text)

    r = call("get", f"/follow-ups?boy_id={b_ids['Omar']}", headers=H)
    check("list follow-ups by boy -> 1", r.status_code == 200 and len(r.json()) == 1, r.text)

    r = call("patch", f"/follow-ups/{fu_id}", headers=H, json={"status": "visit"})
    check("patch follow-up -> 200", r.status_code == 200 and r.json()["status"] == "visit", r.text)

    r = call("post", "/follow-ups", headers=H, json={
        "teacher_id": t_ids["Mark"], "boy_id": b_ids["Sara"], "action_date": NEWEST.isoformat(),
    })
    check("cross-class follow-up allowed by admin -> 201", r.status_code == 201, r.text)

    print("\n== boy note accumulation ==")
    r = call("get", f"/boys/{b_ids['Omar']}", headers=H)
    check("boy note collected from attendance + follow-up",
          "first friday" in (r.json()["note"] or "") and "asked about him" in (r.json()["note"] or ""),
          r.json()["note"])

    print("\n== groups ==")
    r = call("post", "/groups/assign", headers=H, json={
        "teacher_id": t_ids["Mark"], "boy_ids": [b_ids["Omar"], b_ids["Mona"]],
    })
    check("assign group -> 200", r.status_code == 200 and r.json()["assigned"] == 2, r.text)

    r = call("post", "/groups/assign", headers=H, json={
        "teacher_id": t_ids["Mark"], "boy_ids": [b_ids["Sara"]],
    })
    check("assign across classes -> 400", r.status_code == 400, r.text)

    r = call("get", "/groups?class_name=3", headers=H)
    body = r.json()
    check("list groups -> 200", r.status_code == 200, r.text)
    mark_group = [g for g in body["groups"] if g["teacher_name"] == "Mark"][0]
    check("Mark has 2 boys", mark_group["boys_count"] == 2, str(mark_group))
    omar = [b for b in mark_group["boys"] if b["boy_name"] == "Omar"][0]
    check("boy summary has percent", "percent" in omar, str(omar))
    check("boy summary has last_followup", omar["last_followup"] is not None, str(omar))

    r = call("get", "/groups", headers=H)
    check("unassigned lists Sara", r.json()["unassigned_count"] == 1, r.text)

    r = call("post", "/groups/unassign", headers=H, json={"boy_ids": [b_ids["Mona"]]})
    check("unassign -> 200 removed 1", r.status_code == 200 and r.json()["removed"] == 1, r.text)

    print("\n== dashboard ==")
    r = call("get", "/dashboard/summary", headers=H)
    check("dashboard summary -> 200", r.status_code == 200, r.text)
    d = r.json()
    check("counts.boys == 3", d["counts"]["boys"] == 3, str(d["counts"]))
    check("counts.attendance total == 3", d["attendance"]["total"] == 3, str(d["attendance"]))
    check("by_class has 6 classes", len(d["attendance"]["by_class"]) == 6, str(d["attendance"]["by_class"]))
    # Mark has 2 checks (2 attend + 2 prepare + 1 liturgy + 0 follow = 5)
    check("servants scored", len(d["servants"]) == 1 and d["servants"][0]["score"] == 5, str(d["servants"]))
    check("last_friday is the newest friday",
          d["last_friday"]["date"] == NEWEST.isoformat(), f'{d["last_friday"]} vs {NEWEST}')
    check("streaks grouped by class", set(d["streaks"].keys()) == set(f"1 2 3 4 5 6".split()), str(list(d["streaks"])))

    r = call("get", "/dashboard/summary?class_name=3", headers=H)
    check("dashboard scoped to class 3 -> 2 boys", r.json()["counts"]["boys"] == 2, str(r.json()["counts"]))

    r = call("get", f"/dashboard/boys/{b_ids['Omar']}", headers=H)
    check("boy profile -> 200", r.status_code == 200, r.text)
    prof = r.json()
    check("boy profile history -> 2 records", len(prof["history"]) == 2, str(prof["history"]))
    check("boy profile has season table", prof["season"]["total"] > 0, str(prof["season"]))
    check("boy profile followups -> 1", len(prof["followups"]) == 1, str(prof["followups"]))
    check("boy profile birth_date key present", "birth_date" in prof["boy"])

    # NOTE: a non-admin hitting /dashboard/summary with NO class_name gets 403.
    # This is pre-existing behaviour carried over verbatim from the Firestore
    # version (resolve_class -> ensure_class_access(None, user)). The UI only
    # sends class_name when a class is selected. Asserting it stays that way.
    r = call("get", "/dashboard/summary", headers=H_amin)
    check("amin dashboard without class -> 403 (pre-existing)", r.status_code == 403, r.text)

    r = call("get", "/dashboard/summary?class_name=3", headers=H_amin)
    check("amin dashboard scoped to class 3 -> 2 boys",
          r.status_code == 200 and r.json()["counts"]["boys"] == 2, r.text)

    r = call("get", f"/dashboard/boys/{b_ids['Sara']}", headers=H_amin)
    check("amin boy profile of class 5 -> 403", r.status_code == 403, r.text)

    print("\n== excel export ==")
    r = call("get", "/groups/export?class_name=3", headers=H)
    check("groups export xlsx -> 200", r.status_code == 200 and "spreadsheetml" in r.headers.get("content-type", ""), r.text[:200])

    print("\n== deletes ==")
    r = call("delete", f"/attendance/{attend_id}", headers=H)
    check("delete attend -> 204", r.status_code == 204, r.text)
    r = call("delete", f"/boys/{b_ids['Sara']}", headers=H)
    check("delete boy cascades follows -> 204", r.status_code == 204, r.text)
    r = call("get", "/dashboard/summary", headers=H)
    check("dashboard after cascade -> 2 boys", r.json()["counts"]["boys"] == 2, r.text)

    r = call("delete", f"/auth/users/{amin_id}", headers=H)
    check("delete user -> 200", r.status_code == 200, r.text)

print("\n" + "=" * 60)
print(f"PASSED: {passed}   FAILED: {len(failed)}")
if failed:
    for f in failed:
        print("  -", f)
    raise SystemExit(1)
print("ALL GREEN")
