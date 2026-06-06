"""The rollables compiler: find the dice hiding in data (MODRON.md §6).

Dice-SYNTAX knowledge lives here — parsing `1d4/1d4/2d6 (claw/claw/bite)`,
inverting `3-18` to `3d6`, reading `THAC0 7` and `morale champion (16)` and
`Hit: 14 (2d8+5)`. Dice-LAW (which modifiers apply) does not.

Every spec carries field-level provenance; everything uncertain says so:
range inversions ship alternatives, prose finds are `from_prose` +
`requires_confirmation`, crosschecks report mismatches instead of fixing them.
The crosschecks double as the gate's dice-lawfulness witness (MODRON.md §2.4).
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

from .analysis import mean_of
from .grammar import DiceSyntaxError, parse

COMMON_DICE = (6, 8, 4, 10, 12, 20, 3, 2, 100)

# OCR leniency in DICE CONTEXT ONLY (the v1b normalization map: I/l→1, O→0)
_OCR_DIGIT = str.maketrans({"I": "1", "l": "1", "O": "0", "o": "0"})

_DICE_RE = re.compile(
    r"(?<![A-Za-z0-9])([0-9Il]{0,3})\s*[dD]\s*([0-9OIl]{1,4})\s*((?:[+-]\s*[0-9OIl]{1,3})?)"
    r"(?![A-Za-z0-9])")
_RANGE_RE = re.compile(r"^\s*(\d{1,3})\s*[-–—]\s*(\d{1,3})\s*$")
_PCT_RE = re.compile(r"(\d{1,3})\s*%")
_PAREN_NUM_RE = re.compile(r"\((\d{1,3})\)")


def _ocr_int(s: str) -> int:
    return int(s.translate(_OCR_DIGIT))


def clean_dice_text(m: re.Match) -> str | None:
    """One _DICE_RE hit -> a parseable expression (OCR-normalized), or None."""
    count = m.group(1) or "1"
    sides = m.group(2)
    bonus = (m.group(3) or "").replace(" ", "")
    try:
        expr = f"{_ocr_int(count)}d{_ocr_int(sides)}"
        if bonus:
            expr += f"{bonus[0]}{_ocr_int(bonus[1:])}"
        parse(expr)
        return expr
    except (ValueError, DiceSyntaxError):
        return None


# ---------------------------------------------------------------------------
# Range inversion: '3-18' -> 3d6 (alternatives surfaced, never silently picked)
# ---------------------------------------------------------------------------

def range_to_dice(lo: int, hi: int) -> dict | None:
    """Decompose a min..max range into NdS+B candidates, ranked.

    Rank law: bonus-free first, then common-die order, then fewer dice.
    Returns {expr, alternatives[], ambiguous} or None if nothing fits.
    """
    if hi <= lo or lo < 1:
        return None
    candidates: list[tuple[tuple, str]] = []
    span = hi - lo
    for s in COMMON_DICE:
        if span % (s - 1) != 0:
            continue
        n = span // (s - 1)
        if n < 1 or n > 100:
            continue
        b = lo - n
        expr = f"{n}d{s}" + (f"{b:+d}" if b else "")
        # rank key: (has_bonus, common-die position, dice count)
        candidates.append(((b != 0, COMMON_DICE.index(s), n), expr))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    exprs = [c[1] for c in candidates]
    return {"expr": exprs[0], "alternatives": exprs[1:4], "ambiguous": len(exprs) > 1,
            "range": [lo, hi]}


def text_to_expr(raw: str) -> dict | None:
    """A damage-ish fragment -> spec dict: direct dice, or an inverted range."""
    raw = raw.strip()
    if not raw:
        return None
    m = _DICE_RE.search(raw)
    if m:
        expr = clean_dice_text(m)
        if expr:
            out = {"expr": expr, "raw": raw}
            if expr.replace(" ", "") != raw.replace(" ", ""):
                out["normalized_from"] = raw
            return out
    m = _RANGE_RE.match(raw)
    if m:
        inv = range_to_dice(int(m.group(1)), int(m.group(2)))
        if inv:
            return {"expr": inv["expr"], "raw": raw, "inverted_from_range": inv["range"],
                    "alternatives": inv["alternatives"], "ambiguous": inv["ambiguous"]}
    return None


# ---------------------------------------------------------------------------
# Crosschecks — the dice-lawfulness witness
# ---------------------------------------------------------------------------

def avg_crosscheck(printed: int, expr: str) -> dict:
    """5e printed average vs floor(exact mean). Mismatch = transcription smell."""
    mean = mean_of(expr)
    if mean is None:
        return {"check": "printed_average", "verdict": "unknown", "expr": expr}
    expected = int(mean)  # floor of a positive Fraction
    ok = expected == printed
    return {"check": "printed_average", "expr": expr, "printed": printed,
            "floor_mean": expected, "exact_mean": float(mean),
            "verdict": "ok" if ok else "MISMATCH"}


def hp_range_crosscheck(printed_hp: int, expr: str) -> dict:
    """2e rolled-up HP vs the HD expression's reachable range."""
    try:
        from .analysis import pmf as _pmf
        p, _ = _pmf(parse(expr))
        lo, hi = min(p), max(p)
    except Exception:
        return {"check": "hp_in_hd_range", "verdict": "unknown", "expr": expr}
    mean = mean_of(expr)
    verdict = "ok" if lo <= printed_hp <= hi else "OUT_OF_RANGE"
    return {"check": "hp_in_hd_range", "expr": expr, "printed": printed_hp,
            "range": [lo, hi], "exact_mean": float(mean) if mean is not None else None,
            "verdict": verdict}


