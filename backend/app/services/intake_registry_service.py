from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def intake_paths(root: Path) -> dict[str, Path]:
    return {
        "intake_root": root / "00_admin" / "intake",
        "registry": root / "00_admin" / "intake" / "utility_intake.sqlite",
        "raw_submissions": root / "01_raw" / "submissions",
        "temp_uploads": root / "temp" / "uploads",
        "logs": root / "logs" / "intake",
    }


def ensure_intake_storage(root: Path) -> dict[str, Path]:
    paths = intake_paths(root)
    for key, path in paths.items():
        if key != "registry":
            path.mkdir(parents=True, exist_ok=True)
    with connect(root) as connection:
        initialize(connection)
    return paths


def connect(root: Path) -> sqlite3.Connection:
    paths = intake_paths(root)
    paths["intake_root"].mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(paths["registry"])
    connection.row_factory = sqlite3.Row
    initialize(connection)
    return connection


def initialize(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS intake_submissions (
            submission_id TEXT PRIMARY KEY,
            submission_name TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            utility_system TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_format TEXT NOT NULL,
            source_owner TEXT NOT NULL,
            source_description TEXT NOT NULL,
            sensitivity_level TEXT NOT NULL,
            project_id TEXT,
            submitted_by TEXT,
            authorization_confirmed INTEGER NOT NULL,
            file_size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            mime_type TEXT,
            extension TEXT,
            current_status TEXT NOT NULL,
            current_stage TEXT NOT NULL,
            inventory_status TEXT NOT NULL,
            classification_status TEXT NOT NULL,
            staging_status TEXT NOT NULL,
            duplicate_of_submission_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            raw_registered_at TEXT,
            inventory_started_at TEXT,
            inventory_completed_at TEXT,
            error_category TEXT,
            safe_error_message TEXT,
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_intake_submissions_sha256 ON intake_submissions(sha256);
        CREATE INDEX IF NOT EXISTS idx_intake_submissions_stage ON intake_submissions(current_stage);

        CREATE TABLE IF NOT EXISTS intake_events (
            event_id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            previous_status TEXT,
            new_status TEXT,
            message TEXT NOT NULL,
            actor TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS intake_files (
            file_id TEXT PRIMARY KEY,
            submission_id TEXT NOT NULL,
            safe_filename TEXT NOT NULL,
            relative_role TEXT NOT NULL,
            extension TEXT,
            size_bytes INTEGER,
            sha256 TEXT,
            validation_status TEXT NOT NULL,
            notes TEXT
        );
        """
    )
    connection.commit()


def insert_submission(root: Path, row: dict[str, Any]) -> None:
    with connect(root) as connection:
        columns = ", ".join(row)
        placeholders = ", ".join("?" for _ in row)
        connection.execute(f"INSERT INTO intake_submissions ({columns}) VALUES ({placeholders})", tuple(row.values()))
        connection.commit()


def update_submission(root: Path, submission_id: str, **updates: Any) -> None:
    if not updates:
        return
    updates["updated_at"] = utc_now()
    with connect(root) as connection:
        assignments = ", ".join(f"{key} = ?" for key in updates)
        connection.execute(f"UPDATE intake_submissions SET {assignments} WHERE submission_id = ?", (*updates.values(), submission_id))
        connection.commit()


def add_event(
    root: Path,
    *,
    event_id: str,
    submission_id: str,
    event_type: str,
    message: str,
    previous_status: str = "",
    new_status: str = "",
    actor: str = "",
) -> None:
    with connect(root) as connection:
        connection.execute(
            """
            INSERT INTO intake_events (event_id, submission_id, event_type, previous_status, new_status, message, actor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_id, submission_id, event_type, previous_status, new_status, message, actor, utc_now()),
        )
        connection.commit()


def add_file(root: Path, row: dict[str, Any]) -> None:
    with connect(root) as connection:
        connection.execute(
            """
            INSERT INTO intake_files (file_id, submission_id, safe_filename, relative_role, extension, size_bytes, sha256, validation_status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["file_id"],
                row["submission_id"],
                row["safe_filename"],
                row["relative_role"],
                row.get("extension", ""),
                row.get("size_bytes", 0),
                row.get("sha256", ""),
                row.get("validation_status", ""),
                row.get("notes", ""),
            ),
        )
        connection.commit()


def find_duplicate(root: Path, sha256: str) -> str | None:
    with connect(root) as connection:
        row = connection.execute(
            "SELECT submission_id FROM intake_submissions WHERE sha256 = ? AND current_stage = 'raw' ORDER BY created_at LIMIT 1",
            (sha256,),
        ).fetchone()
    return str(row["submission_id"]) if row else None


def get_submission(root: Path, submission_id: str) -> dict[str, Any] | None:
    with connect(root) as connection:
        row = connection.execute("SELECT * FROM intake_submissions WHERE submission_id = ?", (submission_id,)).fetchone()
    return dict(row) if row else None


def list_submissions(
    root: Path,
    *,
    status: str | None = None,
    utility_system: str | None = None,
    source_format: str | None = None,
    current_stage: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    clauses: list[str] = []
    values: list[Any] = []
    for field, value in {
        "current_status": status,
        "utility_system": utility_system,
        "source_format": source_format,
        "current_stage": current_stage,
    }.items():
        if value:
            clauses.append(f"{field} = ?")
            values.append(value)
    if search:
        clauses.append("(LOWER(submission_name) LIKE ? OR LOWER(original_filename) LIKE ?)")
        needle = f"%{search.lower()}%"
        values.extend([needle, needle])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect(root) as connection:
        total = connection.execute(f"SELECT COUNT(*) AS count FROM intake_submissions {where}", values).fetchone()["count"]
        rows = connection.execute(
            f"SELECT * FROM intake_submissions {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*values, limit, offset),
        ).fetchall()
    return [dict(row) for row in rows], int(total)


def list_events(root: Path, submission_id: str) -> list[dict[str, Any]]:
    with connect(root) as connection:
        rows = connection.execute(
            "SELECT event_id, submission_id, event_type, previous_status, new_status, message, actor, created_at FROM intake_events WHERE submission_id = ? ORDER BY created_at",
            (submission_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_files(root: Path, submission_id: str) -> list[dict[str, Any]]:
    with connect(root) as connection:
        rows = connection.execute(
            "SELECT safe_filename, relative_role, extension, size_bytes, sha256, validation_status, notes FROM intake_files WHERE submission_id = ? ORDER BY relative_role, safe_filename",
            (submission_id,),
        ).fetchall()
    return [dict(row) for row in rows]
