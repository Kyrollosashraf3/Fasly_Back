from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user
from app.core.data import ClassService, GroupsService
from app.core.EDA.importer import read_upload
from app.core.EDA.read_excel import read_groups_workbook
from app.core.EDA.write_groups import build_groups_workbook
from app.db.database import get_db
from app.schemas.group import GroupAssign, GroupUnassign
from app.schemas.user import UserResponse

router = APIRouter(prefix="/groups", tags=["Groups"])

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


@router.post("/assign")
def assign_group(
    data: GroupAssign,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return GroupsService(db, current_user).assign(data.teacher_id, data.boy_ids)


@router.post("/unassign")
def unassign_group(
    data: GroupUnassign,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return GroupsService(db, current_user).unassign(data.boy_ids)


@router.post("/import")
def import_groups(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Sheet columns: teacher_name | boy_name | class_name."""
    classes = ClassService(db, current_user).label_lookup()
    data = read_upload(file)
    try:
        rows, parse_errors = read_groups_workbook(data, classes=classes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    result = GroupsService(db, current_user).import_rows(rows)
    failed = parse_errors + result["failed"]
    return {
        "total_rows": len(rows) + len(parse_errors),
        "created_count": len(result["created"]),
        "failed_count": len(failed),
        "created": result["created"],
        "failed": failed,
    }


@router.get("")
def list_groups(
    class_id: int | None = None,
    teacher_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Roster plus each boy's attendance % and last follow-up (the sheet the
    UI renders needs those two columns, so the export payload is reused)."""
    return GroupsService(db, current_user).export_rows(
        class_id=class_id, teacher_id=teacher_id
    )


@router.get("/export")
def export_groups(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    service = GroupsService(db, current_user)
    payload = service.export_rows(class_id=class_id)

    names = {row.id: row.name for row in ClassService(db, current_user).list()}
    class_ids = {g["class_id"] for g in payload["groups"]}
    if class_id is not None:
        label = names.get(class_id, "")
    elif len(class_ids) == 1:
        label = names.get(next(iter(class_ids)), "")
    else:
        label = "كل الفصول"

    content = build_groups_workbook(payload["groups"], class_label=label)
    return Response(
        content=content,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": 'attachment; filename="follow_up_groups.xlsx"'
        },
    )
