"""Unit tests for the nightly image pruner.

``prune_expired_images`` is pure-function-shaped: all external dependencies
(Mongo + filesystem) are injected, so tests exercise the composition without
touching either.
"""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timedelta

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")

from services.image_pruner import prune_expired_images


class ImagePrunerTests(unittest.TestCase):
    def test_prune_deletes_stale_rows_and_files(self):
        now = datetime(2026, 4, 21, 3, 0)
        stale = [
            {"_id": "r1", "imagePath": "a.jpg"},
            {"_id": "r2", "imagePath": "b.png"},
        ]
        deleted_files: list[str] = []
        marked: list[list] = []

        def fake_find(cutoff):
            self.assertEqual(cutoff, now - timedelta(hours=24))
            return stale

        def fake_mark(ids):
            marked.append(ids)
            return len(ids)

        def fake_delete_file(path):
            deleted_files.append(path)
            return True

        def fake_prune_orphans(seconds):
            self.assertEqual(seconds, 24 * 3600)
            return 3

        result = prune_expired_images(
            retention_hours=24,
            now=now,
            find_stale=fake_find,
            mark_deleted=fake_mark,
            delete_file=fake_delete_file,
            prune_orphans=fake_prune_orphans,
        )

        self.assertEqual(deleted_files, ["a.jpg", "b.png"])
        self.assertEqual(marked, [["r1", "r2"]])
        self.assertEqual(result.rows_scanned, 2)
        self.assertEqual(result.files_deleted, 2)
        self.assertEqual(result.rows_marked_deleted, 2)
        self.assertEqual(result.orphan_files_deleted, 3)

    def test_prune_skips_rows_without_image_path(self):
        rows = [{"_id": "r1", "imagePath": None}, {"_id": "r2", "imagePath": "x.jpg"}]
        file_calls: list[str] = []

        result = prune_expired_images(
            retention_hours=24,
            now=datetime(2026, 4, 21),
            find_stale=lambda _cutoff: rows,
            mark_deleted=lambda ids: len(ids),
            delete_file=lambda p: (file_calls.append(p) or True),
            prune_orphans=lambda _s: 0,
        )

        self.assertEqual(file_calls, ["x.jpg"])
        self.assertEqual(result.rows_scanned, 2)
        self.assertEqual(result.files_deleted, 1)
        self.assertEqual(result.rows_marked_deleted, 2)

    def test_prune_counts_only_actually_removed_files(self):
        rows = [{"_id": "r1", "imagePath": "gone.jpg"}, {"_id": "r2", "imagePath": "there.jpg"}]

        def fake_delete(path):
            return path == "there.jpg"

        result = prune_expired_images(
            retention_hours=24,
            now=datetime(2026, 4, 21),
            find_stale=lambda _c: rows,
            mark_deleted=lambda ids: len(ids),
            delete_file=fake_delete,
            prune_orphans=lambda _s: 0,
        )

        self.assertEqual(result.files_deleted, 1)
        self.assertEqual(result.rows_marked_deleted, 2)

    def test_prune_with_no_stale_rows_still_runs_orphan_sweep(self):
        orphan_calls: list[int] = []

        result = prune_expired_images(
            retention_hours=12,
            now=datetime(2026, 4, 21),
            find_stale=lambda _c: [],
            mark_deleted=lambda ids: (_ for _ in ()).throw(AssertionError("should not be called")),
            delete_file=lambda p: True,
            prune_orphans=lambda s: (orphan_calls.append(s) or 5),
        )

        self.assertEqual(result.rows_scanned, 0)
        self.assertEqual(result.files_deleted, 0)
        self.assertEqual(result.rows_marked_deleted, 0)
        self.assertEqual(result.orphan_files_deleted, 5)
        self.assertEqual(orphan_calls, [12 * 3600])

    def test_prune_result_to_dict_uses_camel_case(self):
        result = prune_expired_images(
            retention_hours=24,
            now=datetime(2026, 4, 21),
            find_stale=lambda _c: [{"_id": "r1", "imagePath": "a.jpg"}],
            mark_deleted=lambda ids: len(ids),
            delete_file=lambda _p: True,
            prune_orphans=lambda _s: 7,
        )
        self.assertEqual(
            result.to_dict(),
            {
                "rowsScanned": 1,
                "filesDeleted": 1,
                "rowsMarkedDeleted": 1,
                "orphanFilesDeleted": 7,
            },
        )


if __name__ == "__main__":
    unittest.main()
