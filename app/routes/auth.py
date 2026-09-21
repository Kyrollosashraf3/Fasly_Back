from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.deps import get_current_user, require_admin
from app.core.auth.rate_limit import (
    LOGIN_EMAIL_LIMIT,
    LOGIN_IP_LIMIT,
    limiter,
    login_email_key,
)
from app.core.auth.security import create_access_token, verify_password
from app.core.data.users import UserService, get_user_by_mail
from app.db.firebase import get_db
from app.models.user import Token, UserCreate, UserResponse, UserUpdate

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
@limiter.limit(LOGIN_IP_LIMIT)
@limiter.limit(LOGIN_EMAIL_LIMIT, key_func=login_email_key)
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db=Depends(get_db),
):
    """Exchange credentials (username = mail) for a JWT. Open to all roles."""
    logger.info(f"Login attempt for mail: {form_data.username}")

    found = get_user_by_mail(db, form_data.username)
    if not found or not verify_password(form_data.password, found[1].get("password_hash", "")):
        logger.warning(f"Login failed for mail: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect mail or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id, data = found
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(subject=user_id, expires_delta=access_token_expires)
    logger.info(f"Login successful: {data.get('mail')} (id={user_id}, role={data.get('role')})")
    return Token(access_token=access_token, token_type="bearer")


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: UserCreate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(require_admin),
):
    """Admin only: create an amin (class-scoped) or another admin account."""
    user = UserService(db, current_user).create_user(user_in)
    logger.info(f"User registered: {user.mail} (id={user.id}, role={user.role}) by {current_user.mail}")
    return user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Admin sees all users; amin sees only users of own class."""
    return UserService(db, current_user).list_users()


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    user_in: UserUpdate,
    db=Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    """Admin can update anyone; amin only users of own class (no promotion to admin)."""
    user = UserService(db, current_user).update_user(user_id, user_in)
    logger.info(f"{current_user.mail} ({current_user.role}) updated user id={user.id}")
    return user


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    db=Depends(get_db),
    current_user: UserResponse = Depends(require_admin),
):
    """Admin only: delete an account."""
    UserService(db, current_user).delete_user(user_id)
    return {"message": "deleted successfully", "id": user_id}


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: UserResponse = Depends(get_current_user)):
    """Current profile for any authenticated user (admin or amin)."""
    return current_user
