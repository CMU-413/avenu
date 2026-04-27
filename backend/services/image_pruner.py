"""Nightly prune: drop image files + their queue rows once past retention.

Composition is the whole point here: we take the list of stale rows from
Mongo, unlink their files via :mod:`image_store`, then soft-delete the rows.
The store walk is also run so any dangling files (uploads whose row was
purged separately, or files whose path was lost) don't linger.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterable

from config import IMAGE_RETENTION_HOURS, ocr_queue_items_collection
from services import image_store


@dataclass(frozen=True)
class PruneResult:
    rows_scanned: int
    files_deleted: int
    rows_marked_deleted: int
    orphan_files_deleted: int

    def to_dict(self) -> dict[str, int]:
        return {
            "rowsScanned": self.rows_scanned,
            "filesDeleted": self.files_deleted,
            "rowsMarkedDeleted": self.rows_marked_deleted,
            "orphanFilesDeleted": self.orphan_files_deleted,
        }


def prune_expired_images(
    *,
    retention_hours: int | None = None,
    now: datetime | None = None,
    find_stale: Callable[[datetime], Iterable[dict]] | None = None,
    mark_deleted: Callable[[list], int] | None = None,
    delete_file: Callable[[str], bool] | None = None,
    prune_orphans: Callable[[int], int] | None = None,
) -> PruneResult:
    """Delete images (and their queue rows) older than retention.

    Dependency-injected for testability; production defaults hit Mongo + the
    filesystem store.
    """
    hours = retention_hours if retention_hours is not None else IMAGE_RETENTION_HOURS
    current = now or datetime.utcnow()
    cutoff = current - timedelta(hours=hours)
    retention_seconds = hours * 3600

    _find_stale = find_stale or _default_find_stale
    _mark = mark_deleted or _default_mark_deleted
    _delete_file = delete_file or image_store.delete_path
    _prune_orphans = prune_orphans or image_store.prune_older_than

    stale_rows = list(_find_stale(cutoff))
    files_deleted = 0
    deletable_ids: list = []
    for row in stale_rows:
        deletable_ids.append(row["_id"])
        path = row.get("imagePath")
        if path and _delete_file(path):
            files_deleted += 1

    rows_marked = _mark(deletable_ids) if deletable_ids else 0
    orphan_count = _prune_orphans(retention_seconds)

    return PruneResult(
        rows_scanned=len(stale_rows),
        files_deleted=files_deleted,
        rows_marked_deleted=rows_marked,
        orphan_files_deleted=orphan_count,
    )


def _default_find_stale(cutoff: datetime) -> Iterable[dict]:
    # Rows with an imagePath created before the cutoff, not already soft-deleted.
    cursor = ocr_queue_items_collection.find(
        {
            "imagePath": {"$ne": None},
            "status": {"$ne": "deleted"},
            "createdAt": {"$lt": cutoff},
        },
        {"_id": 1, "imagePath": 1},
    )
    return cursor


def _default_mark_deleted(ids: list) -> int:
    if not ids:
        return 0
    result = ocr_queue_items_collection.update_many(
        {"_id": {"$in": ids}},
        {"$set": {"status": "deleted", "imagePath": None, "updatedAt": datetime.utcnow()}},
    )
    return result.modified_count