# ---------------------------------------------------------------------------
# 2e statblock compiler (shape: the v2 extraction envelopes, e.g. a-kin.json)
# ---------------------------------------------------------------------------

# 2e class hit dice — FG&G class-advancement tables (fgg-text p0027/p0030/p0032/
# p0034, printed 17/20/22/24): warriors d10 to LEVEL 9 then +3/level; priests d8
# to 9 then +2; rogues d6 to LEVEL 10 then +2; wizards d4 to LEVEL 10 then +1.
# Per-class dice caps + the specialist code per audit court-fgg
# _provisional:class-hd + G-5-clean-sample-01 (2026-06-06).
_CLASS_HD = {
    "F": (10, 3, 9), "PA": (10, 3, 9), "RA": (10, 3, 9),    # warrior group
    "C": (8, 2, 9), "P": (8, 2, 9), "D": (8, 2, 9),         # priest group
    "T": (6, 2, 10), "B": (6, 2, 10),                        # rogue group
    "M": (4, 1, 10), "W": (4, 1, 10), "MA": (4, 1, 10),      # wizard group
    "ILL": (4, 1, 10),                                       # specialist wizard
}
_CLASS_CODE_RE = re.compile(r"^([A-Za-z]{1,3})\s*(\d{1,2})$")


def parse_class_hp(char_class: str | None, level_hd: str | None) -> dict | None:
    """Class-leveled 2e characters roll CLASS hit dice, not monster d8
    (family-integration catch G4: Tarholt F9 = 9d10+Con, not 9d8).

    'F9' -> 9d10; 'M12' -> 10d4+2 (wizards/rogues gain dice to level 10 —
    FG&G class tables; audit court-fgg 2026-06-06).
    Con bonus is NOT included (unknown) — the range crosscheck allows it.
    """
    code = (char_class or "").strip()
    m = _CLASS_CODE_RE.match(code)
    # 0-level door: both glyphs ('O-level' and digit-zero '0-level' — audit
    # G-4-hp-roster-06). FG&G Table 13.1 (printed 91) is PER-PROFESSION; 1d6 is
    # the craftsman/teenager default — pass the profession's die when known.
    if not m and re.match(r"^[O0][-\s]?level", code, re.IGNORECASE):
        return {"expr": "1d6", "raw": code, "con_allowance": 2,
                "note": "0-level: 1d6 default — FG&G Table 13.1 (printed 91) is "
                        "per-profession (laborer/soldier d8, scholar 1d3, ...); "
                        "confirm the profession"}
    if not m:
        return None
    cls, level = m.group(1).upper(), int(m.group(2))
    if cls not in _CLASS_HD:
        return None
    die, post, cap = _CLASS_HD[cls]
    dice = min(level, cap)
    flat = (level - cap) * post if level > cap else 0
    expr = f"{dice}d{die}" + (f"+{flat}" if flat else "")
    con_allow = 4 if die == 10 else 2                     # warriors up to +4/die, others +2
    return {"expr": expr, "raw": code, "con_allowance": con_allow * dice,
            "note": f"class HD ({cls} level {level}): d{die} to level {cap}"
                    + (f", +{post}/level past {cap}" if level > cap else "")
                    + " — Con bonus not included (FG&G class tables, printed 17/20/22/24)"}


