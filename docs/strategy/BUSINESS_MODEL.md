# Beyond the Cliff: the business model

Status: v1 draft (2026-07-22). How the practice earns, priced and sequenced so that revenue
never outpaces authority. Builds on the funnel in `POSITIONING_AND_BRAND_ARCHITECTURE.md`
(section 4) and the four revenue layers in the late-career IVST memos, reconciled to the hybrid
product posture locked in `MASTER_PLAN.md`. Owner: R.R. Saum.

Binding inheritance: every figure here is either a design assumption (labeled as one) or drawn
from a named source. Pricing bands are the author's own from the IVST revenue memos. The model
validation figures are from `INSTITUTIONAL_HEALTH_METRICS.md`. Nothing here is a promised
return; the projection in section 6 is illustrative and its assumptions are stated.

---

## 1. What is actually being sold

Not data. Not a rating. **Judgment about how much time and how many moves an institution has
left, and what to do with them.** The tracker and the report are free and public because they
are the proof, not the product. The product is the model applied to one institution's decisions,
sold to the people who make those decisions.

This matters for pricing. A dataset is a commodity and races to zero. Judgment from a named
analyst with prior art and operator credibility is scarce, and the late-career memos put a number
on the scarcity: the four-competency intersection (senior higher-ed practice, formal foresight,
capital-allocation literacy, decision-infrastructure design) plausibly describes under 0.1
percent of the sector. That scarcity is the pricing power. Do not discount it into a commodity.

---

## 2. The revenue layers

Four layers, from the IVST memos, each doing a distinct job. They are entered in order: a layer
does not open until the authority to sell it exists. The hybrid posture shapes what each one can
honestly be.

### Layer 1: Framework Access (legitimacy and reach)

Annual access to the resilience model, the self-assessment instrument, the benchmarks, and
periodic updates. An institution locates itself on the model, privately. This is the paid entry
point and the lead into everything above it.

