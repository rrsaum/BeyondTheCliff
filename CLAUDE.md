# Beyond the Cliff: working agreement

Beyond the Cliff is R.R. Saum's futurist authority brand tracking the contraction of
American higher education (the enrollment cliff, closures, consolidations) and mapping
the way through it. The site is both a public tracker and a credibility engine: it exists
to position the author as the analyst who sees what is coming AND has a thesis about
survival, and to open consulting conversations with the presidents, provosts, CFOs, and
boards of tuition-dependent institutions.

The reader is the struggling school, not a spectator. That single fact governs everything
below: the tracker draws the traffic, but the brand belongs to the solution, never the
disaster. Reader-facing trust is the product, so copy, tone, and UI standards are binding,
not advisory.

Umbrella brand is **Beyond the Cliff**; the tracker ships as a named feature inside it
(e.g. *The Closure & Consolidation Map*), so the morbid-curiosity traffic never becomes the
brand voice.

## Stack and how to run

The closure tracker is a **FastAPI + Jinja app over SQLite** (`app/`), chosen for a small
curated dataset with one maintainer: simple, portable, no server to run. Data flows
CSV -> SQLite:

```
python3 scripts/import_sheeo.py        # (re)seed data/*.csv from the SHEEO source spreadsheet
python3 scripts/import_ipeds_roster.py --commit      # who is still open + sector size, from IPEDS
python3 scripts/import_composite_scores.py --all --commit   # ED financial responsibility scores
python3 scripts/build_db.py            # build data/beyondthecliff.db from data/*.csv
.venv/bin/python -m uvicorn app.main:app --reload   # serve the tracker
```

Both importers preview by default and write nothing without `--commit`, and both are wrapped
by the browser console at `/admin/composite`, so a year loaded there and a year loaded here
produce identical rows.

Or run the whole thing in Docker, which rebuilds the DB and serves the app in one step:

```
docker compose up      # tracker on http://localhost:8002 (-d to background it)
docker compose down    # stop it
```

The compose service bind-mounts the repo, so `/admin` edits to `data/*.csv` land in the
working tree where git sees them, and uvicorn `--reload` still picks up code edits. The host
port is `TRACKER_PORT` (default 8002) and the container name is derived from the directory, so
each worktree gets its own stack. Nothing is hardcoded; see "More than one session at once".

## More than one session at once (binding)

**Never run a second writing session in this checkout. Use a worktree.** Full procedure and the
port table: `docs/technical/PARALLEL_SESSIONS.md`. Invoke the `parallel-sessions` skill when a
session starts alongside another, or the moment a file changes under you mid-edit.

```
git worktree add ../BeyondTheCliff-<name> -b <name>
cd ../BeyondTheCliff-<name> && printf 'TRACKER_PORT=8003\n' > .env   # .env is NOT carried over
docker compose up -d
```

This is not a style preference. Two sessions shared this checkout once and one silently
destroyed the other's curated data by regenerating a file they had both picked as an output
name. Nothing failed loudly; the only symptom was an importer quietly matching nothing.

Two rules that follow, and both are absolute:

- **A generated file has one owner: its generator.** Never hand-edit a file an importer
  rewrites whole (`data/institutions_open.csv`, `data/sector_size.csv`,
  `data/composite_scores.csv`, `data/financials.csv`, `data/financial_line_items.csv`), and
  never add a column to one expecting it to survive. It will not.
- **A hand-curated fact needs its own hand-curated CSV.** `data/institution_eins.csv` is the
  OPEID/EIN crosswalk precisely because IPEDS publishes no EIN, so it can never ride along on
  the IPEDS-generated roster.

The `data/*.csv` files are the source of truth (committed); `data/beyondthecliff.db` is a
git-ignored build artifact, rebuilt in about half a second, so it is never backed up or
restored: commit the CSVs and the DB follows. Full detail: `docs/technical/DATA_MODEL.md`. Charts are
server-rendered (no JS/CDN dependency). The repo also holds the Claude working config and
the writing/copy/design/style standards ported from the author's other projects.

