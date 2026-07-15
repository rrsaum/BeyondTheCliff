# 360Investor Marketing Style Guide

> **Authoritative reference for all member-facing copy, UI language, feature naming, and promotional material.**
> When this guide and a developer's instinct conflict, this guide wins.
> When this guide and the existing `reference-copy-design-guidelines` memory conflict, consult both. They are complementary.

---

## Brand Position

**Professional-grade intelligence for the retail and armchair investor.**

This one sentence contains three deliberate tensions that define everything:

- **Professional-grade**: rigorous, calibrated, systematic. Not opinion. Not vibes. Not financial entertainment.
- **Retail and armchair**: accessible, affordable, not requiring a Bloomberg terminal or a research staff. Respecting that serious investors exist outside of institutions.
- The gap between those two words is the product.

---

## Voice & Tone

| Quality | What It Means | What to Avoid |
|---|---|---|
| **Authoritative** | Backed by data, cited by source, precise about cadences | Vague ("updated regularly"), hedged into meaninglessness, over-qualified |
| **Plain-spoken** | No jargon without plain-English pairing | Naked acronyms, unexplained signals, "institutional" in tone |
| **Non-partisan** | Historical correlations, academic research, quantitative signals only | Political commentary of any kind, partisan framing, editorial opinion |
| **Confident** | State positions. Don't ask permission. | "We think maybe…", "This might suggest…", toggle-dependent guidance |
| **Precise** | Name the series, name the cadence, name the threshold | "Various data sources", "our proprietary model" without substance |

**Model:** Walt Mossberg. Explains complex technology to smart non-technical readers. Never talks down. Never hides behind jargon. Never hedges what is actually known.

### Before & After: Writing in the Right Voice

The right voice is not just about what you say. It's about what you refuse to say. Alex's four filters: *Is it cited? Is the methodology explained? Is this data or opinion? What would prove this wrong?* Copy that survives all four converts. Copy that fails any one loses Alex permanently.

**Regime status copy**

> ✗ "Markets appear to be showing signs of potential inflationary pressure, which could affect portfolio positioning."

> ✓ "The Stagflationary regime probability is 34%, elevated but not dominant. The signal driving it: WTI crude is up 18% over 90 days while the growth composite is contracting. Historically, that combination has resolved toward either Standard regime (if growth recovers) or full Stagflation (if it doesn't). The 90-day trend is the indicator to watch."

The first hedges everything and commits to nothing. Alex sees through it immediately. The second names the number, names the driver, names the historical context, and tells Alex what to watch next.

---

**Feature description copy**

> ✗ "Our AI-powered platform uses advanced algorithms and comprehensive data to give you real-time insights into market conditions."

> ✓ "The regime matrix scores 130+ public data series (from the Federal Reserve, the U.S. Treasury, the OECD, the BIS, and more) across five dimensions, then maps the result to one of 16 macro scenarios. The scoring uses piecewise linear calibration against historical ranges, not a black-box model. Updated every market day."

The first fails all four of Alex's filters simultaneously. The second passes all four.

**The data-series count is a single source of truth (binding).** Never hardcode the number of data series in a template or a string. The canonical claim lives in `intelligence_api/provenance.py`: `series_band()` is the count rounded DOWN to the nearest ten (so it never overstates), `series_phrase()` is the one canonical phrase ("130+ public data series"), and both are computed LIVE from the `data_series_registry`. Templates pull `{{ series_phrase() }}` / `{{ series_band() }}`; the `/about` source cards loop over `provenance_cards()`. As of 2026-06-17 the band is **130+** (131 sourced series, derived "computed" composites excluded). When the registry grows, every surface updates itself; to reword the phrase, edit `_SERIES_NOUN` in that one file.

---

**Onboarding / empty state copy**

> ✗ "Welcome! Your dashboard is loading. Check back soon for your personalized insights."

> ✓ "Your Intelligence Brief initializes once the regime engine has run its first full scoring cycle. That happens daily at 18:30 ET. If you're setting up now, your first reading will be ready tomorrow morning."

Alex doesn't want to be welcomed. Alex wants to know what's happening and when it will be done.

---

**Tier upgrade prompt**

> ✗ "Upgrade to Silver for more features and deeper insights."

> ✓ "The Fiscal Stress Vitals are a Silver instrument. They score five independent macro signals (Buffett Ratio, Ferguson Limit, R vs G Spread, Fiscal Dominance, and CB Independence) each against published historical thresholds. When the regime is ambiguous, this is where the answer usually lives."

The first is a sales line. The second is a methodology brief. To a Sage, the methodology brief is the sales line.

---

## People We Draw On

Three rosters, one rule. Each names the authorities we anchor our standards to, one owner per domain, and none of these names are ever cited in member-facing copy. They differ only in what they govern: the **Experts** shape how the product looks and reads, the **Economists** shape how we interpret a signal, and the **Chief Investment Officers / Portfolio Advisers** shape what a disciplined investor does with it. Read together they form one chain: economists set the meaning, the CIO roster frames positioning, Tetlock states the probability, Marks and Dalio set the voice, the design experts decide how it is shown.

### Experts We Draw On

This guide isn't invented from scratch. It rests on a small set of named authorities, one per domain. Each owns a single discipline; when a copy, UI, or data question falls inside their domain, their rule is the tie-breaker. The point is not to cite them in member-facing copy. It is to keep our internal standards anchored to people who got these problems right.

| Domain | Expert | The discipline they enforce | Where it applies here |
|---|---|---|---|
| **Voice / explanatory writing** | **Walt Mossberg** | Explain complex things to a smart non-specialist. Never talk down, never hide behind jargon, never hedge what is actually known. | Voice & Tone; all body and Brief copy |
| **Data visualization** | **Edward Tufte** | Maximize data-ink, eliminate chartjunk. Every gauge, the regime matrix, and the scorecards show data, not decoration. | Brief design; UI Copy Standards |
| **UX & interaction usability** | **Don Norman** | Affordances and error prevention. The product never makes Alex guess what state it is in or what an action will do. | Status Lines & Data States; Empty States |
| **Information architecture / clarity** | **Steve Krug** | "Don't make me think." Remove cognitive friction between Alex and the signal; each fact appears exactly once. | UI Copy Standards; redundancy rule |
| **Product design / simplicity & craft** | **Jony Ive** | Reduce to the essential, then obsess over the finish. The product should feel inevitable and cohesive: nothing arbitrary, nothing extra, every element considered. Restraint at the whole-product level, not just the single chart. | Overall Brief and page cohesion; visual restraint; component polish |
| **Financial credibility / macro framing** | **Howard Marks + Ray Dalio** | Marks: second-level thinking, calibrated risk language, no false certainty, respect asymmetry. Dalio: long-cycle and debt-cycle framing (the changing world order) for structural macro context. | Data Validation Claims; Copy Never Sounds Like Advice |
| **Persuasion / copywriting (incl. UI copy)** | **David Ogilvy + Eugene Schwartz + Joanna Wiebe** | Ogilvy: research-led, specific, no hype, "the consumer isn't a moron." Schwartz: meet the reader's awareness and sophistication stage. Wiebe: voice-of-customer phrasing, conversion-tested clarity. Governs promotional and UI copy (labels, empty states). | PAS framework; Approved Copy Bank; Button & Action Labels |
| **Forecasting / calibration rigor** | **Philip Tetlock** | Probabilistic humility and accountability. Report calibrated distributions, track calls, revise transparently when wrong. | Brier scoring; accountability in Exit Triggers |

When two experts touch the same string (Ogilvy on a button label, Krug on whether it adds friction), clarity wins. Krug and Norman govern *whether* an element should exist and how it behaves; Ogilvy governs *what it says*; Mossberg governs *how plainly it reads*. Ive and Tufte both pursue reduction, but at different scales: Tufte governs density and restraint *within* a single data display (data-ink in a gauge or scorecard), while Ive governs cohesion and restraint *across* the whole product (how the pages and components hang together as one considered thing). When reduction risks hiding a fact, Krug and Tufte win over polish.

---

### Economists / Macro Thinkers We Draw On

The design roster above governs how the product looks and reads. This roster governs how we *interpret the economics*: which discipline owns a given signal, and whose framing breaks a tie when a number is ambiguous. Same rule as the design roster: one owner per domain, names never cited in member-facing copy, the discipline is the tie-breaker. Howard Marks and Ray Dalio (in the design roster) still own macro *voice and framing*; the economists below own the *analytical interpretation* of the underlying signals.

#### Foundational theorists (the classical canon)

