FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libsodium-dev git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY xe ./xe
COPY desk ./desk
COPY alembic.ini ./
COPY alembic ./alembic
COPY config ./config
COPY docs ./docs

RUN pip install --upgrade pip && pip install .

# Record the build commit so GET /v1 can report it. Pass --build-arg GIT_COMMIT=$(git rev-parse --short HEAD).
ARG GIT_COMMIT=unknown
ENV DESK_GIT_COMMIT=${GIT_COMMIT}

EXPOSE 8000

# --proxy-headers with Caddy only: the app trusts the first X-Forwarded-For hop from the proxy and nothing else.
CMD ["uvicorn", "desk.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
