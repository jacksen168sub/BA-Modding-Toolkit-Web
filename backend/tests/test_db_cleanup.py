# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 jacksen168sub
#
# Verifies the one-off startup cleanup that removes legacy SPLIT/MERGE task rows.
# SQLAlchemy's Enum persists member NAMES, so the rows are stored as 'SPLIT'/'MERGE';
# leaving them would make the next Task load raise LookupError once the enum members
# were removed.

from sqlalchemy import create_engine

from app.models import database
from app.models.task import TaskType


def _insert_legacy_task(engine, task_id: str, type_name: str):
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "INSERT INTO tasks (id, session_uuid, type, status, options, created_at, expires_at) "
            "VALUES (:id, 's1', :type, 'PENDING', '{}', '2026-01-01 00:00:00', '2030-01-01 00:00:00')",
            {"id": task_id, "type": type_name},
        )


def test_init_db_removes_legacy_split_and_merge_rows(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setattr(database, "engine", engine)

    database.Base.metadata.create_all(bind=engine)
    _insert_legacy_task(engine, "t-split", "SPLIT")
    _insert_legacy_task(engine, "t-merge", "MERGE")
    _insert_legacy_task(engine, "t-update", "UPDATE")

    database.init_db()

    with engine.begin() as conn:
        legacy = conn.exec_driver_sql(
            "SELECT count(*) FROM tasks WHERE type IN ('SPLIT','MERGE')"
        ).scalar()
        kept = conn.exec_driver_sql("SELECT count(*) FROM tasks").scalar()

    assert legacy == 0
    assert kept == 1  # the UPDATE task survives


def test_legacy_value_is_the_enum_member_name():
    """Pins the storage format the cleanup SQL depends on."""
    assert {t.name for t in TaskType} == {"UPDATE", "PACK", "EXTRACT", "CRC"}
