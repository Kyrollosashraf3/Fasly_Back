from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user, require_admin
from app.core.auth.rate_limit import (
    LOGIN_EMAIL_LIMIT,
    LOGIN_IP_LIMIT,
    limiter,
    login_email_key,
)
from app.core.auth.security import create_access_token, verify_password
from app.core.data import UserService, get_user_by_email
from app.db.database import get_db
from app.schemas.user import Token, UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
@limiter.limit(LOGIN_IP_LIMIT)
@limiter.limit(LOGIN_EMAIL_LIMIT, key_func=login_email_key)
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 password flow. ``username`` carries the email address."""
    user = get_user_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(str(user.id)),
        token_type="bearer",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(require_admin),
):
    return UserService(db, current_user).create_user(user_in)


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return UserService(db, current_user).list_users()


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
):
    return UserService(db, current_user).update_user(user_id, user_in)


@router.delete(
    "/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: UserResponse = Depends(require_admin),
):
    UserService(db, current_user).delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: UserResponse = Depends(get_current_user)):
    return current_user
