from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from server.auth import TOKEN_HEADER, token_guard


def _client(tokens):
    app = FastAPI()

    @app.get("/secret", dependencies=[Depends(token_guard(tokens))])
    def secret():
        return {"ok": True}

    return TestClient(app)


def test_guard_accepts_current_token(tokens):
    response = _client(tokens).get("/secret", headers={TOKEN_HEADER: tokens.current})
    assert response.status_code == 200


def test_guard_rejects_old_token_after_rotate(tokens):
    old = tokens.current
    tokens.rotate()
    response = _client(tokens).get("/secret", headers={TOKEN_HEADER: old})
    assert response.status_code == 401
