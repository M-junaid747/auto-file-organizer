"""
logger_db.py
------------
Handles all SQLite persistence for the Desktop Automation System.

Responsibilities:
1. Store a hash of every file ever processed (for duplicate detection
   across runs, not just within a single run).
2. Store every move made, tagged with a batch_id, so an entire run
   can be undone with one command.
3. Provide read helpers used by main.py for reporting and undo.

This module is intentionally the ONLY place that touches the database.
Every other module calls into here rather than running raw SQL itself,
so the schema only has to be known in one place.
"""

import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

DB_FILENAME = "organized_log.db"


def get_db_path(base_dir: Path) -> Path:
    """Resolve the database path relative to the project's base directory."""
    return base_dir / DB_FILENAME


def init_db(db_path: Path) -> None:
    """
    Create the required tables if they do not already exist.
    Safe to call on every run.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS file_hashes (
            hash TEXT PRIMARY KEY,
            first_seen_path TEXT NOT NULL,
            first_seen_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS moves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            original_path TEXT NOT NULL,
            new_path TEXT NOT NULL,
            file_hash TEXT,
            action_type TEXT NOT NULL,
            reverted INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    conn.commit()
    conn.close()


def new_batch_id() -> str:
    """Generate a unique ID for this run, so all its moves can be grouped and undone together."""
    return str(uuid.uuid4())


def is_known_hash(db_path: Path, file_hash: str) -> bool:
    """Return True if this hash has been seen in a previous run (true duplicate)."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM file_hashes WHERE hash = ?", (file_hash,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def record_hash(db_path: Path, file_hash: str, file_path: str) -> None:
    """Store a newly seen file hash. Ignored if it already exists."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO file_hashes (hash, first_seen_path, first_seen_at) VALUES (?, ?, ?)",
        (file_hash, file_path, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def record_move(
    db_path: Path,
    batch_id: str,
    original_path: str,
    new_path: str,
    file_hash: str,
    action_type: str,
) -> None:
    """
    Log a single file move so it can be reported on and undone later.
    action_type is one of: 'moved', 'duplicate', 'archived'.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO moves (batch_id, timestamp, original_path, new_path, file_hash, action_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (batch_id, datetime.now().isoformat(), original_path, new_path, file_hash, action_type),
    )
    conn.commit()
    conn.close()


def get_latest_batch_id(db_path: Path) -> str | None:
    """Find the most recent batch_id that has not been fully reverted."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT batch_id FROM moves
        WHERE reverted = 0
        ORDER BY id DESC
        LIMIT 1
        """
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_moves_for_batch(db_path: Path, batch_id: str) -> list[tuple]:
    """Return all move records for a given batch_id, most recent first."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, original_path, new_path, action_type FROM moves
        WHERE batch_id = ? AND reverted = 0
        ORDER BY id DESC
        """,
        (batch_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_reverted(db_path: Path, move_id: int) -> None:
    """Mark a single move record as reverted so it can't be undone twice."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE moves SET reverted = 1 WHERE id = ?", (move_id,))
    conn.commit()
    conn.close()


def get_batch_summary(db_path: Path, batch_id: str) -> dict:
    """Return counts grouped by action_type for a given batch — used in the report."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT action_type, COUNT(*) FROM moves
        WHERE batch_id = ?
        GROUP BY action_type
        """,
        (batch_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return dict(rows)
