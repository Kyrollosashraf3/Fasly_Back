"""write_servants.py - Build the "تفاصيل الخدام" Excel export.

One simple sheet: exactly the rows the dashboard table shows, in the order the
user picked (metric + asc/desc), with the same Arabic column headers.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.config.logger import get_logger

logger = get_logger(__name__)

NAVY_FILL = PatternFill("solid", fgColor="1E2A4A")
HEADER_FONT = Font(bold=True, color="FFFFFF", size=12)
TITLE_FONT = Font(bold=True, color="1E2A4A", size=14)

#: ``metric`` query value -> (row key, the Arabic label used in the title).
METRICS = {
    "all": ("score", "مجموع النقاط"),
    "attend": ("attend", "الحضور"),
    "liturgy": ("liturgy", "القداس"),
    "follow": ("follow", "الافتقاد"),
    "prepare": ("prepare", "التحضير"),
    "teachers_meeting": ("teachers_meeting", "اجتماع الخدام"),
}

PERIOD_LABELS = {
    "last_friday": "آخر جمعة",
    "all": "كل الفترة",
    "season": "من بداية السنة الكنسية",
}

COLUMNS = [
    "الخادم",
    "الفصل",
    "النقاط",
    "حاضر",
    "تحضير الدرس",
    "القداس",
    "افتقاد",
    "اجتماع الخدام",
]
WIDTHS = [28, 16, 9, 8, 13, 8, 9, 14]


def build_servants_workbook(
    servants: list[dict],
    scope: dict,
    metric: str = "all",
    order: str = "desc",
) -> bytes:
    """Render the servant detail rows into an .xlsx file (as bytes)."""
    key, metric_label = METRICS.get(metric, METRICS["all"])

    # Name first, then the metric: the second sort is stable, so equal scores
    # stay alphabetical whichever direction was asked for.
    rows = sorted(servants, key=lambda s: str(s.get("teacher_name") or ""))
    rows.sort(key=lambda s: int(s.get(key) or 0), reverse=order != "asc")

    labels = scope.get("class_labels") or {}
    classes = scope.get("classes") or []
    class_label = labels.get(classes[0], "") if len(classes) == 1 else "كل الفصول"
    period = PERIOD_LABELS.get(scope.get("date_mode"), "كل الفترة")

    wb = Workbook()
    ws = wb.active
    ws.title = "تفاصيل الخدام"
    ws.sheet_view.rightToLeft = True

    for i, width in enumerate(WIDTHS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    title = ws.cell(
        row=1,
        column=1,
        value=(
            f"تفاصيل الخدام — {class_label} — {period}"
            f"  (مرتبة حسب {metric_label} —"
            f" {'تصاعديًا' if order == 'asc' else 'تنازليًا'})"
        ),
    )
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(COLUMNS))
    title.font = TITLE_FONT
    title.alignment = Alignment(horizontal="right")

    for col, header in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=2, column=col, value=header)
        cell.font = HEADER_FONT
        cell.fill = NAVY_FILL
        cell.alignment = Alignment(horizontal="center")

    row = 3
    for s in rows:
        ws.cell(row=row, column=1, value=s.get("teacher_name"))
        ws.cell(row=row, column=2, value=labels.get(s.get("class_id"), "—"))
        ws.cell(row=row, column=3, value=int(s.get("score") or 0))
        for offset, flag in enumerate(
            ("attend", "prepare", "liturgy", "follow", "teachers_meeting"), start=4
        ):
            cell = ws.cell(row=row, column=offset, value=int(s.get(flag) or 0))
            cell.alignment = Alignment(horizontal="center")
        row += 1

    ws.freeze_panes = "A3"
    logger.info("Servants workbook built: %d rows", len(rows))

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
