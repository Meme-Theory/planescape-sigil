"""Semantic rolls: attack / save / check / morale / reaction / … per the view's pack.

The procedure comes from the convention pack (data); the values come from the
caller, Mimir, or Mechanus — never invented here (MODRON.md §1). This module
turns (kind, view, params, mods) into a concrete expression, evaluates it, and
computes the outcome the way that edition reads dice: roll-over vs roll-under,
THAC0's "you hit AC X", crit naturals, reaction bands, low-wins initiative.
"""

from __future__ import annotations

from typing import Any

from . import conventions
from .engine import DiceStream, EvalResult, evaluate, transform_crit
from .grammar import Bin, Dice, Node, Num, normal_form, parse
from .modifiers import ModifierError, compose, resolve_d20_state, resolve_mods


class CheckError(ValueError):
    pass


def _to_int(name: str, value: Any) -> int:
    try:
        return int(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        raise CheckError(f"parameter {name!r} must be an integer, got {value!r}")


_WORD_RE = __import__("re").compile(r"[A-Za-z_]\w*")


def _eval_template(template: str | int, params: dict, *, what: str) -> int:
    """Evaluate a diceless arithmetic template like 'thac0 - ac' with int params.

    Whole-word substitution only ('ac' never bites into 'thac0')."""
    if isinstance(template, int):
        return template

    missing: list[str] = []

    def sub(m) -> str:
        name = m.group(0)
        if name in params:
            return str(_to_int(name, params[name]))
        missing.append(name)
        return name

    expr = _WORD_RE.sub(sub, str(template))
    if missing:
        raise CheckError(f"{what}: template {template!r} needs params {sorted(set(missing))}")
    node = parse(expr)
    from .grammar import dice_groups
    if dice_groups(node):
        raise CheckError(f"{what}: target template may not contain dice: {template!r}")
    return evaluate(node, DiceStream(b"\x00" * 16, 0)).total  # diceless: draws nothing


def _primary_d20_naturals(result: EvalResult) -> list[int]:
    """Kept naturals of the FIRST dice group (the check die), if any."""
    if not result.groups:
        return []
    return result.groups[0].kept_naturals()


def _collect_d20_sources(instances, kind: str) -> dict:
    """Pre-scan instances for d20 state effects (the swap must precede compose)."""
    sources = {"advantage": [], "disadvantage": [], "upgrades": []}
    for inst in instances:
        for eff in inst.effects:
            if eff.get("applies_to") and eff["applies_to"] != kind:
                continue
            if eff.get("op") == "d20_state":
                state = eff.get("state")
                if state in ("advantage", "disadvantage"):
                    sources[state].append(inst.id)
            elif eff.get("op") == "d20_upgrade":
                sources["upgrades"].append(eff.get("key"))
    return sources


def roll_check(kind: str, view: str, params: dict | None, mods: list | None,
               stream: DiceStream, *, state: str | None = None) -> dict:
    """Resolve and roll a semantic check. Returns the full record (server ledgers it).

    params — the values the pack's templates need (attack_bonus, ac, thac0, dc,
    score, morale, …), from the caller / Mimir / Mechanus.
    state — explicit 'advantage'|'disadvantage'|None, on top of mod-carried states.
    """
    params = dict(params or {})
    spec, pack = conventions.get_check_spec(view, kind)
    notes: list[str] = list_wrap(spec.get("notes"))

    d20_able = bool(spec.get("d20")) and "d20_states" in pack and \
        pack["d20_states"].get("advantage") is not None

    # -- resolve modifiers (registry + inline), purpose-filtered --
    instances = resolve_mods(mods, view=view)
    for inst in instances:
        reg_applies = inst_applies_to(inst)
        if reg_applies and kind not in reg_applies and kind != "damage":
            notes.append(f"{inst.id}: registered for {reg_applies}, applied to {kind!r} "
                         "on the caller's word (recorded)")

    # -- the check die: state machine FIRST (so per-die mods attach to the
    #    state's dice — halfling luck must reroll both advantage d20s), then compose --
    roll_template = spec["roll"]
    base = parse(roll_template)
    if d20_able:
        sources = _collect_d20_sources(instances, kind)
        die_expr, state_notes = resolve_d20_state(sources, pack, explicit=state)
        notes.extend(state_notes)
        if die_expr != pack["d20_states"].get("flat", "1d20"):
            base = _replace_first_die(base, parse(die_expr))
    elif state not in (None, "", "flat"):
        notes.append(f"explicit {state!r} ignored — view {view!r} check {kind!r} "
                     "has no d20 state machine")
    comp = compose(base, instances, purpose=kind, d20_allowed=d20_able)

    # -- additive params (e.g. attack_bonus); 'sub' mirrors for subtractive
    #    arithmetic (Limbo's alteration roll: 1d100 + spell_level - caster_level) --
    for pname in spec.get("add", []):
        if pname in params:
            comp.ast = Bin("+", comp.ast, Num(_to_int(pname, params[pname])))
    for pname in spec.get("sub", []):
        if pname in params:
            comp.ast = Bin("-", comp.ast, Num(_to_int(pname, params[pname])))

    result = evaluate(comp.ast, stream, rounding=pack.get("rounding", "down"),
                      crit_effect=pack.get("crit_effect", "double_dice"))

    # -- target + outcome --
    outcome: dict[str, Any] = {}
    target = None
    if "vs_template" in spec:
        needed = spec.get("params", [])
        missing = [p for p in needed if p not in params]
        if missing:
            notes.append(f"no success verdict: missing params {missing}")
        else:
            target = _eval_template(spec["vs_template"], {p: params[p] for p in needed},
                                    what=f"{view}:{kind}")
    elif "vs" in spec:
        vs = spec["vs"]
        if isinstance(vs, int):
            target = vs
        elif vs in params:
            target = _to_int(vs, params[vs])
            for tname in spec.get("add_to_target", []):
                if tname in params:
                    target += _to_int(tname, params[tname])
        else:
            notes.append(f"no success verdict: param {vs!r} not provided")

    naturals = _primary_d20_naturals(result)
    op = spec.get("success_op")
    if target is not None and op:
        success = result.total >= target if op == ">=" else result.total <= target
        margin = (result.total - target) if op == ">=" else (target - result.total)
        outcome.update(target=target, success=success, margin=margin, op=op)
        if spec.get("success_means"):
            outcome["success_means"] = spec["success_means"]

    crit_nat = set(spec.get("crit_nat", []))
    fumble_nat = set(spec.get("fumble_nat", []))
    if naturals and (crit_nat or fumble_nat):
        nat = naturals[0]
        outcome["natural"] = nat
        if nat in crit_nat:
            outcome["crit"] = True
            if spec.get("nat_crit_auto_hits") and "success" in outcome:
                outcome["success"] = True
                notes.append(f"natural {nat}: automatic success")
        if nat in fumble_nat:
            outcome["fumble"] = True
            if spec.get("nat_fumble_auto_misses") and "success" in outcome:
                outcome["success"] = False
                notes.append(f"natural {nat}: automatic miss")
    elif naturals:
        outcome["natural"] = naturals[0]

    for dname, dtemplate in (spec.get("derived") or {}).items():
        try:
            outcome[dname] = _eval_template(dtemplate, {**params, "total": result.total},
                                            what=f"{view}:{kind}:{dname}")
        except CheckError as e:
            notes.append(str(e))

    for band in spec.get("bands", []):
        if band["min"] <= result.total <= band["max"]:
            outcome["band"] = band["label"]
            if spec.get("provisional"):
                notes.append("band table is provisional (see pack) — confirm against FG&G")
            break

    if spec.get("order"):
        outcome["order"] = spec["order"]  # asc = low wins (2e), desc = high wins (5e)

    return {
        "kind": kind,
        "view": view,
        "expr_asked": roll_template,
        "expr_resolved": normal_form(comp.ast),
        "total": result.total,
        "outcome": outcome,
        "groups": [g.to_dict() for g in result.groups],
        "modifiers": comp.applied,
        "modifiers_skipped": comp.skipped,
        "notes": notes + comp.notes + result.notes,
    }


def roll_damage(expr: str, view: str, mods: list | None, stream: DiceStream, *,
                crit: bool = False) -> dict:
    """A damage roll: modifier composition + (on crit) the pack's crit effect."""
    pack = conventions.get_pack(view)
    notes: list[str] = []
    base = parse(expr)
    if crit:
        base, crit_notes = transform_crit(base, pack.get("crit_effect", "double_dice"))
        notes.extend(crit_notes)
    instances = resolve_mods(mods, view=view)
    comp = compose(base, instances, purpose="damage", crit=crit, d20_allowed=False)
    result = evaluate(comp.ast, stream, rounding=pack.get("rounding", "down"),
                      crit_effect=pack.get("crit_effect", "double_dice"))
    return {
        "kind": "damage",
        "view": view,
        "crit": crit,
        "expr_asked": expr,
        "expr_resolved": normal_form(comp.ast),
        "total": result.total,
        "groups": [g.to_dict() for g in result.groups],
        "modifiers": comp.applied,
        "modifiers_skipped": comp.skipped,
        "notes": notes + comp.notes + result.notes,
    }


def _replace_first_die(node: Node, replacement: Node) -> Node:
    """Swap the first plain single die (the check die) for the state template."""
    from .grammar import Func, Neg
    done = False

    def walk(n: Node) -> Node:
        nonlocal done
        if done:
            return n
        if isinstance(n, Dice) and n.count == 1 and not n.ops:
            done = True
            return replacement
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
        raise CheckError("no plain check die found to apply the d20 state to")
    return out


def inst_applies_to(inst) -> list[str]:
    """Registry applies_to for an instance (inline mods usually omit it)."""
    from .modifiers import registry
    row = registry().get(inst.id)
    return row.get("applies_to", []) if row else []


def list_wrap(v) -> list[str]:
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)
