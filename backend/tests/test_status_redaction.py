# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

"""Tests for the /api/status privacy controls (STATUS_REDACT)."""

from app.config import STATUS_REDACTABLE_SECTIONS, Settings
from app.services.status_service import apply_redaction


def sample_payload():
    return {
        "service": {"name": "app", "version": "v1", "commit": "abc123", "status": "healthy"},
        "tasks": {"total": 5},
        "queue": {"pending": 1, "processing": 1},
        "system": {
            "container": {
                "detected": True, "runtime": "docker", "cgroup_version": 2,
                "cpu_quota": 2.0, "memory_limit": 4 * 1024 ** 3,
            },
            "cpu": {"percent": 10.0, "cores": 2, "host_cores": 8, "quota": 2.0, "load_avg": [1.0, 1.0, 1.0]},
            "memory": {"total": 4, "used": 1, "available": 3, "percent": 25.0, "host_total": 32, "limit": 4},
            "disk": {"path": "/app/storage", "total": 100, "used": 90, "free": 10, "percent": 90.0},
            "process": {"pid": 7, "memory_rss": 100, "cpu_percent": 1.0, "threads": 4, "started_at": "t"},
        },
        "storage": {"uploads": {"count": 3, "size": 10}, "outputs": {"count": 1, "size": 5}, "total_size": 15},
        "sessions": {"total": 5, "active": 2},
    }


# --- config parsing --------------------------------------------------------


def test_no_redaction_by_default():
    assert Settings(STATUS_REDACT="").status_redact_set == set()


def test_all_expands_to_every_section():
    assert Settings(STATUS_REDACT="all").status_redact_set == set(STATUS_REDACTABLE_SECTIONS)


def test_unknown_and_blank_entries_are_ignored():
    settings = Settings(STATUS_REDACT=" host , bogus ,, version ")
    assert settings.status_redact_set == {"host", "version"}


# --- blanking --------------------------------------------------------------


def test_empty_section_set_leaves_the_payload_untouched():
    payload = sample_payload()
    assert apply_redaction(payload, set()) == []
    assert payload == sample_payload()


def test_system_section_blanks_utilisation_but_keeps_paths():
    payload = sample_payload()
    assert apply_redaction(payload, {"system"}) == ["system"]

    system = payload["system"]
    assert system["cpu"]["percent"] is None
    assert system["cpu"]["cores"] is None
    assert system["cpu"]["quota"] is None
    assert system["cpu"]["load_avg"] is None
    assert system["memory"]["total"] is None
    assert system["memory"]["percent"] is None
    assert system["disk"]["percent"] is None
    # Paths belong to a different section.
    assert system["disk"]["path"] == "/app/storage"


def test_host_section_blanks_topology_and_container_details():
    payload = sample_payload()
    assert apply_redaction(payload, {"host"}) == ["host"]

    system = payload["system"]
    assert system["cpu"]["host_cores"] is None
    assert system["memory"]["host_total"] is None
    assert system["container"]["detected"] is False
    assert system["container"]["runtime"] is None
    assert system["container"]["cpu_quota"] is None
    # Container-relative figures survive; only the host view goes away.
    assert system["cpu"]["cores"] == 2
    assert system["memory"]["total"] == 4


def test_process_paths_version_storage_and_sessions_sections():
    payload = sample_payload()
    applied = apply_redaction(payload, {"process", "paths", "version", "storage", "sessions"})

    assert applied == ["process", "paths", "version", "storage", "sessions"]
    assert payload["system"]["process"]["pid"] is None
    assert payload["system"]["process"]["memory_rss"] is None
    assert payload["system"]["disk"]["path"] is None
    assert payload["service"]["version"] is None
    assert payload["service"]["commit"] is None
    assert payload["storage"]["uploads"] == {"count": None, "size": None}
    assert payload["storage"]["outputs"] == {"count": None, "size": None}
    assert payload["storage"]["total_size"] is None
    assert payload["sessions"] == {"total": None, "active": None}


def test_task_and_queue_counters_are_never_redacted():
    payload = sample_payload()
    apply_redaction(payload, set(STATUS_REDACTABLE_SECTIONS))
    assert payload["tasks"] == {"total": 5}
    assert payload["queue"] == {"pending": 1, "processing": 1}
