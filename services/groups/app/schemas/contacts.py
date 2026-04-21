from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ContactBase(BaseModel):
    contact_user_id: str
    alias: Optional[str] = None

class ContactCreate(ContactBase):
    pass

class ContactResponse(ContactBase):
    owner_id: str
    created_at: datetime

    class Config:
        from_attributes = True
