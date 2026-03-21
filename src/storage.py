from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

try:
    from vercel.blob import BlobClient
    from vercel.blob.errors import BlobError
except ImportError:  # pragma: no cover - Blob-backed storage is optional in local tests
    BlobClient = None

    class BlobError(Exception):
        pass


logger = logging.getLogger(__name__)


class StorageBackend(Protocol):
    local_path: str

    def sync_from_remote(self) -> None:
        ...

    def sync_to_remote(self) -> None:
        ...

    @contextmanager
    def write_lock(self):
        yield


@dataclass
class LocalStorage:
    local_path: str

    def sync_from_remote(self) -> None:
        return None

    def sync_to_remote(self) -> None:
        return None

    @contextmanager
    def write_lock(self):
        yield


@dataclass
class BlobStorage:
    local_path: str
    blob_path: str
    access: str
    token: str | None
    lock_timeout_seconds: float = 15.0
    lock_poll_seconds: float = 0.25
    lock_stale_after_seconds: float = 60.0

    def _client(self) -> BlobClient:
        if BlobClient is None:
            raise RuntimeError("vercel package is required for BlobStorage")
        if self.token:
            return BlobClient(token=self.token)
        return BlobClient()

    def sync_from_remote(self) -> None:
        os.makedirs(os.path.dirname(self.local_path) or ".", exist_ok=True)
        client = self._client()
        try:
            result = client.get(self.blob_path, access=self.access, use_cache=False)
        except Exception as e:
            if not (isinstance(e, BlobError) or type(e).__name__ == "BlobNotFoundError"):
                raise
            return None
        if not result:
            return None
        status = getattr(result, "status_code", None) or getattr(result, "statusCode", None)
        if status is not None and status != 200:
            return None
        if not result.content:
            return None
        with open(self.local_path, "wb") as f:
            f.write(result.content)

    def sync_to_remote(self) -> None:
        os.makedirs(os.path.dirname(self.local_path) or ".", exist_ok=True)
        client = self._client()
        with open(self.local_path, "rb") as f:
            data = f.read()
        client.put(
            self.blob_path,
            data,
            access=self.access,
            overwrite=True,
        )

    def _lock_path(self) -> str:
        return f"{self.blob_path}.lock"

    def _is_lock_conflict(self, exc: Exception) -> bool:
        name = type(exc).__name__.lower()
        return "conflict" in name or "exists" in name or "already" in name

    def _delete_blob(self, client: BlobClient, path: str) -> None:
        if not hasattr(client, "delete"):
            raise RuntimeError("vercel BlobClient.delete is required for BlobStorage locking")
        client.delete(path)

    def _get_blob_result(self, client: BlobClient, path: str):
        try:
            return client.get(path, access="private", use_cache=False)
        except Exception as exc:
            if isinstance(exc, BlobError) or type(exc).__name__ == "BlobNotFoundError":
                return None
            raise

    def _read_lock_state(self, client: BlobClient, path: str) -> dict[str, Any] | None:
        result = self._get_blob_result(client, path)
        if not result or not getattr(result, "content", None):
            return None
        try:
            raw = result.content.decode("utf-8")
            state = json.loads(raw)
        except Exception:
            return None
        if not isinstance(state, dict):
            return None
        return state

    def _lock_payload(self, lease_id: str) -> bytes:
        now = time.time()
        payload = {
            "lease_id": lease_id,
            "acquired_at": now,
            "expires_at": now + self.lock_stale_after_seconds,
        }
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")

    def _is_stale_lock(self, state: dict[str, Any] | None) -> bool:
        if not state:
            return False
        expires_at = state.get("expires_at")
        if not isinstance(expires_at, (int, float)):
            return False
        return float(expires_at) <= time.time()

    @contextmanager
    def write_lock(self):
        client = self._client()
        lock_path = self._lock_path()
        lease_id = str(uuid.uuid4())
        deadline = time.monotonic() + self.lock_timeout_seconds
        active_error: Exception | None = None

        while True:
            try:
                client.put(
                    lock_path,
                    self._lock_payload(lease_id),
                    access="private",
                    overwrite=False,
                )
                break
            except Exception as exc:
                if not self._is_lock_conflict(exc):
                    raise
                state = self._read_lock_state(client, lock_path)
                if self._is_stale_lock(state):
                    logger.warning("Deleting stale blob write lock for %s", self.blob_path)
                    self._delete_blob(client, lock_path)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out acquiring blob write lock for {self.blob_path}") from exc
                time.sleep(self.lock_poll_seconds)

        try:
            yield
        except Exception as exc:
            active_error = exc
            raise
        finally:
            try:
                self._delete_blob(client, lock_path)
            except Exception as exc:
                if active_error is not None:
                    active_error.add_note(f"Blob write lock cleanup failed for {self.blob_path}: {exc}")
                else:
                    raise RuntimeError(f"Failed to release blob write lock for {self.blob_path}") from exc
