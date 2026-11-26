"""Pairing listener (port 8080, published to 127.0.0.1 only).

Shows the QR code that carries the pairing token to the phone. Only the
laptop can reach this port; Docker port publishing enforces that, since
client IPs are unreliable behind Docker Desktop.
"""

import logging
from pathlib import Path

import segno
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server import __version__
from server.auth import TokenStore
from server.config import PAIR_PORT, PHONE_PORT, Settings
from server.folders import FolderStore

log = logging.getLogger("flick")

# Reject other Host headers so a web page using DNS rebinding cannot
# read the token from this page.
LOCAL_HOSTS = ["localhost", "127.0.0.1"]
LOCAL_ORIGINS = {f"http://{host}:{PAIR_PORT}" for host in LOCAL_HOSTS}
NO_STORE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}
PAGE_DIR = Path(__file__).resolve().parent.parent / "pair"


def pairing_url(settings: Settings, token: str) -> str:
    return f"https://{settings.host_ip}:{PHONE_PORT}/#t={token}"


class NewFolder(BaseModel):
    parent: str = ""
    name: str


class FolderChoice(BaseModel):
    path: str


def create_pair_app(
    settings: Settings, tokens: TokenStore, folders: FolderStore | None = None
) -> FastAPI:
    app = FastAPI(title="Flick pairing", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)
    folders = folders or FolderStore(settings.inbox_dir, settings.data_dir)

    def display(relative: str) -> str:
        """Host path for the user, e.g. C:/Users/me/Desktop/Photos."""
        base = settings.inbox_label.rstrip("/\\") or "INBOX_DIR"
        return f"{base}/{relative}" if relative else base

    @app.get("/api/folders")
    def list_folders(path: str = "") -> dict[str, object]:
        relative = folders.resolve(path).relative_to(folders.root).as_posix()
        relative = "" if relative == "." else relative
        return {
            "path": relative,
            "display": display(relative),
            "folders": folders.list(relative),
            "selected": folders.relative,
        }

    @app.post("/api/folders")
    def create_folder(body: NewFolder, request: Request) -> dict[str, str]:
        _reject_cross_site(request)
        return {"path": folders.create(body.parent, body.name)}

    @app.get("/api/save-folder")
    def get_save_folder() -> dict[str, str]:
        return {"path": folders.relative, "display": display(folders.relative)}

    @app.put("/api/save-folder")
    def set_save_folder(body: FolderChoice, request: Request) -> dict[str, str]:
        _reject_cross_site(request)
        relative = folders.choose(body.path)
        log.info("photos will be saved to %s", display(relative))
        return {"path": relative, "display": display(relative)}

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/pair")

    @app.get("/pair", include_in_schema=False)
    def pair() -> FileResponse:
        return FileResponse(PAGE_DIR / "index.html", headers=NO_STORE)

    @app.get("/api/pair")
    def pair_info() -> JSONResponse:
        qr = segno.make(pairing_url(settings, tokens.current), error="m")
        body = {
            # omitsize adds a viewBox, so CSS scales the code instead of cropping it.
            "qr_svg": qr.svg_inline(border=2, omitsize=True, dark="#101828", light="#fff"),
            "phone_url": f"https://{settings.host_ip}:{PHONE_PORT}/",
            "host": settings.host_ip,
            "version": __version__,
        }
        return JSONResponse(body, headers=NO_STORE)

    @app.post("/api/token/rotate")
    def rotate(request: Request) -> dict[str, bool]:
        _reject_cross_site(request)
        tokens.rotate()
        log.info("pairing token rotated; all phones unpaired")
        return {"ok": True}

    app.mount("/pair-assets", StaticFiles(directory=PAGE_DIR), name="pair-assets")
    return app


def _reject_cross_site(request: Request) -> None:
    """Block form posts from other web pages open in the laptop browser."""
    site = request.headers.get("sec-fetch-site")
    origin = request.headers.get("origin")
    if (site and site not in ("same-origin", "none")) or (origin and origin not in LOCAL_ORIGINS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cross-site request refused")
