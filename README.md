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
- **Service Status** - Task totals, queue depth and host/container load at `/status`

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

## Image tags & nginx updates

### What the tags mean

| Tag | What it is | Who creates it |
|---|---|---|
| `latest` | newest publish of either kind below | CI |
| `v0.6.2` | application release (code changed) | a human, by pushing a `v*` tag |
| `nginx-1.30.7` | **runtime patch only** — same application code, newer nginx | CI, after a human merges the bot PR |

`latest` moves on **both** kinds of release, so anything tracking `latest` picks up nginx security patches automatically. If you pin a `v*` tag instead, you keep that exact build forever and only get nginx fixes by moving tags.

Which nginx a given image carries:

```bash
curl -s localhost/api/version        # {"version":"v0.6.2","nginx":"1.30.7",...}
docker inspect ghcr.io/jacksen168sub/ba-modding-toolkit-web:latest \
  --format '{{ index .Config.Labels "org.opencontainers.image.nginx.version" }}'
```

### How nginx gets updated

1. **Renovate** (`renovate.json`) reads the nginx.org apt index for amd64 + arm64 and opens a PR when the pinned branch (1.30.x) gets a new release. It never touches the application version.
2. **`nginx pr check`** runs on that PR: the CVE gate (`scripts/check_nginx_cves.py`) plus a real `docker build --target nginx-probe` — it must install before anyone is asked to merge.
3. A human merges. **`nginx tag release`** creates `nginx-<version>` and starts the publish workflow.
4. **Publish** builds both architectures, smoke-tests `/health` + `nginx -t` *before* pushing, then creates a GitHub Release whose notes are generated from the advisory page ("what this bump fixed").

The gate only blocks when a candidate would introduce a **major** severity finding that the current version does not have. Being affected isn't enough — the shipped version usually is too, and blocking would just keep the older, equally affected build online.

### Upgrading / rolling back by hand

```bash
# rollback: revert the bot commit, then tag the result yourself
git revert <bot-commit> && git push origin master
git tag nginx-1.30.6-r1 && git push origin nginx-1.30.6-r1
gh workflow run docker-publish.yml --ref nginx-1.30.6-r1
```

Reuse of the original tag is deliberately not automated: registry tags are mutable, and silently republishing a version hides history. The `-rN` suffix keeps both visible.

### Keeping a running container current

`latest` is how this repo ships patches, so poll it with one of:

```yaml
# docker-compose.yml — notify only, decide yourself (recommended)
  diun:
    image: crazymax/diun:latest
    environment:
      DIUN_WATCH_WORKERS: "10"
      DIUN_WATCH_SCHEDULE: "0 */6 * * *"
      DIUN_PROVIDERS_DOCKER: "true"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./diun-data:/data
```

```bash
# or zero-downtime restart whenever the tag moves
docker run -d --name docker-rollout \
  -v /var/run/docker.sock:/var/run/docker.sock \
  wowu/docker-rollout:latest
docker rollout bamt-web
```

**Watchtower is not used**: it was archived on 2025-12-17 and its Docker SDK (API v1.25) predates Docker Engine 29.

### If the weekly nginx check stops

