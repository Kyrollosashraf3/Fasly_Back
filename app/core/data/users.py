from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import get_password_hash
from app.core.data.base import BaseService
from app.core.data.common import ensure_admin, ensure_class_access, ensure_unique_field, enum_value, where_eq
from app.models.enums import RoleEnum
from app.models.user import UserCreate, UserResponse, UserUpdate

logger = get_logger(__name__)

COLLECTION = settings.COLLECTION_USER


def _doc_to_response(doc_id: str, data: dict) -> UserResponse:
    kwargs: dict = {
        "id": doc_id,
        "user_name": data.get("user_name", ""),
        "mail": data.get("mail", ""),
        "phone": data.get("phone"),
        "role": data.get("role", RoleEnum.USER),
        "class_name": data.get("class_name"),
    }
    if data.get("created_at"):
        kwargs["created_at"] = data["created_at"]
    return UserResponse(**kwargs)


def get_user_by_mail(db, mail: str) -> tuple[str, dict] | None:
    """Internal lookup for login — returns (doc_id, raw data) including the hash."""
    docs = list(where_eq(db.collection(COLLECTION), "mail", mail).limit(1).stream())
    if not docs:
        return None
    return docs[0].id, docs[0].to_dict()


class UserService(BaseService):
    """
    RBAC:
    - Admin: full access (any class, can create admins).
    - Amin (USER): sees/manages only users of own class, cannot create admins
      or move users between classes.
    """

    def _col(self):
        return self.db.collection(COLLECTION)

    def create_user(self, data: UserCreate) -> UserResponse:
        ensure_admin(self.current_user)
        if get_user_by_mail(self.db, data.mail):
            logger.warning(f"Attempt to register duplicate mail: {data.mail}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A user with this mail already exists in the system.",
            )
        ensure_unique_field(self.db, COLLECTION, "user_name", data.user_name, label="User")
        _, doc_ref = self._col().add(
            {
                "user_name": data.user_name.strip(),
                "mail": data.mail.strip(),
                "phone": data.phone,
                "password_hash": get_password_hash(data.password),
                "role": enum_value(data.role),
                "class_name": enum_value(data.class_name),
                "created_at": datetime.now(timezone.utc),
            }
        )
        logger.info(f"User created id={doc_ref.id} mail={data.mail} role={data.role}")
        created = self._col().document(doc_ref.id).get().to_dict()
        return _doc_to_response(doc_ref.id, created)

    def get_user(self, user_id: str) -> UserResponse:
        doc = self._col().document(user_id).get()
        if not doc.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        user = _doc_to_response(doc.id, doc.to_dict())
        ensure_class_access(user.class_name, self.current_user)
        return user

    def update_user(self, user_id: str, data: UserUpdate) -> UserResponse:
        doc = self._col().document(user_id).get()
        if not doc.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        current = _doc_to_response(doc.id, doc.to_dict())
        ensure_class_access(current.class_name, self.current_user)

        updates = data.model_dump(exclude_unset=True)
        if "user_name" in updates and updates["user_name"] is not None:
            updates["user_name"] = updates["user_name"].strip()
            ensure_unique_field(self.db, COLLECTION, "user_name", updates["user_name"], exclude_id=user_id, label="User")
        if "mail" in updates and updates["mail"] is not None:
            updates["mail"] = updates["mail"].strip()
        if self.current_user.role != RoleEnum.ADMIN:
            if updates.get("role") == RoleEnum.ADMIN:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Amin cannot promote users to Admin.",
                )
            if "class_name" in updates and updates["class_name"] != self.current_user.class_name:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Amin cannot move users to another class.",
                )
        if "password" in updates:
            updates["password_hash"] = get_password_hash(updates.pop("password"))
        if "role" in updates:
            updates["role"] = enum_value(updates["role"])
        if "class_name" in updates:
            updates["class_name"] = enum_value(updates["class_name"])

        if updates:
            self._col().document(user_id).update(updates)
        logger.info(f"User updated id={user_id} fields={sorted(updates)} by {self.current_user.mail}")
        refreshed = self._col().document(user_id).get().to_dict()
        return _doc_to_response(user_id, refreshed)

    def list_users(self) -> list[UserResponse]:
        if self.current_user.role == RoleEnum.ADMIN:
            docs = self._col().stream()
        else:
            docs = where_eq(self._col(), "class_name", enum_value(self.current_user.class_name)).stream()
        users = [_doc_to_response(d.id, d.to_dict()) for d in docs]
        logger.debug(f"Listed users for {self.current_user.mail} count={len(users)}")
        return users

    def delete_user(self, user_id: str) -> None:
        ensure_admin(self.current_user)
        doc_ref = self._col().document(user_id)
        if not doc_ref.get().exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        doc_ref.delete()
        logger.info(f"User deleted id={user_id} by {self.current_user.mail}")
