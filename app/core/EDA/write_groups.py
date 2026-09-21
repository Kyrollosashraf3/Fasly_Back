"""write_groups.py - Build the groups Excel export.

Layout: for each servant a title row, then his boys table, then a blank
row — next servant below, and so on (Arabic headers).
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.config.logger import get_logger

logger = get_logger(__name__)

NAVY_FILL = PatternFill("solid", fgColor="1E2A4A")
YELLOW_FILL = PatternFill("solid", fgColor="F4C430")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=12)
TITLE_FONT = Font(bold=True, color="1E2A4A", size=14)
SUB_FONT = Font(bold=True, color="1E2A4A", size=11)

COLUMNS = ["الاسم", "التليفون", "تليفون آخر", "العنوان",
           "حاضر", "غائب", "النسبة %", "آخر افتقاد", "طريقة الافتقاد", "ملاحظات"]


def build_groups_workbook(groups: list[dict], class_label: str = "") -> bytes:
    """Render servant groups into an .xlsx file (as bytes)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "المجموعات"
    ws.sheet_view.rightToLeft = True

    widths = [22, 14, 14, 24, 8, 8, 10, 14, 12, 30]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = w

    row = 1
    for g in groups:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(COLUMNS))
        title = ws.cell(row=row, column=1,
                        value=f"مجموعة الخادم: {g.get('teacher_name') or ''}"
                              f"  ({class_label}  -  {g.get('boys_count', 0)} أولاد)")
        title.font = TITLE_FONT
        title.alignment = Alignment(horizontal="right")
        row += 1
        for j, h in enumerate(COLUMNS, start=1):
            c = ws.cell(row=row, column=j, value=h)
            c.font = HEADER_FONT
            c.fill = NAVY_FILL
            c.alignment = Alignment(horizontal="center")
        row += 1
        for b in g.get("boys", []):
            fu = b.get("last_followup") or {}
            ws.cell(row=row, column=1, value=b.get("boy_name"))
            ws.cell(row=row, column=2, value=b.get("phone"))
            ws.cell(row=row, column=3, value=b.get("phone_2"))
            ws.cell(row=row, column=4, value=b.get("address"))
            ws.cell(row=row, column=5, value=b.get("present"))
            ws.cell(row=row, column=6, value=b.get("absent"))
            ws.cell(row=row, column=7, value=b.get("percent"))
            ws.cell(row=row, column=8, value=fu.get("action_date"))
            ws.cell(row=row, column=9, value=fu.get("status"))
            ws.cell(row=row, column=10, value=b.get("note"))
            row += 1
        row += 1  # blank separator before next servant

    buf = BytesIO()
    wb.save(buf)
    logger.info(f"Groups workbook built: {len(groups)} servants")
    return buf.getvalue()
