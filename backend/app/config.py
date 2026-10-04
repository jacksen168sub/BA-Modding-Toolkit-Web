# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

from pathlib import Path
from pydantic_settings import BaseSettings


# Individual facets of GET /api/status that STATUS_REDACT can blank out.
# One facet == one independently hideable piece of information.
STATUS_REDACTABLE_FACETS = (
    # Host resources
    "cpu",          # CPU percent, effective core count, load average
    "memory",       # memory total / used / available / percent
    "disk",         # disk total / used / free / percent
    # Where and on what the service runs
    "paths",        # filesystem path of the storage volume
    "host",         # host core count and host memory total
    "container",    # runtime, cgroup version, CPU quota and memory limit
    "process",      # backend PID, RSS, CPU, thread count, start time
    # Build identity
    "version",      # application version and commit hash
    "uptime",       # uptime and process start time
    # Workload
    "tasks",        # task total plus status / type breakdowns
    "performance",  # success rate and average runtime
    "activity",     # recent task volume (1h / 24h / 7d)
    "queue",        # queue depth and worker-pool occupancy
    # Stored data
    "storage",      # uploaded / result file counts and sizes
    "sessions",     # session counts
)

# Convenience groups, expanded before the facet set is resolved.
STATUS_REDACT_GROUPS = {
    "system": ("cpu", "memory", "disk"),
    "all": STATUS_REDACTABLE_FACETS,
}


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "BA-Modding-Toolkit Web"
    DEBUG: bool = True
    
    # File storage paths
    # In Docker, we're at /app/app/config.py, so PROJECT_ROOT should be /app
    # In development, we're at backend/app/config.py, so PROJECT_ROOT should be project root
    BASE_DIR: Path = Path(__file__).parent.parent  # backend/ or /app/
    
    # Detect if running in Docker (check if /app/.venv exists)
    _is_docker: bool = (Path("/app/.venv").exists())
    
    PROJECT_ROOT: Path = Path("/app") if _is_docker else Path(__file__).parent.parent.parent
    
    # Database - use absolute path
    @property
    def DATABASE_URL(self) -> str:
        db_path = self.PROJECT_ROOT / "data" / "bamt.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path}"
    
    UPLOAD_DIR: str = "storage/uploads"
    OUTPUT_DIR: str = "storage/outputs"
    TEMP_DIR: str = "storage/temp"
    
    # Expiration settings
    SESSION_EXPIRE_HOURS: int = 24
    
    # Cleanup settings
    CLEANUP_INTERVAL_HOURS: int = 1
    
    # File upload limits
    MAX_FILE_SIZE: int = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS: set = {".bundle", ".png", ".skel", ".atlas"}

    # Upload filename black/whitelist rules.
    # Path to a JSON rule file. When empty/missing, built-in default rules
    # (allow all allowed extensions) are used. In Docker, mount a custom file
    # to /app/data/upload-rules.json and set UPLOAD_RULES_FILE accordingly.
    UPLOAD_RULES_FILE: str = ""
    
    # CLI settings
    CLI_TIMEOUT: int = 600  # 10 minutes
    CLI_COMPRESSION: str = "lz4"  # Compression method: lzma, lz4, original, none

    # Concurrency settings
    MAX_CONCURRENT_TASKS: int = 2  # Maximum concurrent tasks

    # Container settings
    # Inside a container the host's /proc describes the whole machine, so the
    # status endpoint reads the cgroup limits and reports CPU / memory relative
    # to this container's own quota. Set to false to always report host figures.
    STATUS_CONTAINER_AWARE: bool = True

    # Status page privacy
    # Comma-separated list of facets to blank out in GET /api/status, for
    # deployments that must not advertise their hardware or traffic. Each facet
    # is hideable on its own; see STATUS_REDACTABLE_FACETS above for the list.
    #   system   - shorthand for cpu,memory,disk
    #   all      - shorthand for every facet
    # Unknown entries are ignored, so a typo silently leaves that facet visible
    # rather than hidden — check the response's `redacted` array to confirm what
    # actually took effect.
    # Examples:
    #   STATUS_REDACT=cpu,disk
    #   STATUS_REDACT=host,paths,version,container
    #   STATUS_REDACT=all
    STATUS_REDACT: str = ""
    
    # CORS settings
    CORS_ORIGINS: str = "*"  # Comma-separated list of allowed origins, e.g., "https://example.com,https://www.example.com"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"  # Comma-separated list, e.g., "GET,POST,DELETE"
    CORS_ALLOW_HEADERS: str = "*"  # Comma-separated list, e.g., "Content-Type,Authorization"
    
    @property
    def upload_path(self) -> Path:
        return self.PROJECT_ROOT / self.UPLOAD_DIR
    
    @property
    def output_path(self) -> Path:
        return self.PROJECT_ROOT / self.OUTPUT_DIR
    
    @property
    def temp_path(self) -> Path:
        return self.PROJECT_ROOT / self.TEMP_DIR
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    @property
    def cors_allow_methods_list(self) -> list[str]:
        """Parse CORS_ALLOW_METHODS into a list."""
        if self.CORS_ALLOW_METHODS == "*":
            return ["*"]
        return [method.strip() for method in self.CORS_ALLOW_METHODS.split(",") if method.strip()]
    
    @property
    def cors_allow_headers_list(self) -> list[str]:
        """Parse CORS_ALLOW_HEADERS into a list."""
        if self.CORS_ALLOW_HEADERS == "*":
            return ["*"]
        return [header.strip() for header in self.CORS_ALLOW_HEADERS.split(",") if header.strip()]

    @property
    def status_redact_set(self) -> set[str]:
        """Resolve STATUS_REDACT into the set of facets to blank out.

        Group names (``system``, ``all``) are expanded, unknown entries are
        ignored, and the result only ever contains redactable facets.
        """
        raw = (self.STATUS_REDACT or "").strip().lower()
        if not raw:
            return set()

        resolved: set[str] = set()
        for token in (part.strip() for part in raw.split(",")):
            if not token:
                continue
            if token in STATUS_REDACT_GROUPS:
                resolved.update(STATUS_REDACT_GROUPS[token])
            elif token in STATUS_REDACTABLE_FACETS:
                resolved.add(token)
        return resolved

    @property
    def upload_rules_file(self) -> Path | None:
        """Resolve the upload rules file path.

        - Absolute paths are used as-is.
        - Relative paths are resolved against PROJECT_ROOT.
        - Empty string returns None (signals: use default rules).
        """
        raw = (self.UPLOAD_RULES_FILE or "").strip()
        if not raw:
            return None
        p = Path(raw)
        if not p.is_absolute():
            p = self.PROJECT_ROOT / p
        return p

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()