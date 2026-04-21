from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# --- Members ---
class GroupMemberBase(BaseModel):
    user_id: str
    role: str = "member"

class GroupMemberCreate(GroupMemberBase):
    pass

class GroupMemberResponse(GroupMemberBase):
    group_id: str
    joined_at: datetime
    
    class Config:
        from_attributes = True

# --- Channels ---
class ChannelBase(BaseModel):
    name: str

class ChannelCreate(ChannelBase):
    pass

class ChannelResponse(ChannelBase):
    id: str
    group_id: str
    created_at: datetime

    class Config:
        from_attributes = True

# --- Groups ---
class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict)

class GroupCreate(GroupBase):
    pass

class GroupResponse(GroupBase):
    id: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class GroupDetailResponse(GroupResponse):
    members: List[GroupMemberResponse] = []
    channels: List[ChannelResponse] = []
