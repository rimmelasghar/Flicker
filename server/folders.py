"""Where photos are saved: a folder inside the inbox, chosen on the laptop.

The container only sees the folder mounted at /inbox (INBOX_DIR), so the
choice is always a sub-folder of it (or the inbox itself). The choice is
stored as a relative path in the data folder and survives restarts.
"""

import json
import os
import re
from pathlib import Path, PurePosixPath

from fastapi import HTTPException, status

CHOICE_FILE = "save-folder.json"
MAX_LISTED = 500
# New folder names: no slashes, nothing hidden, nothing odd.
FOLDER_NAME = re.compile(r"^[A-Za-z0-9 _()\-][A-Za-z0-9 _().\-]{0,63}$")


def _bad(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


class FolderStore:
    def __init__(self, inbox: Path, data_dir: Path) -> None:
        self.root = inbox.resolve()
        self._file = data_dir / CHOICE_FILE
        self._relative = self._load()

    # -- the current choice ------------------------------------------------

    @property
    def relative(self) -> str:
        """Chosen folder relative to the inbox, "" for the inbox itself."""
        return self._relative

    def destination(self) -> Path:
        """Folder to save into now. Re-created if it was deleted meanwhile."""
        try:
            path = self.resolve(self._relative)
        except HTTPException:
            return self.root
        path.mkdir(parents=True, exist_ok=True)
        return path

    def choose(self, relative: str) -> str:
        path = self.resolve(relative)
        if not path.is_dir():
            raise _bad("folder does not exist")
        self._relative = self._to_relative(path)
        self._file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"path": self._relative}))
        os.replace(tmp, self._file)
        return self._relative

    # -- browsing ----------------------------------------------------------

    def resolve(self, relative: str) -> Path:
        """Absolute path for a relative one, refusing anything outside the
        inbox (.., absolute paths, symlinks out) or hidden."""
        parts = PurePosixPath(relative.replace("\\", "/")).parts
        if any(p in ("..", "/") or p.startswith(".") for p in parts):
            raise _bad("invalid folder")
        path = self.root.joinpath(*parts).resolve()
        if not path.is_relative_to(self.root):
            raise _bad("folder is outside the inbox")
        return path

    def list(self, relative: str) -> list[str]:
        path = self.resolve(relative)
        if not path.is_dir():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "folder not found")
        names = []
        try:
            entries = list(os.scandir(path))
        except PermissionError as exc:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "folder not readable") from exc
        for entry in entries:
            if entry.name.startswith(".") or not _is_visible_dir(entry, self.root):
                continue
            names.append(entry.name)
        return sorted(names, key=str.casefold)[:MAX_LISTED]

    def create(self, parent: str, name: str) -> str:
        name = name.strip()
        if not FOLDER_NAME.match(name):
            raise _bad("use letters, digits, spaces, - _ ( ) . (max 64, not starting with .)")
        path = self.resolve(parent) / name
        try:
            path.mkdir()
        except FileExistsError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "folder already exists") from exc
        return self._to_relative(path)

    # -- helpers -----------------------------------------------------------

    def _to_relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix() if path != self.root else ""

    def _load(self) -> str:
        try:
            relative = json.loads(self._file.read_text())["path"]
            if self.resolve(relative).is_dir():
                return self._to_relative(self.resolve(relative))
        except (OSError, ValueError, KeyError, TypeError, HTTPException):
            pass
        return ""


def _is_visible_dir(entry: os.DirEntry, root: Path) -> bool:
    try:
        if not entry.is_dir():
            return False
        # Symlinked folders are fine only if they stay inside the inbox.
        return Path(entry.path).resolve().is_relative_to(root)
    except OSError:
        return False
