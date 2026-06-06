"""The modifier system: named effects as data, composition as AST transforms.

A modifier is a JSON row (data/modifiers/*.json or the local overlay) — or an
inline spec from any caller (DM, Mechanus mid-resolve, a backend). Either way
it carries a `source` {kind, ref} and the ledger records exactly what was
applied and who asserted it (MODRON.md §2.2).

Effect primitives (changeability axis #4 — add one function, registry picks it up):
    add / sub          {expr}                — append ± a term (flat or dice)
    d20_state          {state}               — advantage|disadvantage (pack machine)
    d20_upgrade        {key}                 — e.g. elven_accuracy
    reroll             {cmp, once, scope}    — GWF: cmp '<=2', once, scope 'damage'
    min_die / max_die  {value, scope}        — Reliable Talent: min 10 on the d20
    explode            {cmp?, scope}
    mult_total/div_total {by}                — vulnerability ×2 / resistance ÷2
    extra_crit_dice    {expr}                — Brutal Critical (applies_when 'crit')

scope ∈ d20 (sides==20) | damage (sides!=20) | all.
applies_when ∈ always | crit.
stacking ∈ named (same id collapses, noted) | untyped (stacks).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .grammar import Bin, Cmp, Dice, DieOp, Func, Neg, Node, Num, parse

PACKAGE_DIR = Path(__file__).resolve().parent.parent
MODIFIERS_DIR = PACKAGE_DIR / "data" / "modifiers"
OVERLAY_PATH = PACKAGE_DIR / "data" / "overrides" / "modifiers.local.json"

_CMP_RE = re.compile(r"^(<=|>=|<|>|=)?\s*(\d+)$")


class ModifierError(ValueError):
    pass


def _parse_cmp(s: str | int) -> Cmp:
    if isinstance(s, int):
        return Cmp("=", s)
    m = _CMP_RE.match(str(s).strip())
    if not m:
        raise ModifierError(f"bad cmp spec {s!r} (use e.g. '<=2', '=1', '20')")
    return Cmp(m.group(1) or "=", int(m.group(2)))


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def _load_registry() -> dict[str, dict]:
    reg: dict[str, dict] = {}
    if MODIFIERS_DIR.exists():
        for path in sorted(MODIFIERS_DIR.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                rows = json.load(f)
            for row in rows:
                row.setdefault("_file", path.name)
                reg[row["id"]] = row
    if OVERLAY_PATH.exists():  # local overlay wins (house dice tech, disclosed)
        with open(OVERLAY_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
        for row in rows:
            row.setdefault("_file", OVERLAY_PATH.name)
            row.setdefault("source", {"kind": "table", "ref": "local-overlay"})
            reg[row["id"]] = row
    return reg


def registry() -> dict[str, dict]:
    return _load_registry()


def search(query: str = "", view: str | None = None) -> list[dict]:
    q = (query or "").lower()
    out = []
    for row in _load_registry().values():
        if view and row.get("views") and view not in row["views"]:
            continue
        hay = " ".join([row["id"], row.get("label", ""), row.get("notes", ""),
                        " ".join(row.get("applies_to", []))]).lower()
        if q and q not in hay:
            continue
        out.append(row)
    return sorted(out, key=lambda r: r["id"])


def define_local(spec: dict) -> dict:
    """Guarded write of one modifier into the local overlay (server's define_modifier)."""
    required = {"id", "label", "effects"}
    missing = required - set(spec)
    if missing:
        raise ModifierError(f"modifier spec missing {sorted(missing)}")
    _validate_effects(spec["effects"])
    spec.setdefault("stacking", "named")
    spec.setdefault("source", {"kind": "table", "ref": "local-overlay"})
    rows = []
    if OVERLAY_PATH.exists():
        with open(OVERLAY_PATH, "r", encoding="utf-8") as f:
            rows = json.load(f)
    rows = [r for r in rows if r["id"] != spec["id"]] + [spec]
    OVERLAY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OVERLAY_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    tmp.replace(OVERLAY_PATH)
    return spec


_EFFECT_OPS = {"add", "sub", "d20_state", "d20_upgrade", "reroll", "min_die",
               "max_die", "explode", "mult_total", "div_total", "extra_crit_dice"}


def _validate_effects(effects: list[dict]) -> None:
    for e in effects:
        if e.get("op") not in _EFFECT_OPS:
            raise ModifierError(f"unknown effect op {e.get('op')!r} (known: {sorted(_EFFECT_OPS)})")
        if e["op"] in ("add", "sub", "extra_crit_dice"):
            # placeholders fill with a LAWFUL die size — filling with 1 made
            # '1d{die}' read 1d1 and refused the registry's own shipping shapes
            # at define_modifier time (audit validator_placeholder_fill)
            parse(str(e["expr"]).format(**{k: 6 for k in _placeholders(str(e["expr"]))}))
        if e["op"] in ("reroll",) and "cmp" not in e:
            raise ModifierError("reroll effect needs a cmp")
        if e["op"] in ("min_die", "max_die") and "value" not in e:
            raise ModifierError(f"{e['op']} effect needs a value")
        if e["op"] in ("mult_total", "div_total") and not isinstance(e.get("by"), int):
            raise ModifierError(f"{e['op']} effect needs integer 'by'")


_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def _placeholders(s: str) -> set[str]:
    return set(_PLACEHOLDER_RE.findall(s))


# ---------------------------------------------------------------------------
# Resolution: caller mods -> concrete (effects, source, stacking) instances
# ---------------------------------------------------------------------------

@dataclass
class ModInstance:
    id: str
    label: str
    effects: list[dict]
    source: dict
    stacking: str = "named"
    params: dict = field(default_factory=dict)
    notes: str = ""

    def to_record(self) -> dict:
        d = {"id": self.id, "label": self.label, "source": self.source,
             "effects": self.effects, "stacking": self.stacking}
        if self.params:
            d["params"] = self.params
        if self.notes:
            d["notes"] = self.notes
        return d


def resolve_mods(mods: list[dict | str] | None, view: str | None = None) -> list[ModInstance]:
    """Turn caller mod specs into instances.

    Accepts:
      "bless"                                  — registry id, bare
      {"id": "sneak-attack", "params": {"n": 3}}
      {"id": "circumstance", "effects": [{"op":"add","expr":"2"}],
       "source": {"kind":"fiat","ref":"dm","reason":"high ground"}}   — inline
    Inline effects REQUIRE a source: an unsourced modifier is refused (provenance law).
    """
    out: list[ModInstance] = []
    reg = _load_registry()
    for spec in mods or []:
        if isinstance(spec, str):
            spec = {"id": spec}
        mid = spec.get("id")
        if not mid:
            raise ModifierError(f"modifier spec without id: {spec!r}")
        if "effects" in spec:  # inline definition
            if "source" not in spec:
                raise ModifierError(
                    f"inline modifier {mid!r} has no source — every modifier names its asserter "
                    "(use source: {kind: fiat|mechanus|mimir|core|table, ref: ...})")
            _validate_effects(spec["effects"])
            out.append(ModInstance(mid, spec.get("label", mid), spec["effects"],
                                   spec["source"], spec.get("stacking", "untyped"),
                                   spec.get("params", {}), spec.get("notes", "")))
            continue
        row = reg.get(mid)
        if row is None:
            known = ", ".join(sorted(reg)) or "none"
            raise ModifierError(f"unknown modifier {mid!r} (registry has: {known})")
        if view and row.get("views") and view not in row["views"]:
            raise ModifierError(
                f"modifier {mid!r} is defined for views {row['views']}, not {view!r}")
        out.append(ModInstance(mid, row.get("label", mid), row["effects"],
                               row.get("source", {"kind": "core", "ref": row.get("_file", "?")}),
                               row.get("stacking", "named"),
                               spec.get("params", {}), row.get("notes", "")))
    return out


# ---------------------------------------------------------------------------
# Composition: base AST + instances -> executed AST (+ d20 state + audit)
# ---------------------------------------------------------------------------

def _scope_match(dice: Dice, scope: str) -> bool:
    if scope == "all":
        return True
    if scope == "d20":
        return dice.sides == 20
    if scope == "damage":
        return dice.sides != 20
    raise ModifierError(f"unknown scope {scope!r}")


def _attach_op(node: Node, scope: str, op: DieOp) -> tuple[Node, int]:
    """Attach a DieOp to every dice group matching scope. Returns (ast, hits)."""
    hits = 0

    def walk(n: Node) -> Node:
        nonlocal hits
        if isinstance(n, Dice):
            if _scope_match(n, scope):
                hits += 1
                return Dice(n.count, n.sides, n.ops + (op,))
            return n
        if isinstance(n, Bin):
            return Bin(n.op, walk(n.left), walk(n.right))
        if isinstance(n, Neg):
            return Neg(walk(n.child))
        if isinstance(n, Func):
            return Func(n.name, tuple(walk(a) for a in n.args))
        return n

    return walk(node), hits


def _expr_with_params(expr: str, params: dict) -> Node:
    needed = _placeholders(expr)
    missing = needed - set(params)
    if missing:
        raise ModifierError(f"modifier expr {expr!r} missing params {sorted(missing)}")
    filled = expr.format(**{k: int(params[k]) for k in needed}) if needed else expr
    return parse(filled)


@dataclass
class Composition:
    ast: Node
    applied: list[dict] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    d20_state_sources: dict = field(default_factory=lambda: {"advantage": [], "disadvantage": [],
                                                             "upgrades": []})


def compose(base: Node, instances: list[ModInstance], *, purpose: str | None = None,
            crit: bool = False, d20_allowed: bool = True) -> Composition:
    """Apply modifier instances to a base AST, in fixed documented order:

      1. stacking law (named ids collapse; the dropped are listed, not hidden)
      2. d20_state/d20_upgrade collected for the caller's state machine
      3. per-die attachments (reroll, min/max, explode) by scope
      4. additive terms (add/sub), in instance order
      5. total wraps (div_total/mult_total) LAST — 5e RAW applies resistance/
         vulnerability after all other modifiers, so added dice (brutal critical,
         sneak attack) halve/double with the rest; both wraps applied = noted

    applies_when='crit' effects fire only when crit=True. An effect carrying its
    own applies_to (split-purpose mods like 2e weapon specialization) fires only
    when it matches `purpose`.
    """
    comp = Composition(ast=base)

    # 1. stacking
    chosen: list[ModInstance] = []
    seen_named: dict[str, ModInstance] = {}
    for inst in instances:
        if inst.stacking == "named" and inst.id in seen_named:
            comp.skipped.append({"id": inst.id, "why": "named effect already applied (no stacking)"})
            continue
        if inst.stacking == "named":
            seen_named[inst.id] = inst
        chosen.append(inst)

    attach_phase: list[tuple[ModInstance, dict]] = []
    wrap_phase: list[tuple[ModInstance, dict]] = []
    add_phase: list[tuple[ModInstance, dict]] = []

    for inst in chosen:
        fired = False
        for eff in inst.effects:
            when = eff.get("applies_when", "always")
            if when == "crit" and not crit:
                comp.notes.append(f"{inst.id}: {eff['op']} held (applies on crit only)")
                continue
            eff_purpose = eff.get("applies_to")
            if eff_purpose and purpose and eff_purpose != purpose:
                continue  # split-purpose effect for a different roll kind
            if eff_purpose and not purpose:
                # bare roll() carries no purpose: every half of a split-purpose
                # modifier fires — disclosed, never silent (audit B-2-core-2e-07)
                comp.notes.append(
                    f"{inst.id}: split-purpose effect ({eff_purpose}) applied "
                    "without purpose context — bare roll() fires every half; "
                    "use roll_check/roll_damage or pass a purpose")
            op = eff["op"]
            if op in ("d20_state", "d20_upgrade"):
                if not d20_allowed:
                    comp.notes.append(
                        f"{inst.id}: {op} refused — this view/check has no d20 state machine")
                    continue
                if op == "d20_state":
                    state = eff.get("state")
                    if state not in ("advantage", "disadvantage"):
                        raise ModifierError(f"{inst.id}: d20_state must be advantage|disadvantage")
                    comp.d20_state_sources[state].append(inst.id)
                else:
                    comp.d20_state_sources["upgrades"].append(eff.get("key"))
                fired = True
            elif op in ("reroll", "min_die", "max_die", "explode"):
                attach_phase.append((inst, eff))
                fired = True
            elif op in ("mult_total", "div_total"):
                wrap_phase.append((inst, eff))
                fired = True
            elif op in ("add", "sub", "extra_crit_dice"):
                add_phase.append((inst, eff))
                fired = True
            else:
                raise ModifierError(f"unhandled effect op {op!r}")
        if fired:
            comp.applied.append(inst.to_record())

    # 3. per-die attachments
    for inst, eff in attach_phase:
        scope = eff.get("scope", "all")
        if eff["op"] == "reroll":
            op = DieOp("reroll", cmp=_parse_cmp(eff["cmp"]), once=bool(eff.get("once", True)))
        elif eff["op"] == "min_die":
            op = DieOp("min", n=int(eff["value"]))
        elif eff["op"] == "max_die":
            op = DieOp("max", n=int(eff["value"]))
        else:
            op = DieOp("explode", cmp=_parse_cmp(eff["cmp"]) if "cmp" in eff else None)
        comp.ast, hits = _attach_op(comp.ast, scope, op)
        if hits == 0:
            comp.notes.append(f"{inst.id}: {eff['op']} matched no dice in scope {scope!r}")

    # 4. additive terms (before wraps: resistance/vulnerability apply LAST, 5e RAW)
    for inst, eff in add_phase:
        term = _expr_with_params(str(eff["expr"]), inst.params)
        comp.ast = Bin("-" if eff["op"] == "sub" else "+", comp.ast, term)

    # 5. total wraps
    for inst, eff in wrap_phase:
        by = Num(int(eff["by"]))
        comp.ast = Bin("/" if eff["op"] == "div_total" else "*", comp.ast, by)
    if len(wrap_phase) > 1:
        comp.notes.append("multiple total wraps applied in order — "
                          "whether they should cancel instead is a law question (Mechanus)")

    return comp


def resolve_d20_state(sources: dict, pack: dict,
                      explicit: str | None = None) -> tuple[str, list[str]]:
    """The pack's d20 state machine: sources + explicit ask -> dice template.

    5e law as data: any advantage + any disadvantage -> flat (cancel_to_flat);
    multiples don't stack; upgrades (elven accuracy) replace the adv template.
    Returns (dice_expr, notes).
    """
    states = pack.get("d20_states", {})
    notes: list[str] = []
    adv = list(sources.get("advantage", []))
    dis = list(sources.get("disadvantage", []))
    if explicit in ("advantage", "adv"):
        adv.append("caller")
    elif explicit in ("disadvantage", "dis"):
        dis.append("caller")
    elif explicit not in (None, "", "flat"):
        raise ModifierError(f"unknown d20 state {explicit!r}")

    if adv and dis:
        if states.get("cancel_to_flat", True):
            notes.append(f"advantage ({', '.join(adv)}) and disadvantage ({', '.join(dis)}) "
                         "cancel to flat")
            return states.get("flat", "1d20"), notes
    if adv:
        if len(adv) > 1:
            notes.append(f"multiple advantage sources ({', '.join(adv)}) — they don't stack")
        template = states.get("advantage")
        if template is None:
            notes.append("view defines no advantage state — rolled flat")
            return states.get("flat", "1d20"), notes
        for key in sources.get("upgrades", []):
            up = (states.get("upgrades") or {}).get(key)
            if up and up.get("from") == "advantage":
                notes.append(f"{key}: advantage upgraded to {up['to']}")
                template = up["to"]
        return template, notes
    if dis:
        if len(dis) > 1:
            notes.append(f"multiple disadvantage sources ({', '.join(dis)}) — they don't stack")
        template = states.get("disadvantage")
        if template is None:
            notes.append("view defines no disadvantage state — rolled flat")
            return states.get("flat", "1d20"), notes
        return template, notes
    return states.get("flat", "1d20"), notes
