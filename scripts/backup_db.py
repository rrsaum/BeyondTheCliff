#!/usr/bin/env python3
"""Package the built database into one shippable snapshot, so an install can skip the pipeline.

Normal setup rebuilds data/beyondthecliff.db from the CSV source of truth (scripts/build_db.py,
plus the resilience scoring step). That is fast but needs the whole repo and toolchain. This packs
the ALREADY-BUILT database into a single compressed snapshot plus a manifest, so a deployment can
restore it and serve without running any of the SQL builds (see scripts/install.sh).

Uses SQLite's online-backup API for a consistent copy (safe even while the app holds the DB open
read-only), gzips it, and records per-table row counts and a sha256 the installer verifies against.
Standard library only. Run after building the DB:

    python3 scripts/build_db.py        # make sure the DB is current
    python3 scripts/backup_db.py       # -> dist/beyondthecliff.db.gz + manifest
"""

from __future__ import annotations

import gzip
import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "beyondthecliff.db"
DIST = ROOT / "dist"
GZ = DIST / "beyondthecliff.db.gz"
MANIFEST = DIST / "beyondthecliff.manifest.json"


def table_counts(con: sqlite3.Connection) -> dict[str, int]:
    """Row count per real table. Skips SQLite internals and the FTS shadow tables (whose internal
    layout is version-specific and is rebuilt from the indexed data anyway)."""
    names = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "AND name NOT LIKE 'institution_search_%' ORDER BY name"
        )
    ]
    return {n: con.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def main() -> None:
    if not DB.exists():
        raise SystemExit(
            f"No database at {DB.relative_to(ROOT)}. Build it first: python3 scripts/build_db.py"
        )
    DIST.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "snapshot.db"
        src = sqlite3.connect(DB)
        dst = sqlite3.connect(snap)
        src.backup(dst)  # consistent online snapshot
        src.close()
        dst.close()
        chk = sqlite3.connect(snap).execute("PRAGMA integrity_check").fetchone()[0]
        if chk != "ok":
            raise SystemExit(f"snapshot failed integrity_check: {chk}")
        counts = table_counts(sqlite3.connect(snap))
        raw = snap.read_bytes()

    with gzip.open(GZ, "wb", compresslevel=9) as fh:
        fh.write(raw)
    sha = hashlib.sha256(GZ.read_bytes()).hexdigest()
    MANIFEST.write_text(
        json.dumps(
            {
                "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "file": GZ.name,
                "sha256": sha,
                "bytes_gz": GZ.stat().st_size,
                "bytes_db": len(raw),
                "sqlite_version": sqlite3.sqlite_version,
                "tables": counts,
            },
            indent=2,
        )
        + "\n"
    )
    total = sum(counts.values())
    print(
        f"Backup:   {GZ.relative_to(ROOT)}  "
        f"({GZ.stat().st_size / 1048576:.1f} MB gz, {len(raw) / 1048576:.0f} MB db)"
    )
    print(
        f"Manifest: {MANIFEST.relative_to(ROOT)}  "
        f"({len(counts)} tables, {total:,} rows, sha256 {sha[:12]}...)"
    )
    print("Ship both files together. Restore with: scripts/install.sh")


if __name__ == "__main__":
    main()
