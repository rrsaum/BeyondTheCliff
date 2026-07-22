#!/usr/bin/env bash
#
# Install the tracker database from a complete backup snapshot, with no CSV rebuild.
#
# The normal setup runs scripts/build_db.py to rebuild data/beyondthecliff.db from the CSV source of
# truth. This instead restores a ready-made snapshot produced by scripts/backup_db.py, so a
# deployment does not have to run any of the SQL builds. It verifies the backup's checksum before
# restoring and the restored database's integrity and row counts after, so a corrupt or partial
# backup fails loudly instead of serving bad data.
#
#   scripts/install.sh                          # restore dist/beyondthecliff.db.gz
#   scripts/install.sh path/to/backup.db.gz     # restore a specific backup
#   scripts/install.sh --force                  # overwrite an existing DB without keeping a copy
#
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
force=0
gz=""
for arg in "$@"; do
  case "$arg" in
    --force) force=1 ;;
    -*) echo "Unknown option: $arg" >&2; exit 2 ;;
    *) gz="$arg" ;;
  esac
done
gz="${gz:-$root/dist/beyondthecliff.db.gz}"
db="$root/data/beyondthecliff.db"

# Locate the manifest next to the backup (either <name>.manifest.json or the default name).
manifest="${gz%.db.gz}.manifest.json"
[ -f "$manifest" ] || manifest="$(dirname "$gz")/beyondthecliff.manifest.json"

if [ ! -f "$gz" ]; then
  echo "No backup found at: $gz" >&2
  echo "Create one with:  python3 scripts/backup_db.py" >&2
  exit 1
fi
gzip -t "$gz" || { echo "Backup is corrupt (failed gzip test): $gz" >&2; exit 1; }

# Verify the backup's checksum against its manifest before trusting it.
if [ -f "$manifest" ]; then
  want="$(python3 -c "import json;print(json.load(open('$manifest'))['sha256'])")"
  got="$(python3 -c "import hashlib;print(hashlib.sha256(open('$gz','rb').read()).hexdigest())")"
  if [ "$want" != "$got" ]; then
    echo "Checksum mismatch: the backup does not match its manifest. Not restoring." >&2
    exit 1
  fi
  echo "Backup checksum verified."
else
  echo "Note: no manifest beside the backup; skipping checksum and row-count checks."
fi

# Never clobber an existing database silently: move it aside unless --force.
if [ -f "$db" ] && [ "$force" -ne 1 ]; then
  bak="$db.$(date +%Y%m%d%H%M%S).bak"
  mv "$db" "$bak"
  echo "Existing database moved to: ${bak#"$root"/}"
fi

mkdir -p "$(dirname "$db")"
gzip -dc "$gz" > "$db"

# Verify the restored database: integrity, and row counts against the manifest.
python3 - "$db" "$manifest" <<'PY'
import json, os, sqlite3, sys

db, manifest = sys.argv[1], sys.argv[2]
con = sqlite3.connect(db)
if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
    sys.exit("Restored database failed integrity_check.")
if os.path.exists(manifest):
    want = json.load(open(manifest))["tables"]
    bad = []
    for table, count in want.items():
        got = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        if got != count:
            bad.append(f"{table}: restored {got} rows, manifest says {count}")
    if bad:
        sys.exit("Row-count mismatch after restore:\n  " + "\n  ".join(bad))
    print(f"Restore verified: integrity OK, all {len(want)} tables match the manifest.")
else:
    print("Restore verified: integrity OK (no manifest for row-count check).")
PY

echo "Database installed at data/beyondthecliff.db"
echo "Serve it with:  .venv/bin/python -m uvicorn app.main:app --reload    (or: docker compose up)"
