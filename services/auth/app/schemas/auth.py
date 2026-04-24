from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

USER_ID_PATTERN = re.compile(r"^[a-z0-9_.-]{3,32}$")


class UserOut(BaseModel):
    user_id: str
    email: str
    display_name: str | None = None
    is_active: bool
    is_online: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PublicUserOut(BaseModel):
    user_id: str
    display_name: str | None = None
    is_online: bool

    model_config = ConfigDict(from_attributes=True)


class PresenceUpdateRequest(BaseModel):
    is_online: bool


class AccessTokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AuthResponse(BaseModel):
    user: UserOut
    token: AccessTokenOut


class RegisterRequest(BaseModel):
    user_id: str | None = Field(default=None, min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not USER_ID_PATTERN.fullmatch(normalized):
            raise ValueError(
                "El user_id debe tener 3-32 caracteres y solo usar a-z, 0-9, _, ., -."
            )
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError(
                "La contrasena debe incluir al menos una letra y un numero."
            )
        return value

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        return value.strip().lower()


class TokenIntrospectionOut(BaseModel):
    valid: bool
    user: UserOut | None = None
    reason: str | None = None
    expires_at_epoch_ms: int | None = None


class AccessTokenClaims(BaseModel):
    sub: str
    user_id: str
    email: str
    iss: str
    iat: int
    exp: int
    jti: str

    @model_validator(mode="after")
    def validate_claims(self) -> AccessTokenClaims:
        if self.exp <= self.iat:
            raise ValueError("exp debe ser mayor que iat")
        if self.sub != self.user_id:
            raise ValueError("sub debe coincidir con user_id")
        return self
