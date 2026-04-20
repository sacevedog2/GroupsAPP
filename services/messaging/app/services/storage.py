from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status


@dataclass(slots=True)
class StoredFile:
    original_filename: str
    stored_filename: str
    size_bytes: int
    checksum_sha256: str
    storage_path: str
    content_type: str


class StorageService:
    def __init__(self, root_path: str, max_upload_mb: int) -> None:
        self.root_path = Path(root_path).resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)
        self.max_upload_bytes = max_upload_mb * 1024 * 1024

    async def save_upload(self, upload: UploadFile) -> StoredFile:
        original_name = upload.filename or "file.bin"
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", original_name)
        now = datetime.now(timezone.utc)
        daily_dir = self.root_path / now.strftime("%Y/%m/%d")
        daily_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid4()}_{safe_name}"
        file_path = daily_dir / stored_filename

        sha256 = hashlib.sha256()
        total_size = 0

        try:
            with file_path.open("wb") as file_out:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    total_size += len(chunk)
                    if total_size > self.max_upload_bytes:
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=(
                                f"Archivo supera el limite permitido "
                                f"({self.max_upload_bytes} bytes)."
                            ),
                        )
                    file_out.write(chunk)
                    sha256.update(chunk)
        except HTTPException:
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            if file_path.exists():
                file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"No fue posible almacenar el archivo: {exc}",
            ) from exc
        finally:
            await upload.close()

        content_type = upload.content_type or "application/octet-stream"
        return StoredFile(
            original_filename=original_name,
            stored_filename=stored_filename,
            size_bytes=total_size,
            checksum_sha256=sha256.hexdigest(),
            storage_path=os.fspath(file_path),
            content_type=content_type,
        )
