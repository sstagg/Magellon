from pydantic import BaseModel, Field
from typing import Optional, List
import uuid


class CameraDto(BaseModel):
    Oid: uuid.UUID = Field(description='Camera UUID')
    name: str = Field(min_length=2, max_length=30, description='Camera Name')
    optimistic_lock_field: Optional[int] = Field(None, description='lock')
    gcrecord: Optional[int] = Field(None, description='gc')

    class Config:
        orm_mode = True
