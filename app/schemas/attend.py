from pydantic import BaseModel


class AttendCreate(BaseModel):
    pass


class AttendUpdate(BaseModel):
    pass


class AttendResponse(AttendCreate):
    pass


class AttendItem(BaseModel):
    pass


class AttendBulkCreate(BaseModel):
    pass
