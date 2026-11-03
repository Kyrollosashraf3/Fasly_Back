from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.config.logger import get_logger

logger = get_logger(__name__)

NAVY_FILL = PatternFill("solid", fgColor="1E2A4A")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=12)
COLUMNS = ["اسم الولد", "الحالة", "حضور", "قداس", "تسميع"]
WIDTHS = [34, 18, 14, 14, 16]
_FORBIDDEN = "[]:*?/\\"


def _arabic_date(value: str | None) -> str:
    if not value:
        return ""
    year, month, day = value.split("-")
    return f"{int(day)}/{int(month)}/{year}"


def _sheet_name(sheet: dict) -> str:
    raw = (sheet.get("class_name") or "فحص اليوم").strip()
    return "".join(ch for ch in raw if ch not in _FORBIDDEN)[:31] or "فحص اليوم"


def build_today_check_workbook(sheet: dict) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = _sheet_name(sheet)
    ws.sheet_view.rightToLeft = True
    for index, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLUMNS))
    title = ws.cell(row=1, column=1, value=f"فحص اليوم — {_arabic_date(sheet.get('date'))}")
    title.font = Font(bold=True, color="FFFFFF", size=14)
    title.fill = NAVY_FILL
    title.alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(COLUMNS))
    subtitle = ws.cell(
        row=2,
        column=1,
        value=f"{sheet.get('class_name') or ''} — مسابقة: {sheet.get('task_name') or ''}",
    )
    subtitle.font = Font(bold=True, color="1E2A4A", size=12)
    subtitle.alignment = Alignment(horizontal="center")

    for column, heading in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=4, column=column, value=heading)
        cell.font = HEADER_FONT
        cell.fill = NAVY_FILL
        cell.alignment = Alignment(horizontal="center")

    boys = sheet.get("boys", [])
    for row_index, boy in enumerate(boys, start=5):
        values = [
            boy.get("boy_name"),
            "مكتمل" if boy.get("complete") else "غير مكتمل",
            "✓" if boy.get("present") else "✗",
            "✓" if boy.get("liturgy") else "✗",
            "✓" if boy.get("recited") else "✗",
        ]
        for column, value in enumerate(values, start=1):
            cell = ws.cell(row=row_index, column=column, value=value)
            cell.alignment = Alignment(
                horizontal="right" if column == 1 else "center", vertical="center"
            )

    if boys:
        ws.auto_filter.ref = f"A4:E{len(boys) + 4}"
    else:
        ws.merge_cells(start_row=5, start_column=1, end_row=5, end_column=len(COLUMNS))
        empty = ws.cell(row=5, column=1, value="لا توجد أسماء مطابقة")
        empty.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A5"
    buf = BytesIO()
    wb.save(buf)
    logger.info("Today-check workbook built: %d boys", len(boys))
    return buf.getvalue()
