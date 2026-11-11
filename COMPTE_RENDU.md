# Compte rendu : tester, sécuriser et appeler l'API LogiAI

**Noms :** RHARI Yasmina  **Groupe :** ✏️ ........

> Légende : 📸 = capture d'écran à insérer (dossier `docs/img/`) · ✏️ = valeur à vérifier / compléter avec votre résultat réel.
> Captures retenues : uniquement la page web `http://localhost:5500/` (succès, erreur 422, erreur 401).

---

## 1. Casser son API (activité 1)

| Cas | Requête (corps ou URL) | Prévu | Obtenu |
|---|---|---|---|
| champ manquant | `POST /v1/predict` avec `SANS_POIDS` (VALID sans `poids_kg`) | 422 | 422 (`Field required` sur `poids_kg`) |
| valeur absurde | `POST /v1/predict` avec `{**VALID, "poids_kg": 99999}` | 422 | 422 ✏️ |
| texte au lieu d'un nombre | `POST /v1/predict` avec `{**VALID, "distance_km": "beaucoup"}` | 422 | 422 (`Input should be a valid number`) |
| champ en trop | `POST /v1/predict` avec `{**VALID, "couleur": "rouge"}` | 422 | ✏️ 200 par défaut (Pydantic ignore les champs inconnus) ; 422 si `extra="forbid"` est ajouté dans le schéma |
| mauvaise route | `POST /v1/predictt` (faute de frappe) | 404 | 404 (`Not Found`) |

- **Une requête acceptée alors qu'elle devait être refusée ? Laquelle ?**
  ✏️ Le cas « champ en trop » : par défaut, Pydantic ignore silencieusement les champs inconnus, donc l'API répond 200 alors que la requête est mal formée. Correction : ajouter `model_config = ConfigDict(extra="forbid")` dans le schéma, ce qui donne bien 422 ; le test reste dans `tests/test_casser.py`.
  *(Si vous avez constaté autre chose, remplacez cette réponse par votre cas réel.)*

---

## 2. Les 2 bugs (activité 2)

| Bug | Test qui l'a révélé | Comportement avant | Correction |
|---|---|---|---|
| 1 | ✏️ cas de `CAS_LIMITES` (champ, valeur, attendu 422) | ✏️ la valeur hors borne était acceptée (200 au lieu de 422) | ✏️ borne corrigée dans `schemas.py` (ex. `le=24` → `le=23`) |
| 2 | ✏️ cas de `CAS_LIMITES` (champ, valeur, attendu 200 ou 422) | ✏️ comportement incorrect à la borne | ✏️ borne corrigée dans `schemas.py` |

> Pour chaque bug, précisez : le **champ**, la **valeur envoyée**, le **code attendu**, le **code obtenu**, puis la ligne modifiée dans `schemas.py`.

- **Sortie de `python -m pytest` à la fin de l'activité 2 :**

```text
✏️ Collez ici la sortie réelle, par exemple :
============================= test session starts =============================
...
tests/test_casser.py  .....
tests/test_limites.py ....................
tests/test_api.py     .....
============================== N passed in X.XXs ==============================
```

---

## 3. La clé API (sprint 1)

- **Ma fonction `verify_api_key()`** (✏️ remplacez par votre code exact si différent) :

```python
def verify_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """Authentifie l'appelant et renvoie son rôle ("admin" ou "user")."""
    if x_api_key is None:
        raise HTTPException(status_code=401, detail="Clé API absente")
    if _egal(x_api_key, config.ADMIN_KEY):
        return "admin"
    if _egal(x_api_key, config.API_KEY):
        return "user"
    raise HTTPException(status_code=401, detail="Clé API invalide")


def require_admin(role: str = Depends(verify_api_key)) -> str:
    """Autorise uniquement le rôle admin ; sinon 403."""
    if role != "admin":
        raise HTTPException(status_code=403, detail="Droits administrateur requis")
    return role
```

`_egal` utilise `secrets.compare_digest` (comparaison en temps constant). Si `API_KEY` ou `ADMIN_KEY` valent `None` (`.env` non chargé), toute requête est refusée : l'API échoue de façon sûre.

| Requête | Code obtenu |
|---|---|
| `/v1/predict` sans clé | 401 |
| `/v1/predict` fausse clé | 401 |
| `/v1/predict` clé utilisateur | 200 |
| `/v1/model-info` clé utilisateur | 403 |
| `/v1/model-info` clé administrateur | 200 |
| `/health` sans clé | 200 |

- **Preuve que `.env` n'est pas dans Git (sortie de `git status`) :**

```text
✏️ Collez votre sortie réelle. Exemple attendu :
On branch tp-securite
Changes to be committed:
        new file:   .env.example
        new file:   COMPTE_RENDU.md
        modified:   logiai/api/main.py
        new file:   logiai/api/security.py
        ...
(aucune ligne .env)
```

---

## 4. Le client web (sprint 2)

- **Mon `fetch`** (fonction `appelerApi` dans `web/index.html`) :

