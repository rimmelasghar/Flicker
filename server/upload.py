"""Saving uploaded images into the inbox folder."""

import datetime as dt
import errno
import logging
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import filetype
from fastapi import HTTPException, status

CHUNK = 1024 * 1024
MAX_STEM = 80
MAX_COLLISIONS = 1000
HEAD_BYTES = 512  # enough for every allowed format's signature
# Uploads are written here first, then moved into the inbox complete.
TMP_DIR = ".flick-tmp"
# errno values meaning "this filesystem cannot make hard links".
LINK_UNSUPPORTED = {errno.EPERM, errno.ENOTSUP, errno.EOPNOTSUPP, errno.EXDEV, errno.ENOSYS}

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


def _publish(tmp: Path, inbox: Path, base: str, ext: str) -> Path:
    """Move a finished temp file into the inbox under a free name.

    os.link fails if the name exists, so two uploads can never overwrite
    each other, and the file appears complete in one step. Filesystems
    without hard links fall back to reserving the name, then os.replace.
    """
    for n in range(MAX_COLLISIONS):
        path = inbox / (f"{base}.{ext}" if n == 0 else f"{base}-{n}.{ext}")
        try:
            os.link(tmp, path)
        except FileExistsError:
            continue
        except OSError as exc:
            if exc.errno not in LINK_UNSUPPORTED:
                raise
            try:
                path.open("xb").close()
            except FileExistsError:
                continue
            os.replace(tmp, path)
            return path
        tmp.unlink()
        return path
    raise HTTPException(status.HTTP_409_CONFLICT, "too many files with the same name")


def clean_temp(inbox: Path) -> None:
    """Remove temp files left behind by a crash (call before serving)."""
    tmp_dir = inbox / TMP_DIR
    if tmp_dir.is_dir():
        for leftover in tmp_dir.iterdir():
            leftover.unlink(missing_ok=True)


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
    tmp_dir = inbox / TMP_DIR
    tmp = tmp_dir / secrets.token_hex(8)
    try:
        tmp_dir.mkdir(exist_ok=True)
        with tmp.open("xb") as target:
            size = _copy_limited(source, target, max_bytes)
        path = _publish(tmp, inbox, f"{stamp}-{stem}", ext)
    except OSError as exc:
        if exc.errno == errno.ENOSPC:
            raise HTTPException(status.HTTP_507_INSUFFICIENT_STORAGE, "disk full") from exc
        raise
    finally:
        tmp.unlink(missing_ok=True)
    log.info("received %s (%d KB)", path.name, round(size / 1024))
    return SavedFile(name=path.name, size=size)
