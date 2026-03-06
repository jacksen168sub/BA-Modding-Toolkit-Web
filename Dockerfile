# Build stage for frontend (only runs on amd64)
FROM --platform=$BUILDPLATFORM node:20-alpine AS frontend-build

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install uv and supervisor
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Setup backend
COPY backend/pyproject.toml ./
COPY backend/.python-version ./
RUN uv sync --no-dev

COPY backend/app ./app

# Copy upstream BA-Modding-Toolkit (submodule)
COPY upstream ./upstream

# Setup frontend (copy from build stage, works for all platforms)
COPY --from=frontend-build /app/frontend/dist /var/www/html
COPY nginx.conf /etc/nginx/sites-available/default

# Enable nginx site
RUN rm -f /etc/nginx/sites-enabled/default && \
    ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# Create necessary directories
RUN mkdir -p /app/storage/uploads /app/storage/outputs /app/storage/temp /app/data

# Supervisor configuration
RUN mkdir -p /var/log/supervisor
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 80

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