These are the canonical thinkers the rest of the roster reasons from. They do not own a live signal; they own the *first principles* a domain rests on. When a newer reading and an older framework seem to conflict, the foundation defines the lens and the academic and field economists below set the actual read. One owner per first principle; names never cited in member-facing copy.

| First principle | Theorist | The framework they anchor | Where it applies here |
|---|---|---|---|
| **Markets as price discovery (the invisible hand)** | **Adam Smith (1723-1790)** | Decentralized prices aggregate dispersed information and coordinate supply without a planner; *The Wealth of Nations* and classical free-market theory. | The premise under every market-based signal: Treasury auction demand, market-set yields, price-derived stress reads |
| **Comparative advantage & trade** | **David Ricardo (1772-1823)** | Why nations gain from trade even when one is less efficient at everything; the classical architecture of relative cost. | Global and trade context; country-scoped signals (the foundation under Krugman's live trade mechanics) |
| **Demand management & the business cycle** | **John Maynard Keynes (1883-1946)** | Founder of macroeconomics: aggregate demand drives output, and fiscal or monetary action can blunt a downturn. | Fiscal stress engine; government-borrowing and fiscal-dominance framing; cycle-stage and recession reads |
| **Prices as distributed knowledge; intervention risk** | **Friedrich Hayek (1899-1992)** | The Austrian-school case that prices carry knowledge no planner holds, and that intervention distorts the signal (*The Road to Serfdom*). | Financial-repression regime; reflexivity context; skepticism when policy distorts a market price |
| **Money supply & monetarism** | **Milton Friedman (1912-2006)** | The money supply, and the Federal Reserve's control of it, drives inflation and the cycle; deregulation and free-trade priors. | Monetary-policy dimension (the Federal Reserve's stance); inflation and liquidity first principles (Bernanke owns the live crisis read) |
| **Supply, demand & marginal analysis** | **Alfred Marshall (1842-1924)** | The neoclassical synthesis: supply and demand, marginal utility, and cost of production in one framework. | The supply-versus-demand framing beneath every dimension: auction demand vs issuance, labor supply vs demand |
| **Mathematical synthesis (classical + Keynesian)** | **Paul Samuelson (1915-2009)** | Put economics on a rigorous mathematical footing and unified classical and Keynesian thought. | The quantitative method itself: the 0 to 100 composite, weighted sub-scores, and backtested scoring discipline |
| **Game theory & strategic interaction** | **John von Neumann (1903-1957)** | *Theory of Games and Economic Behavior*: model agents as strategic actors who anticipate one another. | Reflexivity (actors reacting to each other); auction bidder dynamics; positioning under strategic uncertainty |

#### Academic and policy economists (structural interpretation)

| Domain | Economist | The discipline they enforce | Where it applies here |
|---|---|---|---|
| **Monetary policy & financial crises** | **Ben S. Bernanke** | How credit seizures become real-economy damage; lender-of-last-resort logic; QE and tapering transmission. Read liquidity stress as a forward growth signal, not a sideshow. | Liquidity & credit signals; Treasury / fiscal dominance; taper-style repricing analogues |
| **Sovereign debt & international finance** | **Kenneth S. Rogoff** | Debt thresholds and sovereign-default history; "this time is different" skepticism. Pairs with the Reinhart-Rogoff base already in the conditions spec. | Fiscal stress engine; debt-cycle framing; sovereign risk |
| **Trade & currency crises** | **Paul Krugman** | Trade imbalances and currency-crisis mechanics; consumer expectations flow to consumption to GDP, so confidence is a Growth signal. | Growth signals; consumer-confidence placement; global trade context |
| **Institutions & long-run growth** | **Daron Acemoglu** | Institutions drive divergence; the gap between market sentiment and consumer sentiment is exactly when each reading matters most. | Regime / structural context; cross-country calibration rationale |
| **Labor economics & human capital** | **James J. Heckman** | Rigorous labor-market measurement and identification; do not confuse selection effects for signal. | Labor Market dashboard; employment signal interpretation |
| **Applied microeconometrics (consumption & labor)** | **Richard W. Blundell** | Household consumption and labor-supply empirics; careful identification before any causal read. | Consumer confidence to Growth; spending and income signals |
| **Market structure & regulation** | **Jean Tirole** | Market power, incentives, and the regulation of dominant firms; competitive position is an analyzable structure, not a story. | Company Intelligence (moats, competitive position); sector structure |
| **Behavioral finance / inefficient markets** | **Andrei Shleifer** | Investor sentiment and consumer sentiment are distinct constructs; limits of arbitrage; noise-trader risk. | Sentiment vs Growth separation; reflexivity context |
| **Empirical asset pricing / factor models** | **Kenneth R. French** | The cross-section of returns and factor exposures; evidence over narrative. | Company Scorecard style-fit grades; factor framing |
| **Coordination, focal points & credible commitment** | **Thomas Schelling** | Strategy as the art of coordination without communication: the focal points people converge on when they cannot talk, and the credible commitments that make a stance believable. Applies von Neumann's game theory to real coordination and deterrence. | The Brief as a shared reference point members coordinate around without a social graph; the Predictions Ledger as a credible commitment to keep score; the truthful-revelation design of any aggregated member signal |

#### House and field economists (real-time regional reads)

These are working forecasting economists who own the near-term, on-the-ground read for their regions. When a current number is ambiguous, they own the *immediate* interpretation; the academic economists above own the *structural* one.

| Domain | Economist | The discipline they enforce | Where it applies here |
|---|---|---|---|
| **Global & Asia macro (real-time)** | **Taimur Baig** | Top-down global and Asian growth, inflation, and policy reads on a live cadence; connect the regional data to the global cycle. | Country-scoped signals; Asia and global macro context |
| **China & broader Asia** | **Carlos Casanova** | China credit, policy, and spillover into the rest of Asia; where the official data and the market read diverge. | Country-scoped signals; China / Asia context |
| **Emerging Asia** | **Alex Holmes** | Emerging-Asia growth and external-balance dynamics; small-economy sensitivity to global conditions. | Country-scoped signals; emerging-Asia context |
| **ASEAN** | **Yun Liu** | ASEAN growth, trade, and inflation; supply-chain and export-cycle reads. | Country-scoped signals; ASEAN context |
| **Baltics & Northern Europe** | **Mihkel Nestor** | Baltic and Nordic real-economy reads; small-open-economy exposure to European demand. | Country-scoped signals; Baltic / Northern Europe context |
| **Europe & UK** | **Rory Fennessy** | European and UK growth and inflation forecasting; near-term activity reads against the European cycle. | Country-scoped signals; European / UK macro context |

**Tie-break order for economic signals:** the foundational theorists own the *first principles* a signal rests on; the field economists own the *near-term read* of a live number; the academic economists own its *structural meaning*; Tetlock (design roster) owns *how the resulting probability is stated*; Marks and Dalio own *how it is voiced* to the member. When a regional read conflicts with the structural frame, surface both, never silently pick one.

---

### Chief Investment Officers / Portfolio Advisers We Draw On

The economists tell us what a signal *means*. This roster governs what a disciplined investor *does* with it: position sizing, conviction, entry and exit, style, and risk control. Same rules: one owner per domain, names never cited in member-facing copy, the discipline is the tie-breaker. This is positioning discipline, not advice to the member. We surface what these disciplines would weigh, then the member decides. Marks and Dalio (design roster) still own framing and voice; this roster owns *positioning, sizing, and risk*.

| Domain | Investor | The discipline they enforce | Where it applies here |
|---|---|---|---|
| **Contrarian global value / maximum pessimism** | **John Templeton** | Buy at the point of maximum pessimism; hunt bargains across every market, not just the home one. The crowd's despair is the entry. | Regime positioning; contrarian entry timing; global breadth reads |
| **Disciplined low-multiple value** | **John Neff** | Low price-to-earnings discipline, unglamorous quality, total return measured against the multiple paid. Never overpay for a story. | Company Scorecard value and style-fit grades; entry-price tiers |
| **Global macro & reflexivity / asymmetric bets** | **George Soros** | Reflexivity: prices shape the fundamentals that then justify them. Press an asymmetric edge hard, and cut fast when the thesis breaks. | Reflexivity Monitor; regime turning points; conviction sizing |
| **Quality compounding & intrinsic value** | **Warren Buffett** | Durable moats, intrinsic value, margin of safety, long horizon, stay inside the circle of competence. | Company Intelligence (moats, 3-tier entry); style-fit; retiring "no positions" language |
| **Bottom-up growth / know what you own** | **Peter Lynch** | Bottom-up scuttlebutt, growth at a reasonable price (PEG), categorize the story, never buy what you cannot explain simply. | Company Scorecard growth and style fit; Investigations evidence |
| **Multi-strategy risk management / drawdown control** | **Israel "Izzy" Englander** | Diversified, risk-controlled, near market-neutral process; tight limits and process discipline beat any single heroic bet. | Risk framing; drawdown and position discipline; portfolio-level guidance |
| **Top-down macro conviction & capital preservation** | **Stanley Druckenmiller** | Be big when the edge is clear and small when it is not; follow liquidity; preserve capital first so you survive to press the next clear bet. | Regime positioning guidance; Investment Clock; conviction calibration |