```javascript
async function appelerApi(livraison, cle) {
  const reponse = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-API-Key": cle },
    body: JSON.stringify(livraison),   // l'objet devient du texte JSON
  });
  const corps = await reponse.json();  // la réponse, en objet
  return { status: reponse.status, corps };
}
```

- **Ce qui s'affiche :**

| Cas | Affichage |
|---|---|
| livraison normale | la probabilité de retard, avec l'alerte correspondante (HTTP 200) ✏️ |
| pluie de 500 mm | message d'erreur 422 lisible (champ `pluie_mm` hors borne) ✏️ |
| fausse clé | message « clé API invalide » (HTTP 401) ✏️ |

📸 **Livraison normale : la clé fonctionne (200)**

![Livraison normale](docs/img/09-page-normale.png)

📸 **Pluie de 500 mm : erreur 422**

![Pluie de 500 mm](docs/img/10-page-422.png)

📸 **Fausse clé : 401**

![Fausse clé](docs/img/11-page-401.png)

- **Expérience CORS (page servie sur le port 5501) : que disent la page et la console (F12) ? Pourquoi `curl` marche-t-il quand même ?**
  - **Page :** elle affiche « API injoignable » : le navigateur a bloqué la réponse, la page n'a donc rien reçu.
  - **Console (F12) :** message du type
    `Access to fetch at 'http://localhost:8000/v1/predict' from origin 'http://localhost:5501' has been blocked by CORS policy: Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present on the requested resource.`
    L'origine `http://localhost:5501` n'est pas dans `ALLOWED_ORIGINS` (seul le port 5500 l'est), donc la requête préliminaire `OPTIONS` n'obtient pas l'autorisation.
  - **`curl` :** CORS est une règle appliquée **par le navigateur** pour protéger l'utilisateur. `curl` n'est pas un navigateur : il n'envoie pas de pré-requête et ne vérifie aucun en-tête `Access-Control-*`. Seule la clé API compte pour lui.

- **Où voyez-vous la clé dans F12 ?**
  Onglet **Network** → requête `predict` → **Headers** → *Request Headers* → `X-API-Key`. La clé voyage donc en clair dans l'en-tête de la requête, visible par l'utilisateur de la page (d'où l'intérêt de HTTPS en production). Si elle était écrite dans le code JavaScript, elle serait visible par **tous** ceux qui chargent la page (onglet Sources ou « afficher le code source »), sans même qu'ils aient à faire un appel, et elle finirait aussi dans Git.

---

## 5. Questions de compréhension

1. **Quelle différence entre 401, 403 et 422 ?**
   - **401** : l'API ne sait pas *qui* appelle (clé absente ou fausse) : problème d'**authentification**.
   - **403** : l'API sait qui appelle, mais l'action n'est **pas permise** (clé utilisateur sur `/v1/model-info`, réservée à l'admin) : problème d'**autorisation**.
   - **422** : l'appelant est accepté, mais les **données** sont invalides (champ manquant, valeur hors bornes, mauvais type).
   - Ordre des contrôles : route (404) → clé (401/403) → données (422) → modèle (503). Une pluie de 500 mm *sans clé* donne donc 401, pas 422.

2. **Pourquoi la clé n'est-elle ni dans le code ni dans Git ?**
   Parce que tout ce qui est commité reste dans l'historique de Git, même si le fichier est supprimé ensuite, et devient lisible par tous ceux qui ont accès au dépôt (public ou non). Une clé exposée doit être changée. On la place donc dans `.env` (ignoré par Git, lu au démarrage) ; seul `.env.example`, avec de fausses valeurs, est commité pour documenter la configuration.

3. **Pourquoi comparer avec `compare_digest` plutôt qu'avec `==` ?**
   `==` s'arrête au premier caractère différent : la durée de la réponse dépend du nombre de caractères corrects au début. Un attaquant peut mesurer ces écarts (attaque par canal temporel) et deviner la clé caractère par caractère. `secrets.compare_digest` prend un temps constant, qui ne dépend pas de la position de la première différence.

4. **Pourquoi `curl` fonctionne-t-il alors que la page du port 5501 est bloquée ?**
   CORS est une politique du **navigateur**, pas du serveur : l'API se contente d'envoyer ou non `Access-Control-Allow-Origin`, et c'est le navigateur qui bloque la lecture de la réponse. `curl` (comme Python ou Java) ne fait pas ce contrôle. CORS protège l'utilisateur contre une page malveillante, pas l'API contre les appels directs : la clé reste indispensable.

5. **Pourquoi la validation faite par le navigateur ne remplace-t-elle pas celle de l'API ?**
   Le code JavaScript s'exécute chez le client, qui peut le modifier, le contourner ou ne jamais l'utiliser : `curl`, un script ou les outils de développement envoient n'importe quelle requête directement à l'API. Seule la validation côté serveur (schémas Pydantic, clé API) est fiable. La validation côté page n'est qu'un confort d'utilisation.

---
