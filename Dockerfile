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
