from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.events import DomainEvent
from app.services.event_publisher import EventPublisher
from app.services.password_hasher import PasswordHasher
from app.services.token_service import TokenService, TokenValidationError


@dataclass(slots=True)
class AuthResult:
    user: User
    access_token: str
    expires_in: int


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        event_publisher: EventPublisher,
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self.session = session
        self.event_publisher = event_publisher
        self.password_hasher = password_hasher
        self.token_service = token_service

    def _build_user_id_candidates(self, email: str) -> list[str]:
        local_part = email.split("@", maxsplit=1)[0].strip().lower()
        normalized = re.sub(r"[^a-z0-9_.-]+", "-", local_part)
        normalized = re.sub(r"[-_.]{2,}", "-", normalized).strip("-_.")

        if len(normalized) < 3:
            normalized = f"user-{normalized}".strip("-")
        if len(normalized) < 3:
            normalized = "user"

        base = normalized[:32]
        candidates = [base]
        for suffix in range(1, 1000):
            suffix_text = str(suffix)
            prefix = base[: 32 - len(suffix_text) - 1].rstrip("-_.") or "user"
            candidates.append(f"{prefix}-{suffix_text}")
        return candidates

    async def _generate_available_user_id(self, email: str) -> str:
        candidates = self._build_user_id_candidates(email)
        stmt = select(User.user_id).where(User.user_id.in_(candidates))
        existing_ids = set((await self.session.scalars(stmt)).all())

        for candidate in candidates:
            if candidate not in existing_ids:
                return candidate

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar un user_id disponible.",
        )

    async def register(self, payload: RegisterRequest) -> AuthResult:
        resolved_user_id = payload.user_id or await self._generate_available_user_id(
            payload.email
        )
        stmt = select(User).where(
            or_(User.user_id == resolved_user_id, User.email == payload.email)
        )
        existing_users = list((await self.session.scalars(stmt)).all())

        if any(user.user_id == resolved_user_id for user in existing_users):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El user_id ya existe.",
            )
        if any(user.email == payload.email for user in existing_users):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El email ya existe.",
            )

        user = User(
            user_id=resolved_user_id,
            email=payload.email,
            display_name=payload.display_name or resolved_user_id,
            password_hash=self.password_hasher.hash_password(payload.password),
            is_active=True,
        )

        self.session.add(user)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El user_id o email ya existe.",
            ) from exc
        await self.session.refresh(user)

        access_token, expires_in = self.token_service.issue_access_token(
            user_id=user.user_id,
            email=user.email,
        )

        await self.event_publisher.publish(
            DomainEvent(
                id=str(uuid4()),
                event_type="user.registered",
                subject_type="user",
                subject_id=user.user_id,
                payload={
                    "user_id": user.user_id,
                    "email": user.email,
                },
                created_at=datetime.now(timezone.utc),
            )
        )

        return AuthResult(user=user, access_token=access_token, expires_in=expires_in)

    async def login(self, payload: LoginRequest) -> AuthResult:
        stmt = select(User).where(
            or_(User.user_id == payload.identifier, User.email == payload.identifier)
        )
        user = (await self.session.execute(stmt)).scalar_one_or_none()

        if user is None or not self.password_hasher.verify_password(
            payload.password, user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales invalidas.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario inactivo.",
            )

        user.last_login_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(user)

        access_token, expires_in = self.token_service.issue_access_token(
            user_id=user.user_id,
            email=user.email,
        )

        await self.event_publisher.publish(
            DomainEvent(
                id=str(uuid4()),
                event_type="user.logged_in",
                subject_type="user",
                subject_id=user.user_id,
                payload={
                    "user_id": user.user_id,
                },
                created_at=datetime.now(timezone.utc),
            )
        )

        return AuthResult(user=user, access_token=access_token, expires_in=expires_in)

    async def get_current_user(self, access_token: str) -> tuple[User, int]:
        try:
            claims, expires_at_epoch_ms = self.token_service.validate_access_token(
                access_token
            )
        except TokenValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        user = await self.session.get(User, claims.sub)
        if user is None or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuario no valido para el token.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user, expires_at_epoch_ms

    async def get_user_by_id(self, user_id: str) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' no existe.",
            )
        return user

    async def get_public_user_by_id(self, user_id: str) -> User:
        user = await self.get_user_by_id(user_id)
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{user_id}' no existe.",
            )
        return user

    async def update_presence(self, user_id: str, is_online: bool) -> User:
        user = await self.get_user_by_id(user_id)
        user.is_online = is_online
        
        await self.session.commit()
        await self.session.refresh(user)

        await self.event_publisher.publish(
            DomainEvent(
                id=str(uuid4()),
                event_type="user.presence_changed",
                subject_type="user",
                subject_id=user.user_id,
                payload={
                    "user_id": user.user_id,
                    "is_online": user.is_online,
                },
                created_at=datetime.now(timezone.utc),
            )
        )
        return user
