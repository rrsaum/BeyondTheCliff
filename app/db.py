"""Read-only SQLite connection to the built tracker database.

The database is a build artifact (scripts/build_db.py); the app only ever reads it, so it
opens in read-only mode. If the file is missing, the caller gets a clear instruction to
build it rather than an opaque sqlite error.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "beyondthecliff.db"


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise RuntimeError(
            f"database not found at {DB_PATH}. Build it first: python3 scripts/build_db.py"
        )
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn
