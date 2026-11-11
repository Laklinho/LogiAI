# Compte rendu : conteneuriser et déployer LogiAI avec Docker (Atelier 5)

**Noms :** ✏️ ........  **Groupe :** ✏️ ........
**Branche :** `tp-docker` · **Pull request :** ✏️ (lien à ajouter après création) · **Tag :** `tp5`

> Compte rendu de l'Atelier 4 archivé dans `docs/comptes-rendus/atelier4.md`.
> Environnement : Windows 11, Docker 29.9.3 (moteur Linux, WSL2), Python 3.11.9.

---

## 0. Préparer : point de départ

- `docker --version` → `Docker version 29.9.3` ; `docker info` répond (OSType `linux`).
- `python -m pytest` sur `main` : **42 échecs / 55**. Causes et corrections (prérequis de l'atelier) :
  - les tests dépendaient des clés du `.env` local (absent sur un poste neuf) et `test_api.py`
    n'envoyait aucune clé → `tests/conftest.py` fixe désormais des clés de test (`monkeypatch`)
    et `test_api.py` envoie `X-API-Key` ;
  - `python-dotenv` était importé par `config.py` mais absent de `requirements.txt` → aurait
    donné `ModuleNotFoundError` dans le conteneur.
  - Après correction : **55 passed**.
- `models/model.joblib` et `models/model_info.json` présents. ⚠️ `models/` et `data/*.csv` sont
  dans `.gitignore` : après un `git clone`, il faut lancer `python -m logiai.dataset` puis
  `python -m logiai.train` **avant** le build, sinon `COPY models/ : not found`.

### Premier constat : ça ne marche que chez nous

| Ce que le projet suppose | Qui le garantit avant Docker | Qui le garantit avec Docker |
|---|---|---|
| Python 3.11 et des bibliothèques compatibles avec `model.joblib` | nous, avec `.venv` et `requirements.txt` (versions non figées) | l'image `python:3.11-slim` + `requirements.txt` figé |
| Le fichier `.env` avec les deux clés | nous | toujours nous (`.env` jamais dans l'image) ; `.env.example` documente le format et `/health` indique `auth_configured` |
| Un modèle entraîné dans `models/` | nous, avec `python -m logiai.train` | copié dans l'image au build (et monté en volume en dev) |
| Deux terminaux : `uvicorn`, puis `python -m http.server 5500` | nous | `docker compose up -d --build` |

**« Si je donne mon dossier à un camarade, il doit… »** installer la bonne version de Python,
créer un `.venv`, installer les dépendances (en espérant obtenir le même scikit-learn que celui
qui a écrit le modèle), créer son `.env`, entraîner le modèle, puis ouvrir deux terminaux.
Avec Docker : installer Docker Desktop, créer son `.env` (à partir de `.env.example`), et lancer
une seule commande.

---

## 1. Activité 1 : l'API seule dans un conteneur

### `.dockerignore`

```
.venv/
.venv_test/
venv/
.git/
.gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
build/
dist/
*.egg-info/
.env
.vscode/
.idea/
docs/
tests/
```

### `Dockerfile` (API)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 1. Dépendances d'abord : couche la plus lente, réutilisée tant que requirements.txt ne change pas
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 2. Le code, puis les données et le modèle (ce qui change le plus souvent en dernier)
COPY logiai/ ./logiai/
COPY data/ ./data/
COPY models/ ./models/

# Pour aller plus loin : l'API ne tourne pas en root
RUN useradd --create-home --uid 1000 logiai && chown -R logiai:logiai /app
USER logiai

ENV LOGIAI_HOME=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "logiai.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Écarts par rapport au modèle du sujet : utilisateur non-root (`USER logiai`, « pour aller plus
loin ») et `PYTHONUNBUFFERED=1` pour que les logs uvicorn arrivent sans délai dans
`docker logs`. `logiai/config.py` lit maintenant `LOGIAI_HOME` (sinon la variable ne servait à
rien) : `ROOT = Path(os.getenv("LOGIAI_HOME", <dossier du dépôt>))`.

### Construire, lancer, vérifier

```
docker build -t logiai:1.0 .                      # ~1 min 15 au premier build
docker images logiai
IMAGE        ID             DISK USAGE   CONTENT SIZE
logiai:1.0   d9595af47ef7        746MB          169MB

docker run -d --name logiai-api-test -p 8001:8000 --env-file .env logiai:1.0
docker ps
logiai-api-test   Up 4 seconds   0.0.0.0:8001->8000/tcp

curl.exe http://localhost:8001/health
{"status":"ok","model_loaded":true,"auth_configured":true}
```

| Requête `POST http://localhost:8001/v1/predict` (`livraison.json`) | Attendu | Obtenu |
|---|---|---|
| sans clé | 401 | **401** `{"detail":"API key missing"}` |
| fausse clé | 401 | **401** `{"detail":"Invalid API key"}` |
| clé de `.env` | 200 | **200** `{"probabilite_retard":0.732,"alerte":true,"seuil":0.4,"model_version":"1.0"}` |

Vérification : `docker exec logiai-api-test ls -a /app` → `data logiai models requirements.txt`,
**pas de `.env` dans l'image** ; `whoami` → `logiai`.

### Trois expériences pour casser le conteneur

| # | Expérience | Prévu | Obtenu | Explication |
|---|---|---|---|---|
| 1 | Sans `--env-file` | `/health` OK, `/v1/predict` refusé | `/health` → `{"status":"ok","model_loaded":true,"auth_configured":false}` ; predict avec la bonne clé → **401** `Invalid API key` | Le conteneur ne voit pas le disque de Windows : `.env` est exclu de l'image et n'est pas transmis, donc `API_KEY`/`ADMIN_KEY` valent `None` et toute clé est refusée (échec sûr). |
| 2 | Sans `-p 8001:8000` | `curl` échoue | conteneur **Up**, colonne PORTS = `8000/tcp` ; `curl` → exit 7 *Failed to connect* | `EXPOSE` ne fait que documenter le port ; sans `-p`, aucun port de l'hôte n'est relié au conteneur, joignable seulement depuis le réseau Docker. |
| 3 | uvicorn sur `--host 127.0.0.1` (image `logiai:test`, avec `-p`) | `curl` échoue malgré le port publié | conteneur Up, port publié ; `curl` → exit 52 *Empty reply from server* ; depuis l'intérieur (`docker exec … urlopen('http://127.0.0.1:8000/health')`) → 200 | `127.0.0.1` est le loopback **du conteneur** : le trafic relayé par Docker arrive sur l'interface réseau du conteneur, où personne n'écoute. Il faut `0.0.0.0`. |

---

## 2. TP sprint 1 : la page dans un conteneur Nginx

### `web/index.html` (une ligne)

```js
const API_URL = '/api/v1/predict';
```

### `nginx/default.conf`

```nginx
server {
    listen 80;
    server_name localhost;

    root /usr/share/nginx/html;
    index index.html;

    # La page : fichier statique servi par Nginx
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Les appels API : relayés au service "api" du réseau Docker.
    # Le slash final retire le préfixe : /api/v1/predict -> http://api:8000/v1/predict
    location /api/ {
        proxy_pass http://api:8000/;                                    # TODO 1
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;                        # TODO 2
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### `web/Dockerfile`

```dockerfile
FROM nginx:alpine

# Contexte de build = racine du projet : les chemins commencent par web/ et nginx/
COPY web/index.html /usr/share/nginx/html/index.html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
```

### Chemin de `/api/v1/predict`, de la page à FastAPI

1. La page, servie par `http://localhost:8080/`, appelle le **chemin relatif** `/api/v1/predict`
   → le navigateur l'envoie à `http://localhost:8080/api/v1/predict` (même origine).
2. Docker relaie le port 8080 de Windows vers le port 80 du conteneur `logiai-web`.
3. Nginx fait correspondre `location /api/` ; `proxy_pass http://api:8000/` (slash final) remplace
   le préfixe `/api/` par `/` → requête `POST http://api:8000/v1/predict`, avec les en-têtes
   d'origine (`X-API-Key` compris) plus `X-Real-IP` / `X-Forwarded-For`.
4. Le DNS interne du réseau Docker résout `api` vers l'IP du conteneur `logiai-api`.
5. uvicorn (à l'écoute sur `0.0.0.0:8000`) passe la requête à FastAPI : vérification de la clé,
   validation Pydantic, prédiction. La réponse refait le chemin inverse.

---

## 3. TP sprint 2 : Docker Compose

### `docker-compose.yml`

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    image: logiai:1.0
    container_name: logiai-api
    ports:
      - "8001:8000"              # TODO 1 : hôte:conteneur
    env_file:
      - .env                     # TODO 2 : les clés, lues au démarrage, jamais dans l'image
    environment:
      LOGIAI_HOME: /app
    volumes:
      - ./models:/app/models     # TODO 3 : modèle et données vus sans reconstruire l'image
      - ./data:/app/data
    healthcheck:                 # TODO 4 : pas de curl dans l'image slim -> python
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  web:
    build:
      context: .
      dockerfile: web/Dockerfile
    image: logiai-web:1.0
    container_name: logiai-web
    ports:
      - "8080:80"
    depends_on:                  # TODO 5 : attendre que l'API soit saine, pas seulement démarrée
      api:
        condition: service_healthy
```

### Valider, démarrer, vérifier

```
docker compose config --quiet        # OK
docker compose up -d --build
 Container logiai-api Started
 Container logiai-api Waiting
 Container logiai-api Healthy
 Container logiai-web Started        # web ne démarre qu'après "Healthy"

docker compose ps
logiai-api   Up 19 seconds (healthy)   0.0.0.0:8001->8000/tcp
logiai-web   Up 13 seconds             0.0.0.0:8080->80/tcp
```

### Étape 4 : test de bout en bout

- `http://localhost:8080` : page affichée ; avec la clé de `.env` et la livraison de
  `livraison.json` (120 km, 450 kg, 17 h, 8 mm, trafic 7,5, 4 arrêts, camion) → l'API répond
  **probabilité 73,2 %, alerte Oui** (vérifié par `curl` via Nginx ; ✏️ capture de la page à
  ajouter, clé masquée).
- `http://localhost:8001/docs` → 200 (Swagger) ; `http://localhost:8001/health` → 200.

### Étape 5 : les quatre codes par Nginx (`curl.exe`, port 8080)

| Requête | Code |
|---|---|
| `GET /api/health` | **200** `{"status":"ok","model_loaded":true,"auth_configured":true}` |
| `POST /api/v1/predict` sans clé | **401** `API key missing` |
| `POST /api/v1/predict` fausse clé | **401** `Invalid API key` |
| `POST /api/v1/predict` bonne clé | **200** `probabilite_retard 0.732, alerte true` |

### Étape 6 : onglet Network (F12)

- La requête part vers **`http://localhost:8080/api/v1/predict`** : même hôte, même port que la page.
- **Aucune requête `OPTIONS` préliminaire** (une seule ligne `POST`), contrairement à l'Atelier 4
  (page sur 5500, API sur 8000). Page et API partagent désormais la même origine
  (`http://localhost:8080`) : ce n'est plus une requête *cross-origin*, CORS ne s'applique pas,
  même avec l'en-tête personnalisé `X-API-Key`. Le middleware CORS de l'API ne sert plus ici.

### Étape 7 : observer

`docker compose logs --tail=30 api` (extrait) :

```
logiai-api  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
logiai-api  | INFO:     127.0.0.1:57918 - "GET /health HTTP/1.1" 200 OK          <- healthcheck
logiai-api  | INFO:     172.21.0.3:49146 - "GET /health HTTP/1.1" 200 OK         <- via Nginx
logiai-api  | INFO:     172.21.0.3:49150 - "POST /v1/predict HTTP/1.1" 401 Unauthorized
logiai-api  | INFO:     172.21.0.3:49172 - "POST /v1/predict HTTP/1.1" 200 OK
logiai-api  | INFO:     172.21.0.1:41900 - "GET /docs HTTP/1.1" 200 OK           <- direct 8001
```

On distingue trois appelants : `127.0.0.1` (le healthcheck, exécuté dans le conteneur),
`172.21.0.3` (le conteneur `web`, Nginx) et `172.21.0.1` (la passerelle du réseau Docker, donc
Windows via le port 8001). Le chemin reçu par FastAPI est `/v1/predict` : Nginx a bien retiré `/api`.

`docker stats --no-stream` :

| Conteneur | CPU | Mémoire | Réseau (in / out) | Processus (PIDs) |
|---|---|---|---|---|
| logiai-api | 0,26 % | 125,2 MiB / 15,44 GiB | 5,69 kB / 3,82 kB | 44 |
| logiai-web | 0,00 % | 16,1 MiB / 15,44 GiB | 5,81 kB / 5,37 kB | 21 |

L'API au repos consomme peu de CPU ; l'essentiel de la mémoire vient de pandas/scikit-learn chargés
avec le modèle. Les 44 PIDs sont surtout des threads (uvicorn, numpy/BLAS).

### Étape 8 : casser puis réparer

`docker compose stop api`, puis envoi d'une livraison depuis la page :

- la page reçoit **502 Bad Gateway** (page HTML générée par Nginx, `nginx/1.31.8`) : Nginx tourne,
  mais ne peut plus joindre `api:8000` ;
- elle affiche **« API injoignable ou requête bloquée par CORS. Consultez F12. »** : la réponse
  n'est pas du JSON, `reponse.json()` lève une exception et on tombe dans le `catch`. Le message
  est trompeur ici (ce n'est pas CORS) ; F12 montre bien le 502. Amélioration possible : tester
  `reponse.ok` / le `Content-Type` avant `json()` et afficher « API indisponible (502) ».
- `docker compose start api` → `Up (healthy)` après quelques secondes ; `/api/health` → 200,
  la page prédit de nouveau, **sans redémarrer Nginx**.

### Étape 9 : voir le volume

```
docker compose exec api ls -l /app/models
-rwxrwxrwx 1 root root 3537 Oct 28 16:13 model.joblib
-rwxrwxrwx 1 root root  367 Oct 28 16:13 model_info.json
```

(Sous Git Bash, préfixer par `MSYS_NO_PATHCONV=1`, sinon `/app/models` est converti en chemin Windows.)

- **Nouveau `model.joblib` entraîné sous Windows** : vu sans reconstruire l'image, car
  `./models` est un *bind mount* : le conteneur lit directement le dossier du disque, qui masque la
  copie figée dans l'image. Il suffit de `docker compose restart api`, car le modèle est chargé
  une seule fois au démarrage (`lifespan`).
- **Changement dans `logiai/`** : **pas** vu, le code n'est pas monté, il est copié dans l'image au
  build → `docker compose up -d --build`.

---

## 4. Décisions : ADR 004

Voir [`docs/adr/004-docker.md`](docs/adr/004-docker.md). Résumé :

1. **Modèle : COPY dans l'image + volume en dev.** L'image reste autonome (déployable seule) ;
   le volume évite un rebuild à chaque ré-entraînement.
2. **Ports : 8080 et 8001 en dev.** 8001 sert à Swagger et au diagnostic ; un visiteur qui
   contourne Nginx atteint l'API mais la clé reste vérifiée par FastAPI. En production, seul 8080.

---

## 5. Questions de compréhension

1. **Quelle différence entre une image et un conteneur ?**
   L'image est un modèle immuable (couches en lecture seule : Python, dépendances, code, données,
   modèle). Le conteneur est une instance en cours d'exécution de cette image : un processus isolé
   avec une fine couche inscriptible éphémère. Une image → plusieurs conteneurs ; supprimer un
   conteneur ne supprime pas l'image.

2. **Pourquoi le navigateur appelle-t-il `/api/v1/predict` et non `api:8000` ?**
   Le JavaScript s'exécute dans le navigateur, sur Windows, pas dans le réseau Docker : le nom
   `api` n'y est résolu par aucun DNS. Le chemin relatif part vers l'origine de la page
   (`localhost:8080`), et c'est Nginx, lui dans le réseau Docker, qui relaie vers `api:8000`.
   En prime : même origine, donc pas de CORS.

3. **Pourquoi `depends_on` seul ne suffit-il pas, et que change `service_healthy` ?**
   `depends_on` seul garantit l'ordre de **démarrage** des conteneurs, pas que l'API soit
   **prête** (chargement du modèle, uvicorn à l'écoute). Avec `condition: service_healthy`,
   Compose attend que le healthcheck de l'API réussisse avant de lancer `web`, ce qui évite des
   502 au démarrage.

4. **Pourquoi `.env` n'est-il jamais dans l'image, et comment arrive-t-il au conteneur ?**
   Une image se partage (registre, collègues) et chaque couche peut être inspectée : une clé copiée
   y resterait lisible. `.dockerignore` exclut `.env` du contexte de build ; les variables sont
   injectées **à l'exécution** par `--env-file .env` ou `env_file:` dans Compose.

5. **Pourquoi uvicorn doit-il écouter sur `0.0.0.0` dans le conteneur ?**
   `127.0.0.1` désigne le conteneur lui-même : seules les connexions internes seraient acceptées.
   Le trafic venant de l'hôte (port publié) ou de Nginx arrive par l'interface réseau du conteneur ;
   `0.0.0.0` écoute sur toutes les interfaces (expérience 3).

---

## 6. Pour aller plus loin (réalisé / restant)

- ✅ API exécutée avec un utilisateur non-root (`USER logiai`).
- ✅ Dépendances séparées : `requirements.txt` (exécution, versions figées) / `requirements-dev.txt`
  (pytest, httpx, Streamlit) → image plus légère.
- ✅ Clés longues et aléatoires dans `.env` (`secrets.token_urlsafe(32)`), `.env.example` commité.
- Restant insuffisant pour la production : pas de HTTPS, la clé tapée dans la page reste visible
  dans F12 et partagée par tous les utilisateurs, port 8001 publié, pas de limite de débit,
  modèle monté depuis le disque, pas de politique `restart:`, logs non centralisés.

---

## 7. Rendre

```
docker compose config      # valide
git status                 # .env n'apparaît pas (ignoré par .gitignore)
git commit -m "Atelier 5 : Docker, Nginx et Compose"
git push -u origin tp-docker
# PR tp-docker -> main, relecture, merge ; puis : git switch main, git pull, git tag tp5, git push --tags
```

Pour le relecteur :

```
cp .env.example .env               # puis mettre ses propres clés
pip install -r requirements.txt    # seulement pour générer données et modèle
python -m logiai.dataset           # models/ et data/*.csv ne sont pas dans Git
python -m logiai.train
docker compose up -d --build
```
