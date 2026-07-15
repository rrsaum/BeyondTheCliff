#!/usr/bin/env python3
"""Beyond the Cliff style linter: one hard, universally-applicable house rule plus
two brand-specific advisories. Ported (deliberately lean) from 360Investor's and
QuantSage's style_lint.py, with the finance-specific rules dropped.

Beyond the Cliff is an authority/foresight brand: its readers are the presidents,
provosts, CFOs, and boards of tuition-dependent institutions. The copy has to read
as "I see what is coming and I know the way through," never as a death-watch. Two
things quietly undermine that positioning, so they are checked here:

  HARD  no typographic em-dash (U+2014). Split the sentence, or use a colon, comma,
        or parentheses. Hyphens and en-dashes in numeric ranges are fine. (exit 1)

  ADVISORY  hollow buzzwords that read as marketing filler and cost an analyst
            credibility ("world-class", "cutting-edge", "game-changer", ...). Flag,
            never block: some are legitimate in quotes or proper names.

  ADVISORY  death-watch / schadenfreude tone in reader-facing copy ("doomed",
            "death spiral", "apocalypse", ...). The brand points PAST the cliff; it
            never runs a funeral watch on the schools it wants as clients. Flag for
            a human to judge, since some terms are legitimate when sourced/quoted.

Usage: python3 scripts/style_lint.py <file> [<file> ...]
Prints advisories (non-blocking) then hard violations. Exits 1 only on a hard rule.
"""

from __future__ import annotations

import sys

EM_DASH = chr(0x2014)  # built via chr() so the banned char never appears in this file

# Files where text rules apply. Binaries and data dumps are skipped.
TEXT_SUFFIXES = (
    ".py", ".md", ".html", ".jinja", ".j2", ".css", ".sql",
    ".sh", ".toml", ".txt", ".yml", ".yaml", ".cfg", ".ini", ".js", ".ts", ".jsx", ".tsx",
)
# Reader-facing surfaces where tone/jargon advisories apply. Code and config are exempt
# so identifiers and comments do not false-positive.
COPY_SUFFIXES = (".html", ".jinja", ".j2", ".md")

# This file names the banned terms to document the rules; exempt it from the tone/jargon
# advisories (the em-dash check already never fires here because chr() hides the glyph).
SELF = "style_lint.py"
# Inherited studio docs that carry em-dashes as illustrative or legacy content. The
# style guide shows them as examples of what to avoid; the audit template predates the
# rule. Exempt from the em-dash hard rule (as 360Investor's linter exempts the same two),
# so editing them does not block the gate. Authored copy elsewhere still complies.
EM_DASH_EXEMPT = {"MARKETING_STYLE_GUIDE.md", "AUDIT_TEMPLATE.md"}
# Rule-documenting files legitimately quote the banned terms as examples of what to avoid,
# so the tone/jargon advisories are muted for them (the em-dash hard rule still applies).
COPY_EXEMPT_NAMES = {SELF, "MARKETING_STYLE_GUIDE.md", "CLAUDE.md"}

# Hollow buzzwords: marketing filler that reads as un-sourced hype and costs an analyst
# authority. Fix by naming the specific thing. Low-false-positive list only.
HOLLOW_JARGON = (
    "world-class", "best-in-class", "cutting-edge", "cutting edge", "game-changer",
    "game changer", "game-changing", "revolutionary", "paradigm shift", "synergy",
    "synergies", "thought leader", "thought leadership", "seamless", "turnkey",
    "next-generation", "next generation", "leverage our", "unlock value",
    "move the needle", "boil the ocean", "low-hanging fruit", "circle back",
    "ai-powered", "ai-driven", "disrupt the", "disruptive innovation",
)

# Death-watch / schadenfreude tone. The naming strategy is explicit: schools do not
# hire the analyst running "College Death Watch." Flag grim framing in reader-facing
# copy so it can be reframed toward the way through.
DEATHWATCH_TONE = (
    "death spiral", "death watch", "doomed", "apocalypse", "apocalyptic",
    "meltdown", "carnage", "bloodbath", "extinction", "the end of college",
    "colleges are dying", "higher ed is dying", "collapse of higher",
)


def lint_file(path: str) -> tuple[list[str], list[str]]:
    """Return (hard_violations, advisories) for one file."""
    hard: list[str] = []
    advisory: list[str] = []
    if not path.endswith(TEXT_SUFFIXES):
        return hard, advisory
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError):
        return hard, advisory

    name = path.rsplit("/", 1)[-1]
    is_copy = path.endswith(COPY_SUFFIXES) and name not in COPY_EXEMPT_NAMES
    check_emdash = name != SELF and name not in EM_DASH_EXEMPT
    for n, line in enumerate(lines, 1):
        if check_emdash and EM_DASH in line:
            hard.append(
                f"{path}:{n}: em-dash (U+2014) is banned; use a colon, comma, "
                "parentheses, or split the sentence"
            )
        if is_copy:
            low = line.lower()
            for phrase in HOLLOW_JARGON:
                if phrase in low:
                    advisory.append(
                        f"{path}:{n}: hollow buzzword '{phrase}'; name the specific "
                        "thing instead (authority comes from precision, not hype)"
                    )
            for phrase in DEATHWATCH_TONE:
                if phrase in low:
                    advisory.append(
                        f"{path}:{n}: death-watch tone '{phrase}'; the brand points "
                        "past the cliff, it does not run a funeral watch (reframe, or "
                        "keep only if sourced/quoted)"
                    )
    return hard, advisory


def main(argv: list[str]) -> int:
    hard_all: list[str] = []
    advisory_all: list[str] = []
    for path in argv:
        hard, advisory = lint_file(path)
        hard_all.extend(hard)
        advisory_all.extend(advisory)
    for msg in advisory_all:
        print(f"[advisory] {msg}")
    for msg in hard_all:
        print(f"[style] {msg}")
    if hard_all:
        print(f"\n{len(hard_all)} hard style violation(s).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