**Where these overlap:** Soros and Druckenmiller both run global macro, so split them: Soros owns reflexive turning points, Druckenmiller owns top-down conviction sizing, liquidity, and capital preservation. Templeton, Neff, Buffett, and Lynch are four distinct bottom-up styles, not duplicates: Templeton buys global despair, Neff buys the cheap multiple, Buffett buys durable quality, Lynch buys the understandable grower. Englander is the risk-management lens that sits over all of them.

**Full interpretation chain for any signal:** the economists interpret *what it means* → this roster frames *positioning, conviction, and risk* → Tetlock states *the probability* → Marks and Dalio set *the voice* → the design roster decides *how it is shown*. The member always makes the call; we never tell them to buy or sell.

---

## What We Do Not Cover

**No political commentary. Ever.**

- No attribution of economic conditions to political parties, politicians, or administrations by name
- No framing of data as "good" or "bad" for a political agenda
- Fiscal policy data (deficits, debt, spending) is reported as signals, not as political indictments
- Regime classifications reference historical economic patterns, not political regimes
- If a signal correlates with a policy, describe the historical correlation. Do not assign credit or blame.

**The rule in practice:** A member reading our copy should be unable to determine our political views. That is a design goal, not a limitation.

---

## Membership Vocabulary

### Preferred Terms

| Use This | Not This | Why |
|---|---|---|
| **Member** | Subscriber, user, customer | Conveys belonging and exclusivity, not a transaction |
| **Membership** | Subscription, plan, account | A membership is earned and valued; a subscription is a billing arrangement |
| **Intelligence Brief** | Dashboard, newsletter, report | This is a curated intelligence product, not a page of charts |
| **Signal** | Alert, notification, flag | Signals imply analysis; alerts imply software plumbing |
| **Regime** | Market condition, environment | Regime is precise; it implies a structural state with known characteristics |
| **Access** | Buy, sign up, subscribe | Members access the platform; they don't subscribe to it |
| **Vitals** | Indicators, metrics | Vitals imply health and criticality; the body metaphor is intentional |
| **Instrument** | Tool, feature | Instruments imply craft and precision |
| **Brief** (short form) | Report, update, email | Brief is journalistic and authoritative |
| **Today's Read** | "insights", "summary", "overview", "daily takeaway" | Owned name for the daily synthesis page at `/brief` (shipped name as of 2026-06-09, superseding the earlier "Regime Read" label; see the Owned Term note below). Capitalize as a named instrument. The lowercase CTA verb form stays "Read the regime". |

### Preferred Terms (Updated)

| Use This | Not This | Why |
|---|---|---|
| **Read the regime** | "Get the Brief", "Get started", "Sign up" | Names what Alex will *do*, in his own vocabulary. "Brief" alone reads as a one-time document; "Get started" is the most generic phrase in SaaS. |
| **Start with [Tier]** | "Join as [Tier] member", "Subscribe to [Tier]" | Decisive, no club language. "Join" is social; "Start with" is a tool decision. |
| **Own the edge** | "Get Corporate access", "Contact us", "Learn more" | Competitive outcome language calibrated to Alex's Ruler archetype. Under 20 characters: decisive, possession-coded, no FOMO. Corporate visitors need to feel the competitive advantage, not be routed to a form. |
| **The synthesis is done. Your judgment takes it from here.** | "Not a starting point for more research" | Resolves the tension between "we do the work" and "you do your own work." The platform handles assembly; Alex handles thinking and action. |

### Owned Term: Regime Read

**Regime Read** is the proprietary name for the daily top-line synthesis at the head of the Intelligence Brief: a one-glance statement of where the regime stands and what changed since the last reading. It is a named subreport, not a generic summary or overview. We own this term.

- **Capitalization.** "Regime Read" is capitalized as a named instrument, like Investment Clock or Treasury Auction Monitor. The lowercase verb forms stay conversational: the CTA "Read the regime" and Alex's question "What's the regime read?"
- **Relationship to the Intelligence Brief.** The Intelligence Brief is the whole member home surface. The Regime Read is the synthesis subsection (or subreport) at the top of it. Never use one as a synonym for the other.
- **Why it lands.** It is the exact phrase Alex already uses. Naming the thing he asks for beats any invented label.

**Decision locked 2026-06-01.** The member home stays "Intelligence Brief." "Insights" and "Insights Brief" were evaluated and rejected: "insights" is on the hollow-word list (see Feature Naming Conventions) and appears in this guide only as ✗ examples. Do not reopen.

**Superseded 2026-06-09 (surfaced name).** The daily synthesis page shipped as **"Today's Read"** at `/brief`, and that is the owned, member-facing name going forward (wordmark, nav, and titles all read "Today's Read"). "Regime Read" is retained here only as the historical rationale for why a named, Alex-vocabulary synthesis beats a generic label; the surfaced product name is "Today's Read". The member home is still the "Intelligence Brief"; the lowercase CTA verb form is still "Read the regime". This reconciles the guide with the shipped product (owner decision; the rename itself was made in an earlier session and confirmed 2026-06-09).

### Prohibited Terms

- "Subscribe" / "subscription" in member-facing contexts
- "User" (always "member")
- "Dashboard" for the Intelligence Brief
- "Proprietary model" without citing what it actually uses
- "Real-time" (we are not real-time; be precise about cadences)
- "Comprehensive" or "complete" (implies nothing is missing; never claim this)
- "AI-powered" as a standalone claim: always state what the AI does specifically
- "Get started": the most generic SaaS phrase; fails every one of Alex's filters
- "Join as": club language; Alex is not a joiner, he is a tool-user
- "Get the Brief" as a standalone CTA: "Brief" reads as a one-time document to a first-time visitor; use "Read the regime" instead
- "Central bank" or "central banks": in U.S. context, always "The Federal Reserve." The institution has a name. "Central bank" is generic; it signals imprecision and reads as hedging.
- "Sector rotation guidance" or any variant implying directional advice: use "sector signals" instead. The platform surfaces signals; Alex determines action. Guidance implies we are telling Alex what to do. We are not. See **Copy Never Sounds Like Advice** section.

### Prohibited Punctuation

**Em-dash (—) is prohibited everywhere. Not just member-facing and public copy: internal docs, this guide, specs, memory files, code comments, and commit messages. There is no context where it is acceptable.**

The em-dash signals laziness and is a marker of AI-generated text. Alex notices it. A writer who reaches for an em-dash is avoiding the harder editorial choice: end the sentence, or restructure it. Both options produce cleaner, more confident prose. The rule is total because a half-applied rule trains the wrong habit. If the em-dash is acceptable in a doc, it leaks into the copy.

**What to use instead:**

| Situation | Instead of em-dash | Use |
|---|---|---|
| Amplifying a prior clause | "The data is public — the synthesis is ours." | "The data is public. The synthesis is ours." |
| Introducing a list or elaboration | "Five signals — each scored independently." | "Five signals, each scored independently." |
| Parenthetical aside | "Fiscal Dominance — a structural condition — builds slowly." | "Fiscal Dominance is a structural condition. It builds slowly." |
| Contrast or pivot | "Not a single prediction — a calibrated distribution." | "Not a single prediction. A calibrated probability distribution." |

The test: if an em-dash is holding two thoughts together that could be separate sentences, split them. If it is replacing a colon, use a colon. If it is replacing a comma, use a comma. There is always a better option.

**Hyphens** (single dash, as in "five-dimension," "40+," "A+") are not affected by this rule. Only the typographic em-dash (—) is prohibited.

---

## Membership Tiers

Tiers are named after athletic achievement levels. They convey earned status and progression without corporate baggage. The frame is not "how much do you want to pay" but "how deep do you want to go."

### Bronze

> The essential intelligence layer. Daily regime status, Investment Clock position, sector signals, and yield curve reading, calibrated to whichever of 16 macro scenarios is active right now. Most professional investors would find this alone worth the price of admission.
>
> *For members who want the signal without the noise.*

**What Bronze does for Alex:** Answers the question Alex asks every Sunday evening: "Am I positioned for where the cycle is headed, or where it's been?" The Brief is four minutes. The framework is systematic. No opinion, no narrative, just a calibrated read on the regime, updated every market day.

