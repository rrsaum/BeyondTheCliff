# Handoff: what is correlated with school closure (statistical analysis)

Status: work order, 2026-07-22. Read this first, then read the two files it points you at, before
writing any code. This is a handoff to a session dedicated to the closure-correlation analysis.
It exists so you extend and harden the work already done, not re-derive it or, worse, overfit it.

Owner of the standard: R.R. Saum. When this brief and instinct conflict, this brief and the two
authorities it names win.

---

## 0. Read these before you touch anything

1. `docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md` (the authority). It already defines the
   methodology, reports the validated results, and lists "what to build, in order." Your job is
   the next steps in that document, not its first steps.
2. `scripts/health_panel.py` (descriptive pass), `scripts/health_validate.py` (preregistered
   out-of-sample test), and `scripts/resilience.py` (the shared, FROZEN scoring library). These
   are the code that already exists. Read all three before writing new analysis code, and reuse
   their helpers (percentile, slope, split, AUC) rather than rewriting them.
3. `docs/technical/DATA_MODEL.md` and `CLAUDE.md` (the data model and the binding project rules).

If you find yourself building a survivorship-free panel, a by-institution split, or an AUC
function, stop: they exist. Import them.

---

## 1. The objective, stated precisely

Surface which factors, metrics, and combinations are associated with an institution closing, and
report each honestly graded by how much it actually separates closures from survivors out of
sample. The deliverable is not "a list of scary-looking single charts." It is a defensible,
preregistered answer to "what is associated with closure, how strongly, and how confident are we,"
with the weak and confounded signals reported as weak, not quietly dropped.

The already-established baseline you are improving on (from the authority doc, holdout AUC):

- Federal composite score alone: 0.684. Composite + your signals: 0.736.
- Universal roster (no composite): enrollment level 0.680, + trend 0.710, + Pell 0.776, + net
  tuition 0.846. Admit rate adds essentially nothing (weight near zero), as the value-trap logic
  predicted.

If a new signal or method does not beat these on held-out institutions, it has not earned its
place. Say so plainly.

---

## 2. The methodology is binding (this is why the work is credible)

Carried from the authority doc and from the sibling QuantSage discipline. Violating any of these
turns the analysis into the exact survivorship-bias trap the whole project was built to avoid.

1. **Survivorship-free panel, always.** Closures AND survivors, point-in-time, closure as the
   terminal outcome (not a dropped row). The panel holds 2,221 closures and 4,995 survivors with
   Scorecard history; 955 closures carry composite history. Never analyze closures alone.
2. **Preregister before you read the result.** Write the hypothesis and the pass bar (the AUC or
   effect size a signal must clear) into the doc BEFORE you run the holdout. A metric earns its
   place by clearing a bar set in advance, not by being fit to the closures you happen to hold.
3. **Out of sample or it does not count.** Split by institution (the existing md5-mod-100 hash,
   70/30), so no school is in both train and holdout. Report AUC on the holdout only.
4. **Add the era-forward split.** This is the first named hardening step in the authority doc:
   train on earlier closures, test on later ones, so the model is shown to generalize across time,
   not just across schools. A cross-sectional split can still leak era. Do this.
5. **No single metric is destiny.** The established finding is that combinations validate where
   single factors do not. Test interactions (the classic one: a high and rising discount that
   fails to grow net tuition or fill the class, not the discount alone). Report any single-metric
   claim as weak until a combination proves it.
6. **Cluster and caveat.** Cluster inference by institution. State the base rate (panel closure
   rate is about 28 percent) every time you report an AUC, so no one reads a ranking model as a
   per-school death prediction. It ranks risk; it does not foretell one school's fate.
7. **No fabrication, cite every number.** Every figure is as-reported from a named federal source
   (IPEDS, ED composite, Scorecard, audited filings) or derived by a stated formula. A number the
   data cannot honestly produce is marked NOT AVAILABLE, not estimated. This is the whole basis of
   the authority position.

---

## 3. The open work, in priority order

From the authority doc's "what to build, in order" plus its two named hardening steps. Do them in
this order; each is a clean unit.

1. **Era-forward validation** (hardening step 1). Re-run the existing validation with a
   train-early / test-late split. Report whether the 0.74 to 0.85 holds forward in time. Highest
   priority because it tests the claim the current result cannot: does this generalize across
   eras, or only across schools within an era.
2. **Time-to-event / survival framing** (hardening step 2). The current model is cross-sectional
   discriminative (does this profile look like the ones that closed). A discrete-time hazard or
   survival model attaches a "closes within N years" horizon, which is what a board actually asks.
   Keep it standard-library and reproducible, like the existing code.
