# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub

"""Tests for the /api/status privacy controls (STATUS_REDACT).

The point of the facet model is that each piece of information can be hidden on
its own, so most of these tests check that redacting one facet leaves its
neighbours alone.
"""

import pytest

from app.config import STATUS_REDACTABLE_FACETS, Settings
from app.services.status_service import apply_redaction

GIB = 1024 ** 3


def sample_payload():
    return {
        "service": {
            "name": "app", "version": "v1", "commit": "abc123",
            "status": "healthy", "uptime_seconds": 120, "started_at": "t0",
        },
        "tasks": {
            "total": 5,
            "by_status": {"completed": 4, "failed": 1},
            "by_type": {"update": 5},
            "success_rate": 80.0,
            "avg_duration_seconds": 12.5,
            "recent": {"last_hour": 1, "last_24h": 3, "last_7d": 5},
        },
        "queue": {
            "pending": 1, "processing": 1, "length": 2,
            "max_concurrent": 2, "available_slots": 1, "utilization": 50.0,
        },
        "system": {
            "container": {
                "detected": True, "runtime": "docker", "cgroup_version": 2,
                "cpu_quota": 2.0, "memory_limit": 4 * GIB,
            },
            "cpu": {"percent": 10.0, "cores": 2, "host_cores": 8, "quota": 2.0, "load_avg": [1.0, 1.0, 1.0]},
            "memory": {"total": 4, "used": 1, "available": 3, "percent": 25.0, "host_total": 32, "limit": 4},
            "disk": {"path": "/app/storage", "total": 100, "used": 90, "free": 10, "percent": 90.0},
            "process": {"pid": 7, "memory_rss": 100, "cpu_percent": 1.0, "threads": 4, "started_at": "t1"},
        },
        "storage": {
            "uploads": {"count": 3, "size": 10},
            "outputs": {"count": 1, "size": 5},
            "total_size": 15,
        },
        "sessions": {"total": 5, "active": 2},
    }


# --- config parsing --------------------------------------------------------


def test_no_redaction_by_default():
    assert Settings(STATUS_REDACT="").status_redact_set == set()


def test_all_expands_to_every_facet():
    assert Settings(STATUS_REDACT="all").status_redact_set == set(STATUS_REDACTABLE_FACETS)


def test_system_is_a_shorthand_for_the_three_resource_facets():
    assert Settings(STATUS_REDACT="system").status_redact_set == {"cpu", "memory", "disk"}


def test_unknown_and_blank_entries_are_ignored():
    settings = Settings(STATUS_REDACT=" cpu , bogus ,, disk ")
    assert settings.status_redact_set == {"cpu", "disk"}


def test_groups_and_facets_can_be_mixed():
    settings = Settings(STATUS_REDACT="system,version")
    assert settings.status_redact_set == {"cpu", "memory", "disk", "version"}


# --- facets are independent ------------------------------------------------


def test_empty_facet_set_leaves_the_payload_untouched():
    payload = sample_payload()
    assert apply_redaction(payload, set()) == []
    assert payload == sample_payload()


def test_cpu_hides_only_cpu_figures():
    payload = sample_payload()
    assert apply_redaction(payload, {"cpu"}) == ["cpu"]

    system = payload["system"]
    assert system["cpu"]["percent"] is None
    assert system["cpu"]["cores"] is None
    assert system["cpu"]["load_avg"] is None
    # Neighbours untouched.
    assert system["memory"]["percent"] == 25.0
    assert system["disk"]["percent"] == 90.0
    # Core count of the host, and the container quota, are separate facets.
    assert system["cpu"]["host_cores"] == 8
    assert system["cpu"]["quota"] == 2.0


def test_memory_hides_only_memory_figures():
    payload = sample_payload()
    assert apply_redaction(payload, {"memory"}) == ["memory"]

    memory = payload["system"]["memory"]
    assert memory["total"] is None
    assert memory["used"] is None
    assert memory["available"] is None
    assert memory["percent"] is None
    assert payload["system"]["cpu"]["percent"] == 10.0
    assert payload["system"]["disk"]["percent"] == 90.0
    assert memory["host_total"] == 32
    assert memory["limit"] == 4


def test_disk_hides_only_disk_figures_and_keeps_the_path():
    payload = sample_payload()
    assert apply_redaction(payload, {"disk"}) == ["disk"]

    disk = payload["system"]["disk"]
    assert disk["total"] is None
    assert disk["used"] is None
    assert disk["free"] is None
    assert disk["percent"] is None
    assert disk["path"] == "/app/storage"
    assert payload["system"]["cpu"]["percent"] == 10.0


def test_paths_hides_only_the_filesystem_path():
    payload = sample_payload()
    assert apply_redaction(payload, {"paths"}) == ["paths"]

    disk = payload["system"]["disk"]
    assert disk["path"] is None
    assert disk["percent"] == 90.0


def test_host_hides_host_totals_but_keeps_container_limits():
    payload = sample_payload()
    assert apply_redaction(payload, {"host"}) == ["host"]

    system = payload["system"]
    assert system["cpu"]["host_cores"] is None
    assert system["memory"]["host_total"] is None
    # Container-relative figures and the container block stay.
    assert system["cpu"]["cores"] == 2
    assert system["memory"]["total"] == 4
    assert system["container"]["runtime"] == "docker"


