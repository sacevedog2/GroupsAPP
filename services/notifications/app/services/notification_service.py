from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import desc, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Notification


class NotificationService:
    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self.session = session

    async def list_for_user(
        self,
        user_id: str,
        unread_only: bool = False,
        limit: int = 30,
    ) -> tuple[list[Notification], int]:
        normalized_limit = max(1, min(limit, 100))
        normalized_user_id = user_id.strip().lower()

        stmt = (
            select(Notification)
            .where(Notification.user_id == normalized_user_id)
            .order_by(Notification.is_read.asc(), desc(Notification.created_at))
            .limit(normalized_limit)
        )
        if unread_only:
            stmt = stmt.where(Notification.is_read.is_(False))

        count_stmt = select(func.count()).select_from(Notification).where(
            Notification.user_id == normalized_user_id,
            Notification.is_read.is_(False),
        )
        items = list((await self.session.scalars(stmt)).all())
        unread_count = int((await self.session.execute(count_stmt)).scalar_one())
        return items, unread_count

    async def mark_read(
        self,
        user_id: str,
        notification_ids: list[str] | None = None,
        scope_type: str | None = None,
        scope_id: str | None = None,
    ) -> int:
        normalized_user_id = user_id.strip().lower()
        stmt = update(Notification).where(
            Notification.user_id == normalized_user_id,
            Notification.is_read.is_(False),
        )
        if notification_ids:
            stmt = stmt.where(Notification.id.in_(notification_ids))
        if scope_type and scope_id:
            stmt = stmt.where(
                Notification.scope_type == scope_type,
                Notification.scope_id == scope_id,
            )

        result = await self.session.execute(
            stmt.values(is_read=True, read_at=datetime.now(timezone.utc))
        )
        await self.session.commit()
        return int(result.rowcount or 0)

    async def notify_unread_message(self, event: dict) -> None:
        payload = event.get("payload") or {}
        sender_id = str(payload.get("sender_id") or "").strip().lower()
        participant_ids = [
            str(item).strip().lower()
            for item in payload.get("participant_ids", [])
            if str(item).strip()
        ]

        for user_id in sorted(set(participant_ids)):
            if not user_id or user_id == sender_id:
                continue
            await self._create_notification(
                user_id=user_id,
                notification_type="unread_message",
                title="Nuevo mensaje",
                body=f"Tienes un mensaje nuevo de @{sender_id}.",
                source_service="messaging",
                source_event_id=str(event.get("id") or uuid4()),
                scope_type=event.get("scope_type"),
                scope_id=event.get("scope_id"),
                actor_user_id=sender_id or None,
            )

    async def notify_direct_started(self, event: dict) -> None:
        payload = event.get("payload") or {}
        user_id = str(payload.get("user_id") or "").strip().lower()
        peer_user_id = str(payload.get("peer_user_id") or "").strip().lower()
        actor_user_id = str(payload.get("actor_user_id") or user_id).strip().lower()

        recipients = [item for item in [user_id, peer_user_id] if item and item != actor_user_id]
        for recipient_id in recipients:
            await self._create_notification(
                user_id=recipient_id,
                notification_type="direct_chat_started",
                title="Nuevo chat directo",
                body=f"@{actor_user_id} inicio un chat contigo.",
                source_service="messaging",
                source_event_id=str(event.get("id") or uuid4()),
                scope_type=event.get("scope_type") or "direct",
                scope_id=event.get("scope_id"),
                actor_user_id=actor_user_id,
            )

    async def notify_group_member_added(self, event: dict) -> None:
        payload = event.get("payload") or {}
        user_id = str(payload.get("user_id") or "").strip().lower()
        actor_user_id = str(payload.get("actor_user_id") or "").strip().lower()
        group_id = str(payload.get("group_id") or event.get("scope_id") or "").strip()

        if not user_id or user_id == actor_user_id:
            return

        await self._create_notification(
            user_id=user_id,
            notification_type="group_member_added",
            title="Te agregaron a un grupo",
            body=f"@{actor_user_id or 'un usuario'} te incluyo en un grupo.",
            source_service="groups",
            source_event_id=str(event.get("id") or uuid4()),
            scope_type="group",
            scope_id=group_id or None,
            actor_user_id=actor_user_id or None,
        )

    async def _create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str,
        source_service: str,
        source_event_id: str,
        scope_type: str | None,
        scope_id: str | None,
        actor_user_id: str | None,
    ) -> Notification | None:
        notification = Notification(
            id=str(uuid4()),
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            source_service=source_service,
            source_event_id=source_event_id,
            scope_type=scope_type,
            scope_id=scope_id,
            actor_user_id=actor_user_id,
        )
        self.session.add(notification)
        try:
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            return None

        await self.session.refresh(notification)
        return notification
