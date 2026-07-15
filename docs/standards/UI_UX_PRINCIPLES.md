# 360Investor: UI/UX Operating Principles

The design team, distilled into checkable rules. This exists so we stop asking "what would the team think?" for every decision and instead run the decision against a fixed standard. It is the UI/UX counterpart to `docs/standards/MARKETING_STYLE_GUIDE.md` (which owns copy): the style guide governs the words, this governs how a screen looks, behaves, and is structured.

**Authority.** This document is binding for any template, component, page, gauge, chart, or flow. It draws the design-and-words owners out of the style guide's "Experts We Draw On" roster (the four design owners, the voice owner, and the copywriting owners) and turns each one's body of work into operating principles you can hold a design decision against. The names are internal standards only and are never cited in member-facing copy.

**Scope.** This is the design-reasoning layer: whether an element should exist, how it should behave, how it should look, and what its strings should say. It covers UI copy (labels, buttons, empty states, errors, status lines) because those are design decisions; it does not cover marketing and sales pages, which are owned by `copywriting-craft` and the `copy` skill. The mechanical floor lives elsewhere and is assumed: the `design-system` skill owns the CSS/macros/tokens system, `scripts/html_audit.py` checks the statically decidable accessibility rules, and the visual-regression suite (`intelligence_api/tests/visual`) guards locked surfaces. A green audit is the floor, not proof of good design; that judgement is what this document is for.

---

## How to use this (the protocol)

Run every non-trivial UI/UX decision through three questions, in order:

