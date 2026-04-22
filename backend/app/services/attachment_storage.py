from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class AttachmentStorageError(Exception):
    pass


class AttachmentNotFoundError(AttachmentStorageError):
    pass


class InvalidStorageKeyError(AttachmentStorageError):
    pass


class AttachmentStorage(ABC):
    @abstractmethod
    def save_bytes(self, storage_key: str, content: bytes, *, content_type: str = "application/octet-stream") -> int:
        raise NotImplementedError

    def resolve_existing_path(self, storage_key: str) -> Path:
        raise NotImplementedError("This backend does not support local path resolution")

    def get_signed_url(self, storage_key: str, expires_in_seconds: int = 60) -> str | None:
        return None


class LocalAttachmentStorage(AttachmentStorage):
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str) -> Path:
        key = (storage_key or "").replace("\\", "/").strip("/")
        if not key:
            raise InvalidStorageKeyError("Empty storage key")
        parts = [p for p in key.split("/") if p]
        if any(part in {".", ".."} for part in parts):
            raise InvalidStorageKeyError("Invalid path segments")
        candidate = (self.root_dir / Path(*parts)).resolve()
        root = self.root_dir.resolve()
        if candidate != root and root not in candidate.parents:
            raise InvalidStorageKeyError("Path escapes storage root")
        return candidate

    def save_bytes(self, storage_key: str, content: bytes, *, content_type: str = "application/octet-stream") -> int:
        path = self._resolve_safe_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path.stat().st_size

    def resolve_existing_path(self, storage_key: str) -> Path:
        path = self._resolve_safe_path(storage_key)
        if not path.exists() or not path.is_file():
            raise AttachmentNotFoundError("File not found")
        return path


class SupabaseAttachmentStorage(AttachmentStorage):
    def __init__(self, url: str, key: str, bucket: str):
        from supabase import create_client

        self._client = create_client(url, key)
        self._bucket = bucket

    def save_bytes(self, storage_key: str, content: bytes, *, content_type: str = "application/octet-stream") -> int:
        self._client.storage.from_(self._bucket).upload(
            path=storage_key,
            file=content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return len(content)

    def get_signed_url(self, storage_key: str, expires_in_seconds: int = 60) -> str | None:
        response = self._client.storage.from_(self._bucket).create_signed_url(
            path=storage_key,
            expires_in=expires_in_seconds,
        )
        return response.get("signedURL") or response.get("signed_url")
