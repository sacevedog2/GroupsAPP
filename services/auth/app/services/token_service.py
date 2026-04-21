from __future__ import annotations

import base64
import hashlib
import hmac
import json
from binascii import Error as BinasciiError
from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.auth import AccessTokenClaims


class TokenValidationError(Exception):
    pass


class TokenService:
    def __init__(self, secret_key: str, issuer: str, access_token_ttl_seconds: int) -> None:
        if not secret_key or len(secret_key) < 16:
            raise ValueError("JWT secret key debe tener al menos 16 caracteres.")
        self.secret_key = secret_key.encode("utf-8")
        self.issuer = issuer
        self.access_token_ttl_seconds = max(300, access_token_ttl_seconds)

    def issue_access_token(self, user_id: str, email: str) -> tuple[str, int]:
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        expires_epoch = now_epoch + self.access_token_ttl_seconds

        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "sub": user_id,
            "user_id": user_id,
            "email": email,
            "iss": self.issuer,
            "iat": now_epoch,
            "exp": expires_epoch,
            "jti": str(uuid4()),
        }

        header_segment = self._b64url_encode_json(header)
        payload_segment = self._b64url_encode_json(payload)
        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        signature = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        signature_segment = self._b64url_encode(signature)

        return f"{header_segment}.{payload_segment}.{signature_segment}", self.access_token_ttl_seconds

    def validate_access_token(self, token: str) -> tuple[AccessTokenClaims, int]:
        try:
            header_segment, payload_segment, signature_segment = token.split(".")
        except ValueError as exc:
            raise TokenValidationError("Formato de token invalido.") from exc

        signing_input = f"{header_segment}.{payload_segment}".encode("utf-8")
        expected_signature = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        try:
            provided_signature = self._b64url_decode(signature_segment)
        except (ValueError, BinasciiError) as exc:
            raise TokenValidationError("Firma de token invalida.") from exc
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise TokenValidationError("Firma de token invalida.")

        try:
            payload_raw = self._b64url_decode(payload_segment)
        except (ValueError, BinasciiError) as exc:
            raise TokenValidationError("Payload de token invalido.") from exc
        try:
            payload = json.loads(payload_raw)
        except json.JSONDecodeError as exc:
            raise TokenValidationError("Payload de token invalido.") from exc

        try:
            claims = AccessTokenClaims.model_validate(payload)
        except Exception as exc:
            raise TokenValidationError("Claims de token invalidas.") from exc

        if claims.iss != self.issuer:
            raise TokenValidationError("Issuer invalido.")

        now_epoch = int(datetime.now(timezone.utc).timestamp())
        if now_epoch >= claims.exp:
            raise TokenValidationError("Token expirado.")

        return claims, claims.exp * 1000

    @staticmethod
    def _b64url_encode_json(value: dict[str, object]) -> str:
        raw = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return TokenService._b64url_encode(raw)

    @staticmethod
    def _b64url_encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")

    @staticmethod
    def _b64url_decode(value: str) -> bytes:
        padding = "=" * ((4 - len(value) % 4) % 4)
        return base64.urlsafe_b64decode(value + padding)
