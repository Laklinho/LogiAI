import pytest

VALID = {
    "distance_km": 120.0,
    "poids_kg": 450.0,
    "heure_depart": 17,
    "pluie_mm": 8.0,
    "trafic_index": 7.5,
    "nb_arrets": 4,
    "type_vehicule": "camion",
}

CAS_LIMITES = [
    # Distance
    ("distance_min_invalide", "distance_km", 0.9, 422),
    ("distance_min_valide", "distance_km", 1, 200),
    ("distance_max_valide", "distance_km", 1000, 200),
    ("distance_max_invalide", "distance_km", 1000.1, 422),

    # Poids
    ("poids_min_invalide", "poids_kg", 0, 422),
    ("poids_min_valide", "poids_kg", 0.1, 200),
    ("poids_max_valide", "poids_kg", 40000, 200),
    ("poids_max_invalide", "poids_kg", 40000.1, 422),

    # Heure
    ("heure_min_invalide", "heure_depart", -1, 422),
    ("heure_min_valide", "heure_depart", 0, 200),
    ("heure_max_valide", "heure_depart", 23, 200),
    ("heure_max_invalide", "heure_depart", 24, 422),
    ("heure_decimale", "heure_depart", 11.5, 422),

    # Pluie
    ("pluie_min_invalide", "pluie_mm", -0.1, 422),
    ("pluie_min_valide", "pluie_mm", 0, 200),
    ("pluie_max_valide", "pluie_mm", 200, 200),
    ("pluie_max_invalide", "pluie_mm", 200.1, 422),

    # Trafic
    ("trafic_min_invalide", "trafic_index", -0.1, 422),
    ("trafic_min_valide", "trafic_index", 0, 200),
    ("trafic_max_valide", "trafic_index", 10, 200),
    ("trafic_max_invalide", "trafic_index", 10.1, 422),

    # Arrêts
    ("arrets_min_invalide", "nb_arrets", -1, 422),
    ("arrets_min_valide", "nb_arrets", 0, 200),
    ("arrets_max_valide", "nb_arrets", 50, 200),
    ("arrets_max_invalide", "nb_arrets", 51, 422),
]


@pytest.mark.parametrize("nom, champ, valeur, attendu", CAS_LIMITES)
def test_limites(client, headers_user, nom, champ, valeur, attendu):
    livraison = {**VALID, champ: valeur}

    response = client.post(
        "/v1/predict",
        json=livraison,
        headers=headers_user,
    )

    assert response.status_code == attendu