Still TBD and not yet built (do not assume they exist): IPEDS enrichment for founding year
and enrollment, coverage beyond 2004 to 2020, and the marketing/brand pages. Verify before
describing anything as present.

## The denominator, and what it is not

The database holds both closures and survivors, and they come from different sources and must
never be conflated:

- **Who is open** is the IPEDS HD roster (`data/institutions_open.csv`, `status = 'open'`), a
  snapshot of the newest NCES collection year. `status_year` on an open row means "confirmed
  open through", never "open today". Every list, chart, and count in `app/queries.py` excludes
  open institutions unless `status=open` is asked for explicitly, because listing a healthy
  school on a closure map misrepresents it. `total_count()` is closures only.
- **How big the sector is** is `sector_size` (per year, per control, from IPEDS HD). Always
  chart it broken out by control. Roughly 84% of the 2012 to 2024 decline is the for-profit
  sector contracting; a single total line tells a tuition-dependent private nonprofit its
  sector collapsed by a fifth, which is not what the data says.
- **Composite scores** (`composite_score`) cover PRIVATE NONPROFIT AND PROPRIETARY SCHOOLS ONLY.
  ED does not score public institutions (34 CFR 668.171(g)): they qualify on full faith and
  credit instead. This is a structural limit, not a coverage gap, and any rate off this table
  must say so. ED also rewrote the ratios effective 1 July 2020 (84 FR 49788), so scores either
  side of the AY 2019-20 / 2020-21 boundary are not the same measurement: `COMPOSITE_BREAK` in
  `app/queries.py` draws that break and no line is ever joined across it.

Rows an importer cannot honestly resolve are never guessed into a status. They go to
`scripts/_composite_review.csv` and `scripts/_roster_review.csv` for adjudication.

## Content and copy standards are MANDATORY

Before writing or editing ANY reader-facing copy, page, UI text, or headline, follow the
standards in `docs/standards/`:

- `docs/standards/MARKETING_STYLE_GUIDE.md` (authoritative: voice, vocabulary, prohibited
  terms, PAS framework, UI copy standards). Inherited from the studio, so its finance
  vocabulary and expert roster are being adapted to higher ed; the voice, craft, and
  discipline transfer directly. When the guide and instinct conflict, the guide wins.
- `docs/standards/DESIGN_AND_COPY.md` is the map of every design/UI/copy authority.
- `docs/standards/UI_UX_PRINCIPLES.md` is the design-reasoning standard for any non-trivial
  UI decision.
- `docs/standards/VALUES_AND_CONDUCT.md` and `docs/standards/ENFORCEMENT.md` set the
  conduct floor and the enforcement model.

The `.claude/skills/` library carries the craft: `writing-style`, `writing-guide`,
`writing-headlines`, `writing-rhetoric`, `writing-sticky-ideas`, `writing-humanizer`,
`copy`, `copywriting-craft`, `content-marketing`, `analytical-writing`, `brand`,
`persuasion-psychology`, `manipulation-detection`, `design-system`, and `ux-review`.
Use them.

## No interface ships without mockups (binding)

**Any interface change, and any chart, goes to design first. Design proposes THREE visual
mockups, in the browser, to select from or refine. Nothing is implemented until one is chosen.**
This applies to a new chart, a redesigned one, a new page or panel, and any non-trivial layout
change. It does not apply to a defect fix that restores intended behaviour (a chart rendering
wrong is a bug, fix it), or to copy edits inside an approved layout.

How to run it:

1. **Load `dataviz` BEFORE the first line of chart code**, not after. Its own instruction says
   so, and its `references/anti-patterns.md` is the checklist the result gets held to. Load
   `design-system` for UI structure and `ux-review` to evaluate a surface.
2. **Build three mockups on one page**, with the real data, served from `app/static/` so it opens
   in the browser like everything else. Do not describe them in prose: a mockup is a thing you
   look at.
3. **Say what each one costs**, not just what it does, and name the decisions that are genuinely
   the reader's to make (axis domain, colour meaning, form). One recommendation each, stated.
