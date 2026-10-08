"""read_excel.py - Read Excel sheets into Create models.

Expected sheet: first row = header with the collection's column names.

    boys     : boy_name | gender | birth_date | phone | phone_2 | zone |
                address | location | father_name | national_id | skills |
                skills_custom | class_name | teacher_name |
                last_visit_date | note | issue_flag
    teachers : teacher_name | phone | phone_2 | zone | address | location |
                class_name | last_visit_date | note
    groups   : teacher_name | boy_name | class_name
    users    : phone | class_name | name | role

- Fully empty rows are skipped.
- Cell values are coerced (gender m/f, dates, bools).
- ``class_name`` is resolved to ``class_id`` through the caller's
  :meth:`~app.core.data.classes.ClassService.label_lookup`, so an import can
  only ever land in a class the login is allowed to write into.
- ``teacher_name`` (boys sheet, optional) is resolved through the caller's
  :func:`teacher_lookup`: the servant is filed as the boy's group owner, so
  he can take the boy's attendance right away.
- Returns (items, errors): valid models + per-row parse errors
  ``[{row, <name_key>, error}]`` so the caller can insert the good rows and
  report the bad ones instead of failing the whole file.
"""

from datetime import date, datetime
from io import BytesIO, StringIO
from typing import Callable
import csv
import re

from openpyxl import load_workbook
from pydantic import ValidationError

from app.config.logger import get_logger
from app.models.enums import FatherEnum, GenderEnum, RoleEnum, SkillEnum
from app.schemas.boy import BoyCreate
from app.schemas.teacher import TeacherCreate
from app.schemas.user import UserImportRow, normalise_phone

logger = get_logger(__name__)

BOY_HEADERS = [
    "boy_name",
    "gender",
    "birth_date",
    "phone",
    "phone_2",
    "zone",
    "address",
    "location",
    "father_name",
    "national_id",
    "skills",
    "skills_custom",
    "class_name",
    "teacher_name",
    "last_visit_date",
    "note",
    "issue_flag",
]

TEACHER_HEADERS = [
    "teacher_name",
    "phone",
    "phone_2",
    "zone",
    "address",
    "location",
    "class_name",
    "last_visit_date",
    "note",
]

GROUP_HEADERS = ["teacher_name", "boy_name", "class_name"]

USER_HEADERS = ["phone", "class_name", "name", "role"]

_GENDER_MAP = {
    "m": GenderEnum.MALE,
    "male": GenderEnum.MALE,
    "boy": GenderEnum.MALE,
    "ذكر": GenderEnum.MALE,
    "ولد": GenderEnum.MALE,
    "f": GenderEnum.FEMALE,
    "female": GenderEnum.FEMALE,
    "girl": GenderEnum.FEMALE,
    "أنثى": GenderEnum.FEMALE,
    "انثى": GenderEnum.FEMALE,
    "بنت": GenderEnum.FEMALE,
}

_FATHER_MAP = {
    "ابونا كيرلس روماني": FatherEnum.KIERLOS,
    "كيرلس روماني": FatherEnum.KIERLOS,
    "ابونا ارسانيوس عزت": FatherEnum.ARSANIOUS,
    "ارسانيوس عزت": FatherEnum.ARSANIOUS,
    "ابونا فام عبدالمسيح": FatherEnum.FAMES,
    "فام عبدالمسيح": FatherEnum.FAMES,
}

_SKILL_MAP = {
    "تمثيل": SkillEnum.ACTING,
    "رسم": SkillEnum.DRAWING,
    "تلوين": SkillEnum.COLORING,
    "عزف": SkillEnum.PLAYING,
    "ديكور": SkillEnum.DECOR,
    "برمجة": SkillEnum.PROGRAMMING,
    "تصميم جرافيك": SkillEnum.GRAPHIC_DESIGN,
    "جرافيك": SkillEnum.GRAPHIC_DESIGN,
    "اكسيل": SkillEnum.EXCEL,
    "excel": SkillEnum.EXCEL,
    "كمبيوتر": SkillEnum.COMPUTER,
    "تأليف": SkillEnum.COMPOSITION,
    "اخرى": SkillEnum.OTHER,
}

