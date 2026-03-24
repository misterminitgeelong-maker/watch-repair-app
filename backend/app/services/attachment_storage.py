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
    """
    Small storage contract for attachment persistence.
    Local FS is implemented now; object storage can implement this later.
    """

    @abstractmethod
    def save_bytes(self, storage_key: str, content: bytes) -> int:
        raise NotImplementedError

    @abstractmethod
    def resolve_existing_path(self, storage_key: str) -> Path:
        raise NotImplementedError


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

    def save_bytes(self, storage_key: str, content: bytes) -> int:
        path = self._resolve_safe_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path.stat().st_size

    def resolve_existing_path(self, storage_key: str) -> Path:
        path = self._resolve_safe_path(storage_key)
        if not path.exists() or not path.is_file():
            raise AttachmentNotFoundError("File not found")
        return path
