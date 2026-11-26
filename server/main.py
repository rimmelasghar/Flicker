"""Flick server entry point: builds the apps and starts the listeners."""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI

from server.auth import TokenStore
from server.certs import ensure_certificate
from server.config import PHONE_PORT, Settings, load_settings


def create_phone_app(settings: Settings, tokens: TokenStore) -> FastAPI:
    """App served to the phone over HTTPS on the LAN."""
    app = FastAPI(title="Flick", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

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
    await phone.serve()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
    asyncio.run(serve(load_settings()))


if __name__ == "__main__":
    main()