def parse_hd(level_hd: str, pack: dict) -> dict | None:
    """'12+24' -> 12d8+24 · '8' -> 8d8 · '1-1' -> 1d8-1 · '1/2' -> 2d2 (2e monster HD)
    · '9d4+23' passes through (explicit printed dice — audit G-2-npc-a-05)."""
    hd_cfg = (pack or {}).get("hp_from_hd", {})
    die = hd_cfg.get("die", 8)
    s = str(level_hd).strip()
    frac = (hd_cfg.get("fractional") or {}).get(s)
    if frac:
        return {"expr": frac, "raw": s,
                "note": "fractional HD mapping (1/2 = 2d2 per FG&G printed 283; "
                        "1/4 provisional)"}
    if "d" in s.lower():
        # explicit printed dice expression (Uncaged prints these for
        # incantifier-class oddities) — prefer it verbatim
        try:
            parse(s)
            return {"expr": s, "raw": s,
                    "note": "explicit printed HD expression (audit G-2-npc-a-05)"}
        except DiceSyntaxError:
            pass
    m = re.match(r"^(\d{1,3})\s*([+-]\s*\d{1,3})?$", s)
    if not m:
        return None
    n = int(m.group(1))
    bonus = (m.group(2) or "").replace(" ", "")
    expr = f"{n}d{die}{bonus}"
    try:
        parse(expr)
    except DiceSyntaxError:
        return None
    out = {"expr": expr, "raw": s}
    if n > 40:  # no 2e creature rolls 740d8 — a fused-OCR tell (Cirily: '7+10'→'740')
        out["suspect"] = True
        out["note"] = (f"implausible HD count ({n}) — transcription suspect "
                       "(OCR often fuses '+': '7+10'→'740'); confirm against the page")
    return out


_MULT_RE = re.compile(r"^(.*?)\s*[x×]\s*(\d{1,2})$")


def _split_damage(damage: str) -> list[dict]:
    """'1d4/1d4/2d6 (claw/claw/bite)' -> labeled per-attack specs.

    Also handles 2e idioms (family-integration catch G3): alternative modes
    split on ' or ' ('…claw/claw/bite or 1d6x4 (clawx4)'), and xN multipliers
    ('1d6x4' -> four 1d6 specs)."""
    if not damage:
        return []
    out: list[dict] = []
    modes = re.split(r"\s+or\s+", damage) if " or " in damage else [damage]
    for mode_i, mode in enumerate(modes):
        mode = mode.strip()
        labels: list[str] = []
        m = re.search(r"\(([^)]*)\)\s*$", mode)
        body = mode
        if m:
            lab = m.group(1).strip()
            # label-ish parenthetical: 'claw/claw/bite', 'bite', 'clawx4' — but
            # NOT '(long sword +1)' (dice/bonus text stays in the body)
            if "/" in lab or re.fullmatch(r"[A-Za-z]+(?:\s*[x×]\s*\d{1,2})?", lab):
                labels = [w.strip() for w in lab.split("/")]
                body = mode[: m.start()].strip()
        parts = [p.strip() for p in body.split("/") if p.strip()]
        # expand xN multipliers within this mode
        expanded: list[tuple[str, str | None]] = []
        for i, part in enumerate(parts):
            label = labels[i] if i < len(labels) else None
            mm = _MULT_RE.match(part)
            if mm and text_to_expr(mm.group(1).strip()):
                times = min(int(mm.group(2)), 12)
                base_label = (label or "attack").rstrip("x×0123456789 ")
                expanded.extend((mm.group(1).strip(), f"{base_label} {k + 1}/{times}")
                                for k in range(times))
            else:
                expanded.append((part, label))
        mode_tag = "" if len(modes) == 1 else f" [mode {mode_i + 1}]"
        for j, (part, label) in enumerate(expanded):
            spec = text_to_expr(part)
            label = (label or f"attack {j + 1}") + mode_tag
            key = f"damage.{mode_i + 1}.{j + 1}" if len(modes) > 1 else f"damage.{j + 1}"
            if spec:
                out.append({"key": key, "label": label, "purpose": "damage", **spec})
            else:
                out.append({"key": key, "label": label, "purpose": "damage",
                            "raw": part, "unparsed": True})
    return out


