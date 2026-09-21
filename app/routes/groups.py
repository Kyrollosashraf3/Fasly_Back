from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.auth.deps import get_current_user
from app.core.data.groups import GroupsService
from app.core.EDA.read_excel import read_groups_workbook
from app.core.EDA.write_groups import build_groups_workbook
from app.db.firebase import get_db
from app.models.enums import ClassEnum
from app.models.group import GroupAssign, GroupUnassign
from app.models.user import UserResponse

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.post("/assign")
def assign_group(
    data: GroupAssign,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Put boys into a servant's follow-up group (replaces their old group).

    Admin: any class. Amin: only own class (servant and boys must match)."""
    return GroupsService(db, current_user).assign(data.teacher_id, data.boy_ids)


@router.post("/unassign")
def unassign_group(
    data: GroupUnassign,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Remove boys from any follow-up group."""
    return GroupsService(db, current_user).unassign(data.boy_ids)


@router.post("/import")
def import_groups(
    file: UploadFile = File(...),
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Upload an assignment sheet (teacher_name | boy_name | class_name).

    Names must each match exactly one record in that class.
    Returns {total_rows, assigned_count, failed_count, assigned, failed}.
    """
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .xlsx files are accepted.",
        )
    data = file.file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    try:
        items, parse_errors = read_groups_workbook(data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    result = GroupsService(db, current_user).assign_import(items)
    failed = [
        {"row": e["row"], "boy_name": e["boy_name"],
         "teacher_name": None, "error": e["error"]}
        for e in parse_errors
    ] + result["failed"]
    return {
        "total_rows": len(items) + len(parse_errors),
        "assigned_count": len(result["assigned"]),
        "failed_count": len(failed),
        "assigned": result["assigned"],
        "failed": failed,
    }


@router.get("")
def list_groups(
    class_name: ClassEnum | None = None,
    teacher_id: str | None = None,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Servants with their boy rosters + per-boy summaries.

    Admin: all (optional class/teacher filter). Amin: own class only."""
    return GroupsService(db, current_user).list_groups(class_name, teacher_id)


@router.get("/export")
def export_groups(
    class_name: ClassEnum | None = None,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Download an .xlsx sheet: each servant followed by his group table."""
    data = GroupsService(db, current_user).list_groups(class_name)
    label = f"class {class_name.value}" if class_name else "all classes"
    content = build_groups_workbook(data["groups"], class_label=label)
    filename = f"groups_{class_name.value if class_name else 'all'}.xlsx"
    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
