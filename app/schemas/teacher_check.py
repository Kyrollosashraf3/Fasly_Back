from pydantic import BaseModel


class TeacherCheckCreate(BaseModel):
    pass


class TeacherCheckUpdate(BaseModel):
    pass


class TeacherCheckResponse(TeacherCheckCreate):
    pass


class TeacherCheckItem(BaseModel):
    pass


class TeacherCheckBulkCreate(BaseModel):
    pass
