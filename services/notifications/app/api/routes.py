from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas import MarkReadRequest, NotificationListOut, NotificationOut
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


def get_notification_service(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> NotificationService:
    return NotificationService(
        session=db,
    )


@router.get("", response_model=NotificationListOut, status_code=status.HTTP_200_OK)
async def list_notifications(
    user_id: str,
    unread_only: bool = False,
    limit: int = 30,
    service: NotificationService = Depends(get_notification_service),
) -> NotificationListOut:
    items, unread_count = await service.list_for_user(
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
    )
    return NotificationListOut(
        items=[NotificationOut.model_validate(item) for item in items],
        count=len(items),
        unread_count=unread_count,
    )


@router.post("/read", status_code=status.HTTP_200_OK)
async def mark_read(
    payload: MarkReadRequest,
    user_id: str,
    scope_type: str | None = None,
    scope_id: str | None = None,
    service: NotificationService = Depends(get_notification_service),
) -> dict[str, int]:
    count = await service.mark_read(
        user_id=user_id,
        notification_ids=payload.notification_ids,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    return {"updated": count}
