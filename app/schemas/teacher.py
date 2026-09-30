from pydantic import BaseModel


class TeacherCreate(BaseModel):
    pass


class TeacherUpdate(BaseModel):
    pass


class TeacherResponse(TeacherCreate):
    pass
