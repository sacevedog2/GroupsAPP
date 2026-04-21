from __future__ import annotations

import hashlib
import hmac
import os


class PasswordHasher:
    def __init__(self, iterations: int = 310000) -> None:
        self.iterations = max(120000, iterations)

    def hash_password(self, raw_password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt,
            self.iterations,
            dklen=32,
        )
        return (
            f"pbkdf2_sha256${self.iterations}"
            f"${salt.hex()}"
            f"${digest.hex()}"
        )

    def verify_password(self, raw_password: str, encoded_hash: str) -> bool:
        try:
            scheme, iter_str, salt_hex, digest_hex = encoded_hash.split("$", maxsplit=3)
        except ValueError:
            return False

        if scheme != "pbkdf2_sha256":
            return False

        try:
            iterations = int(iter_str)
            salt = bytes.fromhex(salt_hex)
            expected_digest = bytes.fromhex(digest_hex)
        except ValueError:
            return False

        candidate_digest = hashlib.pbkdf2_hmac(
            "sha256",
            raw_password.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected_digest),
        )
        return hmac.compare_digest(candidate_digest, expected_digest)