# MC-style flat fields (the Monstrous-Compendium creature shape) aliased into
# statblock shape — audit G-1-creatures-01: 16 handbook creatures carry these at
# top level with no statblock sub-object and compiled to a single generic spec.
_MC_FIELD_ALIASES = (("thac0", "thac0"), ("damage_attack", "damage"),
                     ("no_of_attacks", "num_attacks"),
                     ("magic_resistance", "magic_resistance"),
                     ("morale", "morale"), ("hit_dice", "hd"),
                     ("armor_class", "ac"), ("hp", "hp"))


def _statblock_of(entity: dict) -> tuple[dict, dict]:
    """(statblock-shaped dict, canonical-key -> source-field-name map).

    The nested statblock wins when present; otherwise MC flat fields alias in,
    keeping the FLAT names in provenance (audit G-1-creatures-01 fix shape)."""
    sb = entity.get("statblock")
    if isinstance(sb, dict) and sb:
        return sb, {dst: f"statblock.{dst}" for _, dst in _MC_FIELD_ALIASES}
    alias: dict[str, Any] = {}
    fields: dict[str, str] = {}
    for src, dst in _MC_FIELD_ALIASES:
        if entity.get(src) not in (None, ""):
            alias[dst] = entity[src]
            fields[dst] = src
    return alias, fields


