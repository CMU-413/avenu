"""Unit tests for the filesystem image store service.

The store is a pure-stdlib module; these tests use a ``tmp_path``-style
directory to avoid any dependency on MongoDB or the configured
``IMAGE_STORE_DIR``.
"""

from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services import image_store


class ImageStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.root = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_then_open_round_trips_bytes_and_content_type(self):
        rel = image_store.save_bytes(b"hello png", "image/png", root=self.root)
        self.assertTrue(rel.endswith(".png"))
        stream, content_type = image_store.open_path(rel, root=self.root)
        try:
            self.assertEqual(stream.read(), b"hello png")
        finally:
            stream.close()
        self.assertEqual(content_type, "image/png")

    def test_save_uses_content_type_extension(self):
        jpg = image_store.save_bytes(b"x", "image/jpeg", root=self.root)
        gif = image_store.save_bytes(b"x", "image/gif", root=self.root)
        unknown = image_store.save_bytes(b"x", "application/unknown", root=self.root)
        self.assertTrue(jpg.endswith(".jpg"))
        self.assertTrue(gif.endswith(".gif"))
        self.assertTrue(unknown.endswith(".bin"))

    def test_open_path_rejects_traversal(self):
        image_store.save_bytes(b"x", "image/png", root=self.root)
        with self.assertRaises(FileNotFoundError):
            image_store.open_path("../escape.png", root=self.root)
        with self.assertRaises(FileNotFoundError):
            image_store.open_path("/etc/passwd", root=self.root)

    def test_open_path_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            image_store.open_path("nonexistent.png", root=self.root)

    def test_delete_path_removes_file(self):
        rel = image_store.save_bytes(b"x", "image/png", root=self.root)
        self.assertTrue(image_store.delete_path(rel, root=self.root))
        self.assertFalse((Path(self.root) / rel).exists())

    def test_delete_path_returns_false_when_missing(self):
        self.assertFalse(image_store.delete_path("gone.png", root=self.root))

    def test_delete_path_rejects_traversal(self):
        self.assertFalse(image_store.delete_path("../../etc/passwd", root=self.root))

    def test_prune_older_than_only_deletes_stale_files(self):
        fresh = image_store.save_bytes(b"fresh", "image/png", root=self.root)
        stale = image_store.save_bytes(b"stale", "image/png", root=self.root)
        stale_path = Path(self.root) / stale
        old_time = time.time() - (3600 * 48)
        os.utime(stale_path, (old_time, old_time))

        removed = image_store.prune_older_than(3600 * 24, root=self.root)

        self.assertEqual(removed, 1)
        self.assertFalse((Path(self.root) / stale).exists())
        self.assertTrue((Path(self.root) / fresh).exists())

    def test_prune_older_than_with_zero_keeps_everything(self):
        image_store.save_bytes(b"x", "image/png", root=self.root)
        removed = image_store.prune_older_than(60 * 60 * 24 * 365, root=self.root)
        self.assertEqual(removed, 0)


if __name__ == "__main__":
    unittest.main()
