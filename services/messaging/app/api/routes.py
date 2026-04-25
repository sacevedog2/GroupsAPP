from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.domain.enums import ScopeType
from app.schemas.messaging import (
    AttachmentOut,
    DirectConversationAcceptRequest,
    DirectConversationListOut,
    DirectConversationStartRequest,
    DirectConversationSummaryOut,
    MessageCreateRequest,
    MessageListOut,
    MessageOut,
    MessageReceiptOut,
    ReceiptUpdateRequest,
)
from app.services.messaging_service import MessagingService

router = APIRouter(prefix="/v1", tags=["messaging"])


def get_messaging_service(
    request: Request, db: AsyncSession = Depends(get_db)
) -> MessagingService:
    return MessagingService(
        session=db,
        event_publisher=request.app.state.event_publisher,
        storage=request.app.state.storage_service,
    )


@router.post(
    "/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    uploader_id: str = Form(..., min_length=1, max_length=64),
    scope_type: ScopeType = Form(...),
    scope_id: str = Form(..., min_length=1, max_length=64),
    file: UploadFile = File(...),
    service: MessagingService = Depends(get_messaging_service),
) -> AttachmentOut:
    attachment = await service.create_attachment(
        uploader_id=uploader_id,
        scope_type=scope_type,
        scope_id=scope_id,
        upload=file,
    )
    return AttachmentOut.model_validate(attachment)


@router.get("/attachments/{attachment_id}", response_model=AttachmentOut)
async def get_attachment_metadata(
    attachment_id: str,
    service: MessagingService = Depends(get_messaging_service),
) -> AttachmentOut:
    attachment = await service.get_attachment(attachment_id)
    return AttachmentOut.model_validate(attachment)


@router.get("/attachments/{attachment_id}/content")
async def get_attachment_content(
    attachment_id: str,
    service: MessagingService = Depends(get_messaging_service),
) -> FileResponse:
    attachment = await service.get_attachment(attachment_id)
    file_path = Path(attachment.storage_path)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Archivo para attachment '{attachment_id}' no encontrado.",
        )
    return FileResponse(
        path=file_path,
        media_type=attachment.content_type,
        filename=attachment.original_filename,
    )


@router.post("/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def create_message(
    payload: MessageCreateRequest,
    service: MessagingService = Depends(get_messaging_service),
) -> MessageOut:
    message = await service.create_message(payload)
    return MessageOut.model_validate(message)


@router.get("/messages/{message_id}", response_model=MessageOut)
async def get_message(
    message_id: str,
    service: MessagingService = Depends(get_messaging_service),
) -> MessageOut:
    message = await service.get_message(message_id)
    return MessageOut.model_validate(message)


@router.get("/messages", response_model=MessageListOut)
async def list_messages(
    scope_type: ScopeType,
    scope_id: str,
    limit: int = 50,
    before: datetime | None = None,
    service: MessagingService = Depends(get_messaging_service),
) -> MessageListOut:
    items = await service.list_messages(
        scope_type=scope_type,
        scope_id=scope_id,
        limit=limit,
        before=before,
    )
    response_items = [MessageOut.model_validate(item) for item in items]
    return MessageListOut(items=response_items, count=len(response_items))


@router.post(
    "/direct-conversations",
    response_model=DirectConversationSummaryOut,
    status_code=status.HTTP_200_OK,
)
async def get_direct_conversation(
    payload: DirectConversationStartRequest,
    service: MessagingService = Depends(get_messaging_service),
) -> DirectConversationSummaryOut:
    conversation = await service.get_direct_conversation(payload)
    return DirectConversationSummaryOut.model_validate(conversation)


@router.post(
    "/direct-conversations/{scope_id}/accept",
    response_model=DirectConversationSummaryOut,
    status_code=status.HTTP_200_OK,
)
async def accept_direct_conversation(
    scope_id: str,
    payload: DirectConversationAcceptRequest,
    service: MessagingService = Depends(get_messaging_service),
) -> DirectConversationSummaryOut:
    conversation = await service.accept_direct_conversation(
        scope_id=scope_id,
        user_id=payload.user_id,
    )
    return DirectConversationSummaryOut.model_validate(conversation)


@router.get(
    "/direct-conversations",
    response_model=DirectConversationListOut,
    status_code=status.HTTP_200_OK,
)
async def list_direct_conversations(
    user_id: str,
    service: MessagingService = Depends(get_messaging_service),
) -> DirectConversationListOut:
    items = await service.list_direct_conversations(user_id)
    return DirectConversationListOut(
        items=[DirectConversationSummaryOut.model_validate(item) for item in items],
        count=len(items),
    )


@router.post(
    "/messages/{message_id}/receipts",
    response_model=MessageReceiptOut,
    status_code=status.HTTP_200_OK,
)
async def update_receipt(
    message_id: str,
    payload: ReceiptUpdateRequest,
    service: MessagingService = Depends(get_messaging_service),
) -> MessageReceiptOut:
    receipt = await service.update_receipt(message_id=message_id, payload=payload)
    return MessageReceiptOut.model_validate(receipt)
