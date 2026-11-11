
# ADR 004 — Déploiement de LogiAI avec Docker

## Contexte

LogiAI utilise deux services :
- FastAPI pour les prédictions de retard.
- Nginx pour servir l'interface web et transmettre les requêtes à l'API.

Docker Compose permet de démarrer ces services ensemble.

## Décision 1 — Stockage du modèle

Nous choisissons de monter le dossier `models/` en volume :

`./models:/app/models`

Ce choix permet de mettre à jour le fichier `model.joblib` sans reconstruire l'image Docker.

L'alternative serait de copier le modèle dans l'image avec `COPY`. Cela rendrait l'image autonome, mais chaque nouvel entraînement nécessiterait une reconstruction.

## Décision 2 — Publication des ports

Pour cet atelier, nous publions deux ports :
- `8080` pour accéder à Nginx et à l'interface web.
- `8001` pour tester directement FastAPI.

Cela facilite le développement et le débogage.

L'alternative consiste à publier uniquement `8080`. Elle réduit l'exposition directe de l'API, mais empêche son accès direct depuis Windows sans autre configuration.

## Conséquences

- L'API et l'interface disposent de conteneurs indépendants.
- Les clés API sont transmises via `.env` à l'exécution.
- Le modèle peut être remplacé sans reconstruire l'image.
- Un redémarrage de l'API peut être nécessaire pour charger le nouveau modèle en mémoire.
- Pour un déploiement public, il serait préférable de ne publier que le port Nginx.
