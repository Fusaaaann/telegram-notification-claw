from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from vercel.blob import BlobClient
from vercel.blob.errors import BlobError


class StorageBackend(Protocol):
    local_path: str

    def sync_from_remote(self) -> None:
        ...

    def sync_to_remote(self) -> None:
        ...


@dataclass
class LocalStorage:
    local_path: str

    def sync_from_remote(self) -> None:
        return None

    def sync_to_remote(self) -> None:
        return None


@dataclass
class BlobStorage:
    local_path: str
    blob_path: str
    access: str
    token: str | None

    def _client(self) -> BlobClient:
        if self.token:
            return BlobClient(token=self.token)
        return BlobClient()

    def sync_from_remote(self) -> None:
        os.makedirs(os.path.dirname(self.local_path) or ".", exist_ok=True)
        client = self._client()
        try:
            result = client.get(self.blob_path, access=self.access)
        except BlobError:
            return None
        if not result:
            return None
        status = getattr(result, "status_code", None) or getattr(result, "statusCode", None)
        if status is not None and status != 200:
            return None
        if not result.stream:
            return None
        with open(self.local_path, "wb") as f:
            for chunk in result.stream:
                f.write(chunk)

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
