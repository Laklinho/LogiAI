import pytest
from fastapi.testclient import TestClient

from logiai import config
from logiai.api.main import app

CLE_USER = "cle-test-user"
CLE_ADMIN = "cle-test-admin"


@pytest.fixture(autouse=True)
def cles_de_test(monkeypatch):
    """Les tests ne dépendent pas du .env de la machine : clés fixées ici."""
    monkeypatch.setattr(config, "API_KEY", CLE_USER)
    monkeypatch.setattr(config, "ADMIN_KEY", CLE_ADMIN)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers_user():
    return {"X-API-Key": CLE_USER}


@pytest.fixture
def headers_admin():
    return {"X-API-Key": CLE_ADMIN}