---

### Silver

> Everything in Bronze, plus the instruments that matter when the regime is under stress or in transition: Fiscal Stress Vitals (five independent macro signals scored against historical thresholds), Treasury Auction Monitor (7Y, 10Y, and 30Y demand grades updated same-day), Labor Market Health Score, and the full five-dimension Economic Conditions deep-dive.
>
> *For members who go deeper when the macro environment is deteriorating or unclear.*

**What Silver does for Alex:** When the regime matrix shows elevated Fiscal Dominance probability, Alex wants to know why and by how much. Silver has the answer: five vitals, each scored independently, each traceable to a published data source. This is where the conviction behind a positioning decision comes from.

---

### Gold

> Everything in Silver, plus the Reflexivity Monitor: the engine that tracks the feedback loop between price, narrative, and fundamentals. When a signal diverges from what the data supports, it scores how far the loop has run, what phase it is in, and the historical episode it most resembles.
>
> *For members who want to see reflexive turns take shape before the tables confirm them.*

**What Gold does for Alex:** Bronze and Silver tell Alex where the regime is. Gold tells Alex when the market's own narrative is starting to bend it. The Reflexivity Monitor makes feedback-loop analysis systematic: it flags the loops that tend to precede regime turns, scored and dated, so Alex is early to the turn instead of reacting to it.

---

### Corporate

> Everything in Gold, plus five member seats under one billing account. One designated admin manages access. One systematic read (same regime status, same cycle position, same fiscal stress picture) every morning.
>
> *For teams that need to move from the same starting point.*

**What Corporate does for Alex:** Five people reading five sources arrive at five different views of the regime. Monday becomes about reconciling opinions instead of executing on one. When the regime shifts, the team finds out at different times, from different signals. Corporate puts five seats on one systematic read. The edge isn't the data. It's that your whole team reads it first.

---

**Tone rules for tiers:**
- Bronze is not "basic." It is what most professional investors work from daily
- Silver is not "standard." It is where macro picture becomes precise
- Gold is not "premium." It is the reflexivity lens: seeing turns form before the tables confirm them
- Corporate is not "enterprise." It is a team read, not a sales engagement
- Never frame a lower tier as inferior; frame a higher tier as *deeper*
- Never list features as bullet points in promotional copy. Explain what they do for Alex

**In copy always:**
- "Bronze members access…" not "Bronze plan includes…"
- "Upgrade to Silver" not "Upgrade your plan"
- "Join as a Gold member" not "Subscribe to Gold"
- "Corporate membership" not "Firm plan" or "team subscription"

---

## The Persona: Alex

> **STATUS: LOCKED 2026-05-29.**
> Alex is the canonical member persona. Do not modify this section without a deliberate review of all downstream copy, UI language, and feature naming. Changes here cascade everywhere.

Alex is the member we design every feature for and write every line of copy toward.

### Archetype: The Sage (primary) / The Ruler (secondary)

**The Sage** seeks truth through research, expertise, and systematic thinking. They distrust noise. They respect rigor. They feel their deepest satisfaction when they understand *why* something is true, not merely *that* it is. They don't want to be told what to do. They want the framework to decide for themselves. They share knowledge selectively, with a small trusted circle. They are the person who reads the methodology section.

**The Ruler** secondary: Alex wants mastery over their financial future, not domination, control. They are unsettled by complexity they can't structure. They want to be the person in the room who read the macro picture correctly before the consensus caught up. The Ruler drive is what fuels the 3–6 hours per week. The Sage drive is what makes Substack opinions feel hollow.

**The tension that creates the member:** Alex has Ruler ambitions but incomplete Sage tools. They have the intellectual appetite for serious research but lack the infrastructure to do it systematically. That gap is 360Investor.

**Implication for copy:** You do not sell to a Sage with hype or FOMO. You earn their trust by showing your work. Every methodology citation, every source reference, every "here's how we calculate this" is a conversion event with Alex, not friction.

---

### Demographics

- Age 38–52, skews male but not exclusively
- High-earner in a non-finance profession: software engineer, physician, attorney, business owner, senior corporate executive, architect, academic
- Household income $200K+; investable portfolio $200K–$1M, self-managed
- Probably has a 401(k) on autopilot plus a taxable brokerage account they actively manage
- Partner or spouse who may not share the interest. Alex's decisions carry household weight

---

### Psychological Profile

- **Systematic thinker.** Builds mental models before acting. Suspicious of conclusions that skip the reasoning.
- **Mastery-driven, not validation-driven.** Invests because they find it genuinely interesting, not to impress anyone. But they do want to be right, and to know *why* they were right.
- **High complexity tolerance, low noise tolerance.** Can handle the Buffett Ratio if it's explained once. Cannot handle a Twitter thread that yells about the Fed without citing a number.
- **Risk-aware, not risk-averse.** Understands asymmetry. Hates uncompensated risk. More afraid of being confidently wrong than of missing a gain.
- **Skeptical of consensus.** If everyone is saying it, Alex is already asking what everyone is missing.
- **Self-reliant.** Has tried delegation (robo-advisors, financial advisors) and found it unsatisfying: too black-box, too passive, too divorced from the reasoning.

---

### Emotional Landscape

**What Alex feels pride about:**
- Doing their own research when most people just follow the crowd
- Understanding macro concepts their peers don't have language for
- Making a decision with a clear, defensible rationale, and being right

**What Alex feels anxious about:**
- Being wrong at scale: one bad positioning decision can erase years of savings
- Missing a regime shift until it's too late to act
- Not knowing what they don't know: the unknown unknowns of macro
- The spouse conversation after a bad quarter

**What Alex feels frustrated by:**
- Financial media that can't separate signal from politics
- Smart people on Twitter who are confident without being calibrated
- Quarterly research PDFs that are already stale by the time they're published
- Robo-advisors that can't answer "why are you holding bonds right now?"
- The gap between having the data (FRED) and knowing what to do with it

**What Alex feels occasional FOMO about:**
- Seeing someone else correctly call a regime shift they missed
- Hearing that a macro commentator they follow was early on something they were late to
- Not being positioned before a move that was, in retrospect, clearly signaled

**What makes Alex feel confident:**
- A framework they understand well enough to explain to someone else
- Being positioned for the right cycle phase before the consensus sees it
- Knowing the *why* behind a market move, not just observing that it happened
- Checking the Brief and feeling like they already knew what it would say, because they've internalized the framework

---

### Financial Psychology

- **Loss aversion is real but intellectually understood.** Alex knows the math of loss aversion. They still feel it. A good framework helps them override the feeling with data.
- **Anchoring to their own thesis.** Once Alex has a view, they hold it longer than the data warrants. They need a tool that challenges their assumptions, not just confirms them.
- **The classic retail timing failure.** Alex has probably been too cautious at the bottom and too confident at the top, not because they're irrational, but because they were reading narrative, not signals.
- **Top-down thinker.** Alex thinks in macro first, sector second, individual security third. They are not a stock picker. They want to know which environment they're in before they decide what to own.
- **Respects asymmetry.** More interested in "what could go badly wrong" than "what's the upside." A fiscal stress reading that's deteriorating gets more attention than a growth reading that's improving.

---

### Information Behavior

**What Alex currently reads:**
- Newsletters: Lyn Alden, George Gammon, Eric Peters, Jeff Snider (Eurodollar University), Howard Marks memos
- Books: Ray Dalio's *Principles / Changing World Order*, *The Intelligent Investor*, Michael Lewis
- Podcasts: Odd Lots (Bloomberg), Macro Voices, We Study Billionaires
- Data: glances at FRED and Trading Economics, doesn't model it
- Twitter/X: curated macro list, 15–25 accounts, reads more than posts

**What Alex has tried and moved past:**
- **Robo-advisors:** "I'm smarter than a 60/40 rebalancer that doesn't know what cycle we're in"
- **Stock screeners:** "I think top-down, not bottom-up"
- **Financial advisors:** "They don't understand macro well enough and they're selling something"
- **Bloomberg (briefly):** "Too much raw data, zero synthesis. I'd need to be an economist to use it"
- **Investment clubs:** "Too social, not systematic enough, too much groupthink"
- **Paid Substack newsletters:** Has probably paid for at least one and felt it was still someone's opinion, not a methodology

**How Alex evaluates new information:**
1. What is the source? Is it cited?
2. What is the methodology? Is it explained?
3. Is this data or opinion? Can I separate them?
4. What would have to be true for this to be wrong?

If 360Investor copy cannot survive those four questions, Alex will not trust it.

---

### The Defining Mistake

