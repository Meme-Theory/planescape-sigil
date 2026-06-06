"""is_lawful — the mechanical-lawfulness judge (REVIEW-5E §A, mechanized).

This is the gate's L3 consistency channel (ARCHITECTURE.md §3): Mimir asks
"is this entity internally lawful?" and admits on the verdict. Every check is
*derivable* — pure arithmetic over the entity's own fields against cited law
tables — so it is independent of any extractor by construction.

Checks never mutate. The verdict is docket-shaped: per-check expected/actual,
hard vs soft severity, and the law_version it ruled under. A statblock whose
skill bonus ≠ mod + PB is a transcription error, provably — that is the whole
point.

Dice note: HP expressions here are the closed NdS±K statblock subset, judged
by exact mean. Full dice grammar (postfixes, pools, rolling) is Modron's lane;
Mechanus never rolls.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from typing import Any

from . import tables

# The 18 skills and their abilities — PHB/SRD, identical in both 5e rulesets.
SKILL_ABILITY: dict[str, str] = {
    "acrobatics": "dexterity", "animal-handling": "wisdom", "arcana": "intelligence",
    "athletics": "strength", "deception": "charisma", "history": "intelligence",
    "insight": "wisdom", "intimidation": "charisma", "investigation": "intelligence",
    "medicine": "wisdom", "nature": "intelligence", "perception": "wisdom",
    "performance": "charisma", "persuasion": "charisma", "religion": "intelligence",
    "sleight-of-hand": "dexterity", "stealth": "dexterity", "survival": "wisdom",
}

ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")

_HP_ROLL = re.compile(r"^\s*(\d+)d(\d+)\s*(?:([+-])\s*(\d+))?\s*$")
_FEET = re.compile(r"(\d+)\s*ft")


def ability_mod(score: int) -> int:
    return (score - 10) // 2


def mean_hp(roll: str) -> float | None:
    """Exact mean of an NdS±K expression; None if it isn't one."""
    m = _HP_ROLL.match(roll or "")
    if not m:
        return None
    n, s = int(m.group(1)), int(m.group(2))
    k = int(m.group(4) or 0) * (-1 if m.group(3) == "-" else 1)
    return n * (s + 1) / 2 + k


# ---------------------------------------------------------------------------
# Adapters — accept what exists today; one entry per shape, listed in verdicts
# ---------------------------------------------------------------------------

def _adapt_5e_bits(m: dict[str, Any]) -> dict[str, Any]:
    """5e-bits monster JSON → normalized stat dict."""
    ac_entries = m.get("armor_class") or []
    saves, skills = {}, {}
    for p in m.get("proficiencies") or []:
        idx = p["proficiency"]["index"]
        if idx.startswith("saving-throw-"):
            saves[idx.removeprefix("saving-throw-")] = p["value"]
        elif idx.startswith("skill-"):
            skills[idx.removeprefix("skill-")] = p["value"]
    speeds = {}
    for mode, val in (m.get("speed") or {}).items():
        if isinstance(val, str) and (ft := _FEET.search(val)):
            speeds[mode] = int(ft.group(1))
    senses = dict(m.get("senses") or {})
    return {
        "name": m.get("name"),
        "abilities": {a: m.get(a) for a in ABILITIES},
        "ac": ac_entries[0]["value"] if ac_entries else None,
        "hp": m.get("hit_points"),
        "hp_roll": m.get("hit_points_roll") or m.get("hit_dice"),
        "speeds": speeds,
        "cr": m.get("challenge_rating"),
        "pb": m.get("proficiency_bonus"),
        "xp": m.get("xp"),
        "passive_perception": senses.pop("passive_perception", None),
        "special_senses": senses,
        "saves": saves,
        "skills": skills,
        "condition_immunities": [c["index"] for c in m.get("condition_immunities") or []],
    }


_SAVE_ABBR = {"str": "strength", "dex": "dexterity", "con": "constitution",
              "int": "intelligence", "wis": "wisdom", "cha": "charisma"}


def _adapt_envelope_5e(e: dict[str, Any]) -> dict[str, Any]:
    """Mimir envelope (fields.statblock, 5e sub-schema per DIMENSIONS §A) → stat dict."""
    sb = (e.get("fields") or {}).get("statblock") or {}
    senses = dict(sb.get("senses") or {})
    return {
        "name": e.get("name"),
        "abilities": {a: (sb.get("abilities") or {}).get(a) for a in ABILITIES},
        "ac": sb.get("ac"),
        "hp": sb.get("hp"),
        "hp_roll": sb.get("hp_roll") or sb.get("hit_dice"),
        "speeds": sb.get("speeds") or {},
        "cr": sb.get("cr"),
        "pb": sb.get("proficiency_bonus"),
        "xp": sb.get("xp"),
        "passive_perception": senses.pop("passive_perception", None),
        "special_senses": senses,
        "saves": {_SAVE_ABBR.get(k.lower(), k.lower()): v
                  for k, v in (sb.get("saving_throws") or {}).items()},
        "skills": {k.lower().replace(" ", "-"): v
                   for k, v in (sb.get("skills") or {}).items()},
        "condition_immunities": [c.lower() for c in sb.get("condition_immunities") or []],
    }


