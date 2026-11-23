"""Follow-up groups: which boys each servant is responsible for."""

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
from app.features.group.services import GroupsService
from app.features.school_class.services import ClassService
from app.db.database import get_db
from app.features.user.models.user import User
from app.features.group.schemas.group import GroupAssign, GroupUnassign

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get("")
def list_groups(
    class_id: int | None = None,
    teacher_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Roster plus each boy's attendance % and last follow-up - the sheet the
    UI renders needs those two columns."""
    return GroupsService(db, current_user).list_with_stats(
        class_id=class_id, teacher_id=teacher_id
    )


@router.post("/assign")
def assign_group(
    data: GroupAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Put boys under a servant (a boy belongs to exactly one group)."""
    return GroupsService(db, current_user).assign(data.teacher_id, data.boy_ids)


@router.post("/unassign")
def unassign_group(
    data: GroupUnassign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return GroupsService(db, current_user).unassign(data.boy_ids)


@router.get("/template")
def groups_template(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Current groups as a sheet the user can edit and upload back.

    One row per boy: teacher_name | boy_name | class_name - exactly the
    columns ``/groups/import`` reads.
    """
    from app.core.EDA.templates import build_groups_template
    from app.features.sheet.routes import class_labels, xlsx_response

    payload = GroupsService(db, current_user).list(class_id=class_id)
    labels = class_labels(db, current_user)
    rows = [
        {
            "teacher_name": group["teacher_name"],
            "boy_name": boy["boy_name"],
            "class_name": labels.get(group["class_id"], ""),
        }
        for group in payload["groups"]
        for boy in group["boys"]
    ]
    return xlsx_response(build_groups_template(rows), "follow_up_groups_template.xlsx")


@router.post("/import")
def import_groups(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sheet columns: teacher_name | boy_name | class_name."""
    from app.core.EDA.importer import read_upload
    from app.core.EDA.read_excel import read_groups_workbook

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
    assigned = sum(bucket.get("assigned", 0) for bucket in result["created"])
    return {
        "total_rows": len(rows) + len(parse_errors),
        "created_count": assigned,
        "failed_count": len(failed),
        "created": result["created"],
        "failed": failed,
    }


@router.get("/export")
def export_groups(
    class_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The roster sheet as a workbook."""
    from app.core.EDA.write_groups import build_groups_workbook
    from app.features.sheet.routes import xlsx_response

    service = GroupsService(db, current_user)
    payload = service.list_with_stats(class_id=class_id)
    return xlsx_response(
        build_groups_workbook(
            payload["groups"], class_label=_class_label(db, current_user, payload, class_id)
        ),
        "follow_up_groups.xlsx",
    )


def _class_label(db: Session, user: User, payload: dict, class_id: int | None) -> str:
    """Name of the class the workbook is about; "all classes" when mixed."""
    names = {row.id: row.name for row in ClassService(db, user).list()}
    if class_id is not None:
        return names.get(class_id, "")
    classes = {group["class_id"] for group in payload["groups"]}
    if len(classes) == 1:
        return names.get(next(iter(classes)), "")
    return "كل الفصول"