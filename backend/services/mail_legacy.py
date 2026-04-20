"""Helpers for legacy mail documents that used a cumulative ``count`` field."""

from __future__ import annotations

from typing import Any


def legacy_mail_piece_count(doc: dict[str, Any]) -> int:
    """How many logical mail pieces a document represents (new model: always 1 per doc)."""
    raw = doc.get("count")
    if isinstance(raw, int) and raw >= 1:
        return raw
    if isinstance(raw, float) and raw >= 1 and raw == int(raw):
        return int(raw)
    return 1
