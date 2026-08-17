# Production image for Eevie: builds the frontend, then serves it from the
# same FastAPI process that serves the API. One service, no CORS, no
# API-base-URL to configure.

# --- 1. build the SPA -------------------------------------------------------
FROM node:20-alpine AS web

WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# --- 2. runtime -------------------------------------------------------------
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ .

# The VCA catalogue zip, which cannot be fetched at runtime (see
# services/vca_catalog). Shipping it in the image keeps git the source of
# truth, so a fresh environment can rebuild its catalogue unaided.
COPY data/ ./data/

# main.py picks this up automatically and serves it.
COPY --from=web /web/dist ./app/static

# Railway injects $PORT; 8000 is the local default.
ENV PORT=8000
EXPOSE 8000

# Migrations run before the server so a deploy can never serve a schema it
# doesn't have. `sh -c` is needed for $PORT to expand.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
