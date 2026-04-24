from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.domain.enums import ReceiptStatus, ScopeType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sender_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(ScopeType, native_enum=False, validate_strings=True),
        index=True,
        nullable=False,
    )
    scope_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment",
        secondary="message_attachments",
        back_populates="messages",
        lazy="selectin",
    )
    receipts: Mapped[list[MessageReceipt]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DirectConversation(Base):
    __tablename__ = "direct_conversations"

    scope_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )

    participants: Mapped[list[DirectConversationParticipant]] = relationship(
        "DirectConversationParticipant",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    uploader_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    scope_type: Mapped[ScopeType] = mapped_column(
        SAEnum(ScopeType, native_enum=False, validate_strings=True),
        index=True,
        nullable=False,
    )
    scope_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    messages: Mapped[list[Message]] = relationship(
        "Message",
        secondary="message_attachments",
        back_populates="attachments",
        lazy="selectin",
    )


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    attachment_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("attachments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class MessageReceipt(Base):
    __tablename__ = "message_receipts"

    message_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[ReceiptStatus] = mapped_column(
        SAEnum(ReceiptStatus, native_enum=False, validate_strings=True),
        nullable=False,
        default=ReceiptStatus.SENT,
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    message: Mapped[Message] = relationship(back_populates="receipts")


class DirectConversationParticipant(Base):
    __tablename__ = "direct_conversation_participants"

    scope_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("direct_conversations.scope_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    conversation: Mapped[DirectConversation] = relationship(
        "DirectConversation",
        back_populates="participants",
    )


Index(
    "ix_messages_scope_created_at",
    Message.scope_type,
    Message.scope_id,
    Message.created_at.desc(),
)
Index("ix_receipts_user", MessageReceipt.user_id)
Index("ix_direct_conversation_updated_at", DirectConversation.updated_at.desc())
Index("ix_direct_conversation_participant_user", DirectConversationParticipant.user_id)