Every Alex has made one costly decision that clarified what they were missing. Common patterns:

- **Held duration through 2022**, because "bonds are safe in a downturn," without understanding that a fiscal dominance environment breaks the standard playbook. The regime had changed; the mental model hadn't.
- **Sold in March 2020**: panic-driven, not signal-driven. Watched the recovery from the sidelines. Back-calculated the cost as devastating and promised themselves it wouldn't happen again.
- **Missed the 2020–2021 reflation trade**: reading news, not regime signals. The Investment Clock had moved into Recovery; Alex's portfolio was still positioned for contraction.
- **Overweight growth/tech into the 2022 rate cycle**: didn't track monetary policy tightening signals until prices had already moved.

The common thread: **they were reactive, not positioned.** The regime had shifted and they found out from price action, not from leading indicators. That mistake is why they're looking for 360Investor.

---

### Social Context

- Discusses investments seriously with 1–3 trusted people: a friend who also invests, occasionally a financially-literate family member
- Does not broadcast performance (unlike crypto traders). Money is private
- Is the person in their social circle who others occasionally ask "what do you think is going to happen?" and feels the weight of that expectation
- May quietly compare their framework to what a professional investor friend uses, wanting to feel they're operating at a comparable level of rigor

---

### Decision Triggers (What Makes Alex Join)

- Reads something (a piece of copy, a methodology explanation) that names a problem they've been feeling but couldn't articulate
- A macro event (bad CPI print, weak treasury auction, Fed pivot) that the regime matrix called correctly, and Alex sees it explained with the data behind it
- A recommendation from a trusted peer: "have you seen 360Investor?"
- A free piece of content (a methodology explainer, a "Behind the Brief" post) that demonstrates rigor they haven't seen elsewhere
- Feeling that their current toolset is insufficient for the current macro environment

### Retention Drivers (What Keeps Alex)

- The Brief is reliable: it's there every morning, it doesn't editorialize, it doesn't miss days
- The framework becomes Alex's own: they've internalized it well enough to use it without reading instructions
- When a regime shift happens, Alex was watching the signals and was positioned ahead of it
- New subsystems and data series expand the picture. Alex feels they're getting more per dollar over time
- The no-political-commentary rule holds, so Alex can trust the signal isn't colored

### Exit Triggers (What Makes Alex Leave)

- The Brief becomes predictable without being useful: "Standard Regime" for six months with no nuance or explanation of what's changing at the margin
- A significant call goes wrong with no accounting, no revision, no transparency about why
- Political commentary creeps in: this is a dealbreaker, not a concern
- The UI adds friction between Alex and the signal
- A better-calibrated, equally rigorous alternative appears (the competitive moat is the methodology, not the technology)

---

### Alex's Vocabulary

How Alex already talks about investing, or will, once they've internalized the framework:

- "I'm positioned for X" (not "I own X")
- "The macro backdrop is Y" (not "the market is doing Y")
- "The cycle is in Z phase" (once they learn it)
- "What's the regime read?" (goal state, this becomes natural)
- "I'm watching the yield curve / the term premium / jobless claims"
- "That's narrative, not signal"
- "I don't trust consensus on this"

---

**Writing for Alex:** Smart, time-constrained, pattern-seeking, and skeptical. Explain the methodology once, clearly and completely. Then get out of the way and give Alex the signal. Never hedge what is actually known. Never editorialize. Trust Alex to act on the framework once they have it.

**The single test for any piece of copy:** Would Alex forward this to the one or two people in their circle they discuss investing with? If yes, it's the right voice. If it reads like a sales page, it fails.

---

## Data Validation Claims

When making claims about rigor, precision, or coverage, cite specifically. Vague claims ("hundreds of data points") undermine credibility with members who are sophisticated enough to check.

### Current Platform Data Footprint

**Series monitored:** 60+ unique data series across 5 subsystems

| Subsystem | Series Count | Update Cadence |
|---|---|---|
| Economic Conditions | 31 (FRED × 4 cadences + CBOE + OECD) | Daily, weekly, monthly |
| Fiscal Stress | 11 (9 FRED + 2 FiscalData endpoints) | Daily (debt), weekly (Fed holdings), monthly/quarterly (GDP, PCE) |
| Treasury Auctions | 3 maturities (7Y, 10Y, 30Y) | Daily at 4:30pm ET post-auction |
| Labor Market | 4 FRED series → 1 composite | Monthly (first Friday) |
| Regime Engine | Aggregated from all subsystems | Daily |

**Analytical framework parameters:**
- 16 macro scenarios (4 Investment Clock phases × 4 macro regimes)
- 5 fiscal stress vitals scored independently
- 4 probability-weighted regime scenarios reported simultaneously
- 5 economic condition dimensions (Growth, Inflation, Sentiment, Monetary Policy, Liquidity)
- 5 STEEP signal categories (Social, Technological, Economic, Environmental, Political)
- 3 PPP probability tiers (Possible, Probable, Preferred) applied to every extracted signal

**Approved claim formats:**
- "Monitoring 130+ public economic data series, updated daily to monthly from the Federal Reserve, the U.S. Treasury, the OECD, the BIS, and more"
- "16-cell regime matrix updated every market day: the same framework used in academic macro research, calibrated to current data"
- "Five independent fiscal stress vitals, each scored against historical ranges and published thresholds"
- "Four simultaneous regime probabilities, not a single prediction, a calibrated distribution"

**Never:**
- "Comprehensive coverage of global markets" (we do not cover equities, commodities, or international macro yet)
- "Powered by AI" without specifying what AI does (extracts signals from documents; does not generate the regime scores, which are quantitative)
- "Proprietary algorithm." Describe it: "piecewise linear scoring against empirical historical ranges"

---

## Feature Naming Conventions

When naming new features, apply these principles:

1. **Describe the analytical function, not the software function**
   - "Regime Engine" not "Regime Calculator"
   - "Intelligence Brief" not "Dashboard"
   - "Reflexivity Monitor" not "Loop Tracker"

2. **Use the domain vocabulary**
   - Signals, regimes, vitals, readings, conditions, thresholds, probability
   - Not: alerts, metrics, KPIs, analytics, insights (overused and hollow)

3. **Avoid sport/game metaphors** (except tier names)
   - No "leaderboards", "streaks", "badges" in the intelligence context; inconsistent with the professional positioning

4. **Consistency with existing names**
   - Investment Clock (not "Market Clock" or "Cycle Clock")
   - Fiscal Stress Vitals (not "Fiscal Health Score")
   - Regime Matrix (not "Regime Grid" or "Scenario Table")
   - Treasury Auction Monitor (not "Bond Tracker")
   - Regime Read (not "summary," "overview," or "daily takeaway"): the owned name for the synthesis subreport at the top of the Intelligence Brief. See Owned Term: Regime Read.
   - **Treasury Auction**: always capitalize both words. It is a named instrument, not a generic description. Use "Treasury Auction grades" or "Treasury Auction Monitor grades." Never "treasury auction grades."

---

## Prohibited Topics (Detailed)

The following are never appropriate in any member-facing or promotional material:

- Commentary on specific politicians or political parties
- Attribution of economic conditions to a presidential administration by name
- Forward-looking fiscal projections framed as political argument
- Use of partisan language ("big government," "free market," "socialist," "fiscal hawk")
- Endorsement or criticism of any specific investment, security, or fund
- Claims of guaranteed returns or specific performance projections
- Legal or tax advice of any kind
- Suggesting the platform is for making investment decisions: the platform is a research instrument, not a decision-making tool. Never write "use this for investment decisions," "to make better investment decisions," or any equivalent. Permitted framing: "to understand where the cycle stands," "to inform your research process," "to know what the regime is." The platform assembles the picture. Alex decides what to do with it.

**What to do when a data signal is politically loaded:**
Report the signal, name the source, describe the historical correlation. Do not explain why the policy is good or bad.

*Example:* Federal deficit widened to 6.2% of GDP. Historically, sustained deficits above 5% GDP have coincided with elevated inflation and term premium expansion. The Fiscal Dominance score reflects this. This is appropriate.

*Not appropriate:* "The administration's spending policies are driving unsustainable deficits." This is political commentary.

---

## UI Copy Standards

Alex encounters product copy constantly: status lines, empty states, error messages, button labels, tooltip text. These are not low-stakes. Alex's trust is built or lost in the product, not just in marketing copy. Every string that appears in the interface is an opportunity to reinforce that this is a serious instrument, not a consumer app.

### Status Lines & Data States

The product frequently shows data freshness, system state, and processing status. These must be precise. Alex will check them against the Brief to assess whether the data is current.

