from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    id: str
    event_type: str
    subject_type: str
    subject_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
