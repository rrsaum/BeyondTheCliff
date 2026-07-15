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
python3 scripts/import_sheeo.py   # (re)seed data/*.csv from the SHEEO source spreadsheet
python3 scripts/build_db.py       # build data/beyondthecliff.db from data/*.csv
.venv/bin/python -m uvicorn app.main:app --reload   # serve the tracker
```

The `data/*.csv` files are the source of truth (committed); `data/beyondthecliff.db` is a
git-ignored build artifact. Full detail: `docs/technical/DATA_MODEL.md`. Charts are
server-rendered (no JS/CDN dependency). The repo also holds the Claude working config and
the writing/copy/design/style standards ported from the author's other projects.

Still TBD and not yet built (do not assume they exist): IPEDS enrichment for founding year
and enrollment, coverage beyond 2004 to 2020, and the marketing/brand pages. Verify before
describing anything as present.

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
