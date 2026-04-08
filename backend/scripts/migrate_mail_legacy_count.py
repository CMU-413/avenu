#!/usr/bin/env python3
"""
One-time data migration: legacy ``mail`` documents with a cumulative ``count`` field
are expanded into one document per piece (current model).

Usage (from repo root, with MONGO_URI in env):

  cd backend
  ../.venv/bin/python scripts/migrate_mail_legacy_count.py          # dry-run (default)
  ../.venv/bin/python scripts/migrate_mail_legacy_count.py --apply  # write changes

Safe to re-run after partial failure: documents without ``count`` are skipped.
"""

from __future__ import annotations

import argparse
import copy
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("MONGO_URI", "")
from config import mail_collection  # noqa: E402


def _strip_id(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k != "_id"}
    return out


def migrate(*, apply_writes: bool) -> tuple[int, int, int]:
    """Returns (docs_with_count_gt1_cloned, docs_unset_count, docs_examined)."""
    examined = 0
    cloned = 0
    unset = 0

    cursor = mail_collection.find({"count": {"$exists": True}})
    for doc in cursor:
        examined += 1
        raw = doc.get("count")
        if not isinstance(raw, int) or raw < 1:
            continue
        oid = doc["_id"]
        if raw == 1:
            if apply_writes:
                mail_collection.update_one({"_id": oid}, {"$unset": {"count": ""}})
            unset += 1
            continue

        base = _strip_id(doc)
        base.pop("count", None)
        if apply_writes:
            for _ in range(raw - 1):
                mail_collection.insert_one(copy.deepcopy(base))
            mail_collection.update_one({"_id": oid}, {"$unset": {"count": ""}})
        cloned += 1
        unset += 1

    return cloned, unset, examined


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate legacy mail.count to per-piece documents.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform writes (default is dry-run that only reports).",
    )
    args = parser.parse_args()

    if not os.getenv("MONGO_URI"):
        print("error: MONGO_URI must be set", file=sys.stderr)
        return 1

    cloned, unset, examined = migrate(apply_writes=args.apply)
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(
        f"[{mode}] examined {examined} documents with a count field; "
        f"expanded {cloned} multi-count rows; unset count on {unset} originals."
    )
    if not args.apply and (cloned or unset):
        print("Re-run with --apply to write these changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
