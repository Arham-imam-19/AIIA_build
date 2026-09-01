FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# curl is only here so the container healthcheck can hit /api/health.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so Docker caches the (slow) pip install layer and
# only re-runs it when requirements.txt actually changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# chmod in the image, so the script runs even if the host copy lost its
# executable bit (which happens on Windows checkouts).
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

# The entrypoint waits for Postgres, runs `alembic upgrade head`, then starts
# uvicorn with --reload so code edits on the mounted volume take effect without
# a rebuild.
CMD ["/app/entrypoint.sh"]