1. **Should this element exist at all?** (Krug and Norman own this. Default is no.)
2. **Does it behave so the member never has to guess?** (Norman owns state, feedback, and error prevention.)
3. **Is it reduced to the essential and finished with care, and do its words land?** (Tufte owns density inside one display; Ive owns cohesion across the whole product; Mossberg owns whether the words read plainly; Ogilvy, Schwartz, and Wiebe own whether a string actually persuades and uses the member's own language.)

When two owners disagree, use the tie-break order at the bottom. The short version: **clarity beats polish, and a hidden fact beats a clean layout.**

The member you are designing for is Alex: a smart, busy, skeptical non-specialist who is time-poor and will not work to understand a screen. Every principle below assumes that reader.

---

## The house principle: always give context and directionality

This is the one principle that sits above the others, because it is what the product is for. Every other rule here serves it.

**Never show a member a number, signal, or status on its own. Always pair it with context and directionality.**

- **Context** answers "compared to what?" A reading means nothing in isolation; it means something against its own history, against what was expected, or against its peers. (This is Tufte's principle #7 made universal: there the rule governs a single data display, here it governs every surface.)
- **Directionality** answers "which way, and so what?" The member needs to know whether the thing is rising or falling, whether that is the good or the bad direction, and what it implies for the read. A flat snapshot with no vector forces Alex to do the analysis we exist to do for him.

Why it is the house principle: Alex is time-poor and skeptical, and the product's entire promise is synthesis, not a data dump. A bare number hands the work back to the member and breaks that promise. Context and directionality are how a number becomes a signal.

It binds every surface, not just charts:

- A **gauge** shows where the reading sits on its scale (context) and which way it moved (directionality), never a lone dial.
- A **Brief card** or scorecard leads with the comparison and the move, not the raw value (the "show comparison" rule, and the verdict-first scoreboard pattern).
- A **written read** states which way the evidence points and what it implies, never a list of figures (owned in prose by the `analytical-writing` skill's synthesis-over-data-dump rule).

This is a judgment rule with no gate (no linter can catch a missing comparison), so the discipline is the checklist below.

**Fails the house principle:** a single big number with no history or expectation beside it; a status that says where things are but not where they are heading; a gauge reading with no prior value; a Brief paragraph that lists data without saying which way it points.

---

## Don Norman: the product never makes Alex guess

Owner of *interaction usability, state, and error prevention.* From *The Design of Everyday Things.* Norman's core claim: when a person struggles with a thing, the fault is the design's, not the person's. Apply that to every interaction we ship.

1. **Affordance and signifier.** An element must look like what it does. A control that is clickable must signal it (a real `<button>`, a cursor, a hover state); a thing that is not interactive must not look like it is. No clickable `<div>` dressed as text, no static label that begs to be tapped.
2. **Visibility of system state.** The member should always know what state the product is in without asking. Loading, stale data, "gathering data," computed-vs-placeholder, last-updated time: show it. Our gauges and Brief must declare when a number is real, when it is a placeholder, and when it is still filling in (the null-momentum "gathering data" state is this principle in practice).
3. **Mapping.** The relationship between a control and its effect should be natural. A slider that moves right means more; a gauge that fills clockwise means higher. Do not invert a convention to be clever.
4. **Feedback.** Every action gets an immediate, legible response. A click that does nothing visible is a defect. If something takes time, show that it is working.
5. **Constraints (make the wrong action impossible).** Prevent the error rather than explain it after. Disable what cannot be done, validate before submit, and remove paths that lead nowhere. The best error message is the one the design made unreachable.
6. **Good error recovery.** When an error does happen, the message says what happened, why, and the way out, in plain language. No dead ends, no blame, no codes the member cannot act on.
7. **Conceptual model.** The product should teach Alex a single coherent mental model of how it works, and then never violate it. A regime means the same thing on every surface; a color means one thing everywhere (see the LOCKED color systems). Consistency is how the model stays intact.

**Fails the Norman test:** a status with no last-updated time; a placeholder number that looks identical to a real one; an icon-only control with no `aria-label`; a form that only tells you the field was required after you submit.

---

## Steve Krug: don't make Alex think

Owner of *information architecture, clarity, and cognitive friction.* From *Don't Make Me Think.* Krug's first law of usability: a page should be self-evident; the member should never have to spend attention working out what something is or how to use it.

1. **Don't make me think.** Every question the member has to stop and answer ("Is this clickable? Where am I? What does this number mean?") is friction. Remove the question, do not answer it in a tooltip.
2. **We don't read pages, we scan them.** Design for scanning: clear visual hierarchy, meaningful headings, short chunks, the important thing biggest and first. Alex is skimming for the signal, not studying.
3. **Omit needless words, then omit half of what's left.** Krug's "Get rid of half the words on each page, then get rid of half of what's left." Instructional and happy-talk copy is friction. Cut it.
4. **Conventions are your friend.** Use the patterns members already know (a logo links home, a magnifier means search) unless you can do measurably better. Novelty is a cost the member pays.
5. **Each fact appears exactly once.** No redundancy. A number, a status, or a label stated twice forces the member to reconcile the two. One source of truth per screen (this is the redundancy rule in the style guide's UI Copy Standards).
6. **Obvious is better than clever.** If a thing needs an explanation to be understood, redesign the thing. Self-evident first; if you cannot reach self-evident, settle for self-explanatory; never settle for "they'll figure it out."
7. **The trunk test (you always know where you are).** On any screen the member can tell what site this is, what page they are on, and how to get to the main sections. Persistent, consistent navigation.

**Fails the Krug test:** a feature that needs a paragraph of instructions to use; the same fact shown in two places with different framing; a custom control where a standard one would do; a screen where you cannot tell at a glance what matters most.

---

## Edward Tufte: maximize the data, eliminate the decoration

Owner of *data display: gauges, charts, scorecards, the regime matrix.* From *The Visual Display of Quantitative Information* and *Envisioning Information.* Tufte governs density and integrity inside a single data display.

1. **Above all else, show the data.** The data is the point; everything else is in service of it or in the way. Maximize the data-ink ratio: the share of a display's ink that conveys actual information.
2. **Erase chartjunk.** Remove anything that does not carry data: gratuitous gridlines, 3D effects, heavy borders, gradients, drop shadows, redundant legends, decorative color. Our gauges and scorecards show data, not ornament.
3. **Graphical integrity.** The visual must not lie. The representation of numbers should be directly proportional to the numbers; do not truncate an axis to exaggerate a move, do not rescale a dial to dramatize a reading (this is why the regime dial is not rescaled). The "Lie Factor" should be 1.
4. **Maximize data density (within reason).** A small space can carry a lot of well-organized information. Sparklines and compact scorecards beat a giant chart that says one thing. Respect the member's screen and attention.
5. **Small multiples.** To compare across categories or time, repeat one well-designed frame at small size rather than inventing a new chart per case. Same encoding, repeated, so the eye compares effortlessly.
6. **Color and layering with restraint.** Use color to encode meaning, never to decorate. Each hue means exactly one thing (see the LOCKED color systems: brand blue, tier, regime, cycle-stage). Color is never the only channel for a fact (pair it with text or shape), both for integrity and for accessibility.
7. **Show comparison, causality, and context.** A number alone is weak; a number against its history, its expectation, or its peers is a signal. "How the numbers came in" (surprise vs expected) is this principle: the comparison is the content.

**Fails the Tufte test:** a gauge with a gradient and a drop shadow; an axis that starts at a non-zero value to make a move look bigger; a chart that uses three colors where one would do; a single big number with no comparison or history.

---

## Jony Ive: reduce to the essential, then obsess over the finish

Owner of *whole-product cohesion, simplicity, and craft.* From Apple's design philosophy (Ive's interviews and design talks). Where Tufte reduces within one display, Ive reduces across the entire product: how the pages, components, and details hang together as one considered thing.

1. **Simplicity is not the absence of clutter; it is order.** True simplicity comes from understanding the essence of a thing deeply enough to make it feel inevitable, not from stripping features off the surface. Ask what this screen is fundamentally for, then let that govern everything on it.
2. **Reduce, then refine.** First remove everything inessential. Then spend disproportionate care on what remains: spacing, alignment, rhythm, the exact weight of a border. The finish is where craft lives.
3. **Cohesion of the whole.** Every component should feel like it belongs to the same product. Shared tokens, consistent spacing scale, one type system, one set of component macros. Nothing arbitrary, nothing one-off that breaks the family resemblance (this is why styling lives in one stylesheet and components in one macro file).
4. **Care in the unseen details.** The quality of the parts a member never consciously notices (the empty state, the hover, the focus ring, the loading moment) is what makes the whole feel trustworthy. Design the boring states with the same care as the hero.
5. **Deference: the product serves the content.** The interface should step back so the signal is the star. Chrome, controls, and decoration defer to the data and the read. For us the Brief is the product; the frame around it should disappear.
6. **Material honesty.** Do not fake what a thing is. A placeholder looks like a placeholder, a real reading looks real, a static value does not pretend to be live. Honesty in the interface is honesty in the product.
7. **Restraint as the default.** When in doubt, leave it out. Every added element, color, or animation must earn its place against the cohesion of the whole. The bar for adding is high.

**Fails the Ive test:** a new page that invents its own spacing and colors instead of using the system; a polished hero above a neglected empty state; an animation that draws attention to the chrome instead of the data; a one-off component that exists nowhere else.

---

## Walt Mossberg: explain it plainly, never talk down, never hedge

Owner of *the voice on every screen: labels, microcopy, status lines, explanations.* From three decades of technology reviews written for smart non-technical readers. Mossberg's governing rule: the burden is on the product to be clear, never on the person to be technical.

1. **Explain complex things to a smart non-specialist.** Alex is intelligent but not a macro economist. Write every label and explanation so a sharp outsider gets it on first read, without a glossary.
2. **Never talk down.** Plain does not mean dumbed-down. Respect the reader's intelligence; simplify the language, never the substance.
3. **Never hide behind jargon.** No insider vocabulary where a plain word exists. The forbidden-jargon list in the style guide is this principle made mechanical, but the rule is broader than the list: if a member would have to look it up, pair it or replace it.
4. **Never hedge what is actually known.** State what we know plainly. Calibrated uncertainty is honest (that is Tetlock's lane); vague hedging to cover ourselves is not. Say the real thing.
5. **The burden of clarity is on us.** If the member is confused, the screen failed, not the member. This is Mossberg and Norman agreeing from two directions: fix the design, do not write a help doc to paper over it.
6. **Specific and concrete beats abstract.** A real number, a real date, a real comparison earns trust. Mossberg reviewed by showing exactly what happened; our copy should show exactly what the data did.
7. **Microcopy is product.** Button labels, empty states, error messages, and status lines are not afterthoughts; they are where the member meets the product most often. Write them with the same care as the headline. (Construction of these strings is owned by the `copy` skill; this is the standard they meet.)

**Fails the Mossberg test:** a label using a term from the jargon blacklist; an explanation that assumes the reader knows what a series is; a hedge ("results may vary") where a plain calibrated statement was available; an empty state that says "No data" instead of what is happening and what to do.

---

## Ogilvy, Schwartz, Wiebe: the UI-copy strings that carry their weight

Owner of *what a string actually says: labels, buttons, empty states, errors, status lines, microcopy.* Three authorities, one domain. Mossberg (above) governs whether a string reads plainly; these three govern whether it does its job. Their full reach is promotional and sales copy, owned by `copywriting-craft` and `copy`; the slice that is UI is owned here, because a button label is a design decision. The strings themselves are constructed by the `copy` skill and must pass its binding voice, vocabulary, advice-tone, and IP rules; this section is the standard those UI strings meet.

**David Ogilvy: research-led, specific, no hype.**

1. **The reader is not a moron.** "The consumer isn't a moron, she is your wife." Write up to Alex, never down. No hype, no exclamation marks doing the work that substance should do.
2. **Specific beats vague.** A concrete number, date, or fact outsells an adjective. "130+ public data series" earns trust; "comprehensive coverage" does not. Every UI string should prefer the specific true thing. **Corollary, single source of truth:** a fact that shows on more than one surface (a count, a price, a tier name) must be computed or stored in one place and pulled, never re-typed per page, or the copies drift and one becomes a lie. The data-series count lives in `provenance.py` (`series_phrase()`); templates pull it, no surface hardcodes a number.
3. **Clarity over cleverness.** A clever label that the member has to decode has failed. If a witty button and a clear button compete, the clear one ships.

**Eugene Schwartz: meet the reader where they are.**

4. **Awareness stage.** Match the string to what the member already knows. A first-time visitor at a CTA needs a different label than a member deep in the Brief who already understands the product. Do not explain what they know; do not assume what they do not.
5. **Sophistication stage.** The more claims a skeptical Sage has heard, the less a bare claim lands. Lead with the mechanism or the proof, not the boast. On a button or empty state, that means pointing at the real thing the member gets, not at how good it is.
6. **You cannot create desire, only channel it.** Microcopy connects to a want the member already has (clarity, an edge, not being fooled). A label that names that want beats one that announces a feature.

**Joanna Wiebe: use the member's own words.**

7. **Voice of customer.** The best UI string is often one the member would have said. Use their phrasing for the action and the value, not internal product language. "See what changed this week" beats "View delta report."
8. **Specificity converts.** Concrete, testable language outperforms abstraction at the point of action. An empty state or CTA that says exactly what happens next reduces the hesitation that kills the click.
9. **One string, one job.** A button, an empty state, or an error has a single purpose; do not load it with two. Clarity at the moment of action is the whole game.

**Fails the Ogilvy/Schwartz/Wiebe test:** a CTA that hypes instead of saying what happens ("Unlock the power of macro!"); a label in internal product language the member would never use; a button that assumes an awareness stage the member is not at; an empty state that boasts instead of telling the member what to do next.

---

## When experts disagree: the tie-break order

Lifted from the style guide's arbitration rule so the two documents never conflict.

- **Krug and Norman govern whether an element should exist and how it behaves. Ive and Tufte govern how it looks. Ogilvy, Schwartz, and Wiebe govern what a string says. Mossberg governs how plainly it reads.** That ordering is also roughly the order of authority: a beautiful, well-worded control that adds friction or hides state loses to removing it.
- **Clarity wins.** When any two owners touch the same string (Ogilvy on a button label, Krug on whether it adds friction at all), the more legible option wins. Polish and persuasion never beat comprehension.
- **A hidden fact beats a clean layout.** When reduction (Ive or Tufte) would hide information the member needs, Krug and Tufte's integrity rule win over polish. Show the fact.
- **Ive vs Tufte is a question of scale, not a conflict.** Tufte owns restraint *inside* one display (data-ink in a single gauge); Ive owns restraint *across* the whole product (how the pages cohere). They are reducing at different altitudes; apply both.
- **Mossberg and Norman are the same rule from two sides:** the burden of clarity is on the design, never on the member. If they ever seem to disagree, you have misread one of them.

---

## The one-screen decision checklist

Run any UI/UX decision against this. If you cannot answer yes (or "n/a") to all, stop and fix it.

**House principle (cross-cutting)**
- [ ] Does every number, signal, or status carry context (against history, expectation, or peers) and directionality (which way it is heading and what that implies)?

**Exist and behave (Krug, Norman)**
- [ ] Does this element earn its place, or can it be removed? (Default: remove.)
- [ ] Is it self-evident without instructions or a tooltip?
- [ ] Can the member always tell what state the product is in (loading, stale, placeholder, live)?
- [ ] Does every action give immediate, legible feedback?
- [ ] Is the wrong action prevented rather than explained after the fact?
- [ ] Does each fact appear exactly once on the screen?

**Look and cohere (Tufte, Ive)**
- [ ] Is the data the star, with decoration (chartjunk) removed?
- [ ] Is the visual proportional to the numbers (no truncated axes, no rescaled dial)?
- [ ] Does color encode meaning only, with text/shape as a second channel?
- [ ] Does this use the existing tokens, classes, and macros (no one-off styling)?
- [ ] Are the unglamorous states (empty, error, hover, focus, loading) finished with care?

**Read and persuade (Mossberg, Ogilvy/Schwartz/Wiebe)**
- [ ] Would a smart non-specialist understand every label on first read?
- [ ] Is there any jargon a member would have to look up?
- [ ] Does it state what we know plainly, without vague hedging?
- [ ] Is each UI string specific and concrete, not hype or boast?
- [ ] Is it pitched at the member's actual awareness stage (not over- or under-explaining)?
- [ ] Does a CTA/empty state say what happens next, in the member's own words?
- [ ] Does each string pass the `copy` skill's voice/vocabulary/advice-tone/IP gate?

**Floor (assumed, verify separately)**
- [ ] WCAG 2.1 AA: contrast, visible focus, keyboard operability, reduced-motion.
- [ ] Responsive and fluid (verified by resizing, not a parser).
- [ ] `scripts/html_audit.py` clean; locked surfaces pixel-identical (`tests/visual`).

---

## Visual fundamentals: type, space, color, radius, motion

Typography, spacing, color, and radius have no single owner in the roster (Tufte governs data displays, Ive governs whole-product cohesion, but neither hands you a scale). So these are governed by a **shared token system**, and the discipline is uniformity: one source, one minimal scale, applied everywhere. Tokens-first is the rule here. A value belongs in the token file, not inline in a component.

**Single source of truth: `intelligence_api/static/css/tokens.css`.** Both shells link it before their own stylesheet (`public_base.html` then `app.css`; `base.html` then `app-shell.css`), so the public marketing site and the member console draw color, spacing, type, and radius from one place. There is no second token file and no per-page redefinition.

**The minimal scales (the house standard for all new UI):**

- **Color.** Brand (`--navy --slate --blue --blue-dark --blue-light --blue-border`) plus a neutral ramp named by role, not shade (`--text --text-soft --text-label --muted-strong --muted --muted-soft --line --field-border --border --bg-2 --bg --white`). Each value lives once. Semantic status colors (badge green/red/amber, focus ring) are deliberately not yet tokenized; tokenize them as a set when that pass is taken, not one at a time.
- **Spacing.** A 4px base, index = px / 4: `--sp-1` (4px) through `--sp-20` (80px). Reach for the nearest step; do not invent `17px`.
- **Type.** A minimal ladder `--fs-10 … --fs-28` plus `--fs-display` (a fluid `clamp`). This is for chrome, console, and marketing UI.
- **Radius.** `--radius-sm --radius --radius-md --radius-lg --radius-pill`.

**The rule, enforced.** When a color, space, or size has a token, use the token, never the raw value. `scripts/style_lint.py` carries a non-blocking advisory that fires when a CSS value or inline style uses a raw hex that exactly equals a token (`#2563eb -> var(--blue)`), so new work is nudged onto the shared source while the remaining legacy raw values do not block. Minimalism is the discipline: the scale is deliberately small; widen it only with a reason, never with a one-off.

**The one locked exception: the Brief.** The Today's Read / Intelligence Brief editorial type is a bespoke, hand-tuned scale (the `--tr-*` tokens in `app.css`), intentionally finer than `--fs-*`, the way a newspaper sets type. It is LOCKED and is not snapped onto the minimal ladder. This is craft, not sprawl: Tufte and Ive both defend fine editorial typography on the flagship reading surface. Do not coarsen it without explicit approval.

**Motion.** Minimal by default, and chrome defers to content (Ive). The floor is binding: honor `prefers-reduced-motion` (already handled globally in `app-shell.css`). Animation that draws attention to the interface rather than the data fails the Ive test above.

The mechanical how (which file, which macro, the accessibility floor) is owned by the `design-system` skill; this section owns the *why* and the *standard*.

## Where this sits

- **Writing the actual strings** (and the binding voice/vocabulary/advice-tone/IP gate they pass): `copy` skill + `docs/standards/MARKETING_STYLE_GUIDE.md`. This document sets the UI-copy standard; the `copy` skill constructs and validates the words.
- **Marketing and sales copy** (hero sections, landing/pricing pages, email): `copywriting-craft` + `copy`. Ogilvy/Schwartz/Wiebe reach there too; this doc only holds the UI-copy slice.
- **The mechanical system** (CSS, tokens, macros, components): `design-system` skill.
- **Evaluating an existing surface** against these principles: `ux-review` skill.
- **The remaining roster experts** (Marks/Dalio on macro framing; Tetlock on calibration): `docs/standards/MARKETING_STYLE_GUIDE.md`, "Experts We Draw On." They own analysis, not UI/UX, so they are pointers here, not principles.

*Source roster: `docs/standards/MARKETING_STYLE_GUIDE.md`, "Experts We Draw On." This document distills the design-and-words owners (Norman, Krug, Tufte, Ive, Mossberg, and Ogilvy/Schwartz/Wiebe for UI copy) into operating principles. The macro-framing and calibration domains in that roster govern analysis and are out of scope here.*
</content>
</invoke>
