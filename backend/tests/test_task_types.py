# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub
#
# Guards the removal of the split/merge task types (kernel v2.9.2 dropped the
# split/merge commands they wrapped).

from app.models.task import TaskType
from app.routers import tasks as tasks_router


def test_task_type_has_no_split_or_merge():
    values = {t.value for t in TaskType}
    assert values == {"update", "pack", "extract", "crc"}
    assert "split" not in values
    assert "merge" not in values


def test_tasks_router_exposes_no_split_or_merge_endpoints():
    paths = {route.path for route in tasks_router.router.routes}
    assert "/tasks/split" not in paths
    assert "/tasks/merge" not in paths
    # The surviving endpoints are still present.
    for expected in ("/tasks/update", "/tasks/pack", "/tasks/extract", "/tasks/crc"):
        assert expected in paths
