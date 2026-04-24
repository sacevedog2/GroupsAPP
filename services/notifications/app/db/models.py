from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "source_event_id",
            "notification_type",
            name="uq_notifications_user_event_type",
        ),
        Index(
            "ix_notifications_user_unread_created",
            "user_id",
            "is_read",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    source_service: Mapped[str] = mapped_column(String(40), nullable=False)
    source_event_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scope_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scope_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