def statblock_2e(entity: dict, pack: dict) -> list[dict]:
    """Roll specs from a 2e NPC/creature envelope (v2 extraction shape, or the
    MC flat creature shape via _statblock_of)."""
    specs: list[dict] = []
    sb, _field_of = _statblock_of(entity)
    name = entity.get("name", "?")

    def prov(field: str, raw: Any) -> dict:
        return {"entity": name, "field": field, "raw": raw}

    def fld(key: str) -> str:
        return _field_of.get(key, f"statblock.{key}")

    thac0 = sb.get("thac0")
    if thac0 not in (None, ""):
        try:
            t = _ocr_int(str(thac0).strip())
            specs.append({"key": "attack", "label": f"attack (THAC0 {t})", "purpose": "attack",
                          "check": {"kind": "attack", "params": {"thac0": t}},
                          "needs": ["ac (target)"], "provenance": prov(fld("thac0"), thac0)})
        except ValueError:
            specs.append({"key": "attack", "unparsed": True,
                          "provenance": prov(fld("thac0"), thac0)})

    for dspec in _split_damage(str(sb.get("damage") or "")):
        dspec["provenance"] = prov(fld("damage"), sb.get("damage"))
        specs.append(dspec)

    na = str(sb.get("num_attacks") or "").strip()
    if na:
        specs.append({"key": "num_attacks", "info": na, "purpose": "info",
                      "provenance": prov(fld("num_attacks"), na)})

    mr = str(sb.get("magic_resistance") or "").strip()
    if mr:
        m = _PCT_RE.search(mr)
        if m:
            specs.append({"key": "magic_resistance", "label": f"magic resistance {m.group(1)}%",
                          "purpose": "percent",
                          "check": {"kind": "percent", "params": {"pct": int(m.group(1))}},
                          "provenance": prov(fld("magic_resistance"), mr)})

    morale = str(sb.get("morale") or "").strip()
    if morale:
        m = _PAREN_NUM_RE.search(morale) or re.match(r"^(\d{1,2})$", morale)
        if m:
            rating = int(m.group(1))
            specs.append({"key": "morale", "label": f"morale check ({morale})",
                          "purpose": "morale",
                          "check": {"kind": "morale", "params": {"morale": rating}},
                          "provenance": prov(fld("morale"), morale)})
        else:
            # printed morale with no parseable rating (band name, OCR wound):
            # VISIBLE, never silent (audit G-2-npc-a-13)
            specs.append({"key": "morale", "purpose": "info", "raw_morale": morale,
                          "requires_confirmation": True,
                          "note": "morale printed but no rating parsed — 2e band "
                                  "names map to ratings (champion = 15-16, "
                                  "provisional); confirm the number",
                          "provenance": prov(fld("morale"), morale)})

    desc = entity.get("descriptor") or {}
    hd = desc.get("level_hd") or sb.get("hd")
    char_class = desc.get("char_class")
    printed = str(sb.get("hp") or "").strip()
    # class-leveled characters roll CLASS dice (G4); monsters roll the pack die
    parsed = parse_class_hp(char_class, hd) if char_class else None
    # a class string that DIDN'T parse must never silently degrade to monster
    # dice (audit G-2-npc-a-09 / G-5-clean-sample-02/-03): flag the fallback,
    # and surface multiclass component dice when they parse
    class_unparsed_note = None
    if char_class and not parsed:
        comps = []
        if re.search(r"[,/]", str(char_class)):
            comps = [parse_class_hp(c.strip(), None)
                     for c in re.split(r"[,/]", str(char_class))]
        comp_txt = ""
        if comps and all(comps):
            comp_txt = (" — component class HD: "
                        + ", ".join(c["expr"] for c in comps)
                        + " (2e multiclass averages HP across classes; not "
                          "auto-computed)")
        class_unparsed_note = (
            f"class string {str(char_class)!r} not parsed as single-class"
            f"{comp_txt}; the monster-die fallback is SUSPECT — class-leveled "
            "cutters never roll d8s (G4)")
    prov_field = "descriptor.char_class" if parsed else "descriptor.level_hd"
    prov_raw = char_class if parsed else hd
    if not parsed and hd:
        parsed = parse_hd(str(hd), pack)
    if parsed:
        spec = {"key": "hp", "label": f"hit points ({prov_raw})", "purpose": "hp",
                "expr": parsed["expr"],
                "provenance": prov(prov_field, prov_raw)}
        if parsed.get("note"):
            spec["note"] = parsed["note"]
        if parsed.get("suspect"):
            spec["requires_confirmation"] = True
        if class_unparsed_note:
            spec["requires_confirmation"] = True
            spec["note"] = (spec.get("note", "") + " | " if spec.get("note") else "") \
                + class_unparsed_note
        if printed.isdigit():
            cc = hp_range_crosscheck(int(printed), parsed["expr"])
            allow = parsed.get("con_allowance", 0)
            if allow and cc.get("verdict") == "OUT_OF_RANGE" and \
                    cc["range"][0] <= int(printed) <= cc["range"][1] + allow:
                cc["verdict"] = "ok"
                cc["note"] = f"within range given Con allowance (+{allow} max)"
            elif allow:
                cc["con_allowance"] = allow
            spec["crosscheck"] = cc
        specs.append(spec)
    elif printed.isdigit():
        # printed HP with no derivable dice: VISIBLE, never silent (G5)
        note = ("no HD or class-level parse — HP roll not derivable; "
                "printed value shown")
        if class_unparsed_note:
            note += " | " + class_unparsed_note
        specs.append({"key": "hp", "purpose": "info", "printed_hp": int(printed),
                      "note": note,
                      "provenance": prov(fld("hp"), printed)})

    # save targets are law — emit the ask, not an invented number
    specs.append({"key": "save", "purpose": "save", "needs": ["target (save matrices are law — Mechanus/caller supplies)"],
                  "check": {"kind": "save", "params": {}},
                  "provenance": prov("statblock", "saves derived from HD/class — not printed")})
    return specs


# ---------------------------------------------------------------------------
# 5e statblock compiler
# ---------------------------------------------------------------------------

_HIT_RE = re.compile(r"([+-]\d+)\s+to\s+hit", re.I)
_HITDMG_RE = re.compile(r"Hit:\s*(\d+)\s*\(([^)]+)\)(?:[^.]*?\bor\s*(\d+)\s*\(([^)]+)\))?", re.I)
_DC_RE = re.compile(r"DC\s*(\d+)\s+(\w+)\s+saving throw", re.I)
_RECHARGE_RE = re.compile(r"Recharge\s+(\d)(?:\s*[-–]\s*(\d))?", re.I)
_HP_FORMULA_RE = re.compile(r"^\s*(\d+)\s*\(([^)]+)\)\s*$")


