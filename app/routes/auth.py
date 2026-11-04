"""Authentication and login accounts.

Three groups live in one router because they share one story:

    /auth/login, /auth/signup/*   pre-login - no user, so no service
    /auth/me                     the caller's own profile
    /auth/register, /auth/users  accounts - administrators only
"""

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth.deps import get_current_user, require_admin
from app.core.auth.rate_limit import (
    LOGIN_ACCOUNT_LIMIT,
    LOGIN_IP_LIMIT,
    SIGNUP_IP_LIMIT,
    limiter,
    login_account_key,
)
from app.core.auth.security import create_access_token, verify_password
from app.core.data import (
    ClassService,
    UserService,
    complete_signup,
    get_user_by_phone,
    signup_check,
)
from app.db.database import get_db
from app.models.user import User
from app.schemas.user import (
    ManagedClassesUpdate,
    SignupCheckRequest,
    SignupCheckResponse,
    SignupRequest,
    Token,
    UserCreate,
    UserResponse,
    UserUpdate,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
@limiter.limit(LOGIN_IP_LIMIT)
@limiter.limit(LOGIN_ACCOUNT_LIMIT, key_func=login_account_key)
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 password flow - ``username`` carries the phone number."""
    user = get_user_by_phone(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.pending_signup:
        # the account exists but nobody has chosen a password yet
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="هذا الحساب لسه محتاج تسجيل برقم تليفونه.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(str(user.id)), token_type="bearer"
    )


@router.post("/signup/check", response_model=SignupCheckResponse)
@limiter.limit(SIGNUP_IP_LIMIT)
def check_signup(
    request: Request,
    payload: SignupCheckRequest,
    db: Session = Depends(get_db),
):
    """Phone-number lookup used by the signup screen before a password is typed."""
    return SignupCheckResponse(**signup_check(db, payload.phone))


@router.post("/signup", response_model=Token)
@limiter.limit(SIGNUP_IP_LIMIT)
def finish_signup(
    request: Request,
    payload: SignupRequest,
    db: Session = Depends(get_db),
):
    """Set the password of a phone-registered account and log straight in."""
    user = complete_signup(db, payload.phone, payload.password)
    return Token(
        access_token=create_access_token(str(user.id)), token_type="bearer"
    )


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return UserService(db, current_user).list_users()


@router.post(
    "/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Register a login: the number only - the owner picks his password then.

    ``/auth/register`` stays retired; the screen talks to ``/auth/users`` like
    every other directory. The service decides who may create what (a class
    amin only accounts of his classes, a stage-amin or super-admin role only
    the church-wide amin) and raises its own 403.
    """
    return UserService(db, current_user).create_user(user_in)





@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Not found.",
    )

@router.put("/users/{user_id}/classes", response_model=UserResponse)
def set_user_classes(
    user_id: int,
    payload: ManagedClassesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """The classes a stage amin is answerable for - the whole list, every time."""
    return UserService(db, current_user).set_managed_classes(user_id, payload.class_ids)


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """An administrator may change anything; a servant or a boy may reset only
    his own password (the service draws that line)."""
    return UserService(db, current_user).update_user(user_id, user_in)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    UserService(db, current_user).delete_user(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)