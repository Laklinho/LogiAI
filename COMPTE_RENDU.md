# Compte rendu : TP API LogiAI

**Noms :** Abdellah LAKLI, Yaasmina RHARI

## 1. Environnement et premiers tests
- Sortie de `python -m pytest` au départ (collez-la) :

```
FAILED tests/test_api.py::test_predict_valide_renvoie_200 - assert 422 == 200
FAILED tests/test_api.py::test_predict_forme_de_la_reponse - AssertionError: assert {'detail'} == {'alerte', 'm...ard', 'seuil'}
FAILED tests/test_api.py::test_predict_probabilite_entre_0_et_1 - KeyError: 'probabilite_retard'
FAILED tests/test_api.py::test_predict_trajet_risque_plus_eleve_que_trajet_facile - KeyError: 'probabilite_retard'
FAILED tests/test_api.py::test_modele_absent_renvoie_503 - assert 422 == 503
=========================== 5 failed, 8 passed, 1 warning in 5.20s ===========================
```

- Résultats de `python -m logiai.train` :

| Mesure | Valeur |
|---|---|
| Accuracy de la baseline (toujours « à l'heure ») | 72,6 % |
| Accuracy du modèle | 77,4 % |
| Rappel du modèle | 46,4 % |
| Précision du modèle | 61,7 % |
| AUC | 0,769 |

Le modèle ne gagne que 5 points d'accuracy sur la baseline, car 72,6 % des livraisons sont à l'heure : répondre toujours « à l'heure » est déjà « bon » en accuracy, mais ne détecte aucun retard. Le chiffre utile est le **rappel** : sur 100 livraisons réellement en retard, le modèle en détecte environ **46**.

- À quoi sert l'API si le rappel est faible ? Même à 46 %, le dispatcher est prévenu pour presque une livraison en retard sur deux, alors qu'il n'en voyait aucune avant. Quand une alerte sort, elle est juste dans environ 62 % des cas (précision) : elle vaut la peine d'être regardée. L'API ne remplace pas son jugement, elle lui signale les livraisons à surveiller en priorité (prévenir le client, changer de véhicule, avancer le départ).

- Pourquoi certains tests qui attendent un 422 passent-ils déjà, alors que rien n'est écrit ?
  Le schéma ne contenait que `distance_km` et refuse les champs inconnus (`extra="forbid"`). Toute requête contenant `poids_kg`, `pluie_mm`, etc. était donc refusée avec un 422, **même une livraison valide**. Les tests « distance négative », « pluie 500 mm », « véhicule avion »… obtenaient bien un 422, mais pour la mauvaise raison (champ inconnu), pas parce que la valeur testée était contrôlée. C'est le test de succès `test_predict_valide_renvoie_200` qui les démasque : il attend 200 et reçoit 422. Leçon : un test vert ne prouve rien tant qu'on ne sait pas *pourquoi* il passe ; il faut toujours tester aussi le cas qui doit réussir, et vérifier qu'un test devient rouge quand on casse le code.

## 2. Mon schéma
- Mes bornes et leur justification physique (une ligne par variable) :

| Variable | Min | Max | Pourquoi |
|---|---|---|---|
| distance_km | 1 | 1000 | Une livraison fait au moins 1 km ; 1000 km correspond à une longue journée de route d'un camion. |
| poids_kg | > 0 | 40 000 | Un colis pèse forcément quelque chose ; 40 t est le poids maximal autorisé d'un poids lourd. |
| heure_depart | 0 | 23 | Une heure de la journée, en entier (24 n'existe pas, c'est 0). |
| pluie_mm | 0 | 200 | Pas de pluie négative ; 200 mm sur un trajet est déjà un épisode exceptionnel (orage extrême), 500 mm est irréaliste. |
| trafic_index | 0 | 10 | Échelle définie par le contrat : 0 = fluide, 10 = saturé. |
| nb_arrets | 0 | 50 | 0 = livraison directe ; une tournée réelle dépasse rarement 50 arrêts. |

`type_vehicule` est un `Literal["moto", "fourgon", "camion"]` : tout autre texte est refusé.
Les bornes sont **physiques**, pas le min et le max de `livraisons.csv` : sinon une livraison réelle un peu plus longue que celles des données serait refusée à tort.

## 3. Ma fonction predict()

```python
@app.post("/v1/predict", response_model=PredictionOut)
def predict(livraison: Livraison):
    predictor = state.get("predictor")
    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Modèle non chargé : lancez 'python -m logiai.train' puis redémarrez l'API.",
        )
    return PredictionOut(**predictor.predict(livraison.model_dump()))
```

## 4. Quatre requêtes
| Requête | Code obtenu | Pourquoi |
|---|---|---|
| livraison normale | 200 | Valeurs valides : la prédiction est renvoyée (probabilité 0,732, alerte = true). |
| distance_km = -5 | 422 | Hors des bornes du schéma (`ge=1`) : FastAPI refuse avant d'appeler `predict()`. |
| type_vehicule = "avion" | 422 | Pas dans le `Literal` des valeurs autorisées. |
| modèle absent (supprimez models/ et relancez) | 503 | `/health` répond 200 avec `model_loaded: false` ; `/v1/predict` répond 503 car `state` ne contient pas de predictor. |

## 5. Questions de compréhension
1. **Pourquoi charge-t-on le modèle au démarrage et pas à chaque requête ?**
   Lire et désérialiser `model.joblib` depuis le disque prend du temps et de la mémoire. Le faire à chaque requête rendrait chaque réponse lente et ferait s'effondrer le serveur sous la charge. Chargé une seule fois dans `lifespan`, le modèle reste en mémoire et chaque prédiction prend quelques millisecondes.

2. **Qui écrit le contrôle « pluie <= 100 », et où est-il écrit ?**
   C'est nous, les développeurs de l'API, qui l'écrivons, dans le schéma Pydantic `Livraison` (`logiai/api/schemas.py`), avec `Field(le=...)`. Dans notre schéma, la borne est `le=200`. FastAPI applique ce contrôle automatiquement avant d'appeler `predict()` et renvoie un 422 si la valeur dépasse la borne.

3. **Différence entre 422 et 503 ?**
   422 est une erreur **du client** : la requête est invalide (valeur hors bornes, champ manquant) ; renvoyer la même requête échouera toujours, il faut la corriger. 503 est une erreur **du serveur** : la requête est correcte mais le service est momentanément indisponible (modèle non chargé) ; la même requête marchera une fois le problème réglé.

4. **Pourquoi une route `/v1/predict` plutôt que `/predict` ?**
   `/v1` est la version du contrat. Si on change un jour les champs ou la forme de la réponse, on publie `/v2/predict` à côté, et les clients existants (Streamlit, appli mobile) continuent de fonctionner avec `/v1` le temps de migrer.

5. **Que se passerait-il si la distance était déclarée `int` ?**
   Une distance à virgule comme 120,5 km serait refusée avec un 422, alors qu'elle est parfaitement valide. Le type doit correspondre à la réalité physique : une distance est un nombre réel.

## 6. Décision : modèle absent
Répondre 503 ou refuser de démarrer ? Qu'est-ce que chaque option fait perdre ?

**Notre choix : A, démarrer quand même et répondre 503.**

- **Option A (démarrer + 503)** : le service reste joignable. `/health` répond `model_loaded: false`, donc celui qui supervise voit immédiatement *quel* est le problème (le modèle, pas le réseau ni le serveur). Les clients reçoivent un message clair qui dit quoi faire, et dès que le modèle est régénéré et le serveur relancé, tout repart. **Ce qu'on perd** : l'API « a l'air » démarrée alors qu'elle ne sait pas faire son travail principal ; si personne ne surveille `/health`, la panne peut passer inaperçue un moment.
- **Option B (refuser de démarrer)** : la panne est visible tout de suite, au déploiement. **Ce qu'on perd** : plus aucun endpoint ne répond, `/health` compris. Le superviseur voit seulement « service injoignable », sans savoir si c'est le réseau, le serveur ou le modèle, et les clients n'obtiennent aucun message explicatif.

L'option A donne un diagnostic précis et un comportement prévisible pour les clients ; c'est pour cela que nous l'avons retenue.

## 7. Lien de la pull request
https://github.com/Laklinho/LogiAI/pull/1
