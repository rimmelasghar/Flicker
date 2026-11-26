import datetime as real_dt
import io
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from server import upload
from server.auth import TOKEN_HEADER
from server.main import create_phone_app
from server.upload import TMP_DIR, safe_stem, save_upload
from tests import samples

LIMIT = 10 * 1024 * 1024
FROZEN = real_dt.datetime(2026, 11, 26, 9, 5, 7)


class FrozenDatetime(real_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN


@pytest.fixture
def frozen_time(monkeypatch):
    monkeypatch.setattr(upload.dt, "datetime", FrozenDatetime)


def _save(inbox, data=samples.JPEG, name="IMG_0001.HEIC"):
    return save_upload(io.BytesIO(data), name, inbox, LIMIT).name


# --- naming -----------------------------------------------------------------


def test_name_is_timestamp_stem_and_detected_extension(tmp_path, frozen_time):
    assert _save(tmp_path) == "20261126-090507-IMG_0001.jpg"


def test_collisions_get_increasing_suffixes(tmp_path, frozen_time):
    names = [_save(tmp_path) for _ in range(4)]
    assert names == [
        "20261126-090507-IMG_0001.jpg",
        "20261126-090507-IMG_0001-1.jpg",
        "20261126-090507-IMG_0001-2.jpg",
        "20261126-090507-IMG_0001-3.jpg",
    ]


def test_concurrent_uploads_never_overwrite(tmp_path, frozen_time):
    payloads = [samples.JPEG + bytes([i]) for i in range(20)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        names = list(pool.map(lambda data: _save(tmp_path, data), payloads))
    assert len(set(names)) == 20
    stored = {(tmp_path / n).read_bytes() for n in names}
    assert stored == set(payloads)


def test_long_stem_is_truncated():
    assert len(safe_stem("a" * 300 + ".jpg")) == 80


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("Ünïcødé fötø.jpg", "ncdft"),
        ("写真.jpg", "photo"),
        ("my.photo.final.jpg", "myphotofinal"),
        ("..\\..\\windows\\system32\\x.png", "x"),
        ("%2e%2e%2fsecret.jpg", "2e2e2fsecret"),
    ],
)
def test_odd_names_are_sanitised(original, expected):
    assert safe_stem(original) == expected


# --- type ------------------------------------------------------------------


def test_type_check_ignores_name_and_content_type(tmp_path):
    with pytest.raises(upload.HTTPException) as caught:
        save_upload(io.BytesIO(samples.PDF), "scan.jpg", tmp_path, LIMIT)
    assert caught.value.status_code == 415
    assert list(tmp_path.iterdir()) == []


def test_truncated_signature_is_rejected(tmp_path):
    with pytest.raises(upload.HTTPException) as caught:
        save_upload(io.BytesIO(b"\xff\xd8"), "tiny.jpg", tmp_path, LIMIT)
    assert caught.value.status_code == 415


# --- size ------------------------------------------------------------------


class Unsized(io.BytesIO):
    """A stream whose size is unknown up front (seek to end not allowed)."""

    def seek(self, offset, whence=0):
        if whence == 2:
            return 0
        return super().seek(offset, whence)

    def tell(self):
        return 0 if self.closed else super().tell()


def test_limit_is_enforced_while_copying(tmp_path):
    data = samples.JPEG + b"\x00" * 2048
    with pytest.raises(upload.HTTPException) as caught:
        save_upload(Unsized(data), "a.jpg", tmp_path, 1024)
    assert caught.value.status_code == 413
    assert [p.name for p in tmp_path.iterdir()] == [TMP_DIR]
    assert list((tmp_path / TMP_DIR).iterdir()) == []


# --- done-when over HTTP ---------------------------------------------------


def test_done_when_status_codes(settings, tokens):
    client = TestClient(create_phone_app(replace(settings, max_file_mb=1), tokens))

    def post(data, token):
        files = {"file": ("x.jpg", data, "image/jpeg")}
        return client.post("/api/upload", headers={TOKEN_HEADER: token}, files=files)

    assert post(samples.TEXT, tokens.current).status_code == 415
    assert post(samples.JPEG + b"\x00" * (2 * 1024 * 1024), tokens.current).status_code == 413
    assert post(samples.JPEG, "wrong-token").status_code == 401
    assert post(samples.JPEG, tokens.current).status_code == 200
