# Strategic Audit Template

A reusable instrument for evaluating progress, the roadmap, and the strategic docs (`VISION.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `Built.md`). Copy it, fill it in, act on the accepted revisions, archive the result.

> This is the *recurring* successor to the one-off strategic audit of 2026-05-24. Its design fixes that audit's blind spot: a single audit produces findings; a recurring audit must also hold itself accountable to its own prior findings and track drift as a trend.

---

## How to run an audit

1. **Copy** this file to `docs/archive/AUDIT_YYYY-MM-DD.md`.
2. **Fill it in.** Sections 1–3 and 5 run *every time* (they're the recurring backbone). Section 4 is a rotating lens panel — pick 3–4 lenses, rotating so the same blind spot isn't examined twice running.
3. **Apply only accepted revisions** to the active strategic docs. The audit itself stays in `docs/archive/` — it never becomes a fifth active strategic doc. (This mirrors how the 2026-05-24 audit was handled.)
4. **Set the next review date** in Section 8 before you close.

### Cadence & triggers

Run at **every phase boundary** *and* **quarterly**, whichever comes first. Also trigger an off-cycle audit on any of:

- A major frontier-model release (changes the disintermediation baseline and the A/B calculus)
- The first paying customer (unit economics stops being N/A)
- Regulatory news touching AI investment commentary (the advice line moves)
- A **missed ship date or a phase that slipped > 50% past estimate** (execution honesty)
- Any month the operator made zero contact with a real or prospective customer

---

## 0. Metadata

- **Date:**
- **Auditor / lenses used:**
- **Trigger:** (phase boundary / quarterly / model release / first customer / regulatory / slip / other)
- **Scope:** which docs + which phase is current
- **Prior audit:** link to the previous `docs/archive/AUDIT_*.md`

---

## 1. Health scorecard *(every audit)*

The recurring backbone. Fill what exists; **`N/A` is a valid entry and is itself a signal.** A number trending the wrong way for two audits running is a finding even if no lens flagged it.

| Metric | This audit | Last audit | Trend | Healthy when | How to get it |
|---|---|---|---|---|---|
| Backlog item count | | | | flat or shrinking | `ROADMAP.md` → Backlog |
| "What We Will Not Build" count | | | | growing with the backlog | `ROADMAP.md` → anti-features |
| Active Guiding Principles count | | | | ≤ 6 | `VISION.md` |
| Exactly one phase specced under "Next"? | | | | always yes | `ROADMAP.md` |
| Days since last phase shipped | | | | < phase estimate | `Built.md` |
| Days since last real-customer contact | | | | < 30 | discovery/beta log |
| Automated test count | | | | growing with code | `grep -rh "def test_" intelligence_api/tests \| wc -l` |
| Subscriber surfaces at WCAG 2.1 AA | | | | all of them | per-surface a11y review |
| Open findings carried from last audit | | | | trending to 0 | prior audit §6 |
| Active strategic-doc total line count | | | | lean, not ballooning | `wc -l docs/{VISION,ARCHITECTURE,ROADMAP,Built}.md` |
| Regime calls / resolved investigations logged | | | | growing once live | track-record tables |
| Extraction quality (precision / recall / hallucination %) | | | | meets stated bar | Extraction Quality Harness (when built) |
| AI cost per active subscriber | | | | below pricing floor | once revenue exists |

---

## 2. Accountability since last audit *(every audit)*

The learning loop. Do this **before** generating new findings — it changes how seriously you take them.

- **Prior recommendations — disposition of each:** applied / deferred / ignored, and *why*. An ignored recommendation that's still right is a finding; an applied one that didn't help is a lesson.
- **Prior named risks — did any materialize?** For each risk the last audit named: did it happen, get worse, get mitigated, or prove false? Calibrates how much to trust *this* audit's risk calls.
- **Prediction check:** what did the last audit assume about the next quarter (ship dates, beta outcomes, model landscape) that turned out wrong? Name the miss explicitly.

---

## 3. Forcing-function & execution-honesty check *(every audit)*

Judges the *process*, not just the plan.

- **Forcing function:** does every active and next-phase item still ladder to *"makes a Busy Executive more likely to subscribe and renew"*? List anything that doesn't and justify it or cut it.
- **One-Phase Rule:** is scope quietly leaking into the current phase? Is the "Next Phase" spec growing mid-flight? Are satellite docs reappearing?
- **Process adherence:** are the rituals actually happening — discovery calls before building, measurement before public claims (`VISION.md` → *Measured quality over asserted quality*), data capture from day one, phase-completion cleanup into `Built.md`/archive?
- **Doc leanness:** are the four active docs staying lean, or accreting? (Cross-check the line-count metric in §1.)

---

## 4. Lens panel *(rotate 3–4 each audit)*

Each lens: 2–4 findings, concrete and falsifiable. The first three are the original 2026-05-24 panel; the rest close that audit's blind spots. Rotate so coverage stays broad over time, but **always run "Skeptical Customer #1" until there are ≥ 5 renewing subscribers.**

- **Futurist** — Regulatory horizon moving? Disintermination baseline (what can a subscriber get free from a general AI today)? Are we applying our own PPP framework to the platform's 3-year future? Does the 2029 destination still hold?
- **Operator / SRE** *(the Google divisional-lead lens)* — SLOs being met? Observability gaps? Incident-response and single-operator continuity still adequate? Backup/restore actually drilled? Security debt accruing?
- **Designer & Usability** *(Jony Ive + Nielsen Norman Group)* — Backlog/principle inflation? Is the current surface *shown*, not just described — visual hierarchy, brand, and voice coherent, and what would Apple cut? Do interactions hold up against NNG's usability heuristics and Fitts's Law (visible affordances, error prevention, recognition over recall)? **Accessibility:** does every subscriber surface still meet WCAG 2.1 AA — keyboard-only operability, visible focus, 4.5:1 contrast, labelled controls, no colour-only signals? (Admin UI: heuristics yes, formal conformance not required — see `ARCHITECTURE.md` → Usability and Accessibility Standards.)
- **Skeptical Customer #1** — Sit in the Busy Executive's chair. Would I renew this month? What annoyed me, what did I ignore, what made me think "I could get this elsewhere"? Is the synthesis actually saving me time, or am I being handed homework?
- **CFO / Investor** — Unit economics (AI + infra cost per subscriber vs. price)? Runway and burn? Is the $49 anchor validated by real willingness-to-pay yet? Path to profitability, or a science project? *(May be "pre-revenue, N/A" — say so explicitly.)*
- **Market Analyst / Competitor** — What changed in the competitive set since last audit (new models, GuruFocus/Bloomberg/Trading-Economics features, new entrants)? Did the moat get stronger or did the baseline-to-beat rise faster?
- **General Counsel** — Copyright/fair-use posture on ingested content still defensible? Source licensing and scraping ToS honored? Liability exposure on published calls/grades? GDPR deletion path across all tables? Advice-line position holding?
- **Red Team** — *What single event would kill this platform?* Try to falsify the core thesis (that structured intelligence + track record is a durable, payable product). Where is the strategy most fragile?

---

## 5. Risk register *(every audit, kept light)*

Top 5 standing risks, re-scored each audit so rising risks are visible. Likelihood and impact on a 1–5 scale.

| Risk | Likelihood | Impact | Score (L×I) | Δ since last | Mitigation / owner |
|---|---|---|---|---|---|
| | | | | | |

---

## 6. Recommended revisions *(prioritized)*

Numbered, priority order, each naming the target doc and the smallest edit that resolves it. Mark each **apply now** / **defer (with trigger)**. Carry forward any unresolved item from the prior audit and say why it survived.

1.
2.
3.

---

## 7. Deliberately NOT now

Things considered and explicitly declined this cycle — with the **revisit trigger** that would change the answer. (Prevents re-litigating settled questions, and prevents "deferred forever" from hiding real avoidance.)

- *Item* — declined because … ; revisit when …

---

## 8. Decisions & next review

- **Revisions accepted for application:**
- **Revisions rejected / deferred:**
- **New entries added to "What We Will Not Build":**
- **Next audit:** date + trigger
