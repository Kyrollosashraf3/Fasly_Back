"""templates.py - Build .xlsx files: import templates and table exports.

A workbook has two sheets:

* the **first** sheet holds the data — its header row uses the exact
  English keys the readers expect (``boy_name``, ``class_name``, ...),
* the second sheet (``شرح``) is Arabic documentation and is never read.

``class_name`` cells are filled from the classes this login may write into,
so a downloaded template can be uploaded again without editing it.
"""

from datetime import date
from io import BytesIO, StringIO
import csv

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config.logger import get_logger
from app.core.EDA.read_excel import BOY_HEADERS, TEACHER_HEADERS, USER_HEADERS
from app.models.enums import SkillEnum

logger = get_logger(__name__)

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

HEADER_FILL = PatternFill("solid", fgColor="1E2A4A")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)

ARABIC_DOCS = {
    "boy_name": "اسم الولد (إلزامي)",
    "gender": "النوع: m للولد / f للبنت (يقبل \"ولد\" و\"بنت\")",
    "birth_date": "تاريخ الميلاد YYYY-MM-DD",
    "phone": "التليفون",
    "phone_2": "تليفون آخر",
    "zone": "المنطقة",
    "address": "العنوان بالتفصيل",
    "location": "لينك الخريطة",
    "class_name": "اسم الفصل كما هو مسجل بالبرنامج",
    "note": "ملاحظة",
    "issue_flag": "محتاج متابعة: true / false (أو نعم / لا)",
    "teacher_name": "اسم الخادم (إلزامي)",
    "last_visit_date": "آخر اعتراف/زيارة للأب YYYY-MM-DD",
}

# The accounts sheet: who gets a login, in which class, with what role.
USER_DOCS = {
    **ARABIC_DOCS,
    "phone": "رقم التليفون (إلزامي، 01xxxxxxxxx) - به يسجّل الدخول",
    "name": "الاسم: اسم الخادم (أو اسم الولد لو الدور user) - لو مش موجود بيتعمل تلقائيًا",
    "role": "الصلاحية: super_admin / admin / teacher / user",
}

# The boys sheet adds a servant column - optional there, mandatory in the
# group sheet, so the doc line is overridden per workbook.
BOY_DOCS = {
    **ARABIC_DOCS,
    "teacher_name": "اسم الخادم في نفس الفصل (اختياري) — يتسجل مع الولد في مجموعته على طول",
    "last_visit_date": "آخر زيارة/اعتراف للولد YYYY-MM-DD (اختياري، فاضي لو لسه مفيش)",
}

# 10 Egyptian sample rows spread over the available classes.
_BOY_SAMPLES = [
    ("مينا فؤاد حنا", "m", date(2014, 3, 12), "01012345678", "", "شبرا",
     "12 شارع الترعة، شبرا الخيمة", "", date(2026, 9, 13),
     "ولد ملتزم، محتاج متابعة الواجب", False),
    ("ماريا عادل بطرس", "f", date(2013, 7, 5), "01234567890", "01555555555",
     "مصر الجديدة", "45 شارع الحجاز، مصر الجديدة", "", date(2026, 10, 4), "", False),
    ("أنطونيوس سامي جاد", "m", date(2015, 1, 20), "01122334455", "",
     "الزيتون", "8 شارع ابن الهيثم، الزيتون", "", "",
     "بيتأخر كتير", True),
    ("فيرينا ماهر لبيب", "f", date(2014, 11, 2), "01098765432", "",
     "حدائق القبة", "21 شارع المنشية، حدائق القبة", "", date(2026, 11, 1), "", False),
    ("بيشوي رأفت إبراهيم", "m", date(2013, 5, 18), "01277889900", "",
     "شبرا", "5 شارع الخلفاوي، شبرا", "", date(2026, 8, 23), "", False),
    ("إيريني وديع ناشد", "f", date(2015, 9, 27), "01555443322", "",
     "روض الفرج", "33 شارع الترعة، روض الفرج", "", "",
     "جديدة على المجموعة", False),
    ("كيرلس عماد فهمي", "m", date(2014, 6, 30), "01011223344", "",
     "المرج", "17 شارع الجزائر، المرج", "", date(2026, 12, 6), "", False),
    ("مريم ناجي حبيب", "f", date(2013, 12, 9), "01200112233", "",
     "الساحل", "64 شارع بورسعيد، الساحل", "", date(2026, 7, 19), "", False),
    ("أندرو جرجس ميلاد", "m", date(2015, 4, 14), "01199887766", "",
     "المطرية", "9 شارع الجيش، المطرية", "", "",
     "له تليفون وحيد", True),
    ("كارولين صبري عزيز", "f", date(2014, 8, 21), "01033445566", "",
     "العباسية", "40 شارع مصر والسودان، العباسية", "", date(2026, 10, 25), "", False),
]