| Situation | ✗ Don't Write | ✓ Write Instead |
|---|---|---|
| Data loading | "Loading your insights…" | "Fetching regime readings…" |
| Never initialized | "No data yet" | "No readings computed. Run a refresh to initialize" |
| Stale data | "Data may be outdated" | "Last computed 3 days ago. Regime readings may not reflect recent data" |
| Scheduler pending | "Coming soon" | "Updates daily at 18:30 ET. Next run in approximately 4 hours" |
| FRED unavailable | "Data source error" | "FRED API unreachable. Using cached data from [date]. Scores reflect that snapshot." |
| Score not computable | "Insufficient data" | "Insufficient history to compute. Requires 5+ quarters of GDP data. Will update automatically." |

### Button & Action Labels

Buttons should describe the action precisely. Alex doesn't need motivation; they need accuracy.

| Context | ✗ | ✓ |
|---|---|---|
| Manual data refresh | "Update" | "Refresh Now" |
| Regime score | "Learn more" | "View scoring detail" |
| Dismiss a signal alert | "Dismiss" | "Dismiss" *(this one is fine: clarity over cleverness)* |
| Start an investigation | "Get started" | "Open investigation workspace" |
| Confirm a position | "Yes" | "Confirm" |

### Empty States

Empty states happen during onboarding, after filters return nothing, or before a subsystem has run. They should explain the situation and give Alex agency. Never be cute, never apologize, never be vague.

> ✗ "Nothing here yet! Check back soon 😊"

> ✓ "No investigation workspaces yet. A workspace lets you build a structured thesis: state a position, attach evidence, score it against the regime context, and track probability over time."

The second respects Alex's intelligence, explains the instrument, and implies the value without selling it.

### Tooltips & Explainer Text

When a term needs explanation in the UI, explain it the way you would explain it to Alex: once, precisely, without condescension.

> ✗ "The Ferguson Limit is a complex metric used by economists."

> ✓ "Ferguson Limit: the ratio of federal interest payments to defense spending. Above 1.0 historically marks fiscal stress: the government is spending more servicing debt than maintaining security. Current threshold crossed: [value]."

Name the formula. Name the historical significance. Name where we are right now. Done.

### Notifications & Alert Copy

Signal alerts in the product are not notifications in the consumer-app sense. They are regime intelligence. Write them like briefing items.

> ✗ "🚨 Alert: Fiscal stress has increased!"

> ✓ "Fiscal Dominance probability crossed 60%. The Ferguson Limit is now 1.04, above the critical threshold for the first time since [date]. Historically this has preceded [pattern]. Current regime reading has updated."

No exclamation points. No emoji in intelligence copy. State the number, state the threshold, state the historical precedent, state the implication.

### Member-Only Features on Public Pages

Features behind login (the Member Ideas Board, the Reflexivity Monitor) are **never linked, advertised, or surfaced on public pages**.

Advertising them to non-members creates dead ends (click → login wall → no account → frustration), reveals product structure to competitors before it is a conversion reason, and dilutes the gate that drives sign-up.

**Correct pattern:** Public pages describe outcomes (*"the full methodology is inside the platform"*), never the destination (*"click here for the Signals section."*).

### Support & Contact Page Framing

Public support pages that offer a contact channel must scope it precisely to discourage casual queries without blocking legitimate prospects.

- **Heading:** "Not answered here?" rather than "Still have questions?" The second is too broad and implies the FAQ is incomplete.
- **Body copy:** Name the valid reasons to write: *"membership specifics, billing, or anything that requires a direct answer."* Someone with a general curiosity reads that and self-selects out. A genuine prospect knows they are in the right place.
- **Never** position the contact form as a general helpdesk or an alternative to reading the support page.

### Corporate Membership Routing

Corporate membership is self-serve. All Corporate CTAs route to `/join?tier=firm` (the self-serve signup, which starts a 14-day Corporate trial). Never route Corporate prospects to the contact form or write "contact us to set up a Corporate account." The contact form topic "Corporate account question" exists for **existing** Corporate admins who need support. It is not a sign-up path.

---

## Member-Generated Content

Members who share how 360Investor fits into their research process are the most credible voice we have. Alex trusts another Alex more than any copy we write. The goal is to make it easy for members to share their process, and to ensure that what they share reinforces the right positioning.

**Invite members to share their process, not their performance.**

The angle is always: "Here's how I use the regime framework to structure my thinking," not "here's what I made." Performance claims attract the wrong members, create legal exposure, and don't reflect the product's actual value proposition (which is rigor, not tips).

**Approved spotlight framing:**
- "How [Alex] uses the regime matrix to decide when to reduce duration exposure"
- "What the Investment Clock told [Alex] about sector positioning in the current cycle"
- "How [Alex] built an investigation workspace around a stagflation thesis"

**Never:**
- Center a spotlight on returns, percentage gains, or specific investment calls
- Imply that 360Investor's analysis guarantees or predicts outcomes
- Allow member content to contain political commentary. Apply the same standard as our own copy

**Legal note:** All member-generated content used in marketing must include: *"[Member]'s experience reflects their own research process. 360Investor does not provide investment advice. Past regime calls are not a guarantee of future accuracy."*

Members promoting their work (sharing how they use 360Investor in their own research) is a high-value marketing asset. Guidelines:

- Member spotlights should focus on the **framework and process**, not specific investment results or returns
- Never imply or suggest that following 360Investor analysis guarantees outcomes like the featured member's
- Members sharing work must agree that 360Investor is not responsible for their investment decisions
- Preferred framing: "How [Alex] uses regime intelligence to frame portfolio decisions," not "How [Alex] made 22% returns"
- Member-generated content reflects their views, not 360Investor's

---

---

## Public Copy Standard: Address, Don't Describe

**The rule:** Write every public-facing sentence as if you are talking to one specific person who is nodding along. If the reader would feel *described* rather than *addressed*, rewrite it.

**Test:** Read the sentence aloud. If it uses "the investor," "professional investors," "members who," or any third-person label for the audience, it fails. Rewrite in second person.

| ✗ Describes | ✓ Addresses |
|---|---|
| "Bronze is what most professional investors work from daily." | "Bronze gives you the complete daily read." |
| "For the investor who does their own work." | "If you do your own work, this is the infrastructure you've been missing." |
| "Members who run their own research process." | "If you run your own research process…" |
| "The platform builds trust." | "When the regime shifts, you'll know exactly what changed and why." |

**The persona stays internal.** Alex is a writing tool, not a character to introduce. Never use the name "Alex" in any public-facing copy. The reader is "you."

---

## Public Page IP Protection

Public pages describe **outcomes and provenance only**. They never disclose implementation.

**Safe to publish:**
- Data sources (FRED, FiscalData, CBOE, OECD): provenance builds trust and costs nothing
- What the platform measures (5 dimensions, 4 regimes, 16 cells): framework vocabulary, not recipe
- Design philosophy stated at outcome level ("weights leading indicators more heavily than coincident data")
- Update cadences: operational precision, not IP

**Never publish:**
- Specific weight percentages (e.g. 53% leading, 42% coincident)
- Calibration method names ("piecewise linear", "z-score")
- Specific threshold values used in scoring
- Individual signal formulas or grading algorithms
- The exact series composition of each dimension score

**The gate:** Every methodology question on a public page closes with a pointer to the member Signals page: *"The full methodology is documented in the Signals section inside the platform."* This turns the IP boundary into a conversion driver. Alex who wants the detail has a reason to join.

Use that phrase verbatim. Never describe the contents of the gate: no "including data series definitions," no "including scoring rationale," no table of contents for what's behind it. The gate works because it creates curiosity without satisfying it. Describing what's inside reduces the pull and hands competitors a blueprint.

---

---

## Color Systems (LOCKED)

The four color systems below (Brand, Tier, Regime, Cycle-Stage) are locked. The hex values are canonical and approved. Do not introduce a new shade for any of these meanings, do not re-pick a color when migrating a template, and do not reuse one system's hue to mean something in another. A new color system needs explicit approval added here first. Each system names what a color *means*; a color must mean exactly one thing.

---

## Brand & Platform Color

| Role | Color | Hover |
|---|---|---|
| **Platform blue** (brand) | `#2563eb` | `#1d4ed8` |

The platform blue is the brand and product-chrome color: primary CTAs on public and member surfaces, nav, links, focus rings, and neutral/info accents. Token `--blue` (`#2563eb`) with `--blue-dark` (`#1d4ed8`) for hover, plus `--blue-light #eff6ff` / `--blue-border #bfdbfe` for tints, all in `app.css` (mirrored as raw hex in `app-shell.css`).