- **Buyers:** individual institutions; systems and consortia (multi-seat).
- **Price (author's IVST bands):** $5,000 to $25,000 per institution per year; $50,000 to
  $250,000 per system or consortium per year.
- **Hybrid-posture note:** the self-assessment is private to the institution by design. This is
  the layer that most respects the "never rate a living school in public" rule, because the
  school rates itself and no score leaves the building.

### Layer 2: Interpretation and Scenario Advisory (the core income)

Board-level interpretation of a school's position: scenario stress-testing, proximity-to-
irreversibility analysis, and the moves the model reveals while there is still time to make them.
This is where judgment is monetized, and it is the layer that carries the practice.

- **Buyers:** presidents, CFOs, provosts, and boards who have seen their own numbers on the
  model and want to know what to do.
- **Price (author's IVST bands):** $25,000 to $75,000 per engagement; $50,000 to $150,000 for an
  annual retainer.
- **Cadence note:** this layer is hour-intensive. At a 10-hour week (per `MASTER_PLAN.md`) the
  practice can carry only a few engagements at once. Price for scarcity and select for altitude,
  not volume.

### Layer 3: Foundation and System Underwriting (the force multiplier)

A funder or a system underwrites cohort access for a set of institutions, framed as
capacity-building rather than evaluation. This removes the stigma of a single school buying a
"stress test," positions the practice as public-interest infrastructure, and reaches many
institutions through one contract.

- **Buyers:** foundations, state systems, associations, consortia.
- **Price (author's IVST bands):** $250,000 to $1,000,000 per grant or contract.
- **Why it matters most for the endgame:** these are the rooms adjacent to presidencies. A
  funded cohort is both the largest single revenue event and the strongest board-adjacency
  signal in the model. It is the layer the candidacy leans on hardest.

### Layer 4: Opt-in Review and Trustee Education (optional, latest)

Anonymous peer-benchmarking cohorts and trustee-education programs. Present in the strategy memo,
absent from the clean business plan, and gated by a hard constraint from the memos: **this layer
must never become coercive or resemble accreditation.** Treat it as a Year-2-plus option, not a
launch product, and only if it can be built without an enforcement posture.

---

## 3. How the layers ladder (the funnel as revenue)

```
  FREE / PUBLIC          The tracker + The Resilience Report + the briefing
  (authority engine)     draw attention and prove the thesis. No revenue. This is the moat.
        |
        v
  LAYER 1  ($5k-$25k)    Framework Access. First dollar. A school self-locates, privately.
        |
        v
  LAYER 2  ($25k-$150k)  Interpretation & Advisory. The self-assessment reveals a need;
        |                judgment meets it. The core income.
        v
  LAYER 3  ($250k-$1M)   Foundation / system underwriting. One contract, many institutions,
        |                board-adjacency, public-interest framing. The force multiplier.
        v
  SPEAKING wraps all of it, at every altitude, and feeds the candidacy (W5).
```

The free surface is not marketing overhead; it is the asset that makes the paid layers sellable
at these prices. A president pays Layer 2 rates for judgment they already trust because they read
the report and watched the tracker be right and sober for two years first.

---

## 4. Unit economics (the honest version)

The costs here are near-zero in cash and high in hours, which is the defining feature of a
one-analyst authority practice and the reason the cadence constraint governs everything.

- **Cash cost of goods:** negligible. The tracker is a FastAPI app over SQLite (near-zero
  hosting). The data is public federal records. The model is built. The report is written once.
  There is no inventory, no staff, no runway requirement (which matches the "nights and weekends,
  no runway" decision).
- **The real cost is Saum's hours,** and they are the true scarce input. A rough allocation at a
  10-hour week: Layer 1 is low-touch once the instrument exists (hours to onboard, not deliver).
  Layer 2 is the hour sink (an engagement is real weeks of judgment). Layer 3 is high-leverage
  (one sale, many institutions, but heavy to land).
- **The implication for the mix:** the practice should be weighted toward Layer 1 (self-serve,
  scalable, low-hour) and Layer 3 (high-leverage, board-adjacent), with Layer 2 rationed to the
  few engagements that most raise altitude. A practice that fills its hours with Layer 2 bespoke
  work caps out fast and stalls the compounding assets (the book, the report). This is the same
  warning as `MASTER_PLAN.md` section 6, stated in revenue terms.
- **Gross margin is effectively the analyst's time value,** so the pricing discipline is not
  "cover costs" (there are almost none) but "price the scarcity." The floor is what the hours are
  worth against the day job and the candidacy; the ceiling is what a board pays to avoid an
  irreversible mistake, which is high.

---

## 5. Pricing discipline (five rules)

1. **Never discount into a commodity.** The moment the price implies "a dataset," the scarcity
   argument is lost. Hold the bands.
2. **Price Layer 2 for scarcity, not utilization.** Ten hours a week means few slots; few slots
   priced high beats many slots priced low, and protects the compounding assets.
3. **Lead with Layer 1 or Layer 3, not Layer 2.** The self-serve entry and the underwritten
   cohort scale; the bespoke engagement does not. Route new interest to the scalable layers
   first.
4. **The free surface is priced at zero on purpose and forever.** It is the moat, not a funnel
   trick to be gated later. Gating the tracker to force sign-ups would trade the authority asset
   for a short-term list. Do not.
5. **Every price is defended by judgment, not features.** The house voice rule applies to a price
   sheet too: name what the buyer gets to decide differently, not a bundle of deliverables.

---

## 6. Illustrative three-year revenue picture

This is a planning illustration, not a forecast, and it is deliberately conservative to fit the
10-hour cadence and the authority-first rule. Every number is an assumption; adjust as reality
arrives. Years are measured from the start of Wave 3 (`MASTER_PLAN.md`), because no layer sells
before then.

| | Year 1 of selling | Year 2 | Year 3 |
|---|---|---|---|
| **Layer 1** (access) | 3 institutions @ ~$10k | 8 @ ~$12k | 15 @ ~$12k + 1 system @ ~$75k |
| **Layer 2** (advisory) | 1 engagement @ ~$40k | 2 @ ~$50k | 3 @ ~$60k |
| **Layer 3** (underwriting) | none (still earning the right) | 1 cohort @ ~$300k | 1 cohort @ ~$400k |
| **Speaking** | 3 talks @ ~$5k | 6 @ ~$7k | 10 @ ~$10k |
| **Illustrative total** | ~$85k | ~$580k | ~$1.05M |

Read this correctly. The Year-1 number is small on purpose: it is what a nights-and-weekends
practice can earn without cannibalizing the book and the report. The step-up in Years 2 and 3 is
driven almost entirely by Layer 3 (one large underwritten contract) and the scalable Layer 1,
not by grinding more Layer 2 hours. If the book lands mid-way through this window, every number
rises, because the book is the authority event that makes Layer 3 buyers say yes. The point of
the table is the shape (small, then leveraged), not the totals.

**What would make this wrong in the bad direction:** no Layer 3 contract lands (the cohort sale
is the hardest and least certain line), and the practice defaults to Layer 2 grind. Then Year 3
is roughly Year 1 repeated, and the compounding assets are what carried the value instead. That
is survivable, because the compounding assets (book, report, model, candidacy) were always the
real return; the revenue is the proof-of-demand, not the prize.

---

## 7. What the revenue is really for

The candidacy, not the income. The "nights and weekends, no runway" decision means this is not a
practice that has to replace a salary. Its job is to (a) prove the market values the judgment,
which a search committee reads as validation, (b) fund the flywheel modestly, and (c) put Saum
in the rooms adjacent to boards, which is where presidencies are decided. A dollar of Layer 3
foundation revenue is worth more than its face value because of who is in the room when it is
signed. Price and select accordingly.

---

*Open items to resolve before selling anything: finalize the self-assessment instrument (the
5-versus-6-domain reconciliation from `MASTER_PLAN.md` section 3); decide the Layer 1 access
mechanics (annual license terms, what updates include); and draft the one-page engagement scope
for Layer 2 so a president can say yes to a known thing. None of these open until the model is
formalized and the report is published.*
