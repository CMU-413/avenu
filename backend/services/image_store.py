"""Filesystem-backed image store for mail photos.

Purely-stdlib module; no Mongo, no Flask. Images live under
``IMAGE_STORE_DIR`` (typically a host-bind-mounted Docker volume). The module
exposes a small, value-oriented surface: bytes + content-type go in, a
relative path comes out; paths later resolve back to streams. The store does
not track metadata; callers (the queue layer) persist ``imagePath`` on their
own documents.
"""

from __future__ import annotations

import mimetypes
import os
import secrets
import time
from pathlib import Path
from typing import BinaryIO, Iterator

_DEFAULT_EXT = ".bin"
_CONTENT_TYPE_EXTENSIONS: dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/tiff": ".tif",
    "image/bmp": ".bmp",
}


def _ext_for(content_type: str) -> str:
    ct = (content_type or "").split(";", 1)[0].strip().lower()
    return _CONTENT_TYPE_EXTENSIONS.get(ct) or mimetypes.guess_extension(ct) or _DEFAULT_EXT


def _ensure_root(root: str) -> Path:
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def save_bytes(data: bytes, content_type: str, *, root: str | None = None) -> str:
    """Write ``data`` under the store root; return the relative path stored on the item."""
    base = _ensure_root(root or _default_root())
    ext = _ext_for(content_type)
    name = f"{secrets.token_hex(12)}{ext}"
    target = base / name
    with target.open("wb") as f:
        f.write(data)
    return name


def open_path(rel_path: str, *, root: str | None = None) -> tuple[BinaryIO, str]:
    """Open ``rel_path`` for reading; refuses anything resolving outside the store root."""
    base = _ensure_root(root or _default_root())
    resolved = (base / rel_path).resolve()
    if base != resolved and base not in resolved.parents:
        raise FileNotFoundError(rel_path)
    if not resolved.is_file():
        raise FileNotFoundError(rel_path)
    content_type, _ = mimetypes.guess_type(str(resolved))
    return resolved.open("rb"), content_type or "application/octet-stream"


def delete_path(rel_path: str, *, root: str | None = None) -> bool:
    """Best-effort unlink; returns True when a file was actually removed."""
    base = _ensure_root(root or _default_root())
    resolved = (base / rel_path).resolve()
    if base != resolved and base not in resolved.parents:
        return False
    try:
        resolved.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def prune_older_than(seconds: int, *, root: str | None = None) -> int:
    """Remove files under the store root whose mtime is older than ``seconds`` ago."""
    base = _ensure_root(root or _default_root())
    cutoff = time.time() - max(0, seconds)
    removed = 0
    for entry in _iter_files(base):
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
                removed += 1
        except FileNotFoundError:
            continue
        except OSError:
            continue
    return removed


def _iter_files(base: Path) -> Iterator[Path]:
    for root, _dirs, files in os.walk(base):
        for name in files:
            yield Path(root) / name


def _default_root() -> str:
    """Late-bound to avoid import-time coupling with ``config``; tests can override via ``root``."""
    from config import IMAGE_STORE_DIR
    return IMAGE_STORE_DIR
