from datetime import date, datetime

from sqlalchemy.orm import Session


def now_utc() -> datetime:
    pass


def touch(record) -> None:
    pass


def append_boy_note(
    db: Session,
    boy_id: int,
    note: str | None,
    tag: str | None = None,
) -> None:
    pass


def ensure_admin(user) -> None:
    pass


def ensure_class_access(target_class, user) -> None:
    pass


def ensure_record_class_access(record_class, user) -> None:
    pass


def get_or_404(db: Session, model, record_id: int, label: str = "Record"):
    pass


def bulk_create(
    create_fn,
    items: list,
    *,
    label: str,
    name_attr: str,
) -> dict:
    pass


def ensure_unique_field(
    db: Session,
    model,
    field: str,
    value: str | None,
    exclude_id: int | None = None,
    label: str = "Record",
) -> None:
    pass


def commit(db: Session, context: str) -> None:
    pass


def is_past_friday(date_str) -> bool:
    pass


def to_date(value) -> date | None:
    pass


def enum_value(value):
    pass