**The one hard exclusion:** never use the platform blue on a tier-specific element. Tier identity is carried by the tier color (below), never blue. Blue is also not a regime or cycle-stage color; it reads as "the product," not "this regime / this stage."

---

## Tier Identity & Color Palette

Every tier-specific element (CTA button, card label, tier badge, and comparison table checkmark) uses the canonical tier color. Never use the platform blue (`#2563eb`) on a tier CTA. The color is the identity signal. Source: `pricing.html` (`.cta-*` / `h2.*`).

| Tier | Color | Hover |
|---|---|---|
| **Bronze** | `#92400e` | `#78350f` |
| **Silver** | `#607b8b` | `#4e6472` |
| **Gold** | `#b8860b` | `#9a7009` |
| **Corporate** | `#6d28d9` | `#5b21b6` |

Silver features as the recommended tier. Its card carries a tier-colored border, not blue. Note: the Corporate purple (`#6d28d9`) is close to but distinct from the Financial Repression regime purple (`#7c3aed`); they are different systems and must not be swapped (the old Brief repression chip wrongly used `#6d28d9`, now corrected).

---

## Regime Identity & Color Palette

The four macro regimes carry a fixed identity color. Wherever a regime is shown as a colored token (a Learn chip or dot, a regime-gauge fill, the Brief headline overlay, a pressure chip), it uses its canonical color and no other. The same word never appears in two colors. This is the rule that keeps `/learn`, the Brief gauge strip, and the public sample readings telling one story.

| Regime | Color | Reads as |
|---|---|---|
| **Standard Cycle** | `#16a34a` (green) | The baseline, the calm state |
| **Fiscal Dominance** | `#c2410c` (orange) | Policy-driven pressure |
| **Stagflationary** | `#a16207` (amber) | Supply-side pressure |
| **Financial Repression** | `#7c3aed` (purple) | Negative-real-rate pressure |

**Canonical source.** The values live as design tokens in `intelligence_api/static/css/app.css` (`--tr-rg-standard / -fiscal / -stag / -repression`). The member shell (`base.html`) links `app-shell.css`, not `app.css`, so `learn.html` restates the same values as local `--rg-*` vars. When a member template is migrated off inline styles, it should reference these, not re-pick a shade.

**Rules.**
- **Amber means Stagflationary, not "elevated."** Do not reuse a regime's identity color to signal severity or magnitude elsewhere in the same reading. Severity (a "28% elevated" pill) is a separate language; if it would land on a regime's hue, recolor it to that regime's identity instead (this is why the About sample's Fiscal pressure pill is Fiscal orange, not amber).
- **Color is never the only channel.** The regime name always appears as text, and the color rides on a dot, border, or fill that is decorative (`aria-hidden`). The regime hues are accent colors, not AA-safe text colors: green on white is about 2.8:1. For colored text on a light tint, use a darker variant of the hue, not the token value.
- **Standard Cycle has no gauge.** On the Brief regime-gauge strip, Standard is a residual conveyed by a plain-language state line, not a bar (only Fiscal, Stagflationary, and Financial Repression have fills). Standard's green shows where it is a named label (Learn chips and the Framework cards), not as a pressure reading.

**Not the cycle stages.** The investment-clock cycle stages (Reflation, Recovery, Overheat / Slowdown, Stagflation / Contraction) are a separate taxonomy with their own colors (below). The cycle stage "Stagflation" (red) is not the macro regime "Stagflationary" (amber); do not unify them.

---

## Cycle-Stage Colors (Investment Clock)

The four investment-clock cycle stages carry their own fixed identity hue, separate from the macro regimes. Each stage appears in two forms: a saturated dot (the Learn framework cards, `learn.html` `.lx-dot.s-*`) and a darker text-on-tint pill (the Brief regime-context chips, `brief_home.html` `cl_map`). The hue family is the identity; the dot uses the saturated value and the pill uses an AA-safe darker text on a light tint of the same hue.

| Cycle stage | Hue | Dot (saturated) | Pill text / tint |
|---|---|---|---|
| **Reflation** | blue | `#2563eb` | `#1d4ed8` on `#dbeafe` |
| **Recovery** | green | `#16a34a` | `#15803d` on `#dcfce7` |
| **Overheat / Slowdown** | amber | `#d97706` | `#92400e` on `#fef9c3` |
| **Stagflation / Contraction** | red | `#dc2626` | `#991b1b` on `#fee2e2` |

**Rules.**
- **Stagflation here is red, on purpose.** The cycle stage "Stagflation / Contraction" is red; the macro regime "Stagflationary" is amber (`#a16207`). They are different concepts and stay different colors. Do not "fix" one to match the other.
- **Reflation blue is not the brand blue's job.** Reflation reuses the blue hue as a stage identity; it is still a cycle-stage signal, not a CTA. Context (a dot or stage pill) disambiguates.
- **Distinct from the business-cycle phase position.** The phase dial (Recovery / Expansion / Late Cycle / Slowdown, `brief_home.html` cycle dial + `phase_display`) is a separate axis from the investment-clock quadrants and is not governed by this table; do not conflate the two. Support copy already draws this line (`support.html`).

**The canonical framework for all promotional and tier copy is PAS: Problem, Agitate, Solution.**

Alex's documented primary conversion trigger is reading something that *names a problem they've been feeling but couldn't articulate.* PAS is the only framework whose core mechanism matches that trigger precisely. The other frameworks (AIDA, FAB, Before-After-Bridge, 4Ps) are either too promotional for the Sage archetype or too passive to create urgency for the Ruler.

### Why PAS wins for Alex

| Framework | Why it falls short |
|---|---|
| **AIDA** | Takes the reader on a journey. Alex detects the sales arc and resists it. |
| **FAB** | Reads as a spec sheet. Works as secondary structure inside PAS, not as the lead. |
| **Before-After-Bridge** | Logical and Sage-safe, but passive: it describes the gap without making Alex feel the cost of it. |
| **4Ps** | Proof element is Sage gold, but Promise/Picture/Push reads promotional at the lead. |
| **PAS** | Names the exact pain Alex can't articulate → makes the cost real → delivers a precise, cited solution. Every documented Alex conversion trigger is a PAS story. |

### How to apply PAS for Alex

**Problem.** Name the specific situation Alex recognizes as their own. Not a generic pain. The problem must be citable, precise, and free of hype. Generic: *"Frustrated with your tools?"* Specific: *"The question that sits under every Sunday evening: am I positioned for where the cycle is headed, or where it's been?"*

**Agitate.** Make the cost of the problem real without emotional manipulation. For Alex (Sage), agitation is intellectual: name what they lost or missed by not having the signal. The agitation must survive Alex's four filters. Generic: *"You're leaving money on the table."* Specific: *"The regime had shifted. You found out from price action."*

**Solution.** Deliver the resolution with specificity and provenance. Name the series. Name the cadence. Name the threshold. Generic: *"Get deeper insights."* Specific: *"Five fiscal stress vitals, each scored independently against published thresholds. Same-day Treasury Auction grades: 7Y, 10Y, 30Y."*

### PAS by tier: pain angles

| Tier | Pain to name | Agitation | Solution angle |
|---|---|---|---|
| **Bronze** | Sunday evening uncertainty: positioned for cycle past or cycle ahead? | Most sources report what happened. The regime shifted weeks ago. You found out from price action. | 130+ data series → four regime probabilities + Investment Clock + sector signals + yield curve. Four minutes. No opinion. |
| **Silver** | Fiscal Dominance probability rising: why and by how much? | The data is on FRED. The synthesis isn't. Manual assembly is imprecise and stale. | Five vitals, independently scored, each traceable. Same-day Treasury Auction grades. Five-dimension economic conditions. |
| **Gold** | You read the regime, but you find out about turns from price action, not before. | A turn often starts as the market's own narrative bending the fundamentals. Unstructured reading misses the loop until it is obvious. | Reflexivity Monitor: feedback-loop detection, diverging-signal scoring, historical analogue. See the turn form while it is still forming. |
| **Corporate** | Five people, five sources, five regime reads. Monday reconciles opinions instead of executing on one. | When the regime shifts, the team finds out at different times, from different signals. Not moving together. | Five seats, one systematic read: same regime status, same cycle position, same fiscal stress picture, every morning. |

---

## Copy Never Sounds Like Advice

*Canonical definition of the "never advice" rule. This section and the `copy` skill are the single source of truth; CLAUDE.md, the other skills, and the docs that mention the rule point here rather than restating it. Edit it here.*

360Investor provides signals and probabilities. Alex interprets them. **Copy must never imply we are directing action, positioning portfolios, or making investment calls.** This is both a legal constraint and a brand requirement. Alex does not come to 360Investor for advice. He comes for a rigorous signal. The moment copy sounds like advice, it fails Alex's Sage filters and creates legal exposure.

