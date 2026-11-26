import re

import pytest

from server.auth import TOKEN_HEADER
from server.upload import split_name

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _upload(client, tokens, name="IMG_0001.jpg", data=JPEG):
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
    assert body["bytes"] == len(JPEG)
    assert re.fullmatch(r"\d{8}-\d{6}-IMG_0001\.jpg", body["saved"])
    assert (settings.inbox_dir / body["saved"]).read_bytes() == JPEG


def test_same_name_gets_numbered_suffix(phone_client, tokens, settings):
    names = [_upload(phone_client, tokens).json()["saved"] for _ in range(3)]
    assert len(set(names)) == 3
    assert len(list(settings.inbox_dir.iterdir())) == 3


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("IMG_0001.JPG", ("IMG_0001", "jpg")),
        ("../../etc/passwd.png", ("passwd", "png")),
        ("C:\\Users\\me\\holiday pic!.heic", ("holidaypic", "heic")),
        ("noext", ("noext", "bin")),
        ("", ("photo", "bin")),
        (None, ("photo", "bin")),
        (".hidden", ("photo", "hidden")),
    ],
)
def test_split_name_sanitises(original, expected):
    assert split_name(original) == expected
