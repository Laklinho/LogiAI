import os

# Configure test keys before importing the application
os.environ["API_KEY"] = "cle-test-user"
os.environ["ADMIN_KEY"] = "cle-test-admin"

import pytest
from fastapi.testclient import TestClient
from logiai.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def headers_user():
    return {"X-API-Key": "cle-test-user"}


@pytest.fixture
def headers_admin():
    return {"X-API-Key": "cle-test-admin"}