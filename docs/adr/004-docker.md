# ADR 004 : conteneuriser LogiAI (API + page web) avec Docker Compose

**Statut :** accepté · **Date :** 2026-11-11 · **Atelier :** 5

## Contexte

Jusqu'à l'Atelier 4, LogiAI ne tournait que sur la machine du développeur : bonne version de
Python dans `.venv`, `.env` créé à la main, modèle entraîné localement, deux terminaux
(`uvicorn` et `python -m http.server 5500`). On veut une application qui démarre avec une
seule commande (`docker compose up -d --build`) sur n'importe quel poste équipé de Docker.

Architecture retenue : deux services sur un réseau Docker.

```
navigateur ──► :8080 web (Nginx) ──/api/──► api:8000 (FastAPI/uvicorn)
             └► :8001 ───────────────────────► api:8000   (accès direct, dev)
```

Deux décisions demandaient un arbitrage.

---

## Décision 1 : le modèle est copié dans l'image **et** monté en volume

- **Dans l'image (`COPY models/`)** : l'image `logiai:1.0` est autonome. `docker run` seul
  (Activité 1) fonctionne, et l'image pourra être poussée dans un registre et déployée sans
  le dossier `models/` à côté.
- **Monté en volume dans Compose (`./models:/app/models`, idem `./data`)** : en développement,
  le bind mount masque la copie de l'image. Après `python -m logiai.train`, un simple
  `docker compose restart api` charge le nouveau modèle, sans reconstruire l'image.

**Ce que l'autre option ferait perdre :**

- *Volume seul (pas de COPY)* : l'image ne serait plus autonome ; sans le dossier `models/`
  sur l'hôte, l'API démarre sans modèle et `/v1/predict` répond 503. On perd la traçabilité
  « une image = un modèle ».
- *COPY seul (pas de volume)* : à chaque ré-entraînement il faudrait `docker compose up -d
  --build` (rebuild des dernières couches, ~quelques secondes grâce au cache, mais un pas de
  plus et un risque d'oublier).

**Conséquence assumée :** en développement, le modèle utilisé est celui du disque, pas celui
de l'image. Pour la production, on retirerait le volume et on taguerait l'image avec la
version du modèle (`logiai:1.0-model1.0`). Le volume concerne le modèle et les données,
**pas** le code : une modification de `logiai/` exige toujours `--build`.

---

## Décision 2 : publier 8080 **et** 8001

- `8080:80` (web) est le point d'entrée normal : la page et `/api/` sur la même origine,
  donc pas de CORS.
- `8001:8000` (api) est publié **pour le développement** : Swagger (`/docs`), tests `curl`
  directs, et diagnostic quand Nginx renvoie 502 (« est-ce l'API ou le proxy ? »).

**Ce que l'autre option ferait perdre / risquer :**

- *8080 seulement* : surface d'attaque réduite (un seul point d'entrée, que l'on pourrait
  plus tard équiper de TLS, rate limiting, journaux centralisés). Mais `/docs` n'est plus
  joignable directement : on passe par `http://localhost:8080/api/docs` (qui nécessiterait
  `root_path="/api"` côté FastAPI pour que Swagger trouve `openapi.json`) ou par
  `docker compose exec`.
- *Garder 8001* : un visiteur qui contourne Nginx atteint l'API directement. Ce n'est **pas**
  une faille d'authentification (la clé est vérifiée par FastAPI, pas par Nginx : 401 sans
  clé sur les deux ports), mais tout ce qu'on ajouterait plus tard dans Nginx (limites de
  débit, filtrage, en-têtes de sécurité) serait contourné, et `/docs` expose le contrat de
  l'API.

**Conséquence assumée :** acceptable en poste de développement local. En production, on
supprimerait `ports:` du service `api` (il resterait joignable par `web` via le réseau
Docker) et on ne publierait que le port de Nginx.

---

## Autres choix notés

- `.env` n'est jamais copié dans l'image (`.dockerignore`) ; il est lu par Compose via
  `env_file` au démarrage. `/health` expose `auth_configured` (booléen) pour diagnostiquer
  une clé absente sans jamais afficher sa valeur.
- `/health` reste public : c'est lui que le healthcheck interroge ; protégé, il renverrait
  401 et l'API ne serait jamais *healthy*.
- `depends_on: condition: service_healthy` : Nginx ne démarre qu'une fois l'API prête.
- Dépendances d'exécution figées dans `requirements.txt` (même scikit-learn que celui qui a
  écrit `model.joblib`) ; outils de test et Streamlit déplacés dans `requirements-dev.txt`
  pour ne pas alourdir l'image.
- L'API tourne avec un utilisateur non-root (`USER logiai`).