_MORALE = re.compile(r"(\d+)")
_PCT = re.compile(r"(\d+)\s*%")
_INT = re.compile(r"^-?\d+$")


def _int_coerce(v: Any) -> int | None:
    """Mimir's admitted 2e statblocks carry numerics as printed STRINGS
    ('-8', '92', '20,000') — cross-validation gap G1. Coerce, never guess."""
    if isinstance(v, int):
        return v
    if isinstance(v, str) and _INT.match(s := v.strip().replace(",", "")):
        return int(s)
    return None


def _adapt_2e(e: dict[str, Any]) -> dict[str, Any]:
    """2e statblock (envelope fields.statblock, or a bare FG&G-shaped dict).

    Envelope reality (per the poured Uncaged corpus): `level_hd` lives in
    fields.descriptor, not the statblock — fall back there (gap G1).
    """
    fields = e.get("fields") or {}
    sb = fields.get("statblock") or e
    desc = fields.get("descriptor") or {}
    morale = sb.get("morale")
    if isinstance(morale, str):
        morale = int(m.group(1)) if (m := _MORALE.search(morale)) else None
    mr = sb.get("mr") or sb.get("magic_resistance")
    if isinstance(mr, str):
        mr = int(m.group(1)) if (m := _PCT.search(mr)) else (0 if mr.lower() in ("none", "nil") else None)
    hd_raw = sb.get("level_hd") or sb.get("hit_dice") or desc.get("level_hd")
    return {
        "name": e.get("name") or sb.get("name"),
        "ac": _int_coerce(sb.get("ac")),
        "hp": _int_coerce(sb.get("hp")),
        "hd": str(hd_raw or "").split("(")[0].strip() or None,
        "thac0": _int_coerce(sb.get("thac0")),
        "morale": morale,
        "mr": mr,
    }


def detect_shape(entity: dict[str, Any]) -> tuple[str, str]:
    """(shape, default_view). 5e-bits monsters carry their ruleset in `url`."""
    if "challenge_rating" in entity and "index" in entity:
        view = "5e-2024" if "/2024/" in (entity.get("url") or "") else "5e-2014"
        return "5e-bits-monster", view
    if "fields" in entity:
        edition = entity.get("edition", "")
        if edition.startswith("5e"):
            return "envelope-5e", edition
        return "envelope-2e", edition or "2e"
    if "thac0" in entity or "THAC0" in entity or "level_hd" in entity:
        return "bare-2e", "2e"
    raise ValueError("unrecognized entity shape — adapters: 5e-bits-monster, envelope-5e, envelope-2e, bare-2e")


# ---------------------------------------------------------------------------
# The checks
# ---------------------------------------------------------------------------

def _c(name: str, sev: str, ok: bool | None, expected=None, actual=None, detail=None) -> dict:
    return {"name": name, "sev": sev,
            "result": "skip" if ok is None else ("pass" if ok else "fail"),
            **({"expected": expected} if expected is not None else {}),
            **({"actual": actual} if actual is not None else {}),
            **({"detail": detail} if detail else {})}


