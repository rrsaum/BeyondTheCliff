# Running more than one session on this repo

Two sessions in this folder at once will overwrite each other. This is not hypothetical: it
happened here, and it is worth reading what it cost before deciding the setup is optional.

## What went wrong once already

Two sessions ran concurrently in the single checkout, both on `main`, both writing:

- **A file was silently destroyed.** Both sessions independently chose the filename
  `data/institutions_open.csv`. One session hand-wrote a curated row there (Montreat College,
  with its EIN). The other session's `scripts/import_ipeds_roster.py` rewrites that file whole
  from IPEDS. The curated row was erased within the hour.
- **The damage was invisible.** The page kept rendering and the database kept building, because
  the overwritten file still contained an institution row for that school. The only symptom was
  `import_990.py` suddenly refusing to match any filing. Nothing failed loudly.
- **The runtime collided.** `docker-compose.yml` hardcoded a container name and host port, so
  the second session's `docker compose up` died on a name conflict and a port bind error.
- **Every edit sat unprotected on one branch.** Both sessions' work piled up uncommitted in one
  tree. A single bad command would have taken all of it.

The lesson is not "be careful". It is that a shared checkout has no mechanism to protect
anything, so care is the only defence and care does not survive a whole-file rewrite.

## Setup: one worktree per session

From the repo root, per session:

```bash
git worktree add ../BeyondTheCliff-<name> -b <name>
cd ../BeyondTheCliff-<name>
printf 'TRACKER_PORT=8004\n' > .env      # pick a free port; see the table below
docker compose up -d                     # own container, own port, no flags to remember
```

Then open the session in that directory. Clean up when the branch is merged:

```bash
docker compose down
git worktree remove ../BeyondTheCliff-<name>
```

`.env` is gitignored, so it is NOT carried into a new worktree. Writing it is a required step,
not an optional one: without it the worktree binds 8002 and collides with the main checkout.

### Ports on this machine

The host port is the only thing that must be chosen by hand. Taken as of this writing:

| Port | Used by |
|---|---|
| 8000 | another project's container |
| 8001 | quantsage-api |
| 8002 | this repo, default checkout (`TRACKER_PORT` default) |
| 8003+ | free, use for additional worktrees |

Check before claiming one: `lsof -nP -iTCP:8004 -sTCP:LISTEN`.

Compose derives the project name from the directory, so `../BeyondTheCliff-featureA` produces
container `beyondthecliff-featurea-tracker-1` automatically. Nothing is hardcoded, and that is
deliberate: see the comments in `docker-compose.yml`.

## Scope the work by file, and say so up front

The single best protection is that two sessions never write the same file. Before starting
parallel work, agree who owns what. The hotspots in this repo, because everything routes
through them:

- `scripts/schema.sql`, `scripts/build_db.py` (every data layer adds a table here)
- `app/queries.py`, `app/charts.py`, `app/main.py` (every feature adds a query, chart, route)
- `CLAUDE.md`, `docs/TODO.md`

**Generated files have exactly one owner: the script that generates them.** Never hand-edit a
file that an importer rewrites whole, and never add a column to one expecting it to survive.
Currently generated, do not hand-edit:

| File | Written whole by |
|---|---|
| `data/institutions_open.csv`, `data/sector_size.csv` | `scripts/import_ipeds_roster.py` |
| `data/composite_scores.csv` | `scripts/import_composite_scores.py` |
| `data/financials.csv`, `data/financial_line_items.csv` | `scripts/import_990.py` |
| `data/beyondthecliff.db` | `scripts/build_db.py` (git-ignored artifact) |

If a fact has no generator and cannot live in a generated file, it needs its own hand-curated
CSV. `data/institution_eins.csv` exists for exactly that reason: IPEDS does not publish EINs, so
the OPEID/EIN crosswalk can never ride along on the IPEDS roster and has its own table.

## Merging back

Git merges line by line, so edits to different parts of a file come forward on their own. Same
or adjacent lines conflict, and nothing is auto-lost, but a reflexive "take mine" is how a
revision gets dropped.

```bash
git checkout main && git merge <first-branch>
git checkout <second-branch> && git rebase main   # replays on top, conflicts one commit at a time
git checkout main && git merge <second-branch>
scripts/verify.sh                                  # a bad resolution still runs, it just misbehaves
```

Resolve to keep **both** intents, not one side. Commit small and merge often: long branches over
the hotspots above are where this gets painful.

## When a worktree is overkill

If the extra session only reads (explores, plans, answers questions), a second terminal on this
folder is fine. The risk is only concurrent writes.
