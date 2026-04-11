from __future__ import annotations

import json
import tempfile
import unittest

from src.storage import BlobStorage


class FakeBlobClient:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, bytes, bool]] = []
        self.deleted: list[str] = []
        self.blobs: dict[str, bytes] = {}
        self.fail_delete = False

    def put(self, path: str, data: bytes, access: str, overwrite: bool):
        if not overwrite and path in self.blobs:
            raise FileExistsError(path)
        self.put_calls.append((path, data, overwrite))
        self.blobs[path] = data
        return {"path": path}

    def get(self, path: str, access: str, use_cache: bool):
        if path not in self.blobs:
            return None

        class Result:
            def __init__(self, content: bytes) -> None:
                self.content = content
                self.status_code = 200

        return Result(self.blobs[path])

    def delete(self, path: str) -> None:
        if self.fail_delete:
            raise RuntimeError("delete failed")
        self.deleted.append(path)
        self.blobs.pop(path, None)


class BlobStorageTests(unittest.TestCase):
    def test_write_lock_creates_and_releases_lock_blob(self) -> None:
        client = FakeBlobClient()

        class TestBlobStorage(BlobStorage):
            def _client(self):
                return client

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TestBlobStorage(
                local_path=f"{tmpdir}/reminders.sqlite3",
                blob_path="reminders.sqlite3",
                access="private",
                token=None,
            )

            with storage.write_lock():
                pass

        self.assertEqual(client.put_calls[0][0], "reminders.sqlite3.lock")
        self.assertEqual(client.put_calls[0][2], False)
        payload = json.loads(client.put_calls[0][1].decode("utf-8"))
        self.assertIn("lease_id", payload)
        self.assertIn("expires_at", payload)
        self.assertEqual(client.deleted, ["reminders.sqlite3.lock"])

    def test_write_lock_recovers_stale_lock(self) -> None:
        client = FakeBlobClient()

        class TestBlobStorage(BlobStorage):
            def _client(self):
                return client

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TestBlobStorage(
                local_path=f"{tmpdir}/reminders.sqlite3",
                blob_path="reminders.sqlite3",
                access="private",
                token=None,
            )
            client.blobs["reminders.sqlite3.lock"] = json.dumps(
                {"lease_id": "stale", "expires_at": 0}
            ).encode("utf-8")

            with storage.write_lock():
                pass

        self.assertGreaterEqual(client.deleted.count("reminders.sqlite3.lock"), 2)

    def test_write_lock_release_failure_is_visible(self) -> None:
        client = FakeBlobClient()
        client.fail_delete = True

        class TestBlobStorage(BlobStorage):
            def _client(self):
                return client

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TestBlobStorage(
                local_path=f"{tmpdir}/reminders.sqlite3",
                blob_path="reminders.sqlite3",
                access="private",
                token=None,
            )

            with self.assertRaises(RuntimeError) as ctx:
                with storage.write_lock():
                    pass

        self.assertIn("Failed to release blob write lock", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
