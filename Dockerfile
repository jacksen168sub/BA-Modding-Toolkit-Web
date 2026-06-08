# Build stage for frontend (only runs on amd64)
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Build stage for backend dependencies
FROM python:3.12-slim AS backend-builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --no-dev

# Build stage for upstream (needs source code for setuptools build)
FROM python:3.12-slim AS upstream-builder

WORKDIR /app/upstream/BA-Modding-Toolkit

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY upstream/BA-Modding-Toolkit/ .
RUN uv sync --no-dev

# Production stage
FROM python:3.12-slim

# Build arguments for version info
ARG GIT_TAG=""
ARG GIT_COMMIT=""

WORKDIR /app

# Install nginx and supervisor in a single layer, remove build tools afterwards
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    supervisor \
    && curl -fsSL https://nginx.org/keys/nginx_signing.key | gpg --dearmor -o /usr/share/keyrings/nginx-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/nginx-archive-keyring.gpg] http://nginx.org/packages/debian `cat /etc/os-release | grep -oP '(?<=VERSION_CODENAME=).*'` nginx" > /etc/apt/sources.list.d/nginx.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && apt-get remove -y curl gnupg \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy uv binary (needed for `uv run bamt-cli` at runtime)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy backend virtual environment from builder
COPY --from=backend-builder /app/.venv /app/.venv

# Copy upstream (source + virtual environment) from builder
COPY --from=upstream-builder /app/upstream /app/upstream

# Copy backend app
COPY backend/app ./app

# Copy pyproject.toml for version fallback
COPY backend/pyproject.toml ./pyproject.toml

# Write version.json at build time (version source of truth)
RUN echo "{\"version\":\"${GIT_TAG}\",\"tag\":\"${GIT_TAG}\",\"commit\":\"${GIT_COMMIT}\"}" > /app/version.json

# Setup frontend (copy from build stage, works for all platforms)
COPY --from=frontend-build /app/frontend/dist /var/www/html

# Setup nginx - use as main config (not sites-enabled)
COPY nginx.conf /etc/nginx/nginx.conf

# Create necessary directories
RUN mkdir -p /app/storage/uploads /app/storage/outputs /app/storage/temp /app/data

# Supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