def statblock_5e(entity: dict, pack: dict) -> list[dict]:
    specs: list[dict] = []
    name = entity.get("name", "?")
    sb = entity.get("statblock") or entity  # tolerate flat shapes

    def prov(field: str, raw: Any) -> dict:
        return {"entity": name, "field": field, "raw": raw}

    hp = sb.get("hp")
    if isinstance(hp, dict):
        avg, formula = hp.get("average"), hp.get("formula")
    else:
        m = _HP_FORMULA_RE.match(str(hp or ""))
        avg, formula = (int(m.group(1)), m.group(2)) if m else (None, None)
    if formula:
        formula = formula.replace(" ", "")
        spec = {"key": "hp", "label": f"hit points ({formula})", "purpose": "hp",
                "expr": formula, "provenance": prov("statblock.hp", hp)}
        if avg is not None:
            spec["crosscheck"] = avg_crosscheck(int(avg), formula)
        specs.append(spec)

    actions = sb.get("actions") or entity.get("actions") or []
    for i, action in enumerate(actions):
        aname = action.get("name", f"action {i + 1}") if isinstance(action, dict) else f"action {i + 1}"
        text = action.get("text", "") if isinstance(action, dict) else str(action)
        m = _HIT_RE.search(text)
        if m:
            specs.append({"key": f"attack.{aname}", "label": f"{aname}: attack {m.group(1)}",
                          "purpose": "attack",
                          "check": {"kind": "attack", "params": {"attack_bonus": int(m.group(1))}},
                          "needs": ["ac (target)"], "provenance": prov(f"actions.{aname}", m.group(0))})
        for dm in _HITDMG_RE.finditer(text):
            expr = dm.group(2).replace(" ", "")
            spec = {"key": f"damage.{aname}", "label": f"{aname}: damage", "purpose": "damage",
                    "expr": expr, "crosscheck": avg_crosscheck(int(dm.group(1)), expr),
                    "provenance": prov(f"actions.{aname}", dm.group(0))}
            specs.append(spec)
            if dm.group(3) and dm.group(4):  # versatile
                vexpr = dm.group(4).replace(" ", "")
                specs.append({"key": f"damage.{aname}.versatile", "label": f"{aname}: damage (two-handed)",
                              "purpose": "damage", "expr": vexpr,
                              "crosscheck": avg_crosscheck(int(dm.group(3)), vexpr),
                              "provenance": prov(f"actions.{aname}", dm.group(0))})
        m = _DC_RE.search(text)
        if m:
            specs.append({"key": f"save.{aname}", "label": f"{aname}: DC {m.group(1)} {m.group(2)} save",
                          "purpose": "save",
                          "check": {"kind": "save", "params": {"dc": int(m.group(1))}},
                          "needs": ["save_bonus (the target's)"],
                          "provenance": prov(f"actions.{aname}", m.group(0))})
        m = _RECHARGE_RE.search(aname + " " + text)
        if m:
            lo = int(m.group(1))
            specs.append({"key": f"recharge.{aname}", "label": f"{aname}: recharge {m.group(0)}",
                          "purpose": "recharge",
                          "check": {"kind": "recharge", "params": {"threshold": lo}},
                          "provenance": prov(f"actions.{aname}", m.group(0))})
    return specs


# ---------------------------------------------------------------------------
# Prose sweep (OCR-lenient, honest about its grade)
# ---------------------------------------------------------------------------

def _in_stat_array(text: str, m: re.Match) -> bool:
    """True when a COUNT-LESS d-match (' D 15' -> 1d15) sits inside a 2e
    ability-score array ('S 16, D 13, C 16, I 15, W 14, Ch 8') — the audit's
    recurring prose-sweep false positive (G-2/G-3, seven specs denied)."""
    if m.group(1):                      # explicit count like '2d6' — never the artifact
        return False
    ctx = text[max(0, m.start() - 30): m.end() + 30]
    return len(re.findall(r"\b(?:S|D|C|I|W|Ch)\s?\d{1,2}\b", ctx)) >= 3


