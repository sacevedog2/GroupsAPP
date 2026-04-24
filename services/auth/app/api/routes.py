from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.auth import (
    AccessTokenOut,
    AuthResponse,
    LoginRequest,
    PublicUserOut,
    RegisterRequest,
    TokenIntrospectionOut,
    UserOut,
    PresenceUpdateRequest,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/v1/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


def get_auth_service(request: Request, db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(
        session=db,
        event_publisher=request.app.state.event_publisher,
        password_hasher=request.app.state.password_hasher,
        token_service=request.app.state.token_service,
    )


def get_bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Se requiere un Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    result = await service.register(payload)
    return AuthResponse(
        user=UserOut.model_validate(result.user),
        token=AccessTokenOut(access_token=result.access_token, expires_in=result.expires_in),
    )


@router.post("/login", response_model=AuthResponse, status_code=status.HTTP_200_OK)
async def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    result = await service.login(payload)
    return AuthResponse(
        user=UserOut.model_validate(result.user),
        token=AccessTokenOut(access_token=result.access_token, expires_in=result.expires_in),
    )


@router.get("/me", response_model=UserOut, status_code=status.HTTP_200_OK)
async def me(
    access_token: str = Depends(get_bearer_token),
    service: AuthService = Depends(get_auth_service),
) -> UserOut:
    user, _ = await service.get_current_user(access_token)
    return UserOut.model_validate(user)


@router.get("/users/{user_id}", response_model=PublicUserOut, status_code=status.HTTP_200_OK)
async def get_user_by_id(
    user_id: str,
    access_token: str = Depends(get_bearer_token),
    service: AuthService = Depends(get_auth_service),
) -> PublicUserOut:
    await service.get_current_user(access_token)
    user = await service.get_public_user_by_id(user_id.strip().lower())
    return PublicUserOut.model_validate(user)


@router.post("/introspect", response_model=TokenIntrospectionOut)
async def introspect_token(
    access_token: str = Depends(get_bearer_token),
    service: AuthService = Depends(get_auth_service),
) -> TokenIntrospectionOut:
    try:
        user, expires_at_epoch_ms = await service.get_current_user(access_token)
    except HTTPException as exc:
        return TokenIntrospectionOut(valid=False, reason=str(exc.detail))

    return TokenIntrospectionOut(
        valid=True,
        user=UserOut.model_validate(user),
        expires_at_epoch_ms=expires_at_epoch_ms,
    )

@router.post("/presence", response_model=UserOut, status_code=status.HTTP_200_OK)
async def update_presence(
    payload: PresenceUpdateRequest,
    access_token: str = Depends(get_bearer_token),
    service: AuthService = Depends(get_auth_service),
) -> UserOut:
    user, _ = await service.get_current_user(access_token)
    updated_user = await service.update_presence(user.user_id, payload.is_online)
    return UserOut.model_validate(updated_user)