_TRUE_SET = {"1", "true", "yes", "y", "نعم", "صح", "✓"}
_FALSE_SET = {"0", "false", "no", "n", "لا", "خطأ", ""}

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


def _str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _norm(label: str) -> str:
    return " ".join(str(label).split()).lower()


def _parse_gender(value) -> GenderEnum:
    text = (_str(value) or "").lower()
    if text in _GENDER_MAP:
        return _GENDER_MAP[text]
    raise ValueError(f"bad gender {value!r} (use m/f)")


def _parse_father(value) -> FatherEnum | None:
    text = _str(value)
    if text is None:
        return None
    key = text.strip()
    if key in _FATHER_MAP:
        return _FATHER_MAP[key]
    return FatherEnum(key) if key else None


def _parse_skills(value) -> list[SkillEnum] | None:
    """One cell may hold several skills: 'رسم, تمثيل' -> [DRAWING, ACTING]."""
    text = _str(value)
    if text is None:
        return None
    out: list[SkillEnum] = []
    for part in re.split(r"[,/|؛،]+", text):
        key = part.strip()
        if not key:
            continue
        if key in _SKILL_MAP:
            skill = _SKILL_MAP[key]
        else:
            skill = SkillEnum.OTHER
        if skill not in out:
            out.append(skill)
    return out or None


def _resolve_class(value, classes: dict[str, int]) -> int:
    """Turn a ``class_name`` cell into a ``class_id``.

    ``classes`` comes from ``ClassService.label_lookup()`` - already limited to
    the classes this login may write to.
    """
    text = _str(value)
    if not text:
        raise ValueError("class_name is required")
    key = _norm(text)
    if key.endswith(".0"):  # openpyxl hands numeric cells back as 1.0
        key = key[:-2]
    if key in classes:
        return classes[key]
    raise ValueError(
        f"unknown class_name {value!r} (known: {', '.join(sorted(classes))})"
    )


def _parse_date(value, field: str = "birth_date") -> date | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"bad {field} {value!r} (use YYYY-MM-DD)")


def _parse_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    if text in _TRUE_SET:
        return True
    if text in _FALSE_SET:
        return False
    raise ValueError(f"bad issue_flag {value!r} (use true/false)")


def teacher_lookup(rows) -> dict[tuple[int, str], int]:
    """``(class_id, normalized servant name) -> teacher id``.

    Keyed by class because servant names only have to be unique *inside* a
    class, and because a boy may only be filed under a servant of his own
    class.
    """
    return {(t.class_id, _norm(t.teacher_name)): t.id for t in rows}


def _row_to_boy(
    row: dict,
    classes: dict[str, int],
    teachers: dict[tuple[int, str], int] | None,
) -> BoyCreate:
    name = _str(row.get("boy_name"))
    if not name:
        raise ValueError("boy_name is required")
    class_id = _resolve_class(row.get("class_name"), classes)
    servant = _str(row.get("teacher_name"))
    teacher_id = None
    if servant:
        teacher_id = (teachers or {}).get((class_id, _norm(servant)))
        if teacher_id is None:
            known = sorted(
                {n for (cid, n) in (teachers or {}) if cid == class_id}
            )
            raise ValueError(
                f"unknown teacher_name {servant!r} in this class "
                f"(known: {', '.join(known) or '-'})"
            )
    return BoyCreate(
        boy_name=name,
        gender=_parse_gender(
            row.get("gender") if row.get("gender") is not None else "m"
        ),
        birth_date=_parse_date(row.get("birth_date")),
        phone=_str(row.get("phone")),
        phone_2=_str(row.get("phone_2")),
        zone=_str(row.get("zone")),
        address=_str(row.get("address")),
        location=_str(row.get("location")),
        father_name=_parse_father(row.get("father_name")),
        national_id=_str(row.get("national_id")),
        skills=_parse_skills(row.get("skills")),
        skills_custom=_str(row.get("skills_custom")),
        class_id=class_id,
        teacher_id=teacher_id,
        last_visit_date=_parse_date(
            row.get("last_visit_date"), field="last_visit_date"
        ),
        note=_str(row.get("note")),
        issue_flag=_parse_flag(row.get("issue_flag")),
    )


