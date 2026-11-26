"""Flick server entry point: builds the apps and starts the listeners."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, File, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from server import __version__
from server.auth import TokenStore, token_guard
from server.certs import ensure_certificate
from server.config import PAIR_PORT, PHONE_PORT, Settings, load_settings
from server.folders import FolderStore
from server.pairing import create_pair_app
from server.ratelimit import RateLimiter
from server.upload import clean_temp, save_upload

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


def create_phone_app(
    settings: Settings,
    tokens: TokenStore,
    limiter: RateLimiter | None = None,
    folders: FolderStore | None = None,
) -> FastAPI:
    """App served to the phone over HTTPS on the LAN."""
    app = FastAPI(title="Flick", docs_url=None, redoc_url=None, openapi_url=None)
    limiter = limiter or RateLimiter()
    folders = folders or FolderStore(settings.inbox_dir, settings.data_dir)

    @app.middleware("http")
    async def rate_limit(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Runs before the body is read, so a flood is cheap to turn away.
        if request.url.path.startswith("/api/") and not limiter.allow():
            return JSONResponse(
                {"detail": "too many requests"},
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(limiter.retry_after())},
            )
        return await call_next(request)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    # Every route on this router needs the X-Flick-Token header.
    protected = APIRouter(prefix="/api", dependencies=[Depends(token_guard(tokens))])

    @protected.get("/ping")
    def ping() -> dict[str, bool | str]:
        return {"ok": True, "host": settings.host_ip, "version": __version__}

    @protected.post("/upload")
    def upload(file: Annotated[UploadFile, File()]) -> dict[str, bool | str | int]:
        saved = save_upload(
            file.file,
            file.filename,
            settings.inbox_dir,
            settings.max_file_bytes,
            folders.destination(),
            settings.max_video_bytes,
        )
        return {"ok": True, "saved": saved.name, "bytes": saved.size}

    app.include_router(protected)
    # Phone web page; mounted last so it never shadows the API routes.
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


async def serve(settings: Settings) -> None:
    cert_path, key_path = ensure_certificate(settings.data_dir, settings.host_ip)
    tokens = TokenStore(settings.data_dir)
    clean_temp(settings.inbox_dir)
    # One store for both listeners: a choice on the laptop applies at once.
    folders = FolderStore(settings.inbox_dir, settings.data_dir)
    phone = uvicorn.Server(
        uvicorn.Config(
            create_phone_app(settings, tokens, folders=folders),
            host="0.0.0.0",
            port=PHONE_PORT,
            ssl_certfile=cert_path,
            ssl_keyfile=key_path,
        )
    )
    pair = uvicorn.Server(
        uvicorn.Config(create_pair_app(settings, tokens, folders), host="0.0.0.0", port=PAIR_PORT)
    )
    await asyncio.gather(phone.serve(), pair.serve())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    asyncio.run(serve(load_settings()))


if __name__ == "__main__":
    main()
