"""Saving uploaded images into the inbox folder."""

import datetime as dt
import errno
import logging
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import HTTPException, status

CHUNK = 1024 * 1024
MAX_STEM = 80
MAX_COLLISIONS = 1000

log = logging.getLogger("flick")


@dataclass(frozen=True)
class SavedFile:
    name: str
    size: int


def split_name(original: str | None) -> tuple[str, str]:
    """Return a safe (stem, ext) from an uploaded filename.

    Drops any path components (both / and \\), then keeps only letters,
    digits, '-' and '_'.
    """
    base = re.split(r"[\\/]", original or "")[-1]
    stem, dot, ext = base.rpartition(".")
    if not dot:
        stem, ext = ext, ""
    stem = re.sub(r"[^A-Za-z0-9_-]", "", stem)[:MAX_STEM] or "photo"
    ext = re.sub(r"[^A-Za-z0-9]", "", ext).lower()[:8] or "bin"
    return stem, ext


def _open_unique(inbox: Path, base: str, ext: str) -> tuple[Path, BinaryIO]:
    for n in range(MAX_COLLISIONS):
        path = inbox / (f"{base}.{ext}" if n == 0 else f"{base}-{n}.{ext}")
        try:
            return path, path.open("xb")
        except FileExistsError:
            continue
    raise HTTPException(status.HTTP_409_CONFLICT, "too many files with the same name")


def save_upload(source: BinaryIO, original_name: str | None, inbox: Path) -> SavedFile:
    stem, ext = split_name(original_name)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path, target = _open_unique(inbox, f"{stamp}-{stem}", ext)
    try:
        with target:
            shutil.copyfileobj(source, target, CHUNK)
            size = target.tell()
    except OSError as exc:
        path.unlink(missing_ok=True)
        if exc.errno == errno.ENOSPC:
            raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "disk full") from exc
        raise
    log.info("received %s (%d KB)", path.name, round(size / 1024))
    return SavedFile(name=path.name, size=size)
