# BA-Modding-Toolkit-Web

[![Docker Build](https://github.com/jacksen168sub/BA-Modding-Toolkit-Web/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/jacksen168sub/BA-Modding-Toolkit-Web/actions/workflows/docker-publish.yml)
[![GitHub release](https://img.shields.io/github/v/release/jacksen168sub/BA-Modding-Toolkit-Web?include_prereleases)](https://github.com/jacksen168sub/BA-Modding-Toolkit-Web/releases)
[![Docker Pulls](https://img.shields.io/docker/pulls/jacksen168/ba-modding-toolkit-web)](https://hub.docker.com/r/jacksen168/ba-modding-toolkit-web)
[![License](https://img.shields.io/github/license/jacksen168sub/BA-Modding-Toolkit-Web)](LICENSE)

A web service platform for [BA-Modding-Toolkit](https://github.com/Agent-0808/BA-Modding-Toolkit), supporting multi-user self-service usage.

**[中文文档](docs/README.zh-CN.md)**

## Features

- **Mod Update** - Update game mod files to the latest version
- **Asset Pack** - Pack resource files into game bundles
- **Asset Extract** - Extract assets from game bundles
- **CRC Tool** - Calculate and fix CRC checksums

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | FastAPI + SQLAlchemy + SQLite |
| Frontend | Vue 3 + Vite + Element Plus |
| Deployment | Docker Compose |

## Quick Start

### Option 1: Production Mode (Recommended)

Build frontend and start backend, all services run on **port 8000**:

```bash
# 1. Build frontend
cd frontend
npm install
npm run build
cd ..

# 2. Start backend (automatically serves frontend static files)
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
cd ..
```

Visit http://localhost:8000

### Option 2: Development Mode

Run frontend and backend separately with hot reload:

**Terminal 1 - Start backend:**
```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Start frontend:**
```bash
cd frontend
npm install
npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Frontend automatically proxies `/api` requests to backend

### Option 3: Docker (Port 80)

#### Using Docker Compose (Local Build)

```bash
docker-compose up --build
```

Visit http://localhost

#### Using Pre-built Image

Pull from GitHub Container Registry:

```bash
# Pull image
docker pull ghcr.io/jacksen168sub/ba-modding-toolkit-web:latest

# Run container
docker run -d \
  --name bamt-web \
  -p 80:80 \
  -v ./storage:/app/storage \
  -v ./data:/app/data \
  ghcr.io/jacksen168sub/ba-modding-toolkit-web:latest
```

Visit http://localhost

#### Optional Configuration

| Parameter | Description |
|-----------|-------------|
| `-p 80:80` | Port mapping, format: `host_port:container_port` |
| `-v ./storage:/app/storage` | Persistent file storage |
| `-v ./data:/app/data` | Persistent database |

#### Docker Hub

Also available on Docker Hub:

```bash
docker pull jacksen168/ba-modding-toolkit-web:latest
```

## Project Structure

```
BA-Modding-Toolkit-Web/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py          # Application entry
│   │   ├── routers/         # API routes
│   │   ├── services/        # Business logic
│   │   ├── models/          # Data models
│   │   └── utils/           # Utilities
│   └── pyproject.toml
├── frontend/                # Vue 3 frontend
│   ├── src/
│   │   ├── pages/           # Page components
│   │   ├── components/      # Common components
│   │   ├── api/             # API wrappers
│   │   └── stores/          # State management
│   └── package.json
├── storage/                 # File storage
│   ├── uploads/             # User uploads
│   └── outputs/             # Processing results
├── data/                    # SQLite database
└── upstream/                # BA-Modding-Toolkit submodule
```

## Requirements

- Python >= 3.10
- Node.js >= 18
- uv (Python package manager)

## Configuration

Backend configuration is located in `backend/app/config.py`, supports environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| UPLOAD_DIR | Upload directory | storage/uploads |
| OUTPUT_DIR | Output directory | storage/outputs |
| SESSION_EXPIRE_HOURS | Session expiration time | 24 |

## Supported Languages

The interface supports multiple languages:

- English (en-US)
- 简体中文 (zh-CN)
- 繁體中文 (zh-TW)
- 日本語 (ja-JP)
- 한국어 (ko-KR)
- Español (es-ES)
- Français (fr-FR)
- Русский (ru-RU)
- العربية (ar-SA)
- हिन्दी (hi-IN)
- বাংলা (bn-BD)
- ไทย (th-TH)

## Acknowledgments

- [BA-Modding-Toolkit](https://github.com/Agent-0808/BA-Modding-Toolkit) - The upstream CLI tool

## License

MIT