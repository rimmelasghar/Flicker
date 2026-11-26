"""Flick server entry point: builds the apps and starts the listeners."""

import asyncio
import logging
from typing import Annotated

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, File, UploadFile

from server import __version__
from server.auth import TokenStore, token_guard
from server.certs import ensure_certificate
from server.config import PAIR_PORT, PHONE_PORT, Settings, load_settings
from server.pairing import create_pair_app
from server.upload import save_upload


def create_phone_app(settings: Settings, tokens: TokenStore) -> FastAPI:
    """App served to the phone over HTTPS on the LAN."""
    app = FastAPI(title="Flick", docs_url=None, redoc_url=None, openapi_url=None)

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
        saved = save_upload(file.file, file.filename, settings.inbox_dir)
        return {"ok": True, "saved": saved.name, "bytes": saved.size}

    app.include_router(protected)
    return app


async def serve(settings: Settings) -> None:
    cert_path, key_path = ensure_certificate(settings.data_dir, settings.host_ip)
    tokens = TokenStore(settings.data_dir)
    phone = uvicorn.Server(
        uvicorn.Config(
            create_phone_app(settings, tokens),
            host="0.0.0.0",
            port=PHONE_PORT,
            ssl_certfile=cert_path,
            ssl_keyfile=key_path,
        )
    )
    pair = uvicorn.Server(
        uvicorn.Config(create_pair_app(settings, tokens), host="0.0.0.0", port=PAIR_PORT)
    )
    await asyncio.gather(phone.serve(), pair.serve())


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    asyncio.run(serve(load_settings()))


if __name__ == "__main__":
    main()
