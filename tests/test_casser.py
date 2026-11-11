import pytest

# Valid delivery data
VALID = {
    "distance_km": 120.0,
    "poids_kg": 450.0,
    "heure_depart": 17,
    "pluie_mm": 8.0,
    "trafic_index": 7.5,
    "nb_arrets": 4,
    "type_vehicule": "camion",
}

# Valid delivery without poids_kg
SANS_POIDS = {k: v for k, v in VALID.items() if k != "poids_kg"}

# Five invalid requests
CAS_REFUSES = [
    ("champ manquant", "/v1/predict", SANS_POIDS, 422),
    ("valeur absurde", "/v1/predict", {**VALID, "poids_kg": 99999}, 422),
    ("texte au lieu d'un nombre", "/v1/predict", {**VALID, "distance_km": "abc"}, 422),
    ("champ en trop", "/v1/predict", {**VALID, "couleur_camion": "rouge"}, 422),
    ("mauvaise route", "/v1/prediction", VALID, 404),
]

@pytest.mark.parametrize("description, url, corps, attendu", CAS_REFUSES)
def test_request_refuse(client, description, url, corps, attendu, headers_user):
    response = client.post(url, json=corps, headers=headers_user)
    assert response.status_code == attendu