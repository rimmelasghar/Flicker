import re
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from server.auth import TOKEN_HEADER
from server.main import create_phone_app
from server.upload import image_extension, safe_stem
from tests import samples


def visible(inbox):
    """Files a user would see in the inbox (not the hidden temp folder)."""
    return sorted(p.name for p in inbox.iterdir() if not p.name.startswith("."))


def _upload(client, tokens, name="IMG_0001.jpg", data=samples.JPEG):
    return client.post(
        "/api/upload",
        headers={TOKEN_HEADER: tokens.current},
        files={"file": (name, data, "image/jpeg")},
    )


def test_upload_saves_original_bytes(phone_client, tokens, settings):
    response = _upload(phone_client, tokens)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["bytes"] == len(samples.JPEG)
    assert re.fullmatch(r"\d{8}-\d{6}-IMG_0001\.jpg", body["saved"])
    assert (settings.inbox_dir / body["saved"]).read_bytes() == samples.JPEG


def test_same_name_gets_numbered_suffix(phone_client, tokens, settings):
    names = [_upload(phone_client, tokens).json()["saved"] for _ in range(3)]
    assert len(set(names)) == 3
    assert len(visible(settings.inbox_dir)) == 3


@pytest.mark.parametrize(
    ("data", "ext"),
    [
        (samples.JPEG, "jpg"),
        (samples.PNG, "png"),
        (samples.GIF, "gif"),
        (samples.WEBP, "webp"),
        (samples.HEIC, "heic"),
        (samples.HEIF, "heif"),
    ],
)
def test_allowed_types_detected_by_bytes(data, ext):
    assert image_extension(data[:512]) == ext


@pytest.mark.parametrize("data", [samples.TEXT, samples.PDF, samples.AVIF, b""])
def test_other_types_are_not_allowed(data):
    assert image_extension(data[:512]) is None


def test_extension_comes_from_bytes_not_name(phone_client, tokens):
    saved = _upload(phone_client, tokens, name="holiday.jpg", data=samples.PNG).json()["saved"]
    assert saved.endswith("-holiday.png")


@pytest.fixture
def small_limit_client(settings, tokens):
    return TestClient(create_phone_app(replace(settings, max_file_mb=1), tokens))


def test_file_over_limit_is_rejected_with_413(small_limit_client, tokens, settings):
    big = samples.JPEG + b"\x00" * (1024 * 1024)
    response = _upload(small_limit_client, tokens, data=big)
    assert response.status_code == 413
    assert visible(settings.inbox_dir) == []


def test_file_exactly_at_limit_is_accepted(small_limit_client, tokens):
    exact = samples.JPEG + b"\x00" * (1024 * 1024 - len(samples.JPEG))
    response = _upload(small_limit_client, tokens, data=exact)
    assert response.status_code == 200
    assert response.json()["bytes"] == 1024 * 1024


def test_non_image_is_rejected_with_415(phone_client, tokens, settings):
    response = _upload(phone_client, tokens, name="evil.jpg", data=samples.TEXT)
    assert response.status_code == 415
    assert visible(settings.inbox_dir) == []


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("IMG_0001.JPG", "IMG_0001"),
        ("../../etc/passwd.png", "passwd"),
        ("C:\\Users\\me\\holiday pic!.heic", "holidaypic"),
        ("noext", "noext"),
        ("", "photo"),
        (None, "photo"),
        (".hidden", "photo"),
    ],
)
def test_safe_stem_sanitises(original, expected):
    assert safe_stem(original) == expected
