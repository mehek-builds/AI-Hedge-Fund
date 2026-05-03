FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps (api reqs + worker extras)
COPY api/requirements.txt /tmp/api_requirements.txt
COPY worker/requirements.txt /tmp/worker_requirements.txt
RUN pip install --no-cache-dir -r /tmp/api_requirements.txt -r /tmp/worker_requirements.txt

# Copy entire repo so signals/, macro/, rl/, config.py imports work
COPY . /app

ENV PYTHONPATH=/app

CMD ["celery", "-A", "worker.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
