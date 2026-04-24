from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    id: str
    user_id: str
    notification_type: str
    title: str
    body: str
    source_service: str
    source_event_id: str
    scope_type: str | None = None
    scope_id: str | None = None
    actor_user_id: str | None = None
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    count: int
    unread_count: int


class MarkReadRequest(BaseModel):
    notification_ids: list[str] = Field(default_factory=list)
