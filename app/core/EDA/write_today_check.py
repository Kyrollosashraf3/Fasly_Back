"""write_today_check.py - Build the «فحص اليوم» Excel export.

One worksheet per class, in the login's own scope: the general amin gets every
class, a class amin and a servant get theirs. Inside a sheet it is one block per
list - today's liturgy first, then a block per competition that class runs - and
each block is a merged title row, a navy header row, the boys, then a blank
separator. Same shape as the groups sheet.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config.logger import get_logger

logger = get_logger(__name__)

NAVY_FILL = PatternFill("solid", fgColor="1E2A4A")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=12)
TITLE_FONT = Font(bold=True, color="1E2A4A", size=14)
EMPTY_FONT = Font(italic=True, color="8A8F98", size=11)

COLUMNS = ["م", "اسم الولد", "التليفون"]
WIDTHS = [6, 34, 16]
NO_RECORD = "— لسه مفيش تسجيلات النهاردة —"
#: Characters Excel refuses inside a sheet name.
_FORBIDDEN = "[]:*?/\\"


def _arabic_date(value: str | None) -> str:
    """2026-11-03 to 3/11/2026, so the sheet reads the way the screen does."""
    if not value:
        return ""
    parts = value.split("-")
    if len(parts) != 3:
        return value
    year, month, day = parts
    return f"{int(day)}/{int(month)}/{year}"


def _sheet_name(sheet: dict, index: int, taken: set[str]) -> str:
    """The class name as an Excel-legal, unique tab title."""
    raw = (sheet.get("class_name") or f"فصل {index + 1}").strip()
    name = "".join(ch for ch in raw if ch not in _FORBIDDEN)[:31] or f"فصل {index + 1}"
    while name in taken:
        # Two classes with the same name: the id tells them apart.
        name = f"{name[:26]} ({sheet.get('class_id') or len(taken) + 1})"
    taken.add(name)
    return name


def _block(ws, row: int, title: str, boys: list[dict]) -> int:
    """One titled list: title, header, rows, blank separator."""
    span = len(COLUMNS)

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    cell = ws.cell(row=row, column=1, value=f"{title}  ({len(boys)} ولد)")
    cell.font = TITLE_FONT
    cell.alignment = Alignment(horizontal="right")
    row += 1

    for j, head in enumerate(COLUMNS, start=1):
        c = ws.cell(row=row, column=j, value=head)
        c.font = HEADER_FONT
        c.fill = NAVY_FILL
        c.alignment = Alignment(horizontal="center")
    row += 1

    if not boys:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
        c = ws.cell(row=row, column=1, value=NO_RECORD)
        c.font = EMPTY_FONT
        c.alignment = Alignment(horizontal="right")
        return row + 2

    for i, b in enumerate(boys, start=1):
        ws.cell(row=row, column=1, value=i)
        ws.cell(row=row, column=2, value=b.get("boy_name"))
        ws.cell(row=row, column=3, value=b.get("phone"))
        row += 1
    return row + 1


def _write_sheet(ws, sheet: dict) -> None:
    """Fill one class's sheet: its own title, liturgy, then every competition."""
    ws.sheet_view.rightToLeft = True
    span = len(COLUMNS)
    for i, w in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    title = f"فحص اليوم — {_arabic_date(sheet.get('date'))}"
    if sheet.get("class_name"):
        title = f"{title} — {sheet['class_name']}"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    head = ws.cell(row=1, column=1, value=title)
    head.font = Font(bold=True, color="FFFFFF", size=14)
    head.fill = NAVY_FILL
    head.alignment = Alignment(horizontal="right")

    row = _block(ws, 3, "حضور قداس النهاردة", sheet.get("liturgy", {}).get("boys", []))
    for task in sheet.get("tasks", []):
        row = _block(ws, row, f"مسابقة: {task.get('task_name') or ''}", task.get("boys", []))


def build_today_check_workbook(book: dict) -> bytes:
    """Render the day's lists into one workbook, a sheet per class."""
    wb = Workbook()
    # create_sheet never replaces the default one, so drop it first.
    wb.remove(wb.active)
    taken: set[str] = set()

    for index, sheet in enumerate(book.get("sheets", [])):
        _write_sheet(wb.create_sheet(_sheet_name(sheet, index, taken)), sheet)

    buf = BytesIO()
    wb.save(buf)
    logger.info("Today-check workbook built: %d class sheets", len(taken))
    return buf.getvalue()
