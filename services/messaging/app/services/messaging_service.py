from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import Select, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    Attachment,
    DirectConversation,
    DirectConversationParticipant,
    DirectConversationRequest,
    Message,
    MessageAttachment,
    MessageReceipt,
)
from app.domain.enums import DirectRequestStatus, ReceiptStatus, STATUS_RANK, ScopeType
from app.schemas.events import DomainEvent
from app.schemas.messaging import (
    DirectConversationStartRequest,
    MessageCreateRequest,
    ReceiptUpdateRequest,
)
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

    @staticmethod
    def build_direct_scope_id(user_a: str, user_b: str) -> str:
        normalized = ":".join(sorted([user_a.strip().lower(), user_b.strip().lower()]))
        digest = sha256(normalized.encode("utf-8")).hexdigest()
        return f"dm_{digest[:40]}"

    async def ensure_direct_conversation(
        self, user_a: str, user_b: str
    ) -> DirectConversation:
        normalized_a = user_a.strip().lower()
        normalized_b = user_b.strip().lower()
        scope_id = self.build_direct_scope_id(normalized_a, normalized_b)

        conversation = await self.session.get(DirectConversation, scope_id)
        if conversation is not None:
            return conversation

        now = datetime.now(timezone.utc)
        conversation = DirectConversation(
            scope_id=scope_id,
            created_at=now,
            updated_at=now,
        )
        self.session.add(conversation)
        self.session.add_all(
            [
                DirectConversationParticipant(
                    scope_id=scope_id,
                    user_id=normalized_a,
                    joined_at=now,
                ),
                DirectConversationParticipant(
                    scope_id=scope_id,
                    user_id=normalized_b,
                    joined_at=now,
                ),
            ]
        )
        await self.session.commit()
        return await self.get_direct_conversation_record(scope_id)

    async def ensure_direct_conversation_request(
        self, requester_id: str, recipient_id: str
    ) -> tuple[DirectConversation, DirectConversationRequest]:
        normalized_requester = requester_id.strip().lower()
        normalized_recipient = recipient_id.strip().lower()
        conversation = await self.ensure_direct_conversation(
            normalized_requester, normalized_recipient
        )
        existing_request = await self.session.get(
            DirectConversationRequest, conversation.scope_id
        )
        if existing_request is not None:
            return conversation, existing_request

        request = DirectConversationRequest(
            scope_id=conversation.scope_id,
            requester_id=normalized_requester,
            recipient_id=normalized_recipient,
            status=DirectRequestStatus.PENDING,
        )
        self.session.add(request)
        await self.session.commit()
        await self.session.refresh(request)

        await self.event_publisher.publish(
            DomainEvent(
                id=str(uuid4()),
                event_type="direct_conversation.requested",
                scope_type=ScopeType.DIRECT,
                scope_id=conversation.scope_id,
                payload={
                    "scope_id": conversation.scope_id,
                    "user_id": normalized_requester,
                    "peer_user_id": normalized_recipient,
                    "actor_user_id": normalized_requester,
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        return conversation, request

    async def accept_direct_conversation(
        self, scope_id: str, user_id: str
    ) -> dict[str, object]:
        normalized_user_id = user_id.strip().lower()
        conversation = await self.get_direct_conversation_record(scope_id)
        request = await self.session.get(DirectConversationRequest, scope_id)
        if request is None:
            return await self._build_direct_conversation_summary(
                conversation=conversation,
                user_id=normalized_user_id,
                request=None,
            )

        if request.recipient_id != normalized_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el destinatario puede aceptar esta solicitud de chat.",
            )

        if request.status != DirectRequestStatus.ACCEPTED:
            now = datetime.now(timezone.utc)
            request.status = DirectRequestStatus.ACCEPTED
            request.accepted_at = now
            request.updated_at = now
            conversation.updated_at = now
            await self.session.commit()
            await self.session.refresh(request)
            conversation = await self.get_direct_conversation_record(scope_id)

            await self.event_publisher.publish(
                DomainEvent(
                    id=str(uuid4()),
                    event_type="direct_conversation.started",
                    scope_type=ScopeType.DIRECT,
                    scope_id=scope_id,
                    payload={
                        "scope_id": scope_id,
                        "user_id": request.requester_id,
                        "peer_user_id": request.recipient_id,
                        "actor_user_id": normalized_user_id,
                    },
                    created_at=datetime.now(timezone.utc),
                )
            )

        return await self._build_direct_conversation_summary(
            conversation=conversation,
            user_id=normalized_user_id,
            request=request,
        )

    async def get_direct_conversation_record(
        self, scope_id: str
    ) -> DirectConversation:
        stmt = (
            select(DirectConversation)
            .where(DirectConversation.scope_id == scope_id)
            .options(
                selectinload(DirectConversation.participants),
                selectinload(DirectConversation.request),
            )
        )
        conversation = (await self.session.execute(stmt)).scalar_one_or_none()
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversacion '{scope_id}' no existe.",
            )
        return conversation

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

        participants = set(payload.participant_ids)
        participants.add(payload.sender_id)

        scope_id = payload.scope_id
        if payload.scope_type == ScopeType.DIRECT:
            if len(participants) != 2:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Un mensaje direct debe involucrar exactamente dos usuarios.",
                )
            peer_user_id = next(
                participant
                for participant in participants
                if participant != payload.sender_id
            )
            scope_id = self.build_direct_scope_id(payload.sender_id, peer_user_id)
            conversation = await self.get_direct_conversation_record(scope_id)
            request = conversation.request
            if request is not None and request.status != DirectRequestStatus.ACCEPTED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        "La solicitud de chat directo debe ser aceptada antes "
                        "de enviar mensajes."
                    ),
                )
            scope_id = conversation.scope_id
        elif not scope_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="scope_id es obligatorio para mensajes que no son direct.",
            )

        for attachment in attachments:
            if attachment.scope_type != payload.scope_type or attachment.scope_id != scope_id:
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
            scope_id=scope_id,
            body=payload.body,
        )
        self.session.add(message)

        for attachment in attachments:
            self.session.add(
                MessageAttachment(message_id=message.id, attachment_id=attachment.id)
            )

        now = datetime.now(timezone.utc)
        if payload.scope_type == ScopeType.DIRECT:
            conversation.updated_at = now

        for participant in participants:
            if participant == payload.sender_id:
                receipt = MessageReceipt(
                    message_id=message.id,
                    user_id=participant,
                    status=ReceiptStatus.READ,
                    sent_at=now,
                    delivered_at=now,
                    read_at=now,
                    updated_at=now,
                )
            else:
                receipt = MessageReceipt(
                    message_id=message.id,
                    user_id=participant,
                    status=ReceiptStatus.SENT,
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
                scope_id=scope_id,
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

    async def get_direct_conversation(
        self, payload: DirectConversationStartRequest
    ) -> dict[str, object]:
        conversation, request = await self.ensure_direct_conversation_request(
            payload.user_id, payload.peer_user_id
        )
        return await self._build_direct_conversation_summary(
            conversation=conversation,
            user_id=payload.user_id,
            request=request,
        )

    async def list_direct_conversations(self, user_id: str) -> list[dict[str, object]]:
        normalized_user_id = user_id.strip().lower()
        stmt = (
            select(DirectConversation)
            .join(
                DirectConversationParticipant,
                DirectConversationParticipant.scope_id == DirectConversation.scope_id,
            )
            .where(
                DirectConversationParticipant.user_id == normalized_user_id,
            )
            .options(selectinload(DirectConversation.participants))
            .options(selectinload(DirectConversation.request))
            .order_by(desc(DirectConversation.updated_at))
        )

        conversations_db = list((await self.session.scalars(stmt)).unique().all())
        conversations: list[dict[str, object]] = []
        for conversation in conversations_db:
            conversations.append(
                await self._build_direct_conversation_summary(
                    conversation=conversation,
                    user_id=normalized_user_id,
                    request=conversation.request,
                )
            )

        return conversations

    async def _build_direct_conversation_summary(
        self,
        conversation: DirectConversation,
        user_id: str,
        request: DirectConversationRequest | None,
    ) -> dict[str, object]:
        normalized_user_id = user_id.strip().lower()
        peer_user_id = self._extract_peer_user_id_from_conversation(
            conversation, normalized_user_id
        )
        last_message = await self._get_latest_message_for_scope(
            scope_type=ScopeType.DIRECT,
            scope_id=conversation.scope_id,
        )
        unread_count = await self._count_unread_messages(
            scope_id=conversation.scope_id,
            user_id=normalized_user_id,
        )
        request_status = (
            request.status if request is not None else DirectRequestStatus.ACCEPTED
        )
        requester_id = request.requester_id if request is not None else None
        updated_at = last_message.created_at if last_message is not None else None
        return {
            "scope_id": conversation.scope_id,
            "user_id": normalized_user_id,
            "peer_user_id": peer_user_id,
            "request_status": request_status,
            "requester_user_id": requester_id,
            "can_send": request_status == DirectRequestStatus.ACCEPTED,
            "last_message": last_message,
            "unread_count": unread_count,
            "updated_at": updated_at or conversation.updated_at,
        }

    async def _get_latest_message_for_scope(
        self, scope_type: ScopeType, scope_id: str
    ) -> Message | None:
        stmt = (
            select(Message)
            .where(Message.scope_type == scope_type, Message.scope_id == scope_id)
            .options(
                selectinload(Message.attachments),
                selectinload(Message.receipts),
            )
            .order_by(desc(Message.created_at))
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _count_unread_messages(self, scope_id: str, user_id: str) -> int:
        stmt = (
            select(Message)
            .join(
                MessageReceipt,
                MessageReceipt.message_id == Message.id,
            )
            .where(
                Message.scope_type == ScopeType.DIRECT,
                Message.scope_id == scope_id,
                Message.sender_id != user_id,
                MessageReceipt.user_id == user_id,
                MessageReceipt.status != ReceiptStatus.READ,
            )
        )
        unread_messages = list((await self.session.scalars(stmt)).all())
        return len(unread_messages)

    def _extract_peer_user_id_from_conversation(
        self, conversation: DirectConversation, user_id: str
    ) -> str:
        for participant in conversation.participants:
            if participant.user_id != user_id:
                return participant.user_id
        return user_id

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
        if requested_rank <= current_rank:
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