GitHub disables `schedule` triggers after 60 days without repository activity. Re-enable `nginx eol watch` (and Renovate's own schedule) under the Actions tab; the watchdog also opens an issue when the locked branch reaches EOL or a same-branch release has gone unpicked.

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
| CLI_COMPRESSION | Bundle compression method (lzma, lz4, original, none) | lzma |
| STATUS_CONTAINER_AWARE | Report this container's cgroup limits rather than the host's totals | true |
| STATUS_REDACT | Comma-separated facets to hide from `/api/status` | (empty) |

### Hiding information on the status page

`GET /api/status` and the `/status` page can be published without advertising
your hardware or traffic. Every facet is hideable on its own, so you can hide
CPU load while still showing disk, or hide the storage path while keeping the
usage figures:

| Facet | What it hides |
|-------|---------------|
| `cpu` | CPU utilisation, effective core count, load average |
| `memory` | Memory total / used / available / percentage |
| `disk` | Disk total / used / free / percentage |
| `paths` | Filesystem path of the storage volume |
| `host` | Host core count and host memory total |
| `container` | Runtime, cgroup version, CPU quota and memory limit |
| `process` | Backend PID, RSS, CPU, thread count, start time |
| `version` | Application version and commit hash |
| `uptime` | Uptime and process start time |
| `tasks` | Task total and the status / type breakdowns |
| `performance` | Success rate and average runtime |
| `activity` | Recent task volume (1h / 24h / 7d) |
| `queue` | Queue depth and worker-pool occupancy |
| `storage` | Uploaded / result file counts and sizes |
| `sessions` | Session counts |

Two shorthands are accepted: `system` expands to `cpu,memory,disk`, and `all`
expands to every facet above. Unknown entries are ignored, so a typo leaves that
facet *visible* rather than hidden — check the response's `redacted` array to
confirm what actually took effect.

Redacted fields are returned as `null` and listed in the response's `redacted`
array. The page then shows a notice naming the hidden facets and `—` in place of
each value — including a hatched placeholder instead of a misleading `0%` bar.

```bash
# Hide how loaded the machine is and where its storage lives
STATUS_REDACT=cpu,memory,disk,paths

# Keep the resource gauges but reveal nothing about the host or build
STATUS_REDACT=host,container,process,version,uptime

# Everything
STATUS_REDACT=all
```

Inside a container, CPU and memory are reported against the container's own
cgroup quota, so the figures match the resources you actually allocated.
`STATUS_CONTAINER_AWARE=false` restores host-wide reporting.

## Custom page injection

The Docker image keeps its frontend as a **pristine template** and renders it into the web
root on every container start. That lets you add your own HTML to the page — extra styles, a
notice banner, a feedback widget — **without rebuilding the image**, and keeps the published
image free of anything deployment-specific.

Content is inserted at one of two markers that Vite preserves in `index.html`:

| Where | Env var | Mounted file (wins over the env var) |
|-------|---------|--------------------------------------|
| Just before `</head>` | `INJECT_HEAD_HTML` | `/app/data/inject-head.html` |
| Just before `</body>` | `INJECT_BODY_HTML` | `/app/data/inject-body.html` |

A file is preferred, since multi-line HTML is awkward to quote in a shell or compose file.
Override the default paths with `INJECT_HEAD_FILE` / `INJECT_BODY_FILE`. Nothing configured
means nothing is injected.

```bash
# Recommended: keep the fragment in a file next to your database
cat > data/inject-head.html <<'EOF'
<!-- your HTML here -->
EOF

docker run -d --name bamt-web -p 80:80 \
  -v ./storage:/app/storage \
  -v ./data:/app/data \
  ghcr.io/jacksen168sub/ba-modding-toolkit-web:latest
```

The page is re-rendered from the template on every start, so changing the file (or the env
var) and restarting the container takes effect; with nothing set, the page is plain.

### Single-page apps

This is a Vue single-page app: navigating between tools never reloads the document, so an
injected fragment that reacts to document loads would only ever fire once. The app exposes a
hook so injected content can follow in-app navigation:

```js
// `path` is safe to use; `fullPath` may carry a taskId query.
window.__bamtRouteChange = ({ path, fullPath }) => { /* ... */ }
```

### A note on trust

Injection is, by design, "output arbitrary HTML/JS into the page" — the same power you would
have editing the file on disk. It is meant for the operator of a self-hosted instance, so
keep these variables to yourself: do not expose them through the API, and do not let
application users set them. Injection applies to the **Docker image** only; the local
production mode (`start-prod.ps1`) serves the built files directly and does not inject.

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

GNU General Public License v3.0