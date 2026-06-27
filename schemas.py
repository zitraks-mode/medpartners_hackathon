from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class DocumentStatusResponse(BaseModel):
    status: str
    items_extracted: int
    log: Optional[str]

    class Config:
        from_attributes = True