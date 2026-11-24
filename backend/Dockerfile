# Backend image for Azure Container Apps. Build from the repo root:
#   docker build -f backend/Dockerfile -t firstfix-backend .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
# DATA_DIR defaults to /data (../data from /srv). The mock data and the pinned agent
# trajectories ship with the image so LLM_MODE=replay runs the demo without a model; the
# answer key is left out by .dockerignore. Uploads go to /data/uploads (use a volume or
# Azure Storage to keep them across restarts).
COPY data/mock-data /data/mock-data
COPY data/replay /data/replay

RUN useradd --create-home --uid 10001 poc && mkdir -p /data/uploads \
    && chown -R poc:poc /srv /data
USER poc

EXPOSE 8008

# Pending migrations run on every start, so the database keeps up with the code.
CMD ["sh", "-c", "python -m app.scripts.migrate && exec uvicorn app.main:app --host 0.0.0.0 --port 8008"]