_TEACHER_SAMPLES = [
    ("أ. مينا عادل", "01012345678", date(2026, 8, 30), "قائد مجموعة"),
    ("أ. مارينا سمير", "01234567890", date(2026, 9, 6), "مسؤولة البنات"),
    ("أ. فادي حنا", "01122334455", "", ""),
    ("أ. نرمين وديع", "01555555555", date(2026, 5, 15), ""),
    ("أ. رامي فؤاد", "01098765432", "", "خادم جديد"),
]


def _write_sheet(ws, headers: list[str], rows: list[dict]) -> None:
    ws.sheet_view.rightToLeft = True
    for idx, name in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=idx, value=name)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(idx)].width = 18

    for r, row in enumerate(rows, start=2):
        for c, name in enumerate(headers, start=1):
            value = row.get(name)
            cell = ws.cell(row=r, column=c, value=value)
            if isinstance(value, date):
                cell.number_format = "yyyy-mm-dd"


def _write_docs_sheet(
    ws, headers: list[str], docs: dict[str, str] | None = None
) -> None:
    docs = ARABIC_DOCS if docs is None else docs
    ws.sheet_view.rightToLeft = True
    ws.cell(row=1, column=1, value="العمود").font = HEADER_FONT
    ws.cell(row=1, column=1).fill = HEADER_FILL
    ws.cell(row=1, column=2, value="الشرح").font = HEADER_FONT
    ws.cell(row=1, column=2).fill = HEADER_FILL
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 70
    for r, name in enumerate(headers, start=2):
        ws.cell(row=r, column=1, value=name)
        ws.cell(row=r, column=2, value=docs.get(name, ""))


