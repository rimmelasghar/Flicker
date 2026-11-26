"""Saving uploaded images into the inbox folder."""

import datetime as dt
import errno
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import filetype
from fastapi import HTTPException, status

CHUNK = 1024 * 1024
MAX_STEM = 80
MAX_COLLISIONS = 1000
HEAD_BYTES = 512  # enough for every allowed format's signature

# filetype extension -> extension used for the saved file.
ALLOWED = {"jpg": "jpg", "png": "png", "apng": "png", "gif": "gif", "webp": "webp", "heic": "heic"}
# ISO-BMFF brands of HEIF stills that filetype does not report as heic.
HEIF_BRANDS = {"heic", "heix", "hevc", "hevx", "heim", "heis", "mif1", "msf1"}

log = logging.getLogger("flick")


@dataclass(frozen=True)
class SavedFile:
    name: str
    size: int


def safe_stem(original: str | None) -> str:
    """Return a safe file stem from an uploaded filename.

    Drops any path components (both / and \\) and the extension, then
    keeps only letters, digits, '-' and '_'.
    """
    base = re.split(r"[\\/]", original or "")[-1]
    stem, dot, _ = base.rpartition(".")
    if not dot:
        stem = base
    return re.sub(r"[^A-Za-z0-9_-]", "", stem)[:MAX_STEM] or "photo"


def _heif_brand(head: bytes) -> bool:
    if len(head) < 16 or head[4:8] != b"ftyp":
        return False
    size = min(int.from_bytes(head[0:4], "big"), len(head))
    brands = {head[8:12]} | {head[i : i + 4] for i in range(16, size - 3, 4)}
    return any(b.decode("latin-1") in HEIF_BRANDS for b in brands) and b"avif" not in brands


def image_extension(head: bytes) -> str | None:
    """Extension for an allowed image judged by its first bytes, else None."""
    kind = filetype.guess(head)
    if kind is not None and kind.extension in ALLOWED:
        return ALLOWED[kind.extension]
    return "heif" if _heif_brand(head) else None


def _open_unique(inbox: Path, base: str, ext: str) -> tuple[Path, BinaryIO]:
    for n in range(MAX_COLLISIONS):
        path = inbox / (f"{base}.{ext}" if n == 0 else f"{base}-{n}.{ext}")
        try:
            return path, path.open("xb")
        except FileExistsError:
            continue
    raise HTTPException(status.HTTP_409_CONFLICT, "too many files with the same name")


def _too_large(max_bytes: int) -> HTTPException:
    return HTTPException(
        status.HTTP_413_CONTENT_TOO_LARGE,
        f"file is larger than {max_bytes // (1024 * 1024)} MB",
    )


def _copy_limited(source: BinaryIO, target: BinaryIO, max_bytes: int) -> int:
    size = 0
    while chunk := source.read(CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise _too_large(max_bytes)
        target.write(chunk)
    return size


def save_upload(
    source: BinaryIO, original_name: str | None, inbox: Path, max_bytes: int
) -> SavedFile:
    # Cheap early check when the size is known; the copy enforces it anyway.
    source.seek(0, 2)
    if source.tell() > max_bytes:
        raise _too_large(max_bytes)
    source.seek(0)
    # Judge the type by the bytes, never by the name or Content-Type.
    ext = image_extension(source.read(HEAD_BYTES))
    source.seek(0)
    if ext is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "only JPEG, PNG, HEIC/HEIF, WebP and GIF images are accepted",
        )
    stem = safe_stem(original_name)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path, target = _open_unique(inbox, f"{stamp}-{stem}", ext)
    try:
        with target:
            size = _copy_limited(source, target, max_bytes)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except OSError as exc:
        path.unlink(missing_ok=True)
        if exc.errno == errno.ENOSPC:
            raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "disk full") from exc
        raise
    log.info("received %s (%d KB)", path.name, round(size / 1024))
    return SavedFile(name=path.name, size=size)
