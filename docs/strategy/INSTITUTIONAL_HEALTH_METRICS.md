# Institutional health metrics: research, analogs, and a validation plan

Purpose: define a set of metrics that separate healthy, growing institutions from those that
decline and close, borrowing the discipline of quantitative investing (from the sibling
QuantSage project) and grounding every metric in existing higher-education research and in data
we actually hold. This is a design document, written before importing more data, so the metric
set drives what we collect rather than the reverse.

Binding rule, inherited from the whole project and from QuantSage: **no fabrication.** Every
number is as-reported, from a named federal source, or derived by a stated formula. A metric that
our data cannot honestly produce is marked so here, not faked.

## The one methodological principle that matters most

The naive version of this project is: chart a metric for a few closed schools, see it fall
before closure, and declare it predictive. That is survivorship bias plus overfitting, and it is
exactly the trap QuantSage documented for investing. In `Quantsage/docs/VALUE_QUALITY_VALIDATION.md`
every point-estimate valuation method "failed on honest data" once deaths were included; deep
value alone was a **trap** (cheap names died more), and only a combination validated. The lesson
ports directly:

- Build a **survivorship-free panel**: school-year rows for closures AND survivors, point-in-time,
  with closure as the terminal "wipeout" outcome. We already have the raw material: **2,221
  closures and 4,995 survivors carry per-year College Scorecard history**, and 955 closures carry
  ED composite-score history. Most closure research (Zemsky below) has to reconstruct this; we
  hold it.
- **Preregister** the hypothesis and the pass bar before reading results, so a metric earns its
  place instead of being fit to the closures we happen to have.
- Split **out-of-sample** (train on earlier closures, test on later) and cluster inference by
  institution.
- Expect that **no single metric predicts closure**. QuantSage's finding was that value and
  quality together did what neither did alone. The higher-ed analog: a high discount rate, or a
  rising admit rate, or thin reserves, each alone is weak or confounded; the combination
  (thin reserves AND shrinking enrollment AND a discount that no longer grows net revenue) is the
  signal. Test combinations, report single-metric claims as weak until proven.

## Coverage boundary: this is a modern-era model (binding, verified 2026-07-22)

Every predictive result in this document (the validation, the era-forward split, the survival model,
the interaction search) is bounded by where the federal predictor variables exist, and that boundary
must be stated wherever a result is cited. Verified against the database:

- The closure RECORD spans the century: 3,921 closures, closure years 1746 to 2027, of which about
  749 closed before 2004 (78 before 1900, 156 in 1900 to 1949, 177 in 1950 to 1979, 290 in 1980 to
  1999, 48 in 2000 to 2003).
- The model FEATURES come from College Scorecard, which does not reach back that far. First
  populated year: enrollment (ugds) 1997, net tuition (tuitfte) 1999, admit rate 2002, and Pell
  share (pct_pell) only 2009. Composite scores begin 2006-07.
- Consequence: of the 2,063 closures that can enter the panel (three or more Scorecard years), ZERO
  closed before 2004. The hand-curated `enrollment` table reaches to 1882, but only one of the 749
  pre-2004 closures has three or more years in it, so an enrollment-only signal cannot rescue the
  historical era either.

So the predictive model is a **modern federal-data-era closure model** (closure outcomes 2004 and
after, features 2009 and after for the full workhorse). It is not, and cannot honestly be, a
hundred-year predictive model: a college that closed in 1935 has no federal Pell share, net tuition,
admit rate, or composite score to compute a feature from. This is a limit of the public record, not
a scope choice, and no metric is ever fabricated to fill it.

What the full 1746 to 2027 record CAN support is a **descriptive** analysis (closures per decade,
recorded cause by era, lifespans where a founding year is known), reported separately below and
never mixed with the predictive AUCs, because it rests on different data (name, closure year, and a
recorded cause for 366 of the 749 pre-2004 closures) and answers a different question.

## Existing research and frameworks (verified this session)