def test_container_hides_limits_but_keeps_host_totals():
    payload = sample_payload()
    assert apply_redaction(payload, {"container"}) == ["container"]

    system = payload["system"]
    assert system["container"]["detected"] is False
    assert system["container"]["runtime"] is None
    assert system["container"]["cpu_quota"] is None
    assert system["container"]["memory_limit"] is None
    # Host view and the reported figures stay.
    assert system["cpu"]["host_cores"] == 8
    assert system["memory"]["host_total"] == 32
    assert system["cpu"]["percent"] == 10.0


def test_process_hides_only_its_own_fields():
    payload = sample_payload()
    assert apply_redaction(payload, {"process"}) == ["process"]

    process = payload["system"]["process"]
    assert process["pid"] is None
    assert process["memory_rss"] is None
    assert process["cpu_percent"] is None
    assert process["threads"] is None
    assert process["started_at"] is None
    assert payload["system"]["cpu"]["percent"] == 10.0


def test_version_hides_only_the_build_identity():
    payload = sample_payload()
    assert apply_redaction(payload, {"version"}) == ["version"]

    assert payload["service"]["version"] is None
    assert payload["service"]["commit"] is None
    assert payload["service"]["uptime_seconds"] == 120
    assert payload["service"]["name"] == "app"


def test_uptime_hides_only_uptime():
    payload = sample_payload()
    assert apply_redaction(payload, {"uptime"}) == ["uptime"]

    assert payload["service"]["uptime_seconds"] is None
    assert payload["service"]["started_at"] is None
    assert payload["service"]["version"] == "v1"


def test_tasks_hides_totals_but_keeps_recent_activity():
    payload = sample_payload()
    assert apply_redaction(payload, {"tasks"}) == ["tasks"]

    tasks = payload["tasks"]
    assert tasks["total"] is None
    assert tasks["by_status"] == {}
    assert tasks["by_type"] == {}
    assert tasks["recent"] == {"last_hour": 1, "last_24h": 3, "last_7d": 5}


def test_activity_hides_recent_counts_but_keeps_totals():
    payload = sample_payload()
    assert apply_redaction(payload, {"activity"}) == ["activity"]

    tasks = payload["tasks"]
    assert tasks["recent"] == {}
    assert tasks["total"] == 5
    assert tasks["by_status"] == {"completed": 4, "failed": 1}


def test_performance_hides_success_rate_but_keeps_task_totals():
    payload = sample_payload()
    assert apply_redaction(payload, {"performance"}) == ["performance"]

    tasks = payload["tasks"]
    assert tasks["success_rate"] is None
    assert tasks["avg_duration_seconds"] is None
    assert tasks["total"] == 5


def test_queue_blanking_leaves_tasks_alone():
    payload = sample_payload()
    assert apply_redaction(payload, {"queue"}) == ["queue"]

    assert all(value is None for value in payload["queue"].values())
    assert payload["tasks"]["total"] == 5


def test_storage_and_sessions_blank_their_blocks():
    payload = sample_payload()
    applied = apply_redaction(payload, {"storage", "sessions"})

    assert applied == ["sessions", "storage"]
    assert payload["storage"]["uploads"] == {"count": None, "size": None}
    assert payload["storage"]["outputs"] == {"count": None, "size": None}
    assert payload["storage"]["total_size"] is None
    assert payload["sessions"] == {"total": None, "active": None}


def test_system_group_redacts_only_the_three_resource_facets():
    payload = sample_payload()
    applied = apply_redaction(payload, Settings(STATUS_REDACT="system").status_redact_set)

    assert applied == ["cpu", "disk", "memory"]
    assert payload["system"]["cpu"]["percent"] is None
    assert payload["system"]["memory"]["percent"] is None
    assert payload["system"]["disk"]["percent"] is None
    # Everything else survives a bare `system`.
    assert payload["system"]["disk"]["path"] == "/app/storage"
    assert payload["system"]["process"]["pid"] == 7
    assert payload["service"]["version"] == "v1"
    assert payload["tasks"]["total"] == 5
    assert payload["sessions"] == {"total": 5, "active": 2}


@pytest.mark.parametrize("facet", STATUS_REDACTABLE_FACETS)
def test_every_facet_actually_changes_something(facet):
    """A facet that silently does nothing would be a documentation lie."""
    payload = sample_payload()
    assert apply_redaction(payload, {facet}) == [facet]
    assert payload != sample_payload(), f"{facet} did not redact anything"


def test_all_facets_together_leave_no_host_details():
    payload = sample_payload()
    applied = apply_redaction(payload, Settings(STATUS_REDACT="all").status_redact_set)

    assert applied == sorted(STATUS_REDACTABLE_FACETS)
    assert payload["system"]["cpu"]["percent"] is None
    assert payload["system"]["cpu"]["host_cores"] is None
    assert payload["system"]["disk"]["path"] is None
    assert payload["system"]["container"]["detected"] is False
    assert payload["system"]["process"]["pid"] is None
    assert payload["service"]["version"] is None
    assert payload["service"]["uptime_seconds"] is None
    assert payload["tasks"]["total"] is None
    assert payload["storage"]["total_size"] is None
    assert payload["sessions"]["active"] is None
