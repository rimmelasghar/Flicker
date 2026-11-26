"""Pairing token: creation, persistence and rotation."""

import os
import secrets
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import Header, HTTPException, status

TOKEN_FILE = "token"
TOKEN_BYTES = 32
TOKEN_HEADER = "X-Flick-Token"


class TokenStore:
    """Holds the current pairing token, persisted in the data folder.

    Shared by the phone and pairing listeners, so a rotation takes effect
    on both immediately.
    """

    def __init__(self, data_dir: Path) -> None:
        self._path = data_dir / TOKEN_FILE
        data_dir.mkdir(parents=True, exist_ok=True)
        token = self._path.read_text().strip() if self._path.is_file() else ""
        self._token = token or self._save_new()

    @property
    def current(self) -> str:
        return self._token

    def rotate(self) -> str:
        """Replace the token; every paired phone must scan the QR code again."""
        self._token = self._save_new()
        return self._token

    def _save_new(self) -> str:
        token = secrets.token_urlsafe(TOKEN_BYTES)
        tmp = self._path.with_suffix(".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(token)
        os.replace(tmp, self._path)
        return token


def token_guard(tokens: TokenStore) -> Callable[[str | None], None]:
    """FastAPI dependency that rejects requests without the current token."""

    def require_token(
        x_flick_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
    ) -> None:
        expected = tokens.current.encode()
        given = (x_flick_token or "").encode()
        if not secrets.compare_digest(given, expected):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid token")

    return require_token
