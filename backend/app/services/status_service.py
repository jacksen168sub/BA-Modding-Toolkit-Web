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

# Facets redacted by nulling a handful of scalar fields, as dotted payload paths.
_FACET_PATHS = {
    "cpu": (
        "system.cpu.percent",
        "system.cpu.cores",
        "system.cpu.load_avg",
    ),
    "memory": (
        "system.memory.total",
        "system.memory.used",
        "system.memory.available",
        "system.memory.percent",
    ),
    "disk": (
        "system.disk.total",
        "system.disk.used",
        "system.disk.free",
        "system.disk.percent",
    ),
    "paths": ("system.disk.path",),
    "host": (
        "system.cpu.host_cores",
        "system.memory.host_total",
    ),
    "process": (
        "system.process.pid",
        "system.process.memory_rss",
        "system.process.cpu_percent",
        "system.process.threads",
        "system.process.started_at",
    ),
    "version": (
        "service.version",
        "service.commit",
    ),
    "uptime": (
        "service.uptime_seconds",
        "service.started_at",
    ),
    "performance": (
        "tasks.success_rate",
        "tasks.avg_duration_seconds",
    ),
}

# Facets redacted by replacing a whole nested block.
_BLANK_QUEUE = {key: None for key in (
    "pending", "processing", "length", "max_concurrent", "available_slots", "utilization"
)}
_BLANK_STORAGE = {
    "uploads": {"count": None, "size": None},
    "outputs": {"count": None, "size": None},
    "total_size": None,
}
_BLANK_SESSIONS = {"total": None, "active": None}


def _null_path(payload: dict, dotted: str) -> None:
    """Set a dotted payload path to None, ignoring paths that do not exist."""
    *parents, leaf = dotted.split(".")
    node = payload
    for key in parents:
        node = node.get(key)
        if not isinstance(node, dict):
            return
    if leaf in node:
        node[leaf] = None


def apply_redaction(payload: dict, facets: set) -> list:
    """Blank out the requested facets of a status payload in place.

    Each facet is an independently hideable piece of information, so a
    deployment can hide CPU load while still showing disk, or vice versa.
    Returns the facets actually applied, in a stable order, so the response can
    tell the client the page is deliberately incomplete rather than broken.
    """
    if not facets:
        return []

    applied = sorted(facets)

    for facet in applied:
        for dotted in _FACET_PATHS.get(facet, ()):
            _null_path(payload, dotted)

    # Facets that replace a block outright.
    if "container" in facets:
        payload["system"]["container"] = dict(_BLANK_CONTAINER)
    if "tasks" in facets:
        # Counts become null and the breakdowns empty, so the page renders an
        # empty chart rather than a misleading zero.
        payload["tasks"]["total"] = None
        payload["tasks"]["by_status"] = {}
        payload["tasks"]["by_type"] = {}
    if "activity" in facets:
        payload["tasks"]["recent"] = {}
    if "queue" in facets:
        payload["queue"] = dict(_BLANK_QUEUE)
    if "storage" in facets:
        payload["storage"] = {
            "uploads": dict(_BLANK_STORAGE["uploads"]),
            "outputs": dict(_BLANK_STORAGE["outputs"]),
            "total_size": None,
        }
    if "sessions" in facets:
        payload["sessions"] = dict(_BLANK_SESSIONS)

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
