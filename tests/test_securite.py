
import pytest
from fastapi.testclient import TestClient

from logiai.api.main import app
from logiai import config


VALID = {
    "distance_km": 120,
    "poids_kg": 450,
    "heure_depart": 17,
    "pluie_mm": 8,
    "trafic_index": 7.5,
    "nb_arrets": 4,
    "type_vehicule": "camion",
}


@pytest.fixture(autouse=True)
def configure_test_keys(monkeypatch):
    monkeypatch.setattr(config, "API_KEY", "test-user-key")
    monkeypatch.setattr(config, "ADMIN_KEY", "test-admin-key")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_public(client):
    assert client.get("/health").status_code == 200


def test_predict_without_key(client):
    assert client.post("/v1/predict", json=VALID).status_code == 401


def test_predict_invalid_key(client):
    response = client.post(
        "/v1/predict",
        json=VALID,
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_predict_user_key(client):
    response = client.post(
        "/v1/predict",
        json=VALID,
        headers={"X-API-Key": "test-user-key"},
    )
    assert response.status_code == 200


def test_predict_admin_key(client):
    response = client.post(
        "/v1/predict",
        json=VALID,
        headers={"X-API-Key": "test-admin-key"},
    )
    assert response.status_code == 200


def test_model_info_without_key(client):
    assert client.get("/v1/model-info").status_code == 401


def test_model_info_invalid_key(client):
    response = client.get(
        "/v1/model-info",
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_model_info_user_forbidden(client):
    response = client.get(
        "/v1/model-info",
        headers={"X-API-Key": "test-user-key"},
    )
    assert response.status_code == 403


def test_model_info_admin_allowed(client):
    response = client.get(
        "/v1/model-info",
        headers={"X-API-Key": "test-admin-key"},
    )
    assert response.status_code == 200


def test_keys_not_configured(client, monkeypatch):
    monkeypatch.setattr(config, "API_KEY", None)
    monkeypatch.setattr(config, "ADMIN_KEY", None)

    response = client.post(
        "/v1/predict",
        json=VALID,
        headers={"X-API-Key": "test-user-key"},
    )
    assert response.status_code == 401
