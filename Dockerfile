# =============================================================
# Websoccer — Production Dockerfile (Django + Gunicorn)
# Used for the Hetzner production deployment. Replit dev does
# NOT use this image (it runs runserver directly).
# =============================================================
FROM python:3.12-slim

# Python runtime hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies:
#  - libpq5 / libpq-dev: PostgreSQL client libs for psycopg2
#  - build-essential: compile C extensions during pip install
#  - curl: used by the compose healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy the application source
COPY . /app

# Entrypoint handles optional migrate/collectstatic, then starts Gunicorn
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
