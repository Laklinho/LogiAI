
"""L'API LogiAI : python -m uvicorn logiai.api.main:app --reload"""

from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from logiai import config
from fastapi import Depends, FastAPI, HTTPException

from logiai.api.schemas import Livraison, PredictionOut
from logiai.api.security import verify_api_key, require_admin
from logiai.config import MODEL_PATH
from logiai.predict import Predictor


state: dict = {}  # Contient le predictor une fois le modèle chargé


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Exécuté une fois au démarrage du serveur
    if MODEL_PATH.exists():
        state["predictor"] = Predictor(MODEL_PATH)

    yield

    state.clear()


app = FastAPI(
    title="LogiAI",
    version="1.0.0",
    description="Prédit le risque de retard d'une livraison à partir de ses caractéristiques.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)


# =========================
# HEALTH - PUBLIC
# =========================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": "predictor" in state,
    }


# =========================
# PREDICTION - USER + ADMIN
# =========================

@app.post(
    "/v1/predict",
    response_model=PredictionOut,
    dependencies=[Depends(verify_api_key)],
)
def predict(livraison: Livraison):
    predictor = state.get("predictor")

    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Modèle non chargé : lancez 'python -m logiai.train' puis redémarrez l'API.",
        )

    return PredictionOut(**predictor.predict(livraison.model_dump()))


# =========================
# MODEL INFO - ADMIN ONLY
# =========================

@app.get(
    "/v1/model-info",
    dependencies=[Depends(require_admin)],
)
def model_info():
    predictor = state.get("predictor")

    if predictor is None:
        raise HTTPException(
            status_code=503,
            detail="Modèle non chargé.",
        )

    return {
        "model_loaded": True,
        "model_version": app.version,
    }
