# Build stage for frontend (only runs on amd64)
FROM --platform=$BUILDPLATFORM node:24-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Build stage for backend dependencies
FROM python:3.12-slim-bookworm AS backend-builder

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --no-dev

# Build stage for upstream (needs source code for setuptools build)
FROM python:3.12-slim-bookworm AS upstream-builder

WORKDIR /app/upstream/BA-Modding-Toolkit

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# git is required: v2.9.2 sources spineatlas from a git repo rather than PyPI
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ git ca-certificates && rm -rf /var/lib/apt/lists/*

COPY upstream/BA-Modding-Toolkit/ .
RUN uv sync --no-dev

# CI only: prove a candidate nginx version installs on the real base image.
# This stage must stay BEFORE the production stage - the last stage is what a
# plain `docker build .` produces.
FROM python:3.12-slim-bookworm AS nginx-probe
ARG NGINX_VERSION
COPY scripts/nginx-apt-install.sh /tmp/
RUN sh /tmp/nginx-apt-install.sh "${NGINX_VERSION}"

# Production stage
FROM python:3.12-slim-bookworm

# Build arguments for version info
ARG GIT_TAG=""
ARG GIT_COMMIT=""

WORKDIR /app

# nginx version: single source of truth for the whole repo.
# The inline comment below is read by Renovate (custom.regex manager) - keep the
# comment and the ENV on consecutive lines and do not reformat them.
# renovate: datasource=deb depName=nginx
ENV NGINX_VERSION=1.30.8

# Install nginx (pinned) and supervisor in one layer; installation logic lives in
# scripts/nginx-apt-install.sh so the CI probe stage and this stage cannot drift.
COPY scripts/nginx-apt-install.sh /tmp/
RUN sh /tmp/nginx-apt-install.sh "${NGINX_VERSION}" \
    && rm -f /tmp/nginx-apt-install.sh

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
RUN echo "{\"version\":\"${GIT_TAG}\",\"tag\":\"${GIT_TAG}\",\"commit\":\"${GIT_COMMIT}\",\"nginx\":\"${NGINX_VERSION}\"}" > /app/version.json

# Frontend: ship a working copy in the web root, plus a pristine template the entrypoint
# re-renders at startup so an operator can inject their own page HTML without rebuilding.
# The web root is seeded here (not left empty) so the site still serves even if the render
# is ever skipped.
COPY --from=frontend-build /app/frontend/dist /opt/frontend-template
COPY --from=frontend-build /app/frontend/dist /var/www/html

# Setup nginx - use as main config (not sites-enabled)
COPY nginx.conf /etc/nginx/nginx.conf

# Create necessary directories
RUN mkdir -p /app/storage/uploads /app/storage/outputs /app/storage/temp /app/data

# Supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Entrypoint renders the frontend template (and any page injection) before supervisord starts
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
