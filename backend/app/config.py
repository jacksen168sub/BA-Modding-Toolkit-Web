# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

from pathlib import Path
from pydantic_settings import BaseSettings


# Sections of GET /api/status that STATUS_REDACT is allowed to blank out.
STATUS_REDACTABLE_SECTIONS = (
    "system",
    "host",
    "process",
    "paths",
    "version",
    "storage",
    "sessions",
)


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
    # Comma-separated list of sections to blank out in GET /api/status, for
    # deployments that must not advertise their hardware. Accepts any of:
    #   system   - CPU / memory / disk utilisation figures
    #   host     - host core & memory totals, and container / cgroup details
    #   process  - backend PID, memory and thread count
    #   paths    - filesystem path of the storage volume
    #   version  - application version and commit hash
    #   storage  - uploaded / result file counts and sizes
    #   sessions - session counts
    #   all      - every section above
    # Example: STATUS_REDACT=host,process,paths,version
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
        """Parse STATUS_REDACT into the set of sections to blank out.

        Unknown entries are ignored; ``all`` expands to every redactable section.
        """
        raw = (self.STATUS_REDACT or "").strip().lower()
        if not raw:
            return set()
        requested = {part.strip() for part in raw.split(",") if part.strip()}
        if "all" in requested:
            return set(STATUS_REDACTABLE_SECTIONS)
        return requested & set(STATUS_REDACTABLE_SECTIONS)

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