def _checks_5e(s: dict[str, Any], view: str) -> list[dict]:
    out = []
    ab = s["abilities"]

    have_all = all(isinstance(ab.get(a), int) for a in ABILITIES)
    out.append(_c("abilities_present_in_range", "hard",
                  have_all and all(1 <= ab[a] <= 30 for a in ABILITIES),
                  expected="6 scores in 1..30", actual=ab))

    cr_ok = s["cr"] is not None and tables.cr_is_valid(s["cr"])
    out.append(_c("cr_valid", "hard", None if s["cr"] is None else cr_ok,
                  expected="0, 1/8, 1/4, 1/2, 1..30", actual=s["cr"]))

    if cr_ok and s["pb"] is not None:
        exp = tables.cr_to_pb(s["cr"])
        out.append(_c("pb_matches_cr", "hard", s["pb"] == exp, expected=exp, actual=s["pb"]))
    else:
        out.append(_c("pb_matches_cr", "hard", None))

    if cr_ok and s["xp"] is not None:
        legal = tables.cr_to_xp(s["cr"])
        out.append(_c("xp_matches_cr", "soft", s["xp"] in legal, expected=legal, actual=s["xp"],
                      detail="soft: prints deviate (first-printing errata); persistent halved values are the known 5e-bits bug"))
    else:
        out.append(_c("xp_matches_cr", "soft", None))

    if s["hp"] is not None and s["hp_roll"]:
        mean = mean_hp(s["hp_roll"])
        if mean is None:
            out.append(_c("hp_matches_roll", "hard", False, expected="NdS±K expression",
                          actual=s["hp_roll"], detail="unparseable HP roll"))
        else:
            out.append(_c("hp_matches_roll", "hard", abs(s["hp"] - math.floor(mean)) <= 1,
                          expected=math.floor(mean), actual=s["hp"],
                          detail=f"mean({s['hp_roll']}) = {mean}"))
    else:
        out.append(_c("hp_matches_roll", "hard", None))

    out.append(_c("ac_in_range", "hard",
                  None if s["ac"] is None else 5 <= s["ac"] <= 25,
                  expected="5..25 ascending", actual=s["ac"]))

    bad_speeds = {k: v for k, v in s["speeds"].items() if v % 5 != 0}
    out.append(_c("speeds_multiple_of_5", "hard",
                  None if not s["speeds"] else not bad_speeds,
                  actual=bad_speeds or s["speeds"]))

    wis = ab.get("wisdom")
    if s["passive_perception"] is not None and isinstance(wis, int):
        if "perception" in s["skills"]:
            exp = 10 + s["skills"]["perception"]  # skill bonus already includes PB/expertise
        else:
            exp = 10 + ability_mod(wis)
        out.append(_c("passive_perception_math", "hard", s["passive_perception"] == exp,
                      expected=exp, actual=s["passive_perception"]))
    else:
        out.append(_c("passive_perception_math", "hard", None))

    pb = s["pb"] if s["pb"] is not None else (tables.cr_to_pb(s["cr"]) if cr_ok else None)
    if pb is not None and have_all:
        bad = {a: (v, ability_mod(ab[_SAVE_ABBR.get(a, a)]) + pb)
               for a, v in s["saves"].items()
               if _SAVE_ABBR.get(a, a) in ab and v != ability_mod(ab[_SAVE_ABBR.get(a, a)]) + pb}
        out.append(_c("save_bonuses_math", "hard",
                      None if not s["saves"] else not bad,
                      actual={k: v[0] for k, v in bad.items()} or s["saves"],
                      expected={k: v[1] for k, v in bad.items()} or None,
                      detail="bonus == ability mod + PB"))
        bad_sk = {}
        for sk, v in s["skills"].items():
            a = SKILL_ABILITY.get(sk)
            if a and v not in (ability_mod(ab[a]) + pb, ability_mod(ab[a]) + 2 * pb):
                bad_sk[sk] = (v, f"{ability_mod(ab[a]) + pb} or {ability_mod(ab[a]) + 2 * pb}")
        out.append(_c("skill_bonuses_math", "hard",
                      None if not s["skills"] else not bad_sk,
                      actual={k: v[0] for k, v in bad_sk.items()} or s["skills"],
                      detail="bonus == mod + PB (or + 2·PB expertise)"))
    else:
        out.append(_c("save_bonuses_math", "hard", None))
        out.append(_c("skill_bonuses_math", "hard", None))

    known = tables.conditions(view if view in tables.VIEWS_5E else "5e-2014")
    unknown = [c for c in s["condition_immunities"]
               if c.replace("-", " ").title().replace(" ", "") not in {k.replace(" ", "") for k in known}
               and c.title() not in known]
    out.append(_c("conditions_known", "hard",
                  None if not s["condition_immunities"] else not unknown,
                  expected=sorted(known), actual=unknown or s["condition_immunities"]))

    unknown_senses = [k for k in s["special_senses"] if k not in tables.senses()]
    out.append(_c("senses_known", "hard",
                  None if not s["special_senses"] else not unknown_senses,
                  expected=sorted(tables.senses()), actual=unknown_senses or list(s["special_senses"])))
    return out