1. **Composite Financial Index (CFI)** and its four core ratios (Primary Reserve, Net Operating
   Revenues, Return on Net Position, Viability), from *Strategic Financial Analysis for Higher
   Education* (Prager, Sealy & Co. / KPMG). The standard management view of institutional
   financial health. Source: [NBOA course](https://www.nboa.org/programs/online-courses/course/measuring-financial-health-with-the-composite-financial-index).
2. **ED Financial Responsibility Composite Score** (34 CFR 668.171), the regulatory descendant of
   that same Prager/KPMG ratio work, scored -1.0 to 3.0. **We already hold it**: 52,787 rows,
   2006-07 to 2022-23, for private-nonprofit and proprietary schools. It is the single best
   established health metric we have, and any new metric should be tested against it, not replace
   it. Structural limit: it does not cover public institutions, and the ratios were rewritten
   effective 1 July 2020 (84 FR 49788), so scores do not join across that break (see
   `app/queries.py:COMPOSITE_BREAK`).
3. **The College Stress Test** (Zemsky, Shaman, Baldridge; Johns Hopkins University Press, 2020).
   The leading academic closure-prediction framework, built from IPEDS for 2,800+ institutions on
   **four variables: new-student enrollments, net cash price, student retention, and major external
   funding**. Source: [Hopkins Press](https://www.press.jhu.edu/books/title/12286/college-stress-test).
   Note what it uses and does not: it uses **net price**, not the admission rate, as the pricing
   signal, and new enrollment, not selectivity, as the demand signal.
4. **NACUBO Tuition Discounting Study** (annual). Establishes the discount-rate-versus-distress
   link empirically: the average first-time-undergraduate discount rate reached about 56 to 57
   percent in 2024-26, and net tuition revenue per student has been falling for many private
   institutions despite rising discounts. Source: [NACUBO](https://www.nacubo.org/Press-Releases/2025/NACUBO-Study-Finds-Private-Colleges-and-Universities-Are-Offering-Record-Financial-Aid-to-Students),
   [Inside Higher Ed](https://www.insidehighered.com/news/business/revenue-strategies/2025/06/24/tuition-discounting-hits-another-high).

Rating-agency (Moody's, S&P) and consulting (Bain, "The Financially Sustainable University")
frameworks add operating-margin, days-cash-on-hand, leverage, and expense-growth-versus-revenue
lenses. These are my background knowledge, not verified this session; treat their specifics as
to-be-cited before use.

## Investing analogs (from QuantSage), mapped to institutions

QuantSage's method is to operationalize qualitative wisdom into transparent, computable criteria
with data tiers and a stated certainty, and to **invert first** (surface every reason it fails
before any reason it thrives). The mapping:

| QuantSage / investing | Institutional analog | Reading |
|---|---|---|
| Wipeout (terminal drawdown >= 80%) | Closure / merger under distress | the outcome to predict |
| Operating margin, earnings yield | Net operating revenues ratio; operating margin | does a normal year pay for itself |
| Days cash / liquidity, runway | Primary reserve ratio (expendable resources / expenses) | how long it survives a shock |
| Leverage / solvency | Viability ratio (expendable resources / debt) | can it carry its obligations |
| ROIC, asset turnover (quality) | Return on net position; revenue per dollar of assets | how efficiently capital is deployed |
| Unit economics, gross margin | Net tuition per student; cost per student | the per-student engine |
| Customer acquisition cost (CAC) | Student acquisition cost | cost to enroll one student |
| Pricing power / discount to list | Tuition discount rate | pricing strength versus give-away |
| Revenue growth, retention | New-enrollment trend, retention, graduation | demand and the pipeline |
| Value trap (cheap-and-dying) | Heavy discount that fails to grow net revenue or fill the class | the give-away that does not work |

## The metric set, with honest feasibility

Feasibility key: **DONE** = computable now from data we hold; **PARTIAL** = only for some schools
or needs one added field; **NOT AVAILABLE** = public data does not support it.

### A. Financial health (the CFI / ED-score family)
- **ED composite score trajectory and slope.** DONE. We hold it. A falling multi-year slope
  toward the 1.5 line is the most direct distress signal; it already showed on the closures we
  linked this session (Tennessee Temple 0.8, Marymount California 1.1, King's NYC 1.2 before
  closing). Covers private + proprietary only.
- **Primary reserve, net operating revenue, viability, return-on-net-position ratios (the CFI
  four).** PARTIAL. Computable cleanly for the four Form 990 schools (`financial_filing` holds
  total assets, net assets, revenue, expenses). For public schools, `finance_year` holds revenue,
  expenses, and endowment but **not net position or total assets**, so return-on-net-position and
  viability need an added IPEDS Finance field (net position) before they compute.

### B. Unit economics and efficiency
- **Cost per student = total expenses / enrollment.** DONE. `finance_year.total_expenses` (or 990
  `total_expenses`) over `scorecard.ugds` or `enrollment.fte`, per year. Its trend answers "are
  operating costs rising or falling per student."
- **Net tuition revenue per student.** DONE. `scorecard.tuitfte` is exactly this, populated in
  141,064 rows. This is Zemsky's "net cash price" signal and is arguably the single most useful
  per-student number we already hold.
- **Capital efficiency (return on net assets; revenue per dollar of assets).** PARTIAL, same gap
  as the CFI ratios: available for the 990 schools, needs an IPEDS net-position import for public
  schools.
- **Student acquisition cost (CAC).** **NOT AVAILABLE.** Neither IPEDS Finance nor the Form 990
  breaks out recruitment or admissions marketing spend. IPEDS "student services" expense lumps
  admissions with the registrar, financial-aid administration, and student activities, and the
  990 has no recruitment line. A true CAC (recruitment budget / new enrolled students) lives in a
  school's internal admissions budget, which is not in any public federal source. We should not
  publish a CAC and call it that; the closest honest public proxy is student-services expense per
  new student, which must be labeled as a loose proxy, not CAC.

### C. Pricing and discounting
- **Tuition discount rate.** PARTIAL, and the definition matters. The NACUBO/proper discount rate
  is institutional grant aid to undergraduates divided by gross tuition-and-fee revenue.
  - Clean version: the Form 990 gives gross tuition and institutional aid, and we already compute
    `aid_to_tuition` for the 990 schools (verified against Montreat's audit at 53% versus 54%).
  - Rough proxy for everyone: `1 - scorecard.tuitfte / scorecard.tuitionfee_in`. Be careful: this
    divides net revenue per FTE by the published in-state sticker, which is directional, not a
    true discount rate. A clean rate for all schools needs the IPEDS Finance scholarships-and-
    fellowships (aid) field, which we do not currently store.
  - On the health question: the research says **high discounting is a distress signal for
    tuition-dependent privates specifically**, but the value-trap logic warns that the discount
    itself is not the disease. Many healthy schools discount heavily. The predictive combination is
    a **high and rising discount that fails to grow net tuition revenue or fill the class**: the
    give-away that no longer works. Test the discount rate INTERACTED with net-tuition-revenue
    growth and enrollment, not alone.

### D. Demand and selectivity
- **New-enrollment trend and total-enrollment trend.** DONE. `scorecard.ugds` and the `enrollment`
  table over years. This is Zemsky's primary demand signal and the direct link to the enrollment
  cliff the brand tracks.
- **Selectivity (admission rate) trend.** DONE to chart: `scorecard.adm_rate` is populated for
  49,084 rows across 3,450 schools and 24 years. On the closure-correlation question, be
  cautious: a rising admit rate (getting less selective) is a plausible pre-closure signal, but it
  is **confounded**. Most non-selective schools are perfectly healthy (open-access is a mission,
  not distress), and test-optional policies and yield shifts move the admit rate for reasons
  unrelated to health. The leading framework (Zemsky) deliberately uses net price and new
  enrollment, not the admit rate. So: chartable yes, but its predictive value must be validated on
  the death-inclusive panel and reported as weak/confounded unless it survives, rather than assumed.
- **Retention and graduation rates.** PARTIAL. Zemsky's third variable. The Scorecard carries
  these federally; we would need to add the columns (not currently in `scorecard`).
- **Tuition dependency and revenue diversification.** DONE from `finance_year` (tuition / total
  revenue) or 990. Zemsky's fourth variable ("major external funding"). High tuition dependency is
  what turns a demographic dip into a budget crisis, and it is the core of the brand's thesis.

## Direct answers to the specific questions raised
- **Acquisition cost per student:** not available from public data. Honest alternative: student-
  services expense per new student, labeled a loose proxy.
- **Expenses per year / students (cost per student) and whether operating costs are rising or
  falling:** yes, computable now, per year, from finance/990 expenses over enrollment.
- **Efficiency of deploying capital:** yes for the 990 schools (return on net assets); needs an
  IPEDS net-position import for public schools.
- **Net discount rate from net tuition versus sticker, and does high discounting cause distress:**
  a directional proxy is computable now from `tuitfte` versus `tuitionfee_in`; a clean rate needs
  the IPEDS aid field or the 990. The research supports the discount-distress link for tuition-
  dependent privates, but the honest test is discount interacted with net-revenue growth and
  enrollment, not discount alone.
- **Selectivity rate per year, and does becoming less selective precede closure:** the per-year
  admit-rate chart is computable now; the closure correlation is a hypothesis to validate on the
  death-inclusive panel, with the explicit caveat that the admit rate is confounded and the
  leading framework does not rely on it.

## First descriptive results (scripts/health_panel.py)

A first pass on the panel (1,978 closures, 4,960 survivors, three or more usable years each),
every metric normalized to a within-year percentile so a school is compared to its peers that
year. This is DESCRIPTIVE, not the validated out-of-sample test below; read it as which signals
are worth validating, not as a proven predictor. Closed-minus-survivor separation:

| Signal | Closed | Survivor | Read |
|---|---|---|---|
| Enrollment slope, last 5 years | -13.1/yr | +1.1/yr | strongest and cleanest: closures shrink sharply late; survivors grow |
| Pell share (percentile) | 0.76 | 0.46 | largest level gap, but a MARKER of under-resourced, vulnerable-student-serving schools, not a health lever (an equity finding, never a prescription) |
| Composite score (raw / percentile) | 1.8 / 0.29 | 2.4 / 0.50 | the established metric separates: closures sit near the bottom third of health |
| Enrollment size (percentile) | 0.32 | 0.51 | closures are smaller |
| Admit rate (percentile, high = less selective) | 0.64 | 0.53 | closures modestly less selective: weak and confounded, as predicted |
| Net tuition per student (percentile) | 0.62 | 0.47 | closures higher, but this tracks sector and tuition dependency, not health |

What this confirms: the established financial metric (composite) and enrollment separate the
groups; enrollment decline is a **late-stage** signal (steep in the final five years, flat over
full history, so the window matters); and the single-metric pricing and selectivity signals are
weak and confounded, exactly as the research and the value-trap logic warned. The Pell result is
the sobering one and needs care: it says closures fall hardest on schools serving low-income
students, which is context for the brand, not a lever to pull.

## Out-of-sample validation (scripts/health_validate.py)

The descriptive pass above shows separation; it does not show the separation survives on schools
the model never saw. This does. One row per institution, features summarized over its window,
label = closed. Institutions are split by id hash (md5 mod 100), 70 percent train and 30 percent
holdout, so no school is in both. A plain L2-regularized logistic regression is fit on train
moments only; the reported number is AUC on the **holdout** (probability a random closure scores
less healthy than a random survivor). Pure standard library, deterministic, reproducible.

**The question you asked of a health score: does adding our signals beat the federal composite
score alone?** On the private-nonprofit / proprietary subset that carries a composite score:

| Model | Holdout AUC |
|---|---|
| Federal composite score ALONE (baseline) | 0.684 |
| Composite level + trend | 0.695 |
| Composite + enrollment level + trend | 0.720 |
| Composite + our full set (adds Pell) | **0.736** |

Adding enrollment trajectory and Pell reliance to the federal score lifts holdout AUC from 0.684
to 0.736: a real out-of-sample gain, and the exact Quantsage result (single factor decent, the
combination better). For the roster ED does not score (publics and any school without a composite),
the universal Scorecard model stands alone:

| Universal model (whole roster) | Holdout AUC |
|---|---|
| Enrollment level only | 0.680 |
| + enrollment trend | 0.710 |
| + Pell reliance | 0.776 |
| + net tuition (where reported) | 0.846 |

Two honest limits. The 0.846 rests on the subset reporting admit rate and net tuition, and admit
rate adds essentially nothing out of sample (weight near 0.00), exactly as the value-trap logic
predicted: the workhorses are enrollment level, enrollment trend, Pell reliance, and net tuition.
And AUC of 0.74 to 0.85 means the model RANKS closure risk well; it does not foretell any one
school's outcome (panel base rate of closure is about 28 percent). This is a cross-sectional
discriminative test (does this profile look like the ones that closed), not a time-to-event
survival model with a date attached. That, plus an era-forward split, is the next hardening step.

## Era-forward validation (hardening step 1)

The cross-sectional split above holds out schools, not time: it shows the signal generalizes across
institutions, but a model can still ride an era. The 2016 for-profit collapse alone is 455 of the
2,061 dated panel closures (22 percent in one year), so a cross-sectional split can train and test
on the same wave. The era-forward split trains on the earlier closures and tests on the later ones,
which is the harder and more honest question: does a model fit to the past rank the closures that
came after?

### Preregistration (written and committed before the holdout was read)

Design, fixed in advance:

- **Era cutoff Y = 2016**, chosen from the closure-year distribution alone (median split: 1,043
  panel closures with `status_year <= 2016`, about 1,018 from 2017 on), before any AUC was
  computed. EARLY = closures through 2016; LATE = closures 2017 and after.
- **Survivors** (no closure year) are partitioned by `md5(id) mod 2` so no survivor is in both eras
  and each side keeps a realistic base rate (about 30 percent closures per side). The two dated
  panel closures with no `status_year` are dropped.
- **Primary test: train EARLY, test LATE** (the genuine forward direction). Train-LATE / test-EARLY
  is run only as a symmetric robustness check.
- Same machinery as `health_validate.py`: median within-year-percentile features, an L2 logistic
  regression standardized on the train moments only, AUC on the held-out era. Reused, not rewritten.
- **Known limitation, stated up front:** survivor features summarize each survivor's full window,
  not a window truncated at Y, so the temporal generalization is carried by the closure cohorts, not
  by point-in-time survivor snapshots. The rigorous point-in-time version is hardening step 2 (the
  discrete-time hazard model), which is exactly why that step exists. This step tests one thing: do
  the closure patterns learned before 2017 rank the closures after 2016.

Hypotheses and pass bars (a signal earns its place only by clearing a bar set here, in advance):

- **H1 (universal model holds forward).** The universal model (enrollment level, five-year trend,
  Pell reliance, net tuition per student) trained on EARLY ranks LATE closures usefully.
  **Pass bar: LATE-era holdout AUC >= 0.70.** Cross-sectional was 0.776 (enrollment + Pell) to 0.846
  (with net tuition); temporal generalization normally costs AUC, and 0.70 is the floor for "still
  clearly useful and materially above the 0.5 chance line." Below 0.70 means the cross-sectional
  result is materially era-specific, and this doc will say so.
- **H2 (the combination still beats the federal score forward in time).** On the composite subset,
  **era-forward AUC(composite + our signals) minus AUC(composite alone) >= +0.02, and composite-alone
  era-forward AUC >= 0.63.** Cross-sectional lift was 0.684 to 0.736 (+0.052); forward in time the
  combination must still add at least +0.02 to count as robust rather than era-specific.
- **Direction predictions (instability check).** Enrollment level and trend keep negative weights
  (protective), Pell and net tuition keep positive weights (risk-associated), matching the
  cross-sectional signs. Any sign flip forward in time is reported as instability, not smoothed over.

Results are recorded in the next subsection only after this one was committed.

### Result (scripts/health_era.py)

Split: EARLY (closure year <= 2016) 3,478 schools, 979 closures (28 percent); LATE (2017 and
after) 3,458 schools, 997 closures (29 percent). Primary direction, train EARLY and test LATE:

| Model | Cross-sectional AUC | Era-forward AUC (test LATE) |
|---|---|---|
| Enrollment level only | 0.680 | 0.659 |
| + enrollment trend | 0.710 | 0.697 |
| + Pell reliance | 0.776 | 0.757 |
| + net tuition (the workhorse) | 0.846 | **0.793** |
| Federal composite ALONE | 0.684 | 0.692 |
| Composite + trend | 0.695 | 0.682 |
| Composite + enrollment | 0.720 | 0.705 |
| Composite + our full set | 0.736 | **0.714** |

(LATE test base rate 29 percent for the universal models, 26 percent for the composite subset.)

**H1: PASS.** The workhorse universal model, trained only on closures through 2016, ranks the
closures after 2016 at AUC 0.793, well above the 0.70 bar. Direction signs are all as predicted and
stable (enrollment level -0.71, trend -0.87, Pell +1.09, net tuition +0.83), so no instability. The
signal is not an artifact of the 2016 for-profit wave: a model that never saw a post-2016 closure
still ranks them. The forward AUC (0.793) is lower than the cross-sectional (0.846), which is
honest and expected: some of the cross-sectional strength was era-shared, and predicting the future
is harder than holding out contemporaries.

**H2: PASS, narrowly.** Composite plus our signals beats composite alone forward in time by +0.022
(0.714 versus 0.692), clearing the +0.02 bar, and composite alone (0.692) clears its 0.63 floor. But
the forward lift is thinner than the cross-sectional +0.052, and composite SLOPE is fragile: it
helped marginally cross-sectionally yet slightly hurts forward (0.682 < 0.692), so the forward gain
comes from enrollment and net tuition, not from the composite trend. Report the composite-slope term
as weak, not established.

Robustness, reverse direction (train LATE, test EARLY): the workhorse reaches 0.839 and the
composite combination lifts +0.077 over composite alone (0.756 versus 0.679), both stronger than the
forward direction. The asymmetry (forward 0.793, reverse 0.839) is the expected shape: postdicting
earlier closures from later patterns is easier than predicting later closures from earlier ones.
Both directions clear the bars, so the result is not an artifact of which era trains.

Net for the reader: the closure signal generalizes across time, not just across schools, and it does
so mainly through enrollment trajectory, net tuition, and Pell reliance. It still ranks risk rather
than dating any one school's fate (base rate about 28 to 29 percent), and the federal composite
score's own forward edge is real but modest once enrollment and pricing are in the model.

## Time-to-event / survival framing (hardening step 2)

The models above are cross-sectional: they summarize a school's whole window into one row and ask
"does this profile look like the ones that closed." A board asks the sharper question: "given how we
look right NOW, what is the chance we close within the next few years." That is a discrete-time
hazard model, and it also fixes the one honest weakness of steps 1 and 2: features here are computed
AS OF each observation year, not summarized over a window that (for survivors) reaches into the
future. Point-in-time by construction, so no future information leaks into a past observation.

### Preregistration (written and committed before the holdout was read)

Design, fixed in advance:

- **Person-period panel.** One row per institution per Scorecard year t in its history, with features
  computed as of year t: enrollment level (within-year percentile of ugds at t), enrollment trend
  (five-year ugds slope ending at t), Pell (percentile of pct_pell at t), net tuition (percentile of
  tuitfte at t). The composite subset adds the most recent composite score on or before t.
- **Label = closes within H years of t.** For a closure with closure year S and t < S, the event is
  1 if `S - t <= H` else 0. Survivors are always 0. Horizons **H = 3 and H = 5**, both preregistered.
- **Censoring (stated in advance).** A survivor person-period at year t is included only if the
  outcome window is observable, `t + H <= max Scorecard year`; otherwise it is right-censored and
  dropped (we have not yet seen whether it survives H years). Closure person-periods with `t < S` are
  always labelable and kept. This is the standard discrete-time-hazard treatment of censoring.
- **Split by institution** (the existing `md5 mod 100`, 70/30, reused from health_validate), so every
  person-period of a school is in train OR holdout, never split across. Report holdout AUC.
- Same machinery reused (percentile, slope, logistic fit, AUC). Standard library, deterministic.

Hypotheses and pass bars:

- **H3 (the point-in-time hazard is useful at a board horizon).** The workhorse hazard model predicts
  "closes within H years" out of sample. **Pass bar: holdout AUC >= 0.70 for both H = 3 and H = 5.**
  This is a harder, near-horizon, point-in-time task than the window-summary model, and 0.70 is the
  floor for "clearly useful." Because it leaks no future information, it is the most honest single
  discrimination number in this document.
- **H4 (nearer is clearer), directional, not pass/fail.** Predict AUC(H = 3) >= AUC(H = 5): imminent
  closure shows sharper distress than closure five years out. If the order reverses, report it.
- **Direction predictions (instability check).** Enrollment level and trend keep negative weights,
  Pell and net tuition keep positive weights, as in every model above. Sign flips are reported.
- **Reported with:** person-period count, unique institutions, and the event base rate for each
  horizon, plus the caveat that person-periods are clustered within institution (the institution
  split controls leakage; AUC is computed over person-periods and read with that clustering in mind).

Results are recorded in the next subsection only after this one was committed.

## What to build, in order
1. **The survivorship-free panel first** (school-year rows, closures and survivors, point-in-time),
   because every correlation claim depends on it and we already hold the inputs. This is the
   highest-value next step and needs no new import.
2. **Compute the DONE metrics** on that panel: composite-score slope, cost per student, net
   tuition per student, tuition dependency, enrollment trend, admit-rate trend, the rough discount
   proxy.
3. **Preregister and validate** which of them, and which combinations, separate the 2,221 closures
   from the 4,995 survivors out-of-sample, following the QuantSage pattern. Report the weak and
   confounded ones as weak.
4. **Then import** the fields that unlock the rest: IPEDS Finance net position (capital efficiency
   and the CFI ratios for public schools), IPEDS Finance scholarships/aid (a clean discount rate
   for all schools), and Scorecard retention/graduation (Zemsky's third variable). CAC stays out
   of scope: the public data does not support it.