4. **Implement the chosen one**, matching what was actually on screen when it was chosen.

Why this is a rule and not a preference: a chart shipped straight to the page shipped with the
threshold labels printed across the data, an axis 40% empty, and every line rendered as a filled
polygon. It reached the reader because there was no gate between writing it and serving it. The
review page is the gate.

## Factual honesty (enforced)

Accuracy is the whole basis of the authority position. Never fabricate. The standard is
binding and re-asserted every turn by the `UserPromptSubmit` honesty hook.

- **Cite the source of every claim:** `file:line`, command output, or URL. A claim with no
  source is a guess and must be labelled as one.
- **Separate verified fact from inference,** and label inference as inference. Do not
  present a recalled API detail or an assumed file, function, or flag as established fact
  without confirming it exists.
- **Every data point about a school** (a closure, an enrollment figure, a financial ratio,
  a trend) must be sourced to a primary record (IPEDS, an audited filing, an accreditor
  action, a dated news report). Never originate a number. Bands and ranges are fine when
  the basis is stated; a bare point estimate presented as data is not.
- **If you did not read it or run it, say so.** Prefer "I do not know" or "let me check"
  over a confident unverified answer.
- **"Done" means verified by a command, not asserted.** See "Verify before done."

## Hard rules (binding)

- **No typographic em-dash (U+2014) anywhere.** Not copy, not docs, not code comments, not
  commit messages. Split the sentence, or use a colon, comma, or parentheses. Hyphens and
  en-dashes in numeric ranges are fine. Mechanically enforced everywhere by
  `scripts/style_lint.py`.
- **Never a death-watch.** The brand points past the cliff. In reader-facing copy do not
  gloat, catastrophize, or run a funeral watch on the schools you want as clients
  ("death spiral", "doomed", "apocalypse", and the like). Grim source facts are reported
  soberly and sourced; the framing always turns toward the way through. `style_lint.py`
  surfaces the obvious tone leaks as advisories; the rule is broader than the blocklist.
- **No hollow buzzwords.** Authority comes from precision, not hype. Name the specific
  thing instead of reaching for "world-class", "cutting-edge", "game-changer",
  "thought leader", "AI-powered", and their kin. Advisory in `style_lint.py`.
- **No political commentary.** Closures and demographics are politically charged; a reader
  must not be able to determine the author's politics from the copy. Report the demographic
  and policy facts, not a partisan read of them.

## Code and Python style (enforced where code exists)

- Python is linted and formatted by ruff. Run `ruff check <files>; ruff format <files>` on
  any `.py` you touch and fix findings before claiming done. A `PostToolUse` hook warns on
  edited files.
- Reuse first: before adding a route, table, helper, or component, check what already
  exists and reuse it. Run `/simplify` (reuse + simplification) and `/code-review`
  (correctness) before merging non-trivial work. The `lean-code-reviewer` agent is
  available for a focused bloat/reuse pass.
- When a UI does exist, follow `design-system` and `ux-review`: semantic accessible markup,
  design tokens over raw hex, WCAG 2.1 AA, no inline styles for repeated markup.

## Verify before done

Before claiming work is done, run the one gate that covers every changed file:

```
scripts/verify.sh            # style guide + ruff on changed files
scripts/verify.sh --tests    # also run the pytest suite, if one exists
```

This turns "it works / it's clean" into evidence instead of a claim. A `Stop` hook runs
`scripts/verify.sh` at the done boundary and wakes you with the failures if anything is
unverified, so "done" cannot mean "unchecked." For copy work alone you can run
`python3 scripts/style_lint.py <files you changed>`.

## Engineering notes

- First clone setup: run `scripts/install-hooks.sh` once to activate the pre-commit gate
  (style + ruff on staged files) if a `.githooks/` directory has been added.
- `.claude/` is intentionally git-ignored in the sibling projects (local settings, skills,
  everything). Decide per this repo whether to commit it; the standards in `docs/` are meant
  to be shared.