### The line and how to stay on the right side of it

| ✗ Sounds like advice | ✓ Describes a signal |
|---|---|
| "Sector rotation guidance" | "Sector signals" |
| "Positioning guidance" | "Regime probabilities" |
| "Portfolio positioning" | "Regime alignment" |
| "What to own in this regime" | "Which sectors align with the current regime phase" |
| "When to reduce duration" | "The Treasury Auction Monitor grade for the 30Y" |
| "This regime favors X" | "Historically, this regime phase has correlated with X" |

**The test:** If the sentence tells Alex what to do with money, rewrite it to tell Alex what the signal reads. The platform assembles the picture. Alex decides what to do with it.

**The single approved framing for the platform's role:**
> *"The synthesis is done. Your judgment takes it from here."*

---

## Approved Copy Bank

Locked phrases for recurring contexts. Use verbatim. Do not paraphrase, as each word was chosen precisely.

### The Platform's Role (resolving the synthesis/judgment tension)
> *"The synthesis is done. Your judgment takes it from here."*

Use when describing what the platform does vs. what Alex does. The platform handles assembly; Alex handles thinking and action. This resolves the apparent contradiction between "complete picture, no more research needed" and "for investors who do their own work."

### Independence Statement (footer + methodology page)
> *"Independently operated. No institutional affiliations. No sponsored content. No conflicts of interest."*

### Methodology Provenance (About page, design philosophy section)
> *"The signal classification framework draws on strategic foresight methodology, specifically the STEEP signal taxonomy and PPP probability weighting used in academic futures research, applied to financial regime analysis."*

**How to use:** Cite the framework lineage, not the biography. Reference STEEP and PPP by name: these are verifiable academic frameworks Alex can look up. Never write "built by a futurist at [institution]." Write the methodology implication. Alex verifies frameworks, not CVs.

### Scorecard Disclaimer (all pages showing company grades)
> *"Company scorecards reflect systematic analytical grading: financial health, technical signals, and regime alignment. 360Investor does not provide investment advice or buy/sell recommendations."*

---

## Company Scorecard (Planned Feature)

Company scorecards will grade individual companies against financial health, technical signals, investment style fit, and regime alignment. The key framing distinction: scorecards are analytical grades, not recommendations.

**Write:**
- "[Company] scores A– for regime alignment in the current Slowdown phase"
- "[Company] grades B for value-style fit: financial health strong, momentum weak"

**Never write:**
- "We recommend [company]"
- "[Company] is a buy in the current regime"
- Any language implying buy/sell/hold action

The "no positions on individual securities" disclaimer is retired the moment scorecards launch. It is replaced by the Scorecard Disclaimer above, which accurately describes what the platform does (grades) vs. what it does not do (advise).

---

## About Page Policy

**Do not build a traditional About/Team page.**

Alex converts on methodology, not biography. A founder bio signals Substack (one person's opinion) rather than the institutional rigor the platform claims. It is counterproductive to the positioning.

What Alex actually needs to trust the platform:
- **Is it a real company?** → The 360 Investor LLC, Wyoming LLC, in Terms of Service
- **Is the methodology sound?** → Methodology page (`/about`) + member Signals section
- **Is there accountability?** → Contact form
- **Is it independent?** → Independence statement in the footer

**If a credential is worth citing**, work it into the methodology page as a single sentence of intellectual provenance: how it shaped the framework, not who holds it. One sentence. Not biography. Not LinkedIn. Not a page.

---

*Last updated: 2026-05-29. Alex persona locked; Before & After voice examples added; UI copy standards added; tier descriptions rewritten for Alex; member-generated content reframed.*
*Updated: 2026-05-30. CTA language locked; Address Don't Describe rule; IP Protection policy; Tier color palette; Approved Copy Bank; Scorecard framing; About Page policy. Second update 2026-05-30: "central bank" → "The Federal Reserve" added to prohibited terms; Treasury Auction capitalization rule; no investment decision-making language; IP gate copy precision rule (never describe gate contents); member-only features never linked on public pages; support page contact scoping pattern; Firm self-serve routing rule.*
*Updated: 2026-05-31. "Firm" tier renamed to "Corporate" throughout (display name only; database value `firm` unchanged); CTA updated from "Put your firm ahead" to "Own the edge"; PAS established as canonical copywriting framework with full tier-by-tier pain matrix; "Copy Never Sounds Like Advice" section added; "sector rotation guidance" → "sector signals" in prohibited terms and Bronze tier description; all tier card copy rewritten to PAS standard.*
*Updated: 2026-06-01. "Experts We Draw On" section added after Voice & Tone: seven domain authorities (Mossberg, Tufte, Norman, Krug, Marks, Ogilvy, Tetlock), one per domain. Ogilvy scoped to copywriting + UI copy; Norman/Krug retain interaction usability. Em-dash ban clarified as applying everywhere, not just member-facing copy.*
*Updated: 2026-06-01 (em-dash sweep). All em-dashes removed from this guide except the deliberate bad-examples in the Prohibited Punctuation table. Two Approved Copy Bank entries (Methodology Provenance, Scorecard Disclaimer) reworded to drop em-dashes; meaning preserved.*
*Updated: 2026-06-01 (experts expanded to nine). Copywriting domain adds Eugene Schwartz + Joanna Wiebe alongside Ogilvy; macro framing adds Ray Dalio alongside Howard Marks. Same domains, more depth. Enforcement added: CLAUDE.md binding rule + PostToolUse style-lint hook + CI (scripts/style_lint.py).*
*Updated: 2026-06-01 (CIO / Portfolio Adviser roster added). Third sibling roster after Economists: 7 investors (Templeton contrarian global value, Neff low-multiple value, Soros reflexivity/macro, Buffett quality compounding, Lynch bottom-up growth, Englander multi-strat risk control, Druckenmiller top-down macro conviction). Owns positioning/sizing/risk, not advice. Full interpretation chain documented: economists (meaning) → CIO roster (positioning) → Tetlock (probability) → Marks/Dalio (voice) → design roster (presentation).*
*Updated: 2026-06-01 (Economists roster added). New "Economists / Macro Thinkers We Draw On" section after the design roster: 9 academic/policy economists (Bernanke, Rogoff, Krugman, Acemoglu, Heckman, Blundell, Tirole, Shleifer, French) for structural interpretation + 6 house/field economists (Baig, Casanova, Holmes, Liu, Nestor, Fennessy) for real-time regional reads. One owner per domain; tie-break order set (field reads near-term, academics read structural, Tetlock states probability, Marks/Dalio voice it). Recreates a guidance doc that was lost.*
*Updated: 2026-06-01 (Ive added). Jony Ive joins the roster under a new "Product design / simplicity & craft" domain (reduce to essential, then obsess over finish; cohesion of the whole product). Now ten experts across eight domains. Boundary set against Tufte (reduction within a single display) and Krug/Tufte (clarity wins over polish when reduction would hide a fact).*
*Updated: 2026-06-01 (terminology). "Intelligence Brief" confirmed as the member home name (over "Insights" / "Insights Brief", rejected as hollow per the nine-expert poll). "Regime Read" added as an owned term: the named synthesis subreport at the top of the Brief, capitalized as an instrument. "insights" added to the style linter.*
*Updated: 2026-06-09 (Economists roster: foundational canon added). New "Foundational theorists (the classical canon)" subsection at the top of the Economists roster: 8 foundational thinkers (Smith invisible-hand price discovery, Ricardo comparative advantage, Keynes demand management, Hayek prices-as-knowledge / intervention risk, Friedman monetarism, Marshall supply-demand / marginal analysis, Samuelson mathematical synthesis, von Neumann game theory). They own first principles, not live signals; the academic and field economists still own the structural and near-term reads. Tie-break order updated to lead with first principles. Names never cited in member-facing copy.*
*Updated: 2026-06-10 (Schelling added to academic economists). Thomas Schelling joins under a new "Coordination, focal points & credible commitment" domain: the applied layer over von Neumann's game-theory first principle. Owns the strategic design of the network-effect and retention work (the Brief as a shared reference point coordinated around without a social graph; the Predictions Ledger as a credible commitment to keep score; truthful-revelation design of aggregated member signals). Name never cited in member-facing copy. See `docs/strategy/MARKETING_JOURNAL.md` for the brainstorm this came from.*

*See also: `docs/strategy/MARKETING_JOURNAL.md` (live ideas capture), `docs/strategy/COMPETITIVE_POSITIONING.md` (competitive framing), `docs/strategy/VISION.md` (product vision)*
