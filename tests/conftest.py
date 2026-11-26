import pytest
from fastapi.testclient import TestClient

from server.auth import TokenStore
from server.config import Settings
from server.main import create_phone_app


@pytest.fixture
def settings(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return Settings(host_ip="192.168.1.50", data_dir=tmp_path / "data", inbox_dir=inbox)


@pytest.fixture
def tokens(settings):
    return TokenStore(settings.data_dir)


@pytest.fixture
def phone_client(settings, tokens):
    return TestClient(create_phone_app(settings, tokens))