def prose_sweep(entity: dict) -> list[dict]:
    """Find dice and percent-chances in prose fields — flagged, low-confidence."""
    specs: list[dict] = []
    name = entity.get("name", "?")
    fields: list[tuple[str, str]] = []
    for key in ("sections", "fields"):
        for fname, text in (entity.get(key) or {}).items():
            if isinstance(text, str):
                fields.append((f"{key}.{fname}", text))
    for fname in ("body",):
        if isinstance(entity.get(fname), str):
            fields.append((fname, entity[fname]))

    for fname, text in fields:
        for m in _DICE_RE.finditer(text):
            if _in_stat_array(text, m):
                continue
            expr = clean_dice_text(m)
            if not expr:
                continue
            ctx = text[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            specs.append({"key": f"prose.{fname}.{m.start()}", "expr": expr,
                          "purpose": "from_prose", "from_prose": True,
                          "requires_confirmation": True, "context": f"…{ctx}…",
                          "provenance": {"entity": name, "field": fname, "raw": m.group(0)}})
        for m in _PCT_RE.finditer(text):
            pct = int(m.group(1))
            if pct > 100:
                continue
            tail = text[m.end(): m.end() + 28].lower()
            if "chance" not in tail and "in lair" not in tail and "chance" not in \
               text[max(0, m.start() - 16): m.start()].lower():
                continue
            ctx = text[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            specs.append({"key": f"prose.{fname}.pct.{m.start()}",
                          "purpose": "percent", "from_prose": True,
                          "requires_confirmation": True,
                          "check": {"kind": "percent", "params": {"pct": pct}},
                          "context": f"…{ctx}…",
                          "provenance": {"entity": name, "field": fname, "raw": m.group(0)}})
    return specs


# ---------------------------------------------------------------------------
# Entity door
# ---------------------------------------------------------------------------

def unwrap_envelope(entity: dict) -> dict:
    """Flatten a Mimir envelope: payload (statblock/descriptor/sections/body/actions)
    nests under `fields` in handbook.db rows; the v2 build JSONs are already flat.
    Entity-level keys (name/edition/provenance) win on collision.
    (Family-integration catch G1, 2026-06-05.)"""
    fields = entity.get("fields")
    if not isinstance(fields, dict):
        return entity
    return {**fields, **{k: v for k, v in entity.items() if k != "fields"}}


def detect_view(entity: dict) -> str:
    entity = unwrap_envelope(entity)
    e = (entity.get("edition") or "").strip()
    if e in ("5e-2014", "5e-2024", "2e", "1e"):
        return e
    sb = entity.get("statblock") or {}
    if "thac0" in sb or "level_hd" in (entity.get("descriptor") or {}):
        return "2e"
    if "cr" in sb or "challenge" in sb:
        return "5e-2014"
    return "2e"  # this project's scans default 2e; recorded in the output


def compile_entity(entity: dict, pack: dict, view: str, *, sweep_prose: bool = True) -> list[dict]:
    entity = unwrap_envelope(entity)
    if view == "2e":
        specs = statblock_2e(entity, pack)
    else:
        specs = statblock_5e(entity, pack)
    if sweep_prose:
        specs.extend(prose_sweep(entity))
    return specs


# ---------------------------------------------------------------------------
# Tables (dim:table: {dice, entries[{roll,result}]})
# ---------------------------------------------------------------------------

def _entry_bounds(roll: str | int, sides: int) -> tuple[int, int] | None:
    s = str(roll).strip()
    m = re.match(r"^(\d{1,3})\s*[-–]\s*(\d{1,3})$", s)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
    elif s == "00":
        lo = hi = 100
    elif s.isdigit():
        lo = hi = int(s)
    else:
        return None
    if sides == 100:  # percentile: 00 reads 100
        lo = 100 if lo == 0 else lo
        hi = 100 if hi == 0 else hi
    return (lo, hi) if lo <= hi else (hi, lo)


def validate_table(table: dict) -> dict:
    """Coverage report: gaps and overlaps are reported, not papered over."""
    dice = str(table.get("dice") or "1d100").replace(" ", "")
    node = parse(dice)
    from .analysis import pmf as _pmf
    p, _ = _pmf(node)
    lo, hi = min(p), max(p)
    spans, bad = [], []
    for i, entry in enumerate(table.get("entries") or []):
        b = _entry_bounds(entry.get("roll"), hi)
        if b is None:
            bad.append({"entry": i, "roll": entry.get("roll")})
        else:
            spans.append((b[0], b[1], i))
    spans.sort()
    gaps, overlaps = [], []
    cursor = lo
    for s, e, i in spans:
        if s > cursor:
            gaps.append([cursor, s - 1])
        if s < cursor:
            overlaps.append([s, min(e, cursor - 1)])
        cursor = max(cursor, e + 1)
    if cursor <= hi:
        gaps.append([cursor, hi])
    return {"dice": dice, "range": [lo, hi], "entries": len(spans),
            "gaps": gaps, "overlaps": overlaps, "unparsed": bad,
            "verdict": "ok" if not (gaps or overlaps or bad) else "COVERAGE_ISSUES"}


def resolve_table_roll(table: dict, value: int) -> dict | None:
    sides = 100 if "100" in str(table.get("dice", "")) else 10 ** 6
    for entry in table.get("entries") or []:
        b = _entry_bounds(entry.get("roll"), sides)
        if b and b[0] <= value <= b[1]:
            return entry
    return None


# ---------------------------------------------------------------------------
# Encounters — the orchestration plan (MODRON.md §6)
# ---------------------------------------------------------------------------

def encounter_plan(spec: dict, pack: dict, view: str) -> list[dict]:
    """An encounter spec -> ordered roll plan. plan_only callers stop here."""
    doctrine = (pack.get("encounter_doctrine") or {})
    default_steps = doctrine.get("steps", ["number", "hp", "initiative"])
    steps = spec.get("steps", default_steps)
    plan: list[dict] = []

    def step(key: str, **kw) -> None:
        plan.append({"step": key, "view": view, **kw})

    for s in steps:
        if s == "check":
            cfg = spec.get("check") or doctrine.get("check_default")
            if cfg:
                # spec authors write "expr"; packs write "roll" (their check idiom)
                expr = cfg.get("expr") or cfg.get("roll")
                if expr:
                    step("check", expr=expr, encounter_on=cfg.get("encounter_on", "<=1"),
                         label="wandering encounter check")
        elif s == "table" and spec.get("table"):
            step("table", table=spec["table"], label="encounter table")
        elif s == "number":
            na = spec.get("number_appearing")
            if na:
                t = text_to_expr(str(na))
                step("number", expr=(t or {}).get("expr", str(na)),
                     label=f"number appearing ({na})",
                     **({"alternatives": t["alternatives"]} if t and t.get("alternatives") else {}))
        elif s == "hp":
            creature = spec.get("creature") or {}
            hd = creature.get("hd") or creature.get("level_hd")
            hp_expr = creature.get("hp_expr")
            if not hp_expr and hd:
                parsed = parse_hd(str(hd), pack)
                hp_expr = parsed["expr"] if parsed else None
            if hp_expr:
                step("hp", expr=hp_expr, per_creature=True,
                     label=f"hit points per creature ({hp_expr})")
        elif s == "surprise":
            sur = (pack.get("checks") or {}).get("surprise")
            if sur:
                step("surprise", check={"kind": "surprise", "params": {}},
                     sides=["party", "monsters"], label="surprise (each side)")
        elif s == "distance" and spec.get("distance"):
            t = text_to_expr(str(spec["distance"]))
            step("distance", expr=(t or {}).get("expr", str(spec["distance"])),
                 label=f"encounter distance ({spec['distance']})")
        elif s == "reaction":
            rx = (pack.get("checks") or {}).get("reaction")
            if rx:
                params = {k: v for k, v in (spec.get("reaction") or {}).items()}
                step("reaction", check={"kind": "reaction", "params": params},
                     label="reaction roll")
        elif s == "initiative":
            init = (pack.get("checks") or {}).get("initiative")
            if init:
                icfg = spec.get("initiative") or {}
                # §12 Q2 (2026-06-05): party AND monsters by default; the spec
                # omits a side via sides (e.g. the table rolls its own dice)
                for side in icfg.get("sides", ["party", "monsters"]):
                    params = icfg.get(side, {})
                    step("initiative", side=side,
                         check={"kind": "initiative", "params": params},
                         label=f"initiative ({side})")
        elif s == "morale":
            creature = spec.get("creature") or {}
            if creature.get("morale") is not None:
                step("morale", check={"kind": "morale",
                                      "params": {"morale": int(creature["morale"])}},
                     armed=True, label="morale (when triggered — not pre-rolled)")
    return plan
