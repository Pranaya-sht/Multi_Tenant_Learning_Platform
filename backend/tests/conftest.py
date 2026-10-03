import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.support import api as api
from tests.support import database as database


@pytest.fixture
def settings():
    return Settings(_env_file=None, jwt_secret="test-secret-with-at-least-thirty-two-characters")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client
