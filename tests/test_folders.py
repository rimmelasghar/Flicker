import io
import os

import pytest
from fastapi import HTTPException

from server.folders import FolderStore
from server.upload import save_upload
from tests import samples


@pytest.fixture
def store(settings):
    (settings.inbox_dir / "Photos" / "2026").mkdir(parents=True)
    (settings.inbox_dir / "Work").mkdir()
    (settings.inbox_dir / ".secret").mkdir()
    (settings.inbox_dir / "notes.txt").write_text("x")
    return FolderStore(settings.inbox_dir, settings.data_dir)


def test_defaults_to_inbox_root(store, settings):
    assert store.relative == ""
    assert store.destination() == settings.inbox_dir.resolve()


def test_lists_visible_folders_only(store):
    assert store.list("") == ["Photos", "Work"]
    assert store.list("Photos") == ["2026"]


def test_choice_is_saved_and_survives_restart(store, settings):
    assert store.choose("Photos/2026") == "Photos/2026"
    again = FolderStore(settings.inbox_dir, settings.data_dir)
    assert again.relative == "Photos/2026"
    assert again.destination() == (settings.inbox_dir / "Photos" / "2026").resolve()


@pytest.mark.parametrize("bad", ["..", "../x", "Photos/../..", ".secret", "/etc", "Photos/.hidden"])
def test_paths_outside_or_hidden_are_refused(store, bad):
    with pytest.raises(HTTPException):
        store.resolve(bad)


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="no symlinks")
def test_symlink_out_of_inbox_is_not_listed_or_usable(store, settings, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (settings.inbox_dir / "escape").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not permitted here")
    assert "escape" not in store.list("")
    with pytest.raises(HTTPException):
        store.choose("escape")


def test_choose_missing_folder_is_refused(store):
    with pytest.raises(HTTPException):
        store.choose("Nope")


def test_create_folder(store, settings):
    assert store.create("Photos", "Flick drops") == "Photos/Flick drops"
    assert (settings.inbox_dir / "Photos" / "Flick drops").is_dir()
    with pytest.raises(HTTPException) as caught:
        store.create("Photos", "Flick drops")
    assert caught.value.status_code == 409


@pytest.mark.parametrize("name", ["", ".hidden", "a/b", "a\\b", "x" * 65, "con:x"])
def test_create_rejects_bad_names(store, name):
    with pytest.raises(HTTPException):
        store.create("", name)


def test_deleted_choice_is_recreated_on_save(store, settings):
    store.choose("Work")
    (settings.inbox_dir / "Work").rmdir()
    assert store.destination() == (settings.inbox_dir / "Work").resolve()
    assert (settings.inbox_dir / "Work").is_dir()


def test_corrupt_choice_file_falls_back_to_root(settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "save-folder.json").write_text("{not json")
    assert FolderStore(settings.inbox_dir, settings.data_dir).relative == ""


def test_upload_lands_in_chosen_folder(store, settings, tokens):
    store.choose("Photos")
    saved = save_upload(
        io.BytesIO(samples.JPEG), "a.jpg", settings.inbox_dir, 10**7, store.destination()
    )
    assert (settings.inbox_dir / "Photos" / saved.name).read_bytes() == samples.JPEG
    assert not (settings.inbox_dir / saved.name).exists()
