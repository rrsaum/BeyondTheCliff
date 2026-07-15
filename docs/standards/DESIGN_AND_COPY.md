# Design & Copy: the standards map

The single entry point for every design, UI, and copy standard in 360Investor. Start here, then go to the owner. This doc is a **map and an enforcement ledger**, not a new rulebook: it points to where each rule lives and tells you which rules are mechanically caught versus which are on your judgment.

**The honest line up front:** a green build is the floor, not proof of good design or good copy. The gates below catch the mechanically-checkable rules. The judgment rules (does it sound like advice? does it make the reader think? is it reduced and finished?) are not gated and never will be. Those are held by the skills, the docs, and pre-merge review.

---

## The ritual (do this every time)

**Before you write design or copy:** load the owning skill. It pulls the binding rules into context so you are not working from memory.
- Building or editing a template, component, page, or CSS: `design-system` skill.
- Writing any member-facing string (button, label, alert, empty state, tier copy, email): `copy` skill.
- A UI/UX judgment call (should this exist? how should it behave?): `docs/standards/UI_UX_PRINCIPLES.md` (loaded by `design-system`).
- Persuasive long-form (landing/sales page, hero): `copywriting-craft`. Brand/positioning/naming: `brand`.

**While you edit:** the PostToolUse hooks run `style_lint`, `ruff`, and `html_audit` on the file and print findings. Treat any finding as fix-now.

**Before you merge:** run the review pass.
- `/simplify` then `/code-review` (reuse, simplification, correctness).
- `ux-review` skill for any user-facing flow (usability heuristics).
- `scripts/verify.sh --tests` (style + ruff on changed files, plus the suite).
- For a locked surface (the Brief), the visual-regression suite must stay green: `python -m pytest tests/visual` from `intelligence_api/`.

---

## Authority map (who owns what)

| Domain | Authority | What it owns |
|---|---|---|
| **Copy: voice, vocabulary, advice-tone, IP, color systems** | `docs/standards/MARKETING_STYLE_GUIDE.md` | The binding copy rules: voice, prohibited terms and punctuation, "never sounds like advice," PAS, tier copy, public-page IP, the four LOCKED color systems, and the "Experts We Draw On" roster. |
| **UI/UX design reasoning** | `docs/standards/UI_UX_PRINCIPLES.md` | The design team distilled (Norman, Krug, Tufte, Ive, Mossberg, plus Ogilvy/Schwartz/Wiebe for UI copy): the cross-cutting house principle (always give context and directionality), operating principles, the tie-break order, the decision checklist, and the visual-fundamentals (type/space/color) standard. |
| **Design tokens (single source)** | `intelligence_api/static/css/tokens.css` | Canonical color, spacing (`--sp-*`), type (`--fs-*`), and radius tokens, linked by both shells. The minimal scales are the house standard for all new UI. |
| **The mechanical design system** | `design-system` skill | Where styling lives (`app.css`, `app-shell.css`), component macros (`_components.html`), the no-inline-style / no-raw-hex rules, and the accessibility floor. |
| **Member-facing strings** | `copy` skill | Constructs and validates every UI/marketing string against the style-guide rules. This is the gate the words pass. |
| **Persuasive copy construction** | `copywriting-craft` skill | Long-form sales/landing/hero copy technique (Ogilvy, Schwartz, Wiebe), adapted to the Sage reader. |
| **Brand strategy** | `brand` skill + `docs/strategy/COMPETITIVE_POSITIONING.md` | Positioning, the Sage/Ruler archetype, the Alex persona, naming, narrative. The layer above string-level copy. |
| **Evaluating a finished surface** | `ux-review` skill | Audits a flow against usability heuristics (Norman, Krug, Ive, Tufte) as a real member. |
| **Long-form explanatory prose** | `analytical-writing` skill | The Brief synthesis, Learn write-ups, methodology explainers. |
| **Values and conduct** | `docs/standards/VALUES_AND_CONDUCT.md` | The LOCKED values + code-of-conduct charter (pointer layer, not an enforcement surface). |
| **Legal / compliance gate** | `compliance` skill | Before shipping anything with legal risk (advice tone, claims, data, billing, tracking). |