def _workbook(
    headers: list[str],
    rows: list[dict],
    title: str,
    docs: dict[str, str] | None = None,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = title
    _write_sheet(ws, headers, rows)
    _write_docs_sheet(wb.create_sheet("شرح"), headers, docs)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def build_boys_template(
    class_names: list[str],
    teachers_by_class: dict[str, list[str]] | None = None,
) -> bytes:
    """Sample boys sheet ready to upload (class cells already filled).

    ``teachers_by_class`` pre-fills the servant column so a downloaded
    template shows how a boy is filed under a servant on import.
    """
    names = class_names or []
    teachers_by_class = teachers_by_class or {}
    rows = []
    for i, (
        name,
        gender,
        birth,
        phone,
        phone2,
        zone,
        address,
        loc,
        visit,
        note,
        flag,
    ) in enumerate(_BOY_SAMPLES):
        cls = names[i % len(names)] if names else None
        servants = teachers_by_class.get(cls) or []
        rows.append(
            {
                "boy_name": name,
                "gender": gender,
                "birth_date": birth,
                "phone": phone,
                "phone_2": phone2,
                "zone": zone,
                "address": address,
                "location": loc,
                "class_name": cls,
                "teacher_name": servants[(i // len(names)) % len(servants)]
                if servants
                else None,
                "last_visit_date": visit,
                "note": note,
                "issue_flag": flag,
            }
        )
    logger.info("Boys template built: %d rows", len(rows))
    return _workbook(BOY_HEADERS, rows, "الأولاد", BOY_DOCS)


def build_teachers_template(class_names: list[str]) -> bytes:
    names = class_names or []
    rows = []
    for i, (name, phone, visit, note) in enumerate(_TEACHER_SAMPLES):
        rows.append(
            {
                "teacher_name": name,
                "phone": phone,
                "phone_2": None,
                "zone": None,
                "address": None,
                "location": None,
                "class_name": names[i % len(names)] if names else None,
                "last_visit_date": visit,
                "note": note,
            }
        )
    logger.info("Teachers template built: %d rows", len(rows))
    return _workbook(TEACHER_HEADERS, rows, "الخدام")


# phone, servant/boy name, role - one row per login.
_USER_SAMPLES = [
    ("01012345678", "أ. مينا عادل", "teacher"),
    ("01234567890", "أ. مارينا سمير", "admin"),
    ("01122334455", "أ. فادي حنا", "teacher"),
    ("01555555555", "مينا فؤاد حنا", "user"),
]


def _user_template_rows(class_names: list[str]) -> list[dict]:
    names = class_names or []
    rows = []
    for i, (phone, name, role) in enumerate(_USER_SAMPLES):
        rows.append(
            {
                "phone": phone,
                "class_name": names[i % len(names)] if names else None,
                "name": name,
                "role": role,
            }
        )
    return rows


def build_users_template(class_names: list[str]) -> bytes:
    """Sample accounts sheet (``phone | class_name | name | role``)."""
    rows = _user_template_rows(class_names)
    logger.info("Users template built: %d rows", len(rows))
    return _workbook(USER_HEADERS, rows, "الحسابات", USER_DOCS)


def build_users_template_csv(class_names: list[str]) -> bytes:
    """Same template as a CSV, with a BOM so Excel opens the Arabic right."""
    rows = _user_template_rows(class_names)
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(USER_HEADERS)
    for row in rows:
        writer.writerow([row.get(h) or "" for h in USER_HEADERS])
    logger.info("Users CSV template built: %d rows", len(rows))
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def build_boys_export(boys: list, class_label_fn) -> bytes:
    """Round-trip export: same columns the importer accepts."""
    rows = [
        {
            "boy_name": b.boy_name,
            "gender": b.gender.value,
            "birth_date": b.birth_date,
            "phone": b.phone,
            "phone_2": b.phone_2,
            "zone": b.zone,
            "address": b.address,
            "location": b.location,
            "father_name": b.father_name.value if b.father_name else None,
            "national_id": b.national_id,
            "skills": _skills_cell(b.skills),
            "class_name": class_label_fn(b.class_id),
            "teacher_name": b.teacher_name,
            "last_visit_date": b.last_visit_date,
            "note": b.note,
            "issue_flag": b.issue_flag,
        }
        for b in boys
    ]
    return _workbook(BOY_HEADERS, rows, "الأولاد", BOY_DOCS)


def build_teachers_export(teachers: list, class_label_fn) -> bytes:
    rows = [
        {
            "teacher_name": t.teacher_name,
            "phone": t.phone,
            "phone_2": t.phone_2,
            "zone": t.zone,
            "address": t.address,
            "location": t.location,
            "father_name": t.father_name.value if t.father_name else None,
            "skills": _skills_cell(t.skills),
            "class_name": class_label_fn(t.class_id),
            "last_visit_date": t.last_visit_date,
            "note": t.note,
        }
        for t in teachers
    ]
    return _workbook(TEACHER_HEADERS, rows, "الخدام")


def _skills_cell(skills) -> str:
    """A skills column on its way to Excel: enum list -> 'رسم, تمثيل'."""
    if not skills:
        return ""
    return ", ".join(s.value if isinstance(s, SkillEnum) else str(s) for s in skills)