def _row_to_teacher(row: dict, classes: dict[str, int]) -> TeacherCreate:
    name = _str(row.get("teacher_name"))
    if not name:
        raise ValueError("teacher_name is required")
    return TeacherCreate(
        teacher_name=name,
        phone=_str(row.get("phone")),
        phone_2=_str(row.get("phone_2")),
        zone=_str(row.get("zone")),
        address=_str(row.get("address")),
        location=_str(row.get("location")),
        father_name=_parse_father(row.get("father_name")),
        skills=_parse_skills(row.get("skills")),
        skills_custom=_str(row.get("skills_custom")),
        class_id=_resolve_class(row.get("class_name"), classes),
        last_visit_date=_parse_date(
            row.get("last_visit_date"), field="last_visit_date"
        ),
        note=_str(row.get("note")),
    )


def _is_blank(raw: tuple) -> bool:
    return all(c is None or (isinstance(c, str) and not c.strip()) for c in raw)


def read_workbook(
    data: bytes,
    *,
    headers: list[str],
    required: tuple[str, ...],
    name_key: str,
    build_row: Callable[[dict], object],
    entity: str,
    csv: bool = False,
) -> tuple[list, list[dict]]:
    """Parse a workbook (or a CSV) into models.

    Returns (items, errors). Raises ValueError if the file/header is invalid.
    """
    rows = _csv_rows(data) if csv else _xlsx_rows(data)
    return _parse_table(
        rows,
        headers=headers,
        required=required,
        name_key=name_key,
        build_row=build_row,
        entity=entity,
    )


def _xlsx_rows(data: bytes) -> list[tuple]:
    try:
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"cannot open Excel file: {exc}")
    ws = wb.active
    if ws is None:
        raise ValueError("Excel file has no sheet")
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel sheet is empty")
    return rows


def _csv_rows(data: bytes) -> list[tuple]:
    """First row = header, comma / semicolon / tab separated, UTF-8."""
    text = data.decode("utf-8-sig", errors="replace")
    sample = "\n".join(text.splitlines()[:5])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [tuple(r) for r in csv.reader(StringIO(text), dialect)]
    if not rows:
        raise ValueError("CSV file is empty")
    return rows


def _parse_table(
    rows: list[tuple],
    *,
    headers: list[str],
    required: tuple[str, ...],
    name_key: str,
    build_row: Callable[[dict], object],
    entity: str,
) -> tuple[list, list[dict]]:
    """Shared row loop: header check, blank-row skip, per-row error capture."""
    if not rows:
        raise ValueError("the sheet is empty")
    header = [(_str(c) or "") for c in rows[0]]
    missing = [h for h in required if h not in header]
    if missing:
        raise ValueError(f"missing required columns: {missing} (header={header})")
    col = {name: idx for idx, name in enumerate(header)}

    items: list = []
    errors: list[dict] = []
    for i, raw in enumerate(rows[1:], start=2):
        if _is_blank(raw):
            continue  # skip blank rows
        record = {
            h: (raw[col[h]] if h in col and col[h] < len(raw) else None)
            for h in headers
            if h in col
        }
        try:
            items.append(build_row(record))
        except Exception as exc:
            errors.append(
                {
                    "row": i,
                    name_key: _str(record.get(name_key)),
                    "error": str(exc),
                }
            )
            logger.warning(f"Row {i} skipped: {exc}")

    logger.info(f"Sheet parsed ({entity}): valid={len(items)} errors={len(errors)}")
    return items, errors


def read_boys_workbook(
    data: bytes,
    *,
    classes: dict[str, int],
    teachers: dict[tuple[int, str], int] | None = None,
) -> tuple[list[BoyCreate], list[dict]]:
    """Parse an .xlsx file (as bytes) into boys."""
    return read_workbook(
        data,
        headers=BOY_HEADERS,
        required=("boy_name", "class_name"),
        name_key="boy_name",
        build_row=lambda row: _row_to_boy(row, classes, teachers),
        entity="boys",
    )


