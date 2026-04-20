from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Attachment, Message, MessageAttachment, MessageReceipt
from app.domain.enums import ReceiptStatus, STATUS_RANK, ScopeType
from app.schemas.events import DomainEvent
from app.schemas.messaging import MessageCreateRequest, ReceiptUpdateRequest
from app.services.event_publisher import EventPublisher
from app.services.storage import StorageService


class MessagingService:
    def __init__(
        self,
        session: AsyncSession,
        event_publisher: EventPublisher,
        storage: StorageService,
    ) -> None:
        self.session = session
        self.event_publisher = event_publisher
        self.storage = storage

    async def create_attachment(
        self,
        uploader_id: str,
        scope_type: ScopeType,
        scope_id: str,
        upload: UploadFile,
    ) -> Attachment:
        stored = await self.storage.save_upload(upload)
        attachment = Attachment(
            id=str(uuid4()),
            uploader_id=uploader_id,
            scope_type=scope_type,
            scope_id=scope_id,
            original_filename=stored.original_filename,
            stored_filename=stored.stored_filename,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            checksum_sha256=stored.checksum_sha256,
            storage_path=stored.storage_path,
        )
        self.session.add(attachment)
        await self.session.commit()
        await self.session.refresh(attachment)

        await self.event_publisher.publish(
            DomainEvent(
                id=str(uuid4()),
                event_type="attachment.uploaded",
                scope_type=scope_type,
                scope_id=scope_id,
                payload={
                    "attachment_id": attachment.id,
                    "uploader_id": uploader_id,
                    "content_type": attachment.content_type,
                    "size_bytes": attachment.size_bytes,
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        return attachment

    async def get_attachment(self, attachment_id: str) -> Attachment:
        attachment = await self.session.get(Attachment, attachment_id)
        if attachment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Attachment '{attachment_id}' no existe.",
            )
        return attachment

    async def create_message(self, payload: MessageCreateRequest) -> Message:
        attachments: list[Attachment] = []
        if payload.attachment_ids:
            stmt = select(Attachment).where(Attachment.id.in_(payload.attachment_ids))
            attachments = list((await self.session.scalars(stmt)).all())
            found_ids = {attachment.id for attachment in attachments}
            missing_ids = [item for item in payload.attachment_ids if item not in found_ids]
            if missing_ids:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Attachments no encontrados: {missing_ids}",
                )
            for attachment in attachments:
                if (
                    attachment.scope_type != payload.scope_type
                    or attachment.scope_id != payload.scope_id
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Attachment fuera de contexto: scope_type/scope_id "
                            "debe coincidir con el mensaje."
                        ),
                    )

        message = Message(
            id=str(uuid4()),
            sender_id=payload.sender_id,
            scope_type=payload.scope_type,
            scope_id=payload.scope_id,
            body=payload.body,
        )
        self.session.add(message)

        for attachment in attachments:
            self.session.add(
                MessageAttachment(message_id=message.id, attachment_id=attachment.id)
            )

        participants = set(payload.participant_ids)
        participants.add(payload.sender_id)

        now = datetime.now(timezone.utc)
        for participant in participants:
            if participant == payload.sender_id:
                status_value = ReceiptStatus.READ
                receipt = MessageReceipt(
                    message_id=message.id,
                    user_id=participant,
                    status=status_value,
                    sent_at=now,
                    delivered_at=now,
                    read_at=now,
                    updated_at=now,
                )
            else:
                status_value = ReceiptStatus.SENT
                receipt = MessageReceipt(
                    message_id=message.id,
                    user_id=participant,
                    status=status_value,
                    sent_at=now,
                    delivered_at=None,
                    read_at=None,
                    updated_at=now,
                )
            self.session.add(receipt)

        await self.session.commit()
        message = await self.get_message(message.id)

        await self.event_publisher.publish(
            DomainEvent(
                id=str(uuid4()),
                event_type="message.created",
                scope_type=payload.scope_type,
                scope_id=payload.scope_id,
                payload={
                    "message_id": message.id,
                    "sender_id": message.sender_id,
                    "participant_ids": sorted(participants),
                    "attachment_ids": [item.id for item in message.attachments],
                    "has_text": bool(message.body),
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        return message

    async def get_message(self, message_id: str) -> Message:
        stmt = (
            select(Message)
            .where(Message.id == message_id)
            .options(
                selectinload(Message.attachments),
                selectinload(Message.receipts),
            )
        )
        message = (await self.session.execute(stmt)).scalar_one_or_none()
        if message is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message '{message_id}' no existe.",
            )
        return message

    async def list_messages(
        self,
        scope_type: ScopeType,
        scope_id: str,
        limit: int = 50,
        before: datetime | None = None,
    ) -> list[Message]:
        normalized_limit = max(1, min(limit, 200))

        stmt: Select[tuple[Message]] = (
            select(Message)
            .where(Message.scope_type == scope_type, Message.scope_id == scope_id)
            .options(
                selectinload(Message.attachments),
                selectinload(Message.receipts),
            )
            .order_by(desc(Message.created_at))
            .limit(normalized_limit)
        )
        if before is not None:
            stmt = stmt.where(Message.created_at < before)

        return list((await self.session.scalars(stmt)).all())

    async def update_receipt(
        self, message_id: str, payload: ReceiptUpdateRequest
    ) -> MessageReceipt:
        message = await self.get_message(message_id)
        receipt = await self.session.get(
            MessageReceipt,
            {"message_id": message_id, "user_id": payload.user_id},
        )
        now = datetime.now(timezone.utc)

        if receipt is None:
            receipt = MessageReceipt(
                message_id=message_id,
                user_id=payload.user_id,
                status=ReceiptStatus.SENT,
                sent_at=message.created_at,
                delivered_at=None,
                read_at=None,
                updated_at=now,
            )
            self.session.add(receipt)

        current_rank = STATUS_RANK[receipt.status]
        requested_rank = STATUS_RANK[payload.status]
        if requested_rank < current_rank:
            return receipt

        if requested_rank == current_rank:
            return receipt

        if payload.status == ReceiptStatus.DELIVERED:
            receipt.status = ReceiptStatus.DELIVERED
            receipt.delivered_at = receipt.delivered_at or now
        elif payload.status == ReceiptStatus.READ:
            receipt.status = ReceiptStatus.READ
            receipt.delivered_at = receipt.delivered_at or now
            receipt.read_at = now

        receipt.updated_at = now
        await self.session.commit()
        await self.session.refresh(receipt)

        await self.event_publisher.publish(
            DomainEvent(
                id=str(uuid4()),
                event_type="receipt.updated",
                scope_type=message.scope_type,
                scope_id=message.scope_id,
                payload={
                    "message_id": message_id,
                    "user_id": payload.user_id,
                    "status": receipt.status.value,
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        return receipt