Code and engineering standards (honesty, migrations, reuse-first, ruff) live in `CLAUDE.md` and the `migration` skill; they are out of scope for this design/copy map.

---

## Enforcement ledger (what is actually certain)

Three tiers. Know which tier a rule is in before you trust it.

### Tier 1: mechanically gated (blocks, or is one switch from blocking)

| Rule | Gate | Where it runs |
|---|---|---|
| No em-dash (U+2014) anywhere | `style_lint.py` | PostToolUse hook, pre-commit, CI (`style-lint`), `verify.sh` |
| No forbidden jargon in member templates | `style_lint.py` | same |
| Python lint + format | `ruff` | PostToolUse hook, pre-commit, CI (`ruff`), `verify.sh` |
| No duplicate table / column / route | `schema_audit.py`, `route_audit.py` | PreToolUse guard, CI (`schema-route-audit`) |
| No raw hex that has a token, **in CSS files** (`app.css`, `app-shell.css` are swept to zero) | `style_lint.py` (`[hex-token]`) | PostToolUse hook, pre-commit, CI (`style-lint`), `verify.sh` |
| Static a11y / SEO / CWV (heading order, alt, labelable controls, title/meta/JSON-LD, image dims) | `html_audit.py` | PostToolUse hook, CI (`html-audit`); ships advisory, graduates via its `BLOCK_HARD` switch |
| Behavioral correctness | `pytest` | CI (`test-suite`), `verify.sh --tests` |
| Locked Brief stays pixel-identical | visual-regression suite | `tests/visual` (run before merging refactors) |

### Tier 2: advisory (surfaced, does not block)

These print as `[advisory]` and are a fix-now nudge, not a gate. They graduate to Tier 1 as the legacy debt clears.

- Inline `style="..."` in templates (use a class or macro).
- Raw hex that already has a token (`#2563eb -> var(--blue)`), in **template inline styles** (~600 legacy occurrences remain; the CSS-file half of this rule is now hard, Tier 1 above).
- "Experts We Draw On" roster names appearing in member copy.
- Political-reference markers in member copy.
- Duplicated blocks, over-long modules, complexity smells (`quality_audit.py`).

### Tier 3: judgment only (no gate exists, and none can)

These are binding but **not** mechanically checkable. A clean build says nothing about them. They are held by the owning skill and by pre-merge review.

- **Copy never sounds like advice.** (style guide + `copy` skill; the narrow name-check is advisory only.)
- **No political commentary** beyond the blocklist (the rule is broader than any list).
- **"Don't make me think" / visual restraint / data-ink / reduced-and-finished.** (`docs/standards/UI_UX_PRINCIPLES.md` + `ux-review`.)
- **WCAG 2.1 AA beyond the static slice:** contrast, focus order, keyboard operability, reduced-motion, meaningful alt text. (`design-system`.)
- **Responsive/fluid and Core Web Vitals as runtime metrics.** (verify by resizing and measuring, not by a parser.)

---

## Making it more certain over time

Certainty grows by moving rules from Tier 3 to Tier 2 to Tier 1, not by writing more prose:

1. **Clear the legacy debt** behind each Tier 2 advisory (de-inline styles, replace raw hex with tokens), then flip it to a hard block. **Done once:** `app.css` and `app-shell.css` were swept to zero token-duplicate hex, so the hex rule is now hard for CSS files (`[hex-token]`). The remaining lever here is the ~600 inline-style hexes across the templates; clearing those (de-inline into classes/macros) lets the same rule extend to templates.
2. **Graduate `html_audit.py`** via its `BLOCK_HARD` switch once templates are clean.
3. **Add visual baselines** for more surfaces so more of the UI is regression-locked (member-console baselines exist for the account and Learn surfaces; the daily macro pages are intentionally excluded as non-deterministic).
4. **Keep the judgment rules in front of people** by loading the owning skill at the start of the work, which this doc and `CLAUDE.md` both route to.

*This doc is the index; the gates are the enforcement; the skills hold the judgment. Keep all three in sync: when a rule moves tiers, update the ledger here.*
