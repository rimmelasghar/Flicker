"""Flick server entry point.

M0 placeholder: plain HTTP app with a health endpoint only. TLS, the
localhost pairing listener and the phone API arrive in M1.
"""

from fastapi import FastAPI

app = FastAPI(title="Flick")


@app.get("/api/health")
def health() -> dict[str, bool]:
    return {"ok": True}
