"""encounter_budget — XP budgets per SRD 5.2.1 p.202; honest refusal for 2014.

SRD 5.1 never contained encounter-building tables, so under the provenance
policy there is no freely-licensed 5e-2014 budget math. The refusal names that
reason — 'not silently helpful' is doc law (MECHANUS.md §8).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from . import tables

DIFFICULTIES = ("low", "moderate", "high")


class LawUnavailable(Exception):
    """A correct refusal: the law exists, but not in a source we may compute from."""


def encounter_budget(party_levels: list[int], difficulty: str, view: str = "5e-2024") -> dict[str, Any]:
    """Total XP budget for a party (list of character levels) at a difficulty."""
    d = difficulty.strip().lower()
    if d not in DIFFICULTIES:
        raise ValueError(f"difficulty must be one of {DIFFICULTIES}, got {difficulty!r}")
    if view != "5e-2024":
        raise LawUnavailable(
            f"no freely-licensed encounter math for {view}: SRD 5.1 contains no "
            "encounter-building tables (2014 budgets are DMG content). Options: use "
            "view='5e-2024' (SRD 5.2.1 p.202), or wait for PAitM-local tables once poured."
        )
    if not party_levels or not all(isinstance(lv, int) and 1 <= lv <= 20 for lv in party_levels):
        raise ValueError("party_levels must be ints in 1..20")

    per = [(lv, tables.xp_budget_per_character(lv, d)) for lv in party_levels]
    return {
        "view": view,
        "difficulty": d,
        "party": dict(Counter(party_levels)),
        "per_character": [{"level": lv, "xp": xp} for lv, xp in per],
        "budget": sum(xp for _, xp in per),
        "source": tables.budget_source(view),
        "law_version": tables.law_version(),
        "spend_note": "deduct each creature's XP (stat block value) from the budget; "
                      "going slightly under is fine, going over is not (SRD 5.2.1 p.202 step 3)",
    }
