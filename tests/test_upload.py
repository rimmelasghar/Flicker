import re

import pytest

from server.auth import TOKEN_HEADER
from server.upload import image_extension, safe_stem
from tests import samples


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
    assert len(list(settings.inbox_dir.iterdir())) == 3


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


def test_non_image_is_rejected_with_415(phone_client, tokens, settings):
    response = _upload(phone_client, tokens, name="evil.jpg", data=samples.TEXT)
    assert response.status_code == 415
    assert list(settings.inbox_dir.iterdir()) == []


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
