#!/usr/bin/env python
"""integrity.py — mechanical integrity checker over Modron (Modron Audit, Phase 0).

Deterministic, no agents, library-imports only — NO server, NO MCP. Catches
STRUCTURAL violations (bugs, not judgment calls): pack/registry/modifier load
law, dice-math conformance (an independent enumerator vs analysis.pmf), ledger
replay (every rolled row re-derived face-by-face), doc-claim counts, and the
fleet compile (87 handbook entities through the rollables compiler, outputs
dumped for the lane-G review chunks).

Severity law (mirrors pipeline/mimir/tools/integrity.py): `hard` exits nonzero
(fix BEFORE the review workflow); `soft` lands in the report for the workflow's
attention. Adjudication-shaped findings (the creature MC-shape compiler gap)
are ROUTED to the workflow — reported once, systemic, never "fixed" here
(docket-first law). Documented-expected states are whitelisted BY NAME.

Ledger trap honored: ledger._connect() opens read-write and runs executescript;
this tool NEVER calls it — rolls.db opens via sqlite3 mode=ro URI, and replay
uses only pure imports (engine.DiceStream/evaluate, ledger._roll_sha).

Output: build/modron/review/integrity-report.json (+ fixtures/, fleet/)
Run:    py -3.13 pipeline/modron/tools/integrity.py [check|snapshot|verify-snapshot]
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from fractions import Fraction
from itertools import product as iproduct
from pathlib import Path

HERE = Path(__file__).resolve()
MODRON_DIR = HERE.parents[1]                      # pipeline/modron
ROOT = HERE.parents[3]                            # repo root
sys.path.insert(0, str(MODRON_DIR))

from modron import ENGINE_VERSION                                  # noqa: E402
from modron import analysis, conventions, rollables                # noqa: E402
from modron import modifiers as modlib                             # noqa: E402
from modron import registry as rollreg                             # noqa: E402
from modron import semantics, store as mstore                      # noqa: E402
from modron.engine import DiceStream, evaluate, transform_crit     # noqa: E402
from modron.grammar import (Bin, Dice, DiceSyntaxError, Func, Neg,  # noqa: E402
                            Num, normal_form, parse)
from modron.ledger import _roll_sha                                # noqa: E402

REVIEW = ROOT / "build/modron/review"
OUT = REVIEW / "integrity-report.json"
FIXTURES = REVIEW / "fixtures/math-fixtures.json"
FLEET_DIR = REVIEW / "fleet"
SNAPSHOT = REVIEW / "store-snapshot.json"
ROLLS_DB = ROOT / "build/modron/rolls.db"
HANDBOOK = ROOT / "build/mimir/handbook.db"
LAW_DIR = ROOT / "pipeline/mechanus/mechanus/data/law"
FGG_DIR = ROOT / "build/mechanus/fgg-text"
DATA_DIR = MODRON_DIR / "data"

KNOWN_VIEWS = {"2e", "2e-planescape", "5e-2014", "5e-2024"}
APPLIES_VOCAB = {"attack", "save", "check", "damage", "ability", "proficiency",
                 "initiative"}
SOURCE_KINDS = {"core", "mimir", "mechanus", "table", "fiat"}

# ---- known-intentional whitelists (build/modron/review/known-intentional.json) ----
# used_at ids that dangle until their books pour (TSR 2634 planes; mancatcher
# item; plane:smoke joined via the audit's scald retarget, C-4-inner-b-04):
KNOWN_USED_AT_DANGLERS = {
    "plane:inner", "plane:water", "plane:air", "plane:steam", "plane:ice",
    "plane:salt", "plane:magma", "plane:positive-energy", "plane:negative-energy",
    "plane:smoke", "item:planar-mancatcher",
}
# the eph-prefixed fiat row written before the rol:fiat: prefix existed:
KNOWN_ID_PREFIX_ODDITIES = {"rol:eph:ae9cb22ecebb"}
# the hp-not-derivable roster as ADJUDICATED by the audit (G-4): the G11 nine
# minus Parakk (now derives — roster delta filed to Mimir) plus the five new
# members (Koe/Omott/Grixitt = extractor miss, Ylem = needs vision, Patch =
# honest plant). Membership changes from here are findings again.
KNOWN_HP_INFO_NAMES = {
    "black marian", "estavan", "farrow", "iarmid", "ly'kritch",
    "saure", "the us", "verden",
    "koe", "omott", "patch", "the grixitt", "ylem",
}

# product → reflow dir (verified on disk 2026-06-06; the dumper shares this map)
REFLOW_MAP = {
    "Planes of Chaos (TSR 2603)":
        ROOT / "build/planes-of-chaos/tsr2603-planes-of-chaos/reflow",
    "In the Cage: A Guide to Sigil (TSR 2609)":
        ROOT / "build/in-the-cage-a-guide-to-sigil/ddps-inthecage/reflow",
    "The Inner Planes (TSR 2634)":
        ROOT / "build/the-inner-planes/planescape-2634-inner-planes/reflow",
    # PWH added with the D10/D12/D13 acceptance round, 2026-06-06:
    "The Planewalker's Handbook (TSR 2620)":
        ROOT / "build/the-planewalker-s-handbook/planescape-2620-the-planewalkers-handbook/reflow",
    "Planes of Law (TSR 2607), Acheron booklet":
        ROOT / "build/planes-of-law/ddps-planesoflaw-ii/reflow",
    "Planes of Conflict (TSR 2615), Liber Malevolentiae":
        ROOT / "build/planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae/reflow",
}
# product hints inside free-text notes (conventions pack notes cite inline):
NOTE_PRODUCT_HINTS = [
    ("Planes of Chaos", "Planes of Chaos (TSR 2603)"),
    ("Planes of Conflict", "Planes of Conflict (TSR 2615), Liber Malevolentiae"),
    ("In the Cage", "In the Cage: A Guide to Sigil (TSR 2609)"),
    ("The Inner Planes", "The Inner Planes (TSR 2634)"),
    ("The Planewalker's Handbook", "The Planewalker's Handbook (TSR 2620)"),
    ("Planes of Law", "Planes of Law (TSR 2607), Acheron booklet"),
]

_PAGE_RE = re.compile(r"reflow\s+p(\d{1,4})(?:\s*[-–]\s*(\d{1,4}))?")
_LAW_REF_RE = re.compile(r"law:[a-z0-9*:\-]+")
_ROLLABLE_REF_RE = re.compile(r"\b(?:tbl|spc|lkp|enc|dmg):2e:[a-z0-9:\-]+\*?")

# fgg-text pre-grep keywords for the court (pending-FG&G refs + provisional flags)
FGG_KEYWORDS = {
    "bless-2e": ["bless"],
    "curse-2e": ["curse", "bless"],
    "weapon-specialization": ["specialization"],
    "rear-attack": ["rear of", "from the rear", "rear attack"],
    "higher-ground": ["higher ground"],
    "magic-weapon-plus": ["magical weapon", "magic weapon"],
    "_provisional:reaction-bands": ["reaction"],
    "_provisional:fractional-hd": ["hit dice"],
    "_provisional:class-hd": ["hit points", "hit dice"],
    "_provisional:0-level": ["0-level", "zero-level"],
}


# ===========================================================================
# Independent PMF enumerator — implements MODRON.md §4 semantics from the DOC,
# deliberately NOT engine.py's code paths (the point is independence).
# Unsupported (explode, fudge) → SkipExpr with a note.
# ===========================================================================

class SkipExpr(Exception):
    pass


_ENUM_GUARD = 1_500_000


def _i_cmp(cmp, face: int) -> bool:
    op, n = cmp.op, cmp.value
    return {"=": face == n, "<": face < n, ">": face > n,
            "<=": face <= n, ">=": face >= n}[op]


def _i_die_outcomes(node: Dice) -> dict[tuple[int, int], Fraction]:
    """Per-die distribution over (natural, value) pairs. §4 order:
    reroll (initial face only) → clamp(min/max). Explode unsupported here."""
    if node.sides == "F":
        raise SkipExpr("fudge dice: enumerator doesn't model them")
    sides = int(node.sides)
    faces = list(range(1, sides + 1))
    p1 = Fraction(1, sides)

    rerolls = [op for op in node.ops if op.kind == "reroll"]
    explodes = [op for op in node.ops if op.kind == "explode"]
    clamps = [op for op in node.ops if op.kind in ("min", "max")]
    if explodes:
        raise SkipExpr("explode: enumerator skips (unit-tested elsewhere)")
    if len(rerolls) > 1:
        raise SkipExpr("multiple reroll ops")

    nat: dict[int, Fraction] = {f: p1 for f in faces}
    if rerolls:
        op = rerolls[0]
        matched = [f for f in faces if _i_cmp(op.cmp, f)]
        if len(matched) == len(faces):
            raise SkipExpr("reroll matches every face")
        if op.once:
            out: dict[int, Fraction] = {}
            p_match = sum(nat[f] for f in matched)
            for f in faces:
                if f not in matched:
                    out[f] = out.get(f, Fraction(0)) + nat[f]
                out[f] = out.get(f, Fraction(0)) + p_match * p1
            nat = out
        else:  # reroll-forever: uniform over the keepers
            keepers = [f for f in faces if f not in matched]
            nat = {f: Fraction(1, len(keepers)) for f in keepers}

    pairs: dict[tuple[int, int], Fraction] = {}
    for f, p in nat.items():
        v = f
        for op in clamps:
            if op.kind == "min" and v < op.n:
                v = op.n
            elif op.kind == "max" and v > op.n:
                v = op.n
        pairs[(f, v)] = pairs.get((f, v), Fraction(0)) + p
    return pairs


def _i_group_pmf(node: Dice) -> dict[int, Fraction]:
    """Whole-group PMF: keep/drop and cs/cf simulated per ENGINE semantics
    (rank by value; count successes on kept NATURALS)."""
    pairs = _i_die_outcomes(node)
    keeps = [op for op in node.ops if op.kind in ("kh", "kl", "dh", "dl")]
    counts = [op for op in node.ops if op.kind in ("cs", "cf")]

    if not keeps and not counts:
        # plain sum: independent DP convolution over values
        vals: dict[int, Fraction] = {}
        for (f, v), p in pairs.items():
            vals[v] = vals.get(v, Fraction(0)) + p
        acc: dict[int, Fraction] = {0: Fraction(1)}
        for _ in range(node.count):
            nxt: dict[int, Fraction] = {}
            for a, pa in acc.items():
                for v, pv in vals.items():
                    nxt[a + v] = nxt.get(a + v, Fraction(0)) + pa * pv
            acc = nxt
        return acc

    support = sorted(pairs)
    if len(support) ** node.count > _ENUM_GUARD:
        raise SkipExpr(f"{len(support)}^{node.count} tuples exceeds enumerator guard")
    out: dict[int, Fraction] = {}
    for combo in iproduct(support, repeat=node.count):
        p = Fraction(1)
        for pair in combo:
            p *= pairs[pair]
        dice = [{"nat": f, "val": v, "kept": True} for (f, v) in combo]
        for op in keeps:  # sequential, stable sort by value — engine's exact walk
            alive = [d for d in dice if d["kept"]]
            ranked = sorted(alive, key=lambda d: d["val"])
            n = min(op.n, len(alive))
            if op.kind == "kh":
                doomed = ranked[:-n] if n else ranked
            elif op.kind == "kl":
                doomed = ranked[n:]
            elif op.kind == "dh":
                doomed = ranked[len(ranked) - n:]
            else:
                doomed = ranked[:n]
            for d in doomed:
                d["kept"] = False
        kept = [d for d in dice if d["kept"]]
        if counts:
            total = 0
            for d in kept:
                for op in counts:
                    if _i_cmp(op.cmp, d["nat"]):
                        total += 1 if op.kind == "cs" else -1
            if all(op.kind == "cf" for op in counts):
                total = -total
        else:
            total = sum(d["val"] for d in kept)
        out[total] = out.get(total, Fraction(0)) + p
    return out


def _i_combine(a: dict, b: dict, fn) -> dict[int, Fraction]:
    if len(a) * len(b) > _ENUM_GUARD:
        raise SkipExpr("combine exceeds enumerator guard")
    out: dict[int, Fraction] = {}
    for va, pa in a.items():
        for vb, pb in b.items():
            v = fn(va, vb)
            out[v] = out.get(v, Fraction(0)) + pa * pb
    return out


def _i_pmf(node, rounding: str = "down") -> dict[int, Fraction]:
    import math as _m
    if isinstance(node, Num):
        return {node.value: Fraction(1)}
    if isinstance(node, Dice):
        return _i_group_pmf(node)
    if isinstance(node, Neg):
        return {-v: p for v, p in _i_pmf(node.child, rounding).items()}
    if isinstance(node, Bin):
        a, b = _i_pmf(node.left, rounding), _i_pmf(node.right, rounding)
        if node.op == "+":
            return _i_combine(a, b, lambda x, y: x + y)
        if node.op == "-":
            return _i_combine(a, b, lambda x, y: x - y)
        if node.op == "*":
            return _i_combine(a, b, lambda x, y: x * y)
        div = (lambda x, y: _m.ceil(x / y)) if rounding == "up" else \
            (lambda x, y: _m.floor(x / y))
        return _i_combine(a, b, div)
    if isinstance(node, Func):
        if node.name in ("adv", "dis", "ea"):
            count, keep = {"adv": (2, "kh"), "dis": (2, "kl"), "ea": (3, "kh")}[node.name]
            rewritten = _i_first_die(node.args[0], count, keep)
            return _i_pmf(rewritten, rounding)
        if node.name == "repeat":
            inner = _i_pmf(node.args[0], rounding)
            acc: dict[int, Fraction] = {0: Fraction(1)}
            for _ in range(node.args[1].value):
                acc = _i_combine(acc, inner, lambda x, y: x + y)
            return acc
        if node.name == "abs":
            out: dict[int, Fraction] = {}
            for v, p in _i_pmf(node.args[0], rounding).items():
                out[abs(v)] = out.get(abs(v), Fraction(0)) + p
            return out
        if node.name in ("floor", "ceil", "round"):
            return _i_pmf(node.args[0], rounding)
        if node.name in ("min", "max"):
            fn = min if node.name == "min" else max
            acc = _i_pmf(node.args[0], rounding)
            for a in node.args[1:]:
                acc = _i_combine(acc, _i_pmf(a, rounding), lambda x, y: fn(x, y))
            return acc
        raise SkipExpr(f"enumerator has no path for {node.name}()")
    raise SkipExpr(f"unknown node {node!r}")


def _i_first_die(node, count: int, keep: str):
    """Independent adv/dis/ea rewrite: first plain single die -> NdXkh/kl1."""
    from modron.grammar import DieOp
    done = False

    def walk(n):
        nonlocal done
        if done:
            return n
        if isinstance(n, Dice):
            if n.count == 1 and not n.ops:
                done = True
                return Dice(count, n.sides, (DieOp(keep, n=1),))
            raise SkipExpr("adv on a manipulated die")
        if isinstance(n, Bin):
            left = walk(n.left)
            right = n.right if done else walk(n.right)
            return Bin(n.op, left, right)
        if isinstance(n, Neg):
            return Neg(walk(n.child))
        if isinstance(n, Func):
            return Func(n.name, tuple(walk(a) for a in n.args))
        return n

    out = walk(node)
    if not done:
        raise SkipExpr("adv found no die")
    return out


# ===========================================================================
# Shingle law (cite-only paraphrase enforcement)
# ===========================================================================

def _norm_tokens(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def _shingles(text: str, k: int = 10) -> set[str]:
    toks = _norm_tokens(text)
    return {" ".join(toks[i:i + k]) for i in range(len(toks) - k + 1)}


def _reflow_pages(product: str, page_text: str) -> list[Path]:
    """Resolve 'reflow p88-89 / book p84-85' style refs to page files."""
    base = REFLOW_MAP.get(product)
    if base is None:
        return []
    out = []
    for m in _PAGE_RE.finditer(page_text):
        lo = int(m.group(1))
        hi = int(m.group(2)) if m.group(2) else lo
        # 'p88-89' is a page range; 'p88-8' style OCR is not expected here
        if hi < lo:
            hi = lo
        for n in range(lo, hi + 1):
            out.append(base / f"page-{n:04d}.txt")
    return out


def _entry_strings(row: dict) -> list[str]:
    """Each Modron-authored STRING in a rollables entry, separately — the
    paraphrase law tests running text, never synthetic cross-cell adjacency
    (concatenating table cells manufactures 10-token runs the entry doesn't
    actually contain)."""
    parts = [row.get("label", ""), str(row.get("notes", ""))]
    if "table" in row:
        parts += [str(e.get("result", "")) for e in row["table"].get("entries", [])]
    if "rows" in row:
        for r in row["rows"]:
            parts += [str(v) for v in r.values()]
    if "spec" in row:
        parts.append(str(row["spec"].get("label", "")))
    if "encounter" in row:
        parts.append(str(row["encounter"].get("creature", {}).get("name", "")))
    return [p for p in parts if p]


# ===========================================================================
# The check groups
# ===========================================================================

def run_checks() -> dict:
    V: list[dict] = []
    info: dict = {}

    def v(check: str, sev: str, ref: str, detail: str, routed: bool = False):
        row = {"check": check, "sev": sev, "ref": ref, "detail": detail}
        if routed:
            row["routed_to_workflow"] = True
        V.append(row)

    # ---- R: loads ---------------------------------------------------------
    packs_raw: dict[str, dict] = {}
    packs_merged: dict[str, dict] = {}
    for view in sorted(KNOWN_VIEWS):
        raw_path = DATA_DIR / "conventions" / f"{view}.json"
        packs_raw[view] = json.loads(raw_path.read_text(encoding="utf-8"))
        try:
            packs_merged[view] = conventions.get_pack(view)
        except Exception as e:
            v("pack_loads", "hard", view, f"get_pack failed: {e}")
            continue

    kind_count = 0
    for view, raw in packs_raw.items():
        merged = packs_merged.get(view, {})
        for kind, spec in (raw.get("checks") or {}).items():
            kind_count += 1
            ref = f"{view}:{kind}"
            try:
                parse(spec["roll"])
            except (KeyError, DiceSyntaxError) as e:
                v("kind_roll_parses", "hard", ref, f"roll template: {e}")
            for lst in ("add", "sub", "add_to_target", "params", "categories"):
                val = spec.get(lst)
                if val is not None and not (isinstance(val, list)
                                            and all(isinstance(x, str) for x in val)):
                    v("kind_list_fields", "hard", ref, f"{lst} must be a string list")
            vs = spec.get("vs")
            if vs is not None and not isinstance(vs, (int, str)):
                v("kind_vs_shape", "hard", ref, f"vs must be int|param-name, got {vs!r}")
            if "vs_template" in spec:
                dummy = {p: 2 for p in spec.get("params", [])}
                try:
                    semantics._eval_template(spec["vs_template"], dummy,
                                             what=f"integrity:{ref}")
                except Exception as e:
                    v("kind_vs_template", "hard", ref, f"vs_template: {e}")
            for dname, dtemplate in (spec.get("derived") or {}).items():
                dummy = {p: 2 for p in spec.get("params", [])}
                dummy["total"] = 2
                try:
                    semantics._eval_template(dtemplate, dummy, what=f"integrity:{ref}:{dname}")
                except Exception as e:
                    v("kind_derived_template", "hard", f"{ref}:{dname}", f"{e}")
            band_tables = {"": spec.get("bands") or []}
            for col, table in ((spec.get("bands_by") or {}).get("tables") or {}).items():
                band_tables[col] = table
            for col, bands in band_tables.items():
                if not bands:
                    continue
                srt = sorted(bands, key=lambda b: b["min"])
                for a, b in zip(srt, srt[1:]):
                    if b["min"] != a["max"] + 1:
                        v("kind_bands_contiguous", "hard", f"{ref}:{col}" if col else ref,
                          f"gap/overlap between {a['max']} and {b['min']}")

    # modifiers — own placeholder fill (6 = a real die size). modlib's
    # _validate_effects fills placeholders with 1, so the SHIPPING shapes
    # 1d{die} / {n}d{die} would be REFUSED at define_modifier time — a latent
    # validator bug, filed once below as a routed finding.
    mod_reg = modlib.registry()
    validator_refuses: list[str] = []
    for mid, row in sorted(mod_reg.items()):
        ref = f"modifier:{mid} ({row.get('_file')})"
        for e in row["effects"]:
            if e.get("op") not in modlib._EFFECT_OPS:
                v("modifier_effects_valid", "hard", ref, f"unknown op {e.get('op')!r}")
            if e.get("op") in ("add", "sub", "extra_crit_dice"):
                expr = str(e["expr"])
                try:
                    parse(expr.format(**{k: 6 for k in modlib._placeholders(expr)}))
                except (DiceSyntaxError, KeyError, IndexError) as err:
                    v("modifier_effects_valid", "hard", ref, f"expr {expr!r}: {err}")
            if e.get("op") == "reroll" and "cmp" not in e:
                v("modifier_effects_valid", "hard", ref, "reroll effect needs a cmp")
            if e.get("op") in ("min_die", "max_die") and "value" not in e:
                v("modifier_effects_valid", "hard", ref, f"{e['op']} needs a value")
            if e.get("op") in ("mult_total", "div_total") and not isinstance(e.get("by"), int):
                v("modifier_effects_valid", "hard", ref, f"{e['op']} needs integer 'by'")
        try:
            modlib._validate_effects(row["effects"])
        except Exception:
            validator_refuses.append(mid)
    if validator_refuses:
        v("validator_placeholder_fill", "soft", f"modifiers {validator_refuses}",
          "modlib._validate_effects fills placeholders with 1, so these SHIPPING "
          "effect shapes (e.g. '1d{die}') are refused by the very validator that "
          "guards define_modifier inline/local writes — latent code bug (L4 candidate): "
          "fill with a lawful die size instead.", routed=True)
        views = row.get("views") or []
        if not set(views) <= KNOWN_VIEWS:
            v("modifier_views_vocab", "hard", ref, f"unknown views {set(views) - KNOWN_VIEWS}")
        applies = set(row.get("applies_to") or [])
        if not applies <= APPLIES_VOCAB:
            v("modifier_applies_vocab", "hard", ref, f"unknown applies_to {applies - APPLIES_VOCAB}")
        if row.get("stacking", "named") not in ("named", "untyped"):
            v("modifier_stacking_vocab", "hard", ref, f"stacking={row.get('stacking')!r}")
        src = row.get("source") or {}
        if src.get("kind") not in SOURCE_KINDS or not str(src.get("ref", "")).strip():
            v("modifier_source_present", "hard", ref, f"source={src!r}")
    info["modifiers"] = len(mod_reg)

    # rollables registry (load itself enforces source/coverage/dupes/spec-parse)
    try:
        reg = rollreg.registry()
    except Exception as e:
        v("registry_loads", "hard", "rollables", str(e))
        reg = {}
    info["rollables"] = len(reg)
    for rid, row in sorted(reg.items()):
        if row.get("kind") == "spec" and "check" in row["spec"]:
            ckind = row["spec"]["check"].get("kind")
            try:
                semantics.conventions.get_check_spec("2e-planescape", ckind)
            except Exception as e:
                v("rollable_check_kind_exists", "hard", rid, f"{ckind!r}: {e}")
        if row.get("kind") == "encounter":
            na = row["encounter"].get("number_appearing")
            if na and not rollables.text_to_expr(str(na)):
                v("encounter_number_parses", "hard", rid, f"number_appearing {na!r}")
        for xref in _ROLLABLE_REF_RE.findall(str(row.get("notes", "")) + row.get("label", "")):
            if xref.endswith("*"):  # family wildcard, e.g. spc:2e:sigil:mancatcher-*
                prefix = xref.rstrip("*")
                if not any(k.startswith(prefix) for k in reg):
                    v("rollable_xref_resolves", "hard", rid, f"no id matches family {xref!r}")
            elif xref not in reg:
                v("rollable_xref_resolves", "hard", rid, f"note cites missing {xref!r}")

    # used_at resolution (soft; known danglers whitelisted by name)
    used_at_status: dict[str, bool] = {}
    if HANDBOOK.exists():
        con = sqlite3.connect(f"file:{HANDBOOK.as_posix()}?mode=ro", uri=True)
        admitted = {r[0] for r in con.execute("SELECT id FROM entities")}
        con.close()
        targets = sorted({u for row in reg.values() for u in (row.get("used_at") or [])})
        for t in targets:
            used_at_status[t] = t in admitted
            if t not in admitted and t not in KNOWN_USED_AT_DANGLERS:
                v("used_at_resolves", "soft", t, "NEW dangler (not in the known-intentional set)")
    info["used_at"] = used_at_status

    # ---- P: pending-ref resolution feed ------------------------------------
    minted: dict[str, str] = {}            # law_id -> source file
    id_schemes: dict[str, str] = {}
    for law_file in sorted(LAW_DIR.glob("*.json")):
        d = json.loads(law_file.read_text(encoding="utf-8"))

        def walk(o):
            if isinstance(o, dict):
                lid = o.get("law_id")
                if isinstance(lid, str):
                    minted[lid] = law_file.name
                for vv in o.values():
                    walk(vv)
            elif isinstance(o, list):
                for vv in o:
                    walk(vv)
        walk(d)
        if isinstance(d, dict) and "_id_scheme" in d:
            id_schemes[d.get("_family", law_file.stem)] = str(d["_id_scheme"])
    info["minted_law_ids"] = len(minted)

    def law_candidates(stated: str) -> list[str]:
        refs = _LAW_REF_RE.findall(stated)
        cands: list[str] = []
        for r in refs:
            if r in minted:
                cands.append(r)
                continue
            if "*" in r:
                prefix = r.split("*", 1)[0]
                cands.extend(i for i in sorted(minted) if i.startswith(prefix))
        if cands:
            return cands[:10]
        # token-overlap ranking (handles plane-env -> plane-environment renames)
        toks = set(_norm_tokens(" ".join(refs))) - {"law", "pending"}
        scored = sorted(((len(toks & set(_norm_tokens(i))), i) for i in minted),
                        reverse=True)
        return [i for s, i in scored[:5] if s >= 2]

    fgg_texts: dict[str, str] = {}
    if FGG_DIR.exists():
        for p in sorted(FGG_DIR.glob("p*.txt")):
            fgg_texts[p.name] = p.read_text(encoding="utf-8", errors="replace")

    def fgg_candidates(key: str) -> list[dict]:
        kws = FGG_KEYWORDS.get(key, [])
        scored = []
        for fname, text in fgg_texts.items():
            low = text.lower()
            hits = sum(low.count(k.lower()) for k in kws)
            if hits:
                line = next((ln.strip() for ln in text.splitlines()
                             if any(k.lower() in ln.lower() for k in kws)), "")
                scored.append((hits, fname, line[:160]))
        scored.sort(reverse=True)
        return [{"file": (FGG_DIR / f).as_posix(), "hits": h, "line": ln}
                for h, f, ln in scored[:3]]

    pending: list[dict] = []
    for mid, row in sorted(mod_reg.items()):
        stated = str((row.get("source") or {}).get("ref", ""))
        if "pending" not in stated.lower():
            continue
        rec = {"where": f"data/modifiers/{row.get('_file')}#{mid}", "stated": stated}
        if "law:" in stated:
            if "M7" in stated:
                rec["status"] = "parked"
            else:
                cands = law_candidates(stated)
                rec["status"] = "minted-exact" if (
                    len(cands) == 1 and cands[0] in stated) else "minted-candidates"
                rec["candidates"] = cands
        else:
            rec["status"] = "fgg-candidates"
            rec["candidates"] = fgg_candidates(mid)
        pending.append(rec)

    for view, raw in packs_raw.items():
        blob = json.dumps(raw, ensure_ascii=False)
        for kind, spec in (raw.get("checks") or {}).items():
            notes = " ".join(semantics.list_wrap(spec.get("notes")))
            if "pending Mechanus" in notes:
                stated = notes[notes.index("pending Mechanus"):][:160]
                pending.append({"where": f"data/conventions/{view}.json#checks.{kind}",
                                "stated": stated, "status": "minted-candidates",
                                "candidates": law_candidates(notes)})
        if "pending pour" in blob and view == "2e":
            pending.append({"where": f"data/conventions/{view}.json#sources",
                            "stated": "For Gold & Glory (free retroclone, pending pour)",
                            "status": "fgg-pack-note",
                            "detail": "fgg-text cache exists (385 pages) — court-fgg proposes "
                                      "per-kind cites; pack-level note retires in the apply pass"})
    for rid, row in sorted(reg.items()):
        notes = str(row.get("notes", ""))
        if "pending Mechanus M7" in notes:
            pending.append({"where": f"data/rollables/planescape-2e.json#{rid}",
                            "stated": notes[notes.index("pending"):][:120],
                            "status": "parked"})
        elif "pending Mechanus" in notes:
            pending.append({"where": f"data/rollables/planescape-2e.json#{rid}",
                            "stated": notes[notes.index("pending"):][:160],
                            "status": "minted-candidates",
                            "candidates": law_candidates(notes)})
    # The four FG&G-provisional flags (reaction bands / fractional HD /
    # class-HD ladder / 0-level) were court-ruled and APPLIED 2026-06-06
    # (correction-docket lanes L1+L4): reaction = the Table 10.7 disposition
    # matrix, 1/2 HD = 2d2, per-class dice caps + ILL, 0-level both glyphs
    # with the per-profession note. They no longer feed the court.
    # ref-ADDITION candidates: minted law now governs kinds that carry no ref:
    for kind, needle in (("limbo_miniflux", "miniflux"), ("styx_memory", "styx")):
        hits = [i for i in sorted(minted) if needle in i]
        if hits:
            notes = " ".join(semantics.list_wrap(
                packs_raw["2e-planescape"]["checks"][kind].get("notes")))
            if "law:" not in notes:
                pending.append({"where": f"data/conventions/2e-planescape.json#checks.{kind}",
                                "stated": "(no law ref today)", "status": "ref-addition",
                                "candidates": hits})
    info["pending_refs"] = len(pending)

    # ---- S: shingle test (cite-only paraphrase law) -------------------------
    # Hits are PRE-CONFIRMED lane-C findings: data edits are docket-first, so a
    # leak is routed to the workflow (soft + routed), never silently reworded here.
    def shingle_check(ref: str, own_texts: list[str], pages: list[Path]):
        per_text = [(_shingles(t), t) for t in own_texts]
        if not any(s for s, _ in per_text):
            return
        for page in pages:
            if not page.exists():
                v("witness_page_exists", "hard", ref, f"cited page missing: {page.as_posix()}")
                continue
            page_sh = _shingles(page.read_text(encoding="utf-8", errors="replace"))
            for own, text in per_text:
                shared = own & page_sh
                if shared:
                    v("paraphrase_shingle", "soft", ref,
                      f"10-token shingle shared with {page.name}: "
                      f"{sorted(shared)[0][:120]!r} (in: {text[:80]!r})", routed=True)

    for rid, row in sorted(reg.items()):
        src = row.get("source") or {}
        if not src.get("cite_only"):
            continue
        pages = _reflow_pages(src.get("product", ""), str(src.get("page", "")))
        if not pages:
            v("witness_resolvable", "hard", rid,
              f"no reflow pages resolve for {src.get('product')!r} {src.get('page')!r}")
        shingle_check(rid, _entry_strings(row), pages)

    for kind, spec in (packs_raw["2e-planescape"].get("checks") or {}).items():
        for note in semantics.list_wrap(spec.get("notes")):
            for hint, product in NOTE_PRODUCT_HINTS:
                if hint in note:
                    shingle_check(f"2e-planescape:{kind}", [note],
                                  _reflow_pages(product, note))
                    break

    for mid, row in sorted(mod_reg.items()):
        stated = str((row.get("source") or {}).get("ref", ""))
        if "witness:" not in stated:
            continue
        for hint, product in NOTE_PRODUCT_HINTS:
            if hint in stated:
                shingle_check(f"modifier:{mid}",
                              [row.get("label", ""), row.get("notes", "")],
                              _reflow_pages(product, stated))
                break

    # ---- D: math lane (fully mechanical) ------------------------------------
    fixtures: list[dict] = []
    corpus: dict[str, str] = {}    # expr -> origin

    def add_expr(expr: str, origin: str):
        e = str(expr).strip()
        if e and e not in corpus:
            corpus[e] = origin

    for rid, row in sorted(reg.items()):
        if row.get("kind") == "spec" and row["spec"].get("expr"):
            add_expr(row["spec"]["expr"], rid)
        if row.get("kind") == "table":
            add_expr(row["table"].get("dice", "1d100"), rid)
        if row.get("kind") == "lookup":
            for r in row.get("rows", []):
                e = r.get("expr")
                if e and e != "none":
                    add_expr(e, rid)
        if row.get("kind") == "encounter":
            t = rollables.text_to_expr(str(row["encounter"].get("number_appearing", "")))
            if t:
                add_expr(t["expr"], rid)
    for view, raw in packs_raw.items():
        for kind, spec in (raw.get("checks") or {}).items():
            if "roll" in spec:
                add_expr(spec["roll"], f"{view}:{kind}")
    if ROLLS_DB.exists():
        con = sqlite3.connect(f"file:{ROLLS_DB.as_posix()}?mode=ro", uri=True)
        for (e,) in con.execute("SELECT DISTINCT expr_resolved FROM rolls WHERE method='rolled'"):
            add_expr(e, "ledger")
        con.close()
    for e in ("2d6", "3d6", "4d6kh3", "2d20kh1", "2d20kl1", "3d20kh1", "2d6ro<=2",
              "1d20min10", "2d10", "1d100", "1d4+1", "3d6+2", "(2d8+5)*2", "20d6",
              "12d8+24", "4d6min3cs>=3", "adv(1d20+5)", "repeat(2d6+3, 3)"):
        add_expr(e, "stress")

    for expr, origin in sorted(corpus.items()):
        fx = {"expr": expr, "origin": origin}
        try:
            node = parse(expr)
        except DiceSyntaxError as e:
            v("expr_parses", "hard", f"{origin}:{expr}", str(e))
            continue
        # D2: normal-form round-trip idempotence
        nf = normal_form(node)
        nf2 = normal_form(parse(nf))
        if nf != nf2:
            v("normal_form_roundtrip", "hard", expr, f"{nf!r} reparses to {nf2!r}")
        fx["normal_form"] = nf
        # D1: independent PMF vs analysis.pmf
        try:
            mine = _i_pmf(node)
            theirs, _notes = analysis.pmf(node)
            if mine != theirs:
                diff_keys = sorted(set(mine) ^ set(theirs))[:6]
                worst = sorted((abs(mine.get(k, Fraction(0)) - theirs.get(k, Fraction(0))), k)
                               for k in set(mine) | set(theirs))[-1]
                # a divergence on a CORPUS expr poisons live crosschecks (hard);
                # a stress-set-only divergence is a latent code finding for the
                # docket (soft + routed) — the dice that actually fell are clean.
                sev = "hard" if origin != "stress" else "soft"
                v("pmf_conformance", sev, f"{origin}:{expr}",
                  f"independent enumerator (engine semantics: count-successes on "
                  f"kept NATURALS) disagrees with analysis.pmf "
                  f"(support diff {diff_keys}; worst |Δp| {float(worst[0]):.3e} at "
                  f"{worst[1]}) — clamp+count combos: analysis counts post-clamp "
                  f"VALUES, engine counts naturals; MODRON.md §4 pipeline order "
                  f"implies value-counting, so WHICH side is wrong is an "
                  f"adjudication (L4 + doc)", routed=(sev == "soft"))
                fx["verdict"] = "MISMATCH"
            else:
                fx["verdict"] = "match"
                fx["support"] = [min(mine), max(mine)]
                mean = sum((Fraction(k) * p for k, p in mine.items()), Fraction(0))
                fx["mean"] = str(mean)
        except SkipExpr as e:
            fx["verdict"] = f"skipped ({e})"
        except analysis.Inexact as e:
            fx["verdict"] = f"analysis-inexact ({e})"
        fixtures.append(fx)

    # D3: composition-order re-pin (V&V D1 — wraps LAST), outside the suite
    try:
        insts = modlib.resolve_mods(
            ["great-weapon-fighting",
             {"id": "brutal-critical", "params": {"n": 1, "die": 12}},
             "vulnerability"], view="5e-2014")
        comp = modlib.compose(parse("1d12+4"), insts, purpose="damage", crit=True)
        ok = (isinstance(comp.ast, Bin) and comp.ast.op == "*"
              and isinstance(comp.ast.right, Num) and comp.ast.right.value == 2)
        inner = comp.ast.left if ok else None
        ok = ok and isinstance(inner, Bin) and inner.op == "+" \
            and isinstance(inner.right, Dice) and not inner.right.ops
        base = inner.left if ok else None
        ok = ok and isinstance(base, Bin) and isinstance(base.left, Dice) \
            and any(op.kind == "reroll" for op in base.left.ops)
        if not ok:
            v("compose_wraps_last", "hard", "GWF+brutal+vulnerability",
              f"composition shape wrong: {normal_form(comp.ast)!r}")
        else:
            info["compose_pin"] = normal_form(comp.ast)
    except Exception as e:
        v("compose_wraps_last", "hard", "GWF+brutal+vulnerability", str(e))

    # D4: crit transforms honest
    try:
        node, _ = transform_crit(parse("2d6+3"), "double_dice")
        flat = normal_form(node)
        if "4d6" not in flat or "6" in flat.replace("4d6", "").replace("3", ""):
            pass  # shape asserted below structurally instead
        ok = isinstance(node, Bin) and isinstance(node.left, Dice) \
            and node.left.count == 4 and isinstance(node.right, Num) \
            and node.right.value == 3
        if not ok:
            v("crit_double_dice", "hard", "2d6+3", f"got {flat!r}")
        node2, notes2 = transform_crit(parse("2d6+3"), "none")
        if normal_form(node2) != normal_form(parse("2d6+3")) or not notes2:
            v("crit_none_unchanged", "hard", "2d6+3", "none must no-op WITH a note")
    except Exception as e:
        v("crit_transforms", "hard", "transform_crit", str(e))

    # D5: dice_stats honesty — guards trip to FLAGGED Monte Carlo
    st = analysis.stats("30d20kh3")
    if st.get("method") != "monte-carlo" or not any("estimated" in n for n in st.get("notes", [])):
        v("stats_mc_flagged", "hard", "30d20kh3",
          f"expected flagged monte-carlo, got method={st.get('method')!r}")

    FIXTURES.parent.mkdir(parents=True, exist_ok=True)
    FIXTURES.write_text(json.dumps(
        {"engine_version": ENGINE_VERSION, "fixtures": fixtures},
        indent=1, ensure_ascii=False), encoding="utf-8")
    info["math_fixtures"] = {
        "total": len(fixtures),
        "match": sum(1 for f in fixtures if f.get("verdict") == "match"),
        "skipped": sum(1 for f in fixtures if str(f.get("verdict", "")).startswith("skipped")),
    }

    # ---- E: ledger (fully mechanical) ----------------------------------------
    if not ROLLS_DB.exists():
        v("ledger_exists", "hard", "rolls.db", "missing")
    else:
        con = sqlite3.connect(f"file:{ROLLS_DB.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        sessions = [dict(r) for r in con.execute("SELECT * FROM sessions")]
        rolls = [dict(r) for r in con.execute("SELECT * FROM rolls ORDER BY ts, counter")]
        con.close()
        info["ledger"] = {"sessions": len(sessions), "rolls": len(rolls),
                          "fiat": sum(1 for r in rolls if r["method"] == "fiat")}

        commits = {}
        for s in sessions:
            sid = s["session_id"]
            commits[sid] = s["seed_commitment"]
            if s["status"] != "closed":
                v("session_sealed", "soft", sid, "session still open at audit time")
            digest = hashlib.sha256(bytes.fromhex(s["seed_secret_hex"])).hexdigest()
            if digest != s["seed_commitment"]:
                v("session_commitment", "hard", sid, "sha256(seed) != commitment")
            if s["engine_version"] != ENGINE_VERSION:
                v("session_engine_version", "hard", sid, s["engine_version"])
            counters = sorted(r["counter"] for r in rolls
                              if r["session_id"] == sid and r["seed_scope"] == "session")
            if counters != list(range(1, len(counters) + 1)):
                v("session_counters_dense", "hard", sid, f"counters {counters}")
            if counters and s["counter"] != counters[-1]:
                v("session_counter_matches", "hard", sid,
                  f"sessions.counter={s['counter']} but max roll counter={counters[-1]}")

        seeds = {s["session_id"]: bytes.fromhex(s["seed_secret_hex"]) for s in sessions}
        shas = set()
        replayed = 0
        for r in rolls:
            rid = r["roll_id"]
            if r["sha"] in shas:
                v("roll_sha_unique", "hard", rid, "duplicate sha")
            shas.add(r["sha"])
            if r["engine_version"] != ENGINE_VERSION:
                v("roll_engine_version", "hard", rid, r["engine_version"])
            if r["view"] is not None and r["view"] not in KNOWN_VIEWS:
                v("roll_view_known", "hard", rid, f"view={r['view']!r}")
            if r["method"] == "fiat":
                notes = json.loads(r["notes_json"] or "[]")
                if not any(str(n).startswith("FIAT:") and len(str(n)) > 6 for n in notes):
                    v("fiat_reason_present", "hard", rid, f"notes={notes!r}")
                if json.loads(r["groups_json"]) != []:
                    v("fiat_no_dice", "hard", rid, "fiat row carries dice groups")
                if r["seed_scope"] != "none":
                    v("fiat_seed_scope", "hard", rid, r["seed_scope"])
                if not rid.startswith("rol:fiat:") and rid not in KNOWN_ID_PREFIX_ODDITIES:
                    v("fiat_id_prefix", "soft", rid,
                      "fiat row without rol:fiat: prefix (only the known pre-prefix row is expected)")
                continue
            # rolled: re-derive faces, total, sha
            if r["seed_scope"] == "session":
                seed = seeds.get(r["session_id"])
                seed_id = commits.get(r["session_id"])
            else:
                seed = bytes.fromhex(r["seed_hex"])
                seed_id = r["seed_hex"]
            try:
                result = evaluate(parse(r["expr_resolved"]), DiceStream(seed, r["counter"]),
                                  rounding=r["rounding"], crit_effect=r["crit_effect"])
                groups = [g.to_dict() for g in result.groups]
                stored = json.loads(r["groups_json"])
                sha = _roll_sha(r["expr_resolved"], seed_id, r["counter"], stored,
                                r["total"], r["method"])
                if groups != stored:
                    v("roll_replay_faces", "hard", rid, "recomputed groups differ")
                if result.total != r["total"]:
                    v("roll_replay_total", "hard", rid,
                      f"recomputed {result.total} != stored {r['total']}")
                if sha != r["sha"]:
                    v("roll_replay_sha", "hard", rid, "recomputed sha differs")
                replayed += 1
            except Exception as e:
                v("roll_replay", "hard", rid, f"replay failed: {e}")
        info["ledger"]["replayed"] = replayed

    # ---- F: doc-claim counts ---------------------------------------------------
    server_src = (MODRON_DIR / "server.py").read_text(encoding="utf-8")
    n_tools = server_src.count("types.Tool(")
    if n_tools != 17:
        v("doc_tool_count", "hard", "server.py", f"{n_tools} types.Tool(...) != documented 17")
    info["tools"] = n_tools
    if ENGINE_VERSION != "1":
        v("doc_engine_version", "hard", "modron/__init__.py", ENGINE_VERSION)
    if info["rollables"] != 47:
        v("doc_rollables_count", "hard", "registry",
          f"{info['rollables']} != documented 47 (36 post-audit + 4 D13 item "
          "tables + 6 D12 chargen + planology-fortune, PWH round 2026-06-06)")
    if info["modifiers"] != 29:
        v("doc_modifier_count", "hard", "modifiers", f"{info['modifiers']} != documented 29 (28+overlay)")
    own_kinds = {view: len(raw.get("checks") or {}) for view, raw in packs_raw.items()}
    # 2e-planescape 6 -> 15: + hope_drain (Lane-E/D5) + 8 planar NWP kinds (D10), 2026-06-06
    if own_kinds != {"2e": 10, "2e-planescape": 15, "5e-2014": 7, "5e-2024": 0}:
        v("doc_kind_counts", "hard", "conventions", f"{own_kinds}")
    info["check_kinds"] = kind_count

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "--collect-only", "-q",
         "-p", "no:cacheprovider"],
        cwd=str(MODRON_DIR), capture_output=True, text=True, encoding="utf-8")
    m = re.search(r"(\d+) tests collected", proc.stdout)
    n_tests = int(m.group(1)) if m else -1
    if n_tests != 195:
        v("doc_test_count", "hard", "pytest --collect-only",
          f"collected {n_tests} != documented 195 (185 post-audit + 10 PWH-"
          f"acceptance pins, 2026-06-06; rc={proc.returncode})")
    info["tests_collected"] = n_tests

    # ---- G: fleet compile (read-only; outputs feed the lane-G chunks) -----------
    fleet_stats = {"entities": 0, "specs": 0, "by_flag": {}, "hp_info_names": [],
                   "creatures_thin": []}
    if HANDBOOK.exists():
        FLEET_DIR.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(f"file:{HANDBOOK.as_posix()}?mode=ro", uri=True)
        fleet_ids = [(r[0], r[1]) for r in con.execute(
            "SELECT id, type FROM entities WHERE type IN ('npc','creature') ORDER BY id")]
        con.close()
        hb = mstore._mimir_store().HandbookStore(HANDBOOK, readonly=True)
        try:
            for eid, etype in fleet_ids:
                env = hb.get(eid)
                if not env:
                    v("fleet_entity_loads", "hard", eid, "handbook get() returned nothing")
                    continue
                view = rollables.detect_view(env)
                pack = conventions.get_pack(view if view in KNOWN_VIEWS else "2e")
                specs = rollables.compile_entity(env, pack, view)
                fleet_stats["entities"] += 1
                fleet_stats["specs"] += len(specs)

                def bump(flag: str):
                    fleet_stats["by_flag"][flag] = fleet_stats["by_flag"].get(flag, 0) + 1

                non_prose = 0
                for s in specs:
                    if not s.get("from_prose"):
                        non_prose += 1
                    if s.get("unparsed"):
                        bump("unparsed")
                    if s.get("requires_confirmation"):
                        bump("requires_confirmation")
                    if s.get("ambiguous"):
                        bump("ambiguous")
                    cc = s.get("crosscheck") or {}
                    if cc.get("verdict") in ("MISMATCH", "OUT_OF_RANGE"):
                        bump(f"crosscheck_{cc['verdict']}")
                    if s.get("key") == "hp" and s.get("purpose") == "info":
                        bump("hp_info")
                        name = str(env.get("name", eid)).lower()
                        fleet_stats["hp_info_names"].append(env.get("name", eid))
                        if name not in KNOWN_HP_INFO_NAMES:
                            v("fleet_hp_info_roster", "soft", eid,
                              f"NEW hp-not-derivable entity {env.get('name')!r} "
                              "(not on the known G11 roster)")
                if etype == "creature" and non_prose <= 1:
                    fleet_stats["creatures_thin"].append(eid)
                slug = eid.replace(":", "-")
                (FLEET_DIR / f"{slug}.json").write_text(json.dumps(
                    {"id": eid, "type": etype, "name": env.get("name"),
                     "view": view, "specs": specs},
                    indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        finally:
            hb.close()
        if fleet_stats["creatures_thin"]:
            v("fleet_creature_shape_gap", "soft",
              f"{len(fleet_stats['creatures_thin'])} creatures",
              "MC-style flat fields (thac0/hit_dice at top level, no statblock "
              "sub-object) are invisible to statblock_2e — compiles to <=1 non-prose "
              "spec. SYSTEMIC, pre-confirmed; adjudication + L4 fix shape is lane G's.",
              routed=True)
        if fleet_stats["entities"] != 93:
            v("fleet_census", "hard", "handbook",
              f"{fleet_stats['entities']} compiled != 93 (71 npc + 22 creature — "
              "Mimir's Great-Audit re-pour promoted 6 quarantined creatures, "
              "2026-06-06)")
    info["fleet"] = fleet_stats

    # ---- report ------------------------------------------------------------------
    hard = [x for x in V if x["sev"] == "hard"]
    soft = [x for x in V if x["sev"] == "soft"]
    by_check: dict[str, int] = {}
    for x in V:
        by_check[x["check"]] = by_check.get(x["check"], 0) + 1
    return {"violations": V, "pending_refs": pending, "id_schemes": id_schemes,
            "info": info,
            "stats": {"hard": len(hard), "soft": len(soft), "by_check": by_check}}


# ===========================================================================
# Snapshot (the docket-first guarantee)
# ===========================================================================

def _snapshot_files() -> list[Path]:
    files = [ROLLS_DB, MODRON_DIR / "usage_counter.json"]
    files += sorted((DATA_DIR).rglob("*.json"))
    vnv = ROOT / "build/modron/vnv"
    if vnv.exists():
        files += sorted(vnv.glob("*.json"))
    return [f for f in files if f.exists()]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot() -> int:
    shas = {f.relative_to(ROOT).as_posix(): _sha(f) for f in _snapshot_files()}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps({"files": shas}, indent=1), encoding="utf-8")
    print(f"snapshot: {len(shas)} files -> {SNAPSHOT}")
    return 0


def verify_snapshot() -> int:
    want = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["files"]
    got = {f.relative_to(ROOT).as_posix(): _sha(f) for f in _snapshot_files()}
    changed = sorted(k for k in want if got.get(k) != want[k])
    missing = sorted(set(want) - set(got))
    new = sorted(set(got) - set(want))
    if not changed and not missing and not new:
        print(f"verify-snapshot: PASS — {len(want)} files byte-identical")
        return 0
    for k in changed:
        print(f"verify-snapshot: CHANGED {k}")
    for k in missing:
        print(f"verify-snapshot: MISSING {k}")
    for k in new:
        print(f"verify-snapshot: NEW {k}")
    return 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode == "snapshot":
        return snapshot()
    if mode == "verify-snapshot":
        return verify_snapshot()
    report = run_checks()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    st = report["stats"]
    inf = report["info"]
    print(f"integrity: {inf.get('check_kinds')} kinds · {inf.get('modifiers')} modifiers · "
          f"{inf.get('rollables')} rollables · ledger {inf.get('ledger', {})} · "
          f"fleet {inf.get('fleet', {}).get('entities')} entities / "
          f"{inf.get('fleet', {}).get('specs')} specs")
    print(f"math fixtures: {inf.get('math_fixtures')}; minted law ids: {inf.get('minted_law_ids')}; "
          f"pending refs: {inf.get('pending_refs')}; tools {inf.get('tools')}; "
          f"tests {inf.get('tests_collected')}")
    print(f"violations: {st['hard']} hard · {st['soft']} soft · {st['by_check']}")
    for x in report["violations"]:
        if x["sev"] == "hard":
            print(f"  HARD {x['check']:28} {x['ref']}: {x['detail'][:140]}")
    print(f"report -> {OUT}")
    return 1 if st["hard"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
