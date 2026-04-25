from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import DirectRequestStatus, ReceiptStatus, ScopeType


class AttachmentOut(BaseModel):
    id: str
    uploader_id: str
    scope_type: ScopeType
    scope_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageReceiptOut(BaseModel):
    message_id: str
    user_id: str
    status: ReceiptStatus
    sent_at: datetime
    delivered_at: datetime | None = None
    read_at: datetime | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageOut(BaseModel):
    id: str
    sender_id: str
    scope_type: ScopeType
    scope_id: str
    body: str | None = None
    created_at: datetime
    attachments: list[AttachmentOut] = Field(default_factory=list)
    receipts: list[MessageReceiptOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class MessageListOut(BaseModel):
    items: list[MessageOut]
    count: int


class MessageCreateRequest(BaseModel):
    sender_id: str = Field(min_length=1, max_length=64)
    scope_type: ScopeType
    scope_id: str | None = Field(default=None, min_length=1, max_length=64)
    body: str | None = Field(default=None, max_length=8000)
    attachment_ids: list[str] = Field(default_factory=list)
    participant_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_payload(self) -> MessageCreateRequest:
        normalized_body = (self.body or "").strip()
        if not normalized_body and not self.attachment_ids:
            raise ValueError("Debes enviar texto o al menos un attachment.")
        self.body = normalized_body or None

        unique_attachment_ids = list(dict.fromkeys(self.attachment_ids))
        self.attachment_ids = unique_attachment_ids

        unique_participants = list(dict.fromkeys(self.participant_ids))
        self.participant_ids = unique_participants

        if self.scope_type == ScopeType.DIRECT:
            members = set(unique_participants)
            members.add(self.sender_id)
            if len(members) != 2:
                raise ValueError(
                    "Un mensaje direct debe involucrar exactamente dos usuarios."
                )
        elif not self.scope_id:
            raise ValueError("scope_id es obligatorio para mensajes que no son direct.")
        return self


class DirectConversationStartRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    peer_user_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_users(self) -> DirectConversationStartRequest:
        self.user_id = self.user_id.strip().lower()
        self.peer_user_id = self.peer_user_id.strip().lower()
        if self.user_id == self.peer_user_id:
            raise ValueError("No puedes iniciar una conversacion directa contigo mismo.")
        return self


class DirectConversationSummaryOut(BaseModel):
    scope_id: str
    user_id: str
    peer_user_id: str
    request_status: DirectRequestStatus = DirectRequestStatus.ACCEPTED
    requester_user_id: str | None = None
    can_send: bool = True
    last_message: MessageOut | None = None
    unread_count: int = 0
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DirectConversationListOut(BaseModel):
    items: list[DirectConversationSummaryOut]
    count: int


class DirectConversationAcceptRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def normalize_user(self) -> DirectConversationAcceptRequest:
        self.user_id = self.user_id.strip().lower()
        return self


class ReceiptUpdateRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    status: ReceiptStatus

    @model_validator(mode="after")
    def validate_status(self) -> ReceiptUpdateRequest:
        if self.status == ReceiptStatus.SENT:
            raise ValueError("No se permite regresar el estado a 'sent'.")
        return self
