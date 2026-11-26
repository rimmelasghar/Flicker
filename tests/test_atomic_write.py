import errno
import io

import pytest

from server import upload
from server.upload import TMP_DIR, clean_temp, save_upload
from tests import samples

LIMIT = 10 * 1024 * 1024


def test_file_is_not_in_inbox_while_being_written(tmp_path, monkeypatch):
    seen_during_copy = []
    real_copy = upload._copy_limited

    def spying_copy(source, target, max_bytes):
        seen_during_copy.extend(p.name for p in tmp_path.iterdir() if p.name != TMP_DIR)
        return real_copy(source, target, max_bytes)

    monkeypatch.setattr(upload, "_copy_limited", spying_copy)
    saved = save_upload(io.BytesIO(samples.JPEG), "a.jpg", tmp_path, LIMIT)
    assert seen_during_copy == []
    assert (tmp_path / saved.name).read_bytes() == samples.JPEG


def test_temp_folder_is_empty_after_save(tmp_path):
    save_upload(io.BytesIO(samples.JPEG), "a.jpg", tmp_path, LIMIT)
    assert list((tmp_path / TMP_DIR).iterdir()) == []


def test_failed_copy_leaves_nothing_behind(tmp_path, monkeypatch):
    def failing_copy(source, target, max_bytes):
        target.write(b"partial")
        raise OSError(errno.EIO, "boom")

    monkeypatch.setattr(upload, "_copy_limited", failing_copy)
    with pytest.raises(OSError):
        save_upload(io.BytesIO(samples.JPEG), "a.jpg", tmp_path, LIMIT)
    assert [p.name for p in tmp_path.iterdir()] == [TMP_DIR]
    assert list((tmp_path / TMP_DIR).iterdir()) == []


def test_disk_full_maps_to_507(tmp_path, monkeypatch):
    def full_copy(source, target, max_bytes):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(upload, "_copy_limited", full_copy)
    with pytest.raises(upload.HTTPException) as caught:
        save_upload(io.BytesIO(samples.JPEG), "a.jpg", tmp_path, LIMIT)
    assert caught.value.status_code == 507


def test_falls_back_when_hard_links_are_unsupported(tmp_path, monkeypatch):
    def no_link(src, dst):
        raise OSError(errno.EPERM, "Operation not permitted")

    monkeypatch.setattr(upload.os, "link", no_link)
    first = save_upload(io.BytesIO(samples.JPEG), "a.jpg", tmp_path, LIMIT)
    second = save_upload(io.BytesIO(samples.PNG), "a.jpg", tmp_path, LIMIT)
    assert first.name != second.name
    assert (tmp_path / first.name).read_bytes() == samples.JPEG
    assert (tmp_path / second.name).read_bytes() == samples.PNG
    assert list((tmp_path / TMP_DIR).iterdir()) == []


def test_clean_temp_removes_leftovers(tmp_path):
    (tmp_path / TMP_DIR).mkdir()
    (tmp_path / TMP_DIR / "deadbeef").write_bytes(b"half a photo")
    clean_temp(tmp_path)
    assert list((tmp_path / TMP_DIR).iterdir()) == []


def test_clean_temp_without_folder_is_fine(tmp_path):
    clean_temp(tmp_path)