3. **Interaction and combination search, preregistered.** Systematically test the combinations
   the doc flags, especially discount-rate interacted with net-tuition growth and enrollment. Set
   the pass bar first.
4. **Import the fields that unlock the rest** (only after 1 to 3, and each with a source):
   - Scorecard **retention and graduation** (Zemsky's third variable). `data/scorecard.csv` does
     NOT currently carry these columns; add them to `scripts/import_scorecard.py`'s extraction.
   - IPEDS Finance **net position** (unlocks the CFI ratios and capital efficiency for public
     schools, which `finance_year` cannot compute today).
   - IPEDS Finance **scholarships/aid** (a clean discount rate for all schools, not just the 990
     handful).
   - **CAC stays out of scope.** No public federal source breaks out recruitment spend. The
     honest proxy is student-services expense per new student, and it must be labeled a loose
     proxy, never "CAC." Do not publish a CAC.

---

## 4. Guardrails specific to this repo (all binding)

- **Run in a git worktree. Never a second session in this checkout.** This is the absolute rule in
  `CLAUDE.md`. Setup is in section 6 below and in `docs/technical/PARALLEL_SESSIONS.md`. Invoke the
  `parallel-sessions` skill if anything changes under you mid-edit.
- **A generated file has one owner: its generator.** Never hand-edit `data/institutions_open.csv`,
  `data/sector_size.csv`, `data/composite_scores.csv`, `data/financials.csv`, or
  `data/financial_line_items.csv`. A hand-curated fact needs its own hand-curated CSV.
- **The resilience score is FROZEN on purpose.** `scripts/resilience.py` carries frozen
  coefficients because a published, cited score must be stable. Do not silently refit it. If a
  better model is validated, run `--fit`, paste the new FROZEN block, and re-validate with
  `health_validate.py` before adopting it. Peer percentiles stay live; only the weights are frozen.
- **Never rate a living named school in public,** and never store a copyrighted score (no Forbes
  values). Rows the data cannot honestly resolve go to the review files, not into a guessed status.
- **No typographic em-dash anywhere.** Split the sentence or use a colon or comma. Enforced by
  `scripts/style_lint.py`.
- **Python is linted and formatted by ruff.** Run `ruff check` and `ruff format` on any `.py` you
  touch. Note the open item in `docs/TODO.md`: there is no ruff config yet, so pin `line-length`
  (the code uses ~100) before running `ruff format`, or you will reformat the whole repo.
- **Read-only over the DB unless you own the table.** The existing analysis scripts are read-only
  except `resilience.py:write_scores()`. Keep new analysis read-only.

---

## 5. What "done" means for this handoff

- The era-forward result and the survival-model result are in
  `docs/strategy/INSTITUTIONAL_HEALTH_METRICS.md`, with the preregistration written before the
  results and every number sourced.
- Any new signal is reported with its held-out effect and graded honestly (strong, weak,
  confounded, or not available), against the pass bar you set in advance.
- Weak and confounded signals are kept in the write-up and labeled, not dropped. The value of the
  analysis is partly in what does NOT predict closure (the admit rate is the worked example).
- `scripts/verify.sh` passes on every changed file (style + ruff). Run `scripts/verify.sh --tests`
  if a test suite exists for what you touched.
- The frozen resilience score is unchanged, or deliberately refit, revalidated, and documented.

Do NOT, as part of this handoff: name or rank a living school publicly, refit the frozen score
casually, import CAC, or present any single-metric correlation as a closure prediction.

---

## 6. How to start (the launch procedure)

From the repo root, create an isolated worktree so this analysis never shares the main checkout:

```
git worktree add ../BeyondTheCliff-closure-analysis -b closure-analysis
cd ../BeyondTheCliff-closure-analysis
printf 'TRACKER_PORT=8003\n' > .env      # .env is NOT carried over; each worktree needs its own
python3 scripts/build_db.py              # rebuild data/beyondthecliff.db from the CSVs
.venv/bin/python scripts/health_panel.py       # confirm the descriptive pass reproduces
.venv/bin/python scripts/health_validate.py    # confirm the validated baseline reproduces
```

Reproducing those two numbers first is the check that your environment matches the documented
baseline. Only once they reproduce do you start on section 3.

Note: three strategy documents (`MASTER_PLAN.md`, `BUSINESS_MODEL.md`, `BOOK_PROPOSAL.md`) may be
uncommitted on `main` at handoff time; they are unrelated to this analysis and will not appear in
your worktree. That is fine. Your work is the analysis and the authority doc only.