def read_teachers_workbook(
    data: bytes, *, classes: dict[str, int]
) -> tuple[list[TeacherCreate], list[dict]]:
    """Parse an .xlsx file (as bytes) into servants."""
    return read_workbook(
        data,
        headers=TEACHER_HEADERS,
        required=("teacher_name", "class_name"),
        name_key="teacher_name",
        build_row=lambda row: _row_to_teacher(row, classes),
        entity="teachers",
    )


def _row_to_group(row: dict, classes: dict[str, int]) -> dict:
    teacher = _str(row.get("teacher_name"))
    boy = _str(row.get("boy_name"))
    if not teacher:
        raise ValueError("teacher_name is required")
    if not boy:
        raise ValueError("boy_name is required")
    return {
        "teacher_name": teacher,
        "boy_name": boy,
        "class_id": _resolve_class(row.get("class_name"), classes),
    }


def read_groups_workbook(
    data: bytes, *, classes: dict[str, int]
) -> tuple[list[dict], list[dict]]:
    """Parse a group-assignment sheet: teacher_name | boy_name | class_name."""
    return read_workbook(
        data,
        headers=GROUP_HEADERS,
        required=tuple(GROUP_HEADERS),
        name_key="boy_name",
        build_row=lambda row: _row_to_group(row, classes),
        entity="groups",
    )


_ROLE_MAP = {
    "super_admin": RoleEnum.SUPER_ADMIN,
    "superadmin": RoleEnum.SUPER_ADMIN,
    "super": RoleEnum.SUPER_ADMIN,
    "أدمن عام": RoleEnum.SUPER_ADMIN,
    "ادمن عام": RoleEnum.SUPER_ADMIN,
    "admin": RoleEnum.ADMIN,
    "administrator": RoleEnum.ADMIN,
    "أمين": RoleEnum.ADMIN,
    "امين": RoleEnum.ADMIN,
    "أمين فصل": RoleEnum.ADMIN,
    "امين فصل": RoleEnum.ADMIN,
    "teacher": RoleEnum.TEACHER,
    "servant": RoleEnum.TEACHER,
    "خادم": RoleEnum.TEACHER,
    "خدام": RoleEnum.TEACHER,
    "user": RoleEnum.USER,
    "boy": RoleEnum.USER,
    "ولد": RoleEnum.USER,
    "أولاد": RoleEnum.USER,
}


def _parse_role(value) -> RoleEnum:
    text = (_str(value) or "").lower()
    if text in _ROLE_MAP:
        return _ROLE_MAP[text]
    raise ValueError(
        f"bad role {value!r} (use super_admin / admin / teacher / user)"
    )


def _row_to_user(row: dict, classes: dict[str, int]) -> UserImportRow:
    """``phone | class_name | name | role`` -> a resolved import row.

    ``class_name`` is turned into ``class_id`` here (same lookup as every
    other sheet), so a super_admin row is the only one allowed to leave it
    blank.
    """
    role = _parse_role(row.get("role"))
    class_name = _str(row.get("class_name"))
    name = _str(row.get("name"))
    class_id = None
    if role != RoleEnum.SUPER_ADMIN:
        class_id = _resolve_class(class_name, classes)
    try:
        return UserImportRow(
            phone=normalise_phone(_str(row.get("phone")) or ""),
            class_name=class_name,
            name=name,
            role=role,
            class_id=class_id,
        )
    except ValidationError as exc:
        raise ValueError("; ".join(e["msg"] for e in exc.errors())) from None


def read_users_workbook(
    data: bytes, *, classes: dict[str, int], csv_file: bool = False
) -> tuple[list[UserImportRow], list[dict]]:
    """Parse an accounts sheet (.xlsx or .csv) into import rows."""
    return read_workbook(
        data,
        headers=USER_HEADERS,
        required=tuple(USER_HEADERS),
        name_key="phone",
        build_row=lambda row: _row_to_user(row, classes),
        entity="users",
        csv=csv_file,
    )


# Backwards-compatible alias (old constant name).
HEADERS = BOY_HEADERS
