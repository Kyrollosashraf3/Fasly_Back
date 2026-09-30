from pydantic import BaseModel

from app.schemas.base import ORMResponse


class UserCreate(BaseModel):
    pass


class UserUpdate(BaseModel):
    pass


class UserResponse(ORMResponse):
    pass


class UserInDB(UserResponse):
    pass


class Token(BaseModel):
    pass
