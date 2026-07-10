import os
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings


ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


class UploadService:
    @staticmethod
    def validate_file(file: UploadFile) -> str:
        extension = Path(file.filename or "").suffix.lower()
        expected_extension = ALLOWED_CONTENT_TYPES.get(file.content_type or "")
        allowed_extensions = set(ALLOWED_CONTENT_TYPES.values()) | {".jpeg"}

        if extension not in allowed_extensions or expected_extension is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file format. Upload PDF, PNG, JPG, or JPEG files only.",
            )
        return extension

    @staticmethod
    def save_customer_document(customer_id: UUID, file: UploadFile) -> tuple[str, int]:
        extension = UploadService.validate_file(file)
        upload_root = Path(settings.UPLOAD_DIR)
        customer_dir = upload_root / str(customer_id)
        customer_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid4()}{extension}"
        file_path = customer_dir / safe_name
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        size = 0

        try:
            with file_path.open("wb") as buffer:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > max_size:
                        buffer.close()
                        os.remove(file_path)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB} MB upload limit.",
                        )
                    buffer.write(chunk)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store document.",
            ) from exc
        finally:
            file.file.close()

        return str(file_path), size
