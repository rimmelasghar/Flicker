"""Pairing listener (port 8080, published to 127.0.0.1 only).

Shows the QR code that carries the pairing token to the phone. Only the
laptop can reach this port; Docker port publishing enforces that, since
client IPs are unreliable behind Docker Desktop.
"""

import html

import segno
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.auth import TokenStore
from server.config import PHONE_PORT, Settings

# Reject other Host headers so a web page using DNS rebinding cannot
# read the token from this page.
LOCAL_HOSTS = ["localhost", "127.0.0.1"]
NO_STORE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flick pairing</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 32rem; margin: 2rem auto;
         padding: 0 1rem; color: #1d1d1f; background: #fff; text-align: center; }}
  .qr svg {{ width: 18rem; height: 18rem; }}
  code {{ word-break: break-all; font-size: .85rem; }}
  ol {{ text-align: left; }}
</style>
</head>
<body>
<h1>Pair your phone</h1>
<div class="qr">{qr}</div>
<ol>
  <li>Scan this code with the phone camera (phone on the same Wi-Fi).</li>
  <li>Accept the certificate warning once.</li>
  <li>The phone is paired; it stays paired across restarts.</li>
</ol>
<p>Phone address: <code>{lan_url}</code></p>
</body>
</html>
"""


def pairing_url(settings: Settings, token: str) -> str:
    return f"https://{settings.host_ip}:{PHONE_PORT}/#t={token}"


def create_pair_app(settings: Settings, tokens: TokenStore) -> FastAPI:
    app = FastAPI(title="Flick pairing", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=LOCAL_HOSTS)

    @app.get("/pair", response_class=HTMLResponse)
    def pair() -> HTMLResponse:
        qr = segno.make(pairing_url(settings, tokens.current), error="m")
        page = PAGE.format(
            qr=qr.svg_inline(scale=8, border=2),
            lan_url=html.escape(f"https://{settings.host_ip}:{PHONE_PORT}/"),
        )
        return HTMLResponse(page, headers=NO_STORE)

    return app
