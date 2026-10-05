"""importer.py - Shared .xlsx upload flow for collection import endpoints.

Validates the file, parses rows via an EDA reader, bulk-inserts via the
service (per-row failures don't stop the rest), and shapes the summary
response. Keeps the boys/teachers import routes to a few lines each.
"""

from fastapi import HTTPException, UploadFile, status

from app.config.logger import get_logger

logger = get_logger(__name__)


UPLOAD_EXTENSIONS = (".xlsx", ".xlsm", ".csv")


def read_upload(file: UploadFile, extensions: tuple[str, ...] = UPLOAD_EXTENSIONS) -> bytes:
    """Validate the upload envelope and return its bytes.

    Only spreadsheet files are accepted (.csv included) and an empty body is
    rejected before any parser is involved.
    """
    filename = (file.filename or "").lower()
    if not filename.endswith(extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only {' / '.join(extensions)} files are accepted.",
        )
    data = file.file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty."
        )
    return data


def run_import(file: UploadFile, *, reader, service, name_key: str) -> dict:
    """Run a full workbook import. `service` must expose add_list(items)."""
    data = read_upload(file)
    try:
        items, parse_errors = reader(data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    result = service.add_list(items)
    failed = [
        {"row": e["row"], name_key: e[name_key], "error": e["error"]}
        for e in parse_errors
    ] + result["failed"]
    summary = {
        "total_rows": len(items) + len(parse_errors),
        "created_count": len(result["created"]),
        "failed_count": len(failed),
        # plain dicts on purpose: ORM rows are not JSON-encodable here
        "created": [
            {
                "id": getattr(row, "id", None),
                name_key: getattr(row, name_key, None),
            }
            for row in result["created"]
        ],
        "failed": failed,
    }
    logger.info(f"Import done: {summary['created_count']} created, {summary['failed_count']} failed")
    return summary
