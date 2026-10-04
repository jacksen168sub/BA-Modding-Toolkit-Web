# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

"""Aggregates service-wide counters for the status endpoint."""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..models.file import File, FileType
from ..models.session import Session as SessionModel
from ..models.task import Task, TaskStatus, TaskType

# How many of the most recent finished tasks feed the average-duration figure.
_DURATION_SAMPLE_SIZE = 200

# Placeholder for a container block that has been redacted away.
_BLANK_CONTAINER = {
    "detected": False,
    "runtime": None,
    "cgroup_version": None,
    "cpu_quota": None,
    "memory_limit": None,
}


def apply_redaction(payload: dict, sections: set) -> list:
    """Blank out the requested sections of a status payload in place.

    Returns the sections actually applied, so the response can tell the client
    the page is deliberately incomplete rather than broken.
    """
    if not sections:
        return []

    applied = []
    system = payload.get("system") or {}
    cpu = system.get("cpu") or {}
    memory = system.get("memory") or {}
    disk = system.get("disk") or {}
    process = system.get("process") or {}
    service = payload.get("service") or {}

    if "system" in sections:
        for key in ("percent", "cores", "quota", "load_avg"):
            cpu[key] = None
        for key in ("total", "used", "available", "percent", "limit"):
            memory[key] = None
        for key in ("total", "used", "free", "percent"):
            disk[key] = None
        applied.append("system")

    if "host" in sections:
        cpu["host_cores"] = None
        memory["host_total"] = None
        system["container"] = dict(_BLANK_CONTAINER)
        applied.append("host")

    if "process" in sections:
        for key in ("pid", "memory_rss", "cpu_percent", "threads", "started_at"):
            process[key] = None
        applied.append("process")

    if "paths" in sections:
        disk["path"] = None
        applied.append("paths")

    if "version" in sections:
        service["version"] = None
        service["commit"] = None
        applied.append("version")

    if "storage" in sections:
        storage = payload.get("storage") or {}
        for bucket in ("uploads", "outputs"):
            storage[bucket] = {"count": None, "size": None}
        storage["total_size"] = None
        applied.append("storage")

    if "sessions" in sections:
        payload["sessions"] = {"total": None, "active": None}
        applied.append("sessions")

    return applied


class StatusService:
    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _enum_key(value) -> str:
        """Normalise a SQLAlchemy Enum result to its string value."""
        return value.value if hasattr(value, "value") else str(value)

    def task_stats(self) -> dict:
        """Lifetime task counters, broken down by status and by type."""
        by_status = {status.value: 0 for status in TaskStatus}
        for status, count in (
            self.db.query(Task.status, func.count(Task.id)).group_by(Task.status).all()
        ):
            by_status[self._enum_key(status)] = count

        by_type = {task_type.value: 0 for task_type in TaskType}
        for task_type, count in (
            self.db.query(Task.type, func.count(Task.id)).group_by(Task.type).all()
        ):
            by_type[self._enum_key(task_type)] = count

        total = sum(by_status.values())
        finished = by_status[TaskStatus.COMPLETED.value] + by_status[TaskStatus.FAILED.value]

        now = datetime.utcnow()
        recent = {
            "last_hour": self._count_created_since(now - timedelta(hours=1)),
            "last_24h": self._count_created_since(now - timedelta(hours=24)),
            "last_7d": self._count_created_since(now - timedelta(days=7)),
        }

        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "success_rate": (
                round(100.0 * by_status[TaskStatus.COMPLETED.value] / finished, 1)
                if finished
                else None
            ),
            "avg_duration_seconds": self._avg_duration_seconds(),
            "recent": recent,
        }

    def _count_created_since(self, since: datetime) -> int:
        return (
            self.db.query(func.count(Task.id))
            .filter(Task.created_at >= since)
            .scalar()
            or 0
        )

    def _avg_duration_seconds(self) -> Optional[float]:
        """Mean wall-clock runtime of the most recently finished tasks."""
        rows = (
            self.db.query(Task.created_at, Task.completed_at)
            .filter(Task.completed_at.isnot(None))
            .order_by(Task.completed_at.desc())
            .limit(_DURATION_SAMPLE_SIZE)
            .all()
        )

        durations = [
            (completed - created).total_seconds()
            for created, completed in rows
            if created and completed and completed >= created
        ]
        if not durations:
            return None
        return round(sum(durations) / len(durations), 1)

    def queue_stats(self) -> dict:
        """Current queue depth and how much of the worker pool is busy."""
        pending = (
            self.db.query(func.count(Task.id))
            .filter(Task.status == TaskStatus.PENDING)
            .scalar()
            or 0
        )
        processing = (
            self.db.query(func.count(Task.id))
            .filter(Task.status == TaskStatus.PROCESSING)
            .scalar()
            or 0
        )

        max_concurrent = settings.MAX_CONCURRENT_TASKS
        return {
            "pending": pending,
            "processing": processing,
            "length": pending + processing,
            "max_concurrent": max_concurrent,
            "available_slots": max(0, max_concurrent - processing),
            "utilization": (
                round(100.0 * processing / max_concurrent, 1) if max_concurrent else 0.0
            ),
        }

    def storage_stats(self) -> dict:
        """Input/output file totals as recorded in the database."""
        buckets = {FileType.INPUT.value: {"count": 0, "size": 0},
                   FileType.OUTPUT.value: {"count": 0, "size": 0}}

        rows = (
            self.db.query(
                File.type,
                func.count(File.id),
                func.coalesce(func.sum(File.size), 0),
            )
            .group_by(File.type)
            .all()
        )
        for file_type, count, size in rows:
            buckets[self._enum_key(file_type)] = {"count": count, "size": int(size)}

        return {
            "uploads": buckets[FileType.INPUT.value],
            "outputs": buckets[FileType.OUTPUT.value],
            "total_size": buckets[FileType.INPUT.value]["size"]
            + buckets[FileType.OUTPUT.value]["size"],
        }

    def session_stats(self) -> dict:
        """Total sessions, and how many have not yet expired."""
        total = self.db.query(func.count(SessionModel.uuid)).scalar() or 0
        active = (
            self.db.query(func.count(SessionModel.uuid))
            .filter(SessionModel.expires_at > datetime.utcnow())
            .scalar()
            or 0
        )
        return {"total": total, "active": active}
