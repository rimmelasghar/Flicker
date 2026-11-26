import io
from dataclasses import replace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from server.auth import TOKEN_HEADER
from server.main import create_phone_app
from server.upload import save_upload, video_extension
from tests import samples

MB = 1024 * 1024


@pytest.mark.parametrize(
    ("data", "ext"), [(samples.MOV, "mov"), (samples.MP4, "mp4"), (samples.M4V, "mp4")]
)
def test_phone_video_formats_are_recognised(data, ext):
    assert video_extension(data[:512]) == ext


@pytest.mark.parametrize("data", [samples.MKV, samples.JPEG, samples.HEIC, samples.TEXT])
def test_other_formats_are_not_videos(data):
    assert video_extension(data[:512]) is None


def test_hevc_mp4_is_a_video_not_a_heif_photo(tmp_path):
    hevc_mp4 = b"\x00\x00\x00\x1cftypmp42\x00\x00\x00\x00mp42isomhevc" + samples.PAD
    saved = save_upload(io.BytesIO(hevc_mp4), "clip", tmp_path, MB)
    assert saved.name.endswith(".mp4")


def test_video_saved_with_detected_extension(tmp_path):
    saved = save_upload(io.BytesIO(samples.MOV), "IMG_0042.MOV", tmp_path, MB)
    assert saved.name.endswith("-IMG_0042.mov")
    assert (tmp_path / saved.name).read_bytes() == samples.MOV


def test_unsupported_video_container_is_415(tmp_path):
    with pytest.raises(HTTPException) as caught:
        save_upload(io.BytesIO(samples.MKV), "clip.mp4", tmp_path, MB)
    assert caught.value.status_code == 415


def test_videos_use_their_own_limit(tmp_path):
    video = samples.MP4 + b"\x00" * (2 * MB)
    saved = save_upload(io.BytesIO(video), "v.mp4", tmp_path, MB, max_video_bytes=3 * MB)
    assert saved.size == len(video)
    with pytest.raises(HTTPException) as caught:
        save_upload(io.BytesIO(video), "v.mp4", tmp_path, MB, max_video_bytes=2 * MB)
    assert caught.value.status_code == 413


def test_photo_limit_still_applies_to_photos(tmp_path):
    photo = samples.JPEG + b"\x00" * (2 * MB)
    with pytest.raises(HTTPException) as caught:
        save_upload(io.BytesIO(photo), "p.jpg", tmp_path, MB, max_video_bytes=100 * MB)
    assert caught.value.status_code == 413


def test_video_upload_over_http(settings, tokens):
    app = create_phone_app(replace(settings, max_file_mb=1, max_video_mb=5), tokens)
    client = TestClient(app)
    video = samples.MOV + b"\x00" * (3 * MB)
    response = client.post(
        "/api/upload",
        headers={TOKEN_HEADER: tokens.current},
        files={"file": ("IMG_0042.MOV", video, "video/quicktime")},
    )
    assert response.status_code == 200
    assert response.json()["saved"].endswith(".mov")
    assert response.json()["bytes"] == len(video)
