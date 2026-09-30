"""read_excel.py - Read Excel sheets into Create models.

Expected sheet: first row = header with the collection's column names
(boys: boy_name | gender | ... | issue_flag â€” teachers: a subset).

- Fully empty rows are skipped.
- Cell values are coerced (gender m/f, class 1..6, dates, bools).
- Returns (items, errors): valid models + per-row parse errors
  [{row, <name_key>, error}] so the caller can insert the good rows and
  report the bad ones instead of failing the whole file.
"""

from datetime import date, datetime
from io import BytesIO
from typing import Callable

from openpyxl import load_workbook

from app.config.logger import get_logger
from app.schemas.boy import BoyCreate
from app.models.enums import ClassEnum, GenderEnum
from app.schemas.teacher import TeacherCreate

logger = get_logger(__name__)

BOY_HEADERS = [
    "boy_name",
    "gender",
    "birth_date",
    "age",
    "phone",
    "phone_2",
    "address",
    "location",
    "class_name",
    "note",
    "issue_flag",
]

TEACHER_HEADERS = ["teacher_name", "phone", "class_name", "duty", "note"]

GROUP_HEADERS = ["teacher_name", "boy_name", "class_name"]

_GENDER_MAP = {
    "m": GenderEnum.MALE,
    "male": GenderEnum.MALE,
    "boy": GenderEnum.MALE,
    "Ø°ÙƒØ±": GenderEnum.MALE,
    "ÙˆÙ„Ø¯": GenderEnum.MALE,
    "f": GenderEnum.FEMALE,
    "female": GenderEnum.FEMALE,
    "girl": GenderEnum.FEMALE,
    "Ø£Ù†Ø«Ù‰": GenderEnum.FEMALE,
    "Ø§Ù†Ø«Ù‰": GenderEnum.FEMALE,
    "Ø¨Ù†Øª": GenderEnum.FEMALE,
}

_TRUE_SET = {"1", "true", "yes", "y", "Ù†Ø¹Ù…", "ØµØ­", "âœ”"}
_FALSE_SET = {"0", "false", "no", "n", "Ù„Ø§", "Ø®Ø·Ø£", ""}

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y")


def _str(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_gender(value) -> GenderEnum:
    text = (_str(value) or "").lower()
    if text in _GENDER_MAP:
        return _GENDER_MAP[text]
    raise ValueError(f"bad gender {value!r} (use m/f)")


def _parse_class(value) -> ClassEnum:
    text = (_str(value) or "").lower()
    # Accept 1..6 as number or string ("5", "5.0", 5)
    if text.endswith(".0"):
        text = text[:-2]
    for member in ClassEnum:
        if text == member.value:
            return member
    raise ValueError(f"bad class_name {value!r} (use 1..6)")


def _parse_date(value) -> date | None:
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
        raise ValueError(f"bad birth_date {value!r} (use YYYY-MM-DD)")


def _parse_age(value) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        age = int(float(str(value).strip()))
    except (ValueError, TypeError):
        raise ValueError(f"bad age {value!r} (must be a number)")
    if age < 0:
        raise ValueError(f"bad age {value!r} (must be >= 0)")
    return age


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


def _row_to_boy(row: dict) -> BoyCreate:
    name = _str(row.get("boy_name"))
    if not name:
        raise ValueError("boy_name is required")
    return BoyCreate(
        boy_name=name,
        gender=_parse_gender(row.get("gender") if row.get("gender") is not None else "m"),
        birth_date=_parse_date(row.get("birth_date")),
        age=_parse_age(row.get("age")),
        phone=_str(row.get("phone")),
        phone_2=_str(row.get("phone_2")),
        address=_str(row.get("address")),
        location=_str(row.get("location")),
        class_name=_parse_class(row.get("class_name")),
        note=_str(row.get("note")),
        issue_flag=_parse_flag(row.get("issue_flag")),
    )


def _row_to_teacher(row: dict) -> TeacherCreate:
    name = _str(row.get("teacher_name"))
    if not name:
        raise ValueError("teacher_name is required")
    return TeacherCreate(
        teacher_name=name,
        phone=_str(row.get("phone")),
        class_name=_parse_class(row.get("class_name")),
        duty=_str(row.get("duty")),
        note=_str(row.get("note")),
    )


def _is_blank(raw: tuple) -> bool:
    return all(c is None or (isinstance(c, str) and not c.strip()) for c in raw)


def read_workbook(data: bytes, *, headers: list[str], required: tuple[str, ...],
                  name_key: str, build_row: Callable[[dict], object],
                  entity: str) -> tuple[list, list[dict]]:
    """Generic .xlsx reader shared by all import flows.

    Returns (items, errors). Raises ValueError if the file/header is invalid.
    """
    try:
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValueError(f"cannot open Excel file: {exc}")
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel sheet is empty")
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
        record = {h: (raw[col[h]] if h in col and col[h] < len(raw) else None)
                  for h in headers if h in col}
        try:
            items.append(build_row(record))
        except Exception as exc:
            errors.append({"row": i, name_key: _str(record.get(name_key)), "error": str(exc)})
            logger.warning(f"Excel row {i} skipped: {exc}")

    logger.info(f"Excel parsed ({entity}): valid={len(items)} errors={len(errors)}")
    return items, errors


def read_boys_workbook(data: bytes) -> tuple[list[BoyCreate], list[dict]]:
    """Parse an .xlsx file (as bytes) into boys."""
    return read_workbook(data, headers=BOY_HEADERS,
                         required=("boy_name", "class_name"), name_key="boy_name",
                         build_row=_row_to_boy, entity="boys")


def _row_to_group(row: dict) -> dict:
    teacher = _str(row.get("teacher_name"))
    boy = _str(row.get("boy_name"))
    if not teacher:
        raise ValueError("teacher_name is required")
    if not boy:
        raise ValueError("boy_name is required")
    return {"teacher_name": teacher, "boy_name": boy,
            "class_name": _parse_class(row.get("class_name")).value}


def read_teachers_workbook(data: bytes) -> tuple[list[TeacherCreate], list[dict]]:
    """Parse an .xlsx file (as bytes) into servants."""
    return read_workbook(data, headers=TEACHER_HEADERS,
                         required=("teacher_name", "class_name"), name_key="teacher_name",
                         build_row=_row_to_teacher, entity="teachers")


def read_groups_workbook(data: bytes) -> tuple[list[dict], list[dict]]:
    """Parse a group-assignment sheet: teacher_name | boy_name | class_name."""
    return read_workbook(data, headers=GROUP_HEADERS,
                         required=tuple(GROUP_HEADERS), name_key="boy_name",
                         build_row=_row_to_group, entity="groups")


# Backwards-compatible alias (old constant name).
HEADERS = BOY_HEADERS
