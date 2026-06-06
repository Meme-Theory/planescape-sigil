"""Law tables — typed accessors over data/law/*.json.

Every table is extracted from a cited page of a source we hold (SRD 5.1,
SRD 5.2.1, For Gold & Glory) and cross-witnessed where a second transcription
exists. The JSON files carry their own _source/_witness_notes; this module
only loads, parses, and answers. law_version() content-addresses the whole
data directory so dockets can pin the law they ruled under.
"""

from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any

LAW_DIR = Path(__file__).resolve().parent / "data" / "law"

VIEWS_5E = ("5e-2014", "5e-2024")


@lru_cache(maxsize=None)
def _load(name: str) -> dict[str, Any]:
    return json.loads((LAW_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def law_version() -> str:
    """sha256 over every law file, sorted — the conversion_law_version seed."""
    h = hashlib.sha256()
    for p in sorted(LAW_DIR.glob("*.json")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def parse_cr(cr: int | float | str) -> Fraction:
    """Normalize a CR ('1/4', 0.25, 13) to a Fraction; raises on garbage."""
    if isinstance(cr, str):
        cr = cr.strip()
        if "/" in cr:
            num, den = cr.split("/", 1)
            return Fraction(int(num), int(den))
        return Fraction(cr)
    return Fraction(cr).limit_denominator(8)


VALID_CRS = frozenset(
    [Fraction(0), Fraction(1, 8), Fraction(1, 4), Fraction(1, 2)]
    + [Fraction(n) for n in range(1, 31)]
)


def cr_is_valid(cr: int | float | str) -> bool:
    try:
        return parse_cr(cr) in VALID_CRS
    except (ValueError, ZeroDivisionError, ArithmeticError):
        return False


def _cr_key(cr: Fraction) -> str:
    return str(cr) if cr.denominator > 1 else str(cr.numerator)


def cr_to_xp(cr: int | float | str) -> tuple[int, ...]:
    """XP for a CR. Returns a tuple of legal values (CR 0 is '0 or 10')."""
    f = parse_cr(cr)
    if f not in VALID_CRS:
        raise ValueError(f"not a legal CR: {cr!r}")
    val = _load("xp_by_cr.json")["xp"][_cr_key(f)]
    return tuple(val) if isinstance(val, list) else (val,)


def cr_to_pb(cr: int | float | str) -> int:
    """Proficiency Bonus by CR — bracket table, asserted equal to the formula."""
    f = parse_cr(cr)
    if f not in VALID_CRS:
        raise ValueError(f"not a legal CR: {cr!r}")
    by_formula = max(2, math.ceil(f / 4) + 1)
    for lo, hi, pb in _load("pb_by_cr.json")["brackets"]:
        if lo <= f <= hi:
            assert pb == by_formula, f"bracket/formula drift at CR {cr}"
            return pb
    raise ValueError(f"CR {cr} outside bracket table")


def dc_ladder() -> list[dict[str, Any]]:
    return _load("dc_ladder.json")["ladder"]


def dc_source(view: str) -> str:
    return _load("dc_ladder.json")["_source"][view]


def xp_budget_per_character(level: int, difficulty: str) -> int:
    data = _load("xp_budget_2024.json")
    idx = data["difficulties"].index(difficulty)
    return data["budget_per_character"][str(level)][idx]


def budget_source(view: str) -> str:
    return _load("xp_budget_2024.json")["_source"][view]


def conditions(view: str) -> frozenset[str]:
    return frozenset(_load("conditions.json")["conditions"][view])


def senses() -> frozenset[str]:
    return frozenset(_load("conditions.json")["senses"])


def parse_hd_2e(hd: str) -> tuple[float, int]:
    """'6' -> (6, 0); '12+24' -> (12, 24); '1/2' -> (0.5, 0); '1-1' -> (1, -1).

    Fractional HD ('1/2', '1/4') are real 2e monsters (V&V finding F1) — dice
    comes back as a float for them. Raises on true garbage.
    """
    s = hd.strip().replace("–", "-").replace(" ", "")
    if "/" in s:
        num, den = s.split("/", 1)
        return int(num) / int(den), 0
    if "+" in s:
        dice, plus = s.split("+", 1)
        return int(dice), int(plus)
    if "-" in s and not s.startswith("-"):  # '1-1' style
        dice, minus = s.split("-", 1)
        return int(dice), -int(minus)
    return int(s), 0


# ---------------------------------------------------------------------------
# Planar law (rule-effect handoff §M, accepted 2026-06-06 — MECHANUS.md §10).
# Seven families of page-cited 2e planar law distilled from the three boxed
# sets + In the Cage. Row ids are the join surface: Mimir mints `exhibits`
# edges against them; Modron modifiers cite them as
# `source {kind: "mechanus", ref: "<law_id>"}` (the D2 seam, handoff Q3).
# ---------------------------------------------------------------------------

PLANAR_LAW_FILES = {
    "law:planar-conditions": "planar_conditions.json",
    "law:planar-keys": "planar_keys.json",
    "law:seals-wards": "planar_seals_wards.json",
    "law:planar-priest": "planar_priest.json",
    "law:plane-environment": "planar_environment.json",
    "law:planar-spell": "planar_spells.json",
    "law:cage": "cage_law.json",
}


def _slug(ref: str) -> str:
    """'plane:the-abyss' -> 'the-abyss'; bare slugs pass through."""
    return ref.split(":", 1)[1] if ref.startswith("plane:") else ref


def _row_planes(family: str, row: dict[str, Any]) -> set[str]:
    """The plane slugs a row touches (cage rows are Sigil's by charter)."""
    if family == "law:cage":
        return {"sigil"}
    refs = set()
    for key in ("plane", "keyed_to"):
        if row.get(key):
            refs.add(_slug(row[key]))
    for ref in row.get("planes", []):
        refs.add(_slug(ref))
    if family == "law:plane-environment":
        # law:plane-environment:<slug>:<rule> — the id carries the plane
        refs.add(row["law_id"].split(":")[2])
    return refs


def _planar_rows(family: str) -> list[dict[str, Any]]:
    """Flatten one family file into law_id-bearing rows.

    Plane-keyed families (conditions, keys) yield the plane row PLUS one
    synthesized row per school / per key kind (tagged "_sub": True), so an
    `exhibits` edge or a modifier `ref` can land at either grain. Witnesses
    inherit from the parent row.
    """
    doc = _load(PLANAR_LAW_FILES[family])
    rows: list[dict[str, Any]] = []
    if family == "law:planar-conditions":
        rows.extend(doc.get("_general", []))
        for row in doc["planes"].values():
            rows.append(row)
            subs = dict(row.get("schools", {}))
            if "casting_physical" in row:
                subs["casting-physical"] = row["casting_physical"]
            for key, sub in subs.items():
                rows.append({"law_id": f"{row['law_id']}:{key}", "_sub": True,
                             "plane": row["plane"], "rule": sub["rule"],
                             "witness": sub.get("witness", row["witness"]),
                             **({"ocr_note": sub["ocr_note"]} if "ocr_note" in sub else {})})
    elif family == "law:planar-keys":
        for row in doc["planes"].values():
            rows.append(row)
            for kind in ("spell", "power"):
                rows.append({"law_id": f"{row['law_id']}:{kind}", "_sub": True,
                             "plane": row["plane"], "rule": row[f"{kind}_keys"],
                             "witness": row["witness"]})
    else:
        rows.extend(doc["rows"])
    return rows


@lru_cache(maxsize=1)
def planar_law_index() -> dict[str, tuple[str, ...]]:
    """family -> sorted tuple of every resolvable law_id (sub-ids included)."""
    return {fam: tuple(sorted(r["law_id"] for r in _planar_rows(fam)))
            for fam in PLANAR_LAW_FILES}


def planar_law(law_id: str) -> dict[str, Any]:
    """Resolve a law_id to its row (+ family). Raises KeyError if unknown."""
    for fam in PLANAR_LAW_FILES:
        if law_id == fam or law_id.startswith(fam + ":"):
            for row in _planar_rows(fam):
                if row["law_id"] == law_id:
                    return {"family": fam, **row}
            raise KeyError(law_id)
    raise KeyError(law_id)


def planar_law_for_plane(plane: str) -> list[dict[str, Any]]:
    """Every top-level row touching a plane (Mimir id `plane:<slug>` or bare
    slug; `sigil` reaches the cage family). Synthesized sub-rows are omitted —
    their parents carry them."""
    slug = _slug(plane)
    out: list[dict[str, Any]] = []
    for fam in PLANAR_LAW_FILES:
        for row in _planar_rows(fam):
            if row.get("_sub"):
                continue
            if slug in _row_planes(fam, row):
                out.append({"family": fam, **row})
    return out


def thac0_expected_2e(hd: str) -> int:
    """Expected monster THAC0 from Hit Dice, FG&G bracket table + plus-bump.

    Minus HD demote at the 1 boundary only: the canonical row is
    '1-1 or less: 20' — so '1-1' lands the <1 bracket (V&V finding F2).
    """
    dice, plus = parse_hd_2e(hd)
    data = _load("thac0_2e.json")
    effective = dice + (1 if plus >= 3 else 0)
    if dice < 1:
        effective = dice  # fractional HD never bumps
    elif dice == 1 and plus < 0:
        effective = 0.5  # '1-1 or less' row
    for lo, hi, thac0 in data["brackets"]:
        if lo <= effective <= hi:
            return thac0
    raise ValueError(f"HD {hd} outside bracket table")