def _checks_2e(s: dict[str, Any]) -> list[dict]:
    out = []
    if s["hd"] and s["thac0"] is not None:
        try:
            exp = tables.thac0_expected_2e(s["hd"])
            out.append(_c("thac0_vs_hd", "soft", int(s["thac0"]) == exp,
                          expected=exp, actual=s["thac0"],
                          detail="FG&G bracket table + plus-bump; soft — 2e prints deviate by author intent"))
        except (ValueError, TypeError):
            out.append(_c("thac0_vs_hd", "hard", False, actual=s["hd"], detail="unparseable Hit Dice"))
    else:
        out.append(_c("thac0_vs_hd", "soft", None))

    if s["hd"] and s["hp"] is not None:
        try:
            dice, plus = tables.parse_hd_2e(s["hd"])
            # fractional HD floor/ceil; 2e minimum is always 1 hp
            lo = max(1, math.floor(dice * 1 + plus))
            hi = max(1, math.ceil(dice * 8 + plus))
            out.append(_c("hp_in_hd_range", "hard", lo <= s["hp"] <= hi,
                          expected=f"[{lo}, {hi}] for {s['hd']} (d8)", actual=s["hp"]))
        except ValueError:
            out.append(_c("hp_in_hd_range", "hard", False, actual=s["hd"], detail="unparseable Hit Dice"))
    else:
        out.append(_c("hp_in_hd_range", "hard", None))

    out.append(_c("ac_2e_range", "soft",
                  None if s["ac"] is None else -10 <= s["ac"] <= 10,
                  expected="-10..10 descending", actual=s["ac"]))
    out.append(_c("morale_in_range", "soft",
                  None if s["morale"] is None else 2 <= s["morale"] <= 20,
                  expected="2..20", actual=s["morale"]))
    out.append(_c("magic_resistance_pct", "soft",
                  None if s["mr"] is None else 0 <= s["mr"] <= 100,
                  expected="0..100%", actual=s["mr"]))
    return out


# ---------------------------------------------------------------------------
# Waivers — RAW is authoritative even when non-derivable, but only witnessed
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _known_deviations() -> dict[str, Any]:
    p = tables.LAW_DIR / "known_deviations.json"
    return json.loads(p.read_text(encoding="utf-8"))


def known_waivers(index_or_name: str) -> list[dict[str, Any]]:
    """Curated waivers for SRD-attested non-derivable prints (lich, night-hag, priest).

    Each entry carries the printed value, the page witness, and the reason —
    a waiver without a witness is not a waiver, it's a blindfold.
    """
    key = (index_or_name or "").strip().lower().replace(" ", "-")
    return _known_deviations()["attested_deviations"].get(key, [])


def is_lawful(entity: dict[str, Any], view: str | None = None,
              waivers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Judge an entity's internal mechanical lawfulness. Returns a docket.

    `lawful` is True iff no *hard* check fails un-waived. Soft fails lower
    nothing here — they are reported for the gate/curator to weigh
    (VALIDATION.md routes them to low-confidence, not rejection).

    `waivers` (or the entity's own `curated.lawful_waivers`) downgrade named
    hard-fails to result="waived" — disclosed in the docket with their witness,
    never silently passed. Use for print-attested deviations only.
    """
    shape, default_view = detect_shape(entity)
    view = view or default_view

    if shape == "5e-bits-monster":
        stat = _adapt_5e_bits(entity)
        checks = _checks_5e(stat, view)
    elif shape == "envelope-5e":
        stat = _adapt_envelope_5e(entity)
        checks = _checks_5e(stat, view)
    else:  # envelope-2e | bare-2e
        stat = _adapt_2e(entity)
        checks = _checks_2e(stat)

    active_waivers = list(waivers or []) + list(
        (entity.get("curated") or {}).get("lawful_waivers") or [])
    waived: list[str] = []
    by_check = {w["check"]: w for w in active_waivers if w.get("witness")}
    for c in checks:
        if c["result"] == "fail" and c["sev"] == "hard" and c["name"] in by_check:
            w = by_check[c["name"]]
            c["result"] = "waived"
            c["waiver"] = {"witness": w["witness"], "reason": w.get("reason", "")}
            waived.append(c["name"])

    hard_fails = [c["name"] for c in checks if c["sev"] == "hard" and c["result"] == "fail"]
    soft_fails = [c["name"] for c in checks if c["sev"] == "soft" and c["result"] == "fail"]
    ran = sum(1 for c in checks if c["result"] in ("pass", "fail", "waived"))
    return {
        "tool": "mechanus.is_lawful",
        "entity": stat.get("name"),
        "shape": shape,
        "view": view,
        "lawful": not hard_fails,
        # gap G6: all-skip is NOT confirmation — a gate using this as an L3
        # channel must treat applicable=false as "no witness", never as "pass"
        "applicable": ran > 0,
        "checks": checks,
        "summary": {
            "hard_fails": hard_fails,
            "soft_fails": soft_fails,
            "waived": waived,
            "passed": sum(1 for c in checks if c["result"] == "pass"),
            "skipped": sum(1 for c in checks if c["result"] == "skip"),
            "checks_run": ran,
        },
        "law_version": tables.law_version(),
    }
