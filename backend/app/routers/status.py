# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

"""Service status endpoint: task history, queue depth and host load."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..models.database import get_db
from ..models.schemas import ServiceStatus
from ..services.status_service import StatusService, apply_redaction
from ..utils.sysinfo import system_stats
from .version import get_version_info

router = APIRouter(prefix="/status", tags=["Status"])

# Fallback uptime origin for when the process start time is unavailable.
_PROCESS_START = datetime.utcnow()

# Disk usage above this share marks the service degraded.
_DISK_DEGRADED_PERCENT = 90.0


def _build_service_info(system: dict) -> dict:
    """Identity, liveness and uptime of the backend."""
    version = get_version_info()
    started_at = system["process"].get("started_at") or _PROCESS_START
    now = datetime.utcnow()

    disk_percent = system["disk"].get("percent")
    degraded = disk_percent is not None and disk_percent >= _DISK_DEGRADED_PERCENT

    return {
        "name": settings.APP_NAME,
        "version": version["version"],
        "commit": version["commit"],
        "status": "degraded" if degraded else "healthy",
        "uptime_seconds": int((now - started_at).total_seconds()),
        "started_at": started_at,
        "server_time": now,
    }


@router.get("", response_model=ServiceStatus)
def get_service_status(db: Session = Depends(get_db)):
    """Current service status: task totals, queue depth, host load and storage.

    Container limits are honoured, and sections listed in STATUS_REDACT are
    blanked out before the response is returned.
    """
    system = system_stats(
        settings.output_path.parent,
        container_aware=settings.STATUS_CONTAINER_AWARE,
    )
    status_service = StatusService(db)

    queue = status_service.queue_stats()
    # Built before redaction so the health badge stays meaningful even when the
    # underlying figures are hidden.
    service = _build_service_info(system)

    # A backlog with no free worker slot is worth surfacing as degraded.
    if queue["pending"] > 0 and queue["available_slots"] == 0:
        service["status"] = "degraded"

    payload = {
        "service": service,
        "tasks": status_service.task_stats(),
        "queue": queue,
        "system": system,
        "storage": status_service.storage_stats(),
        "sessions": status_service.session_stats(),
    }
    payload["redacted"] = apply_redaction(payload, settings.status_redact_set)

    return payload
