"""Distribution analysis: exact where feasible, estimated where not — and it SAYS which.

Exact machinery (fractions, no floats until presentation):
  - per-die PMF transforms: reroll-once, reroll-forever (closed form),
    min/max clamps, exploding (truncated when residual < 1e-12, flagged);
  - group ops (kh/kl/dh/dl/cs/cf): multiset enumeration over per-die supports
    with multinomial weights — 4d6kh3 is 126 multisets, not 1296 tuples;
  - arithmetic: convolution / pairwise combination with size guards.

When guards trip, Monte Carlo (deterministically seeded from the expression's
normal form, so stats are reproducible) — results carry method='monte-carlo'
and never dress as exact (MODRON.md §8).

This module is also the dice-lawfulness witness (MODRON.md §2.4): exact_mean()
backs the printed-average crosscheck on statblocks.
"""

from __future__ import annotations

import hashlib
import math
from fractions import Fraction
from itertools import combinations_with_replacement

from .engine import FUDGE, DiceStream, evaluate, transform_crit, transform_first_die
from .grammar import Bin, Cmp, Dice, DieOp, Func, Neg, Node, Num, normal_form, parse

# Guards: exact work bails to MC past these (honesty over heroics)
MAX_MULTISETS = 3_000_000
MAX_CONV_PAIRS = 4_000_000
MAX_SUPPORT = 500_000
EXPLODE_EPS = Fraction(1, 10 ** 12)
MC_SAMPLES = 100_000

PMF = dict[int, Fraction]


class Inexact(Exception):
    """Raised internally when exact computation would exceed guards."""


# ---------------------------------------------------------------------------
# Per-die PMFs
# ---------------------------------------------------------------------------

def _die_faces(sides: int | str) -> list[int]:
    return [-1, 0, 1] if sides == FUDGE else list(range(1, int(sides) + 1))


def _single_die_pmf(node: Dice) -> tuple[PMF, list[str]]:
    """PMF of ONE die of the group, after per-die ops (reroll/explode/clamp).

    Returns (pmf over the die's contribution value, notes).
    """
    notes: list[str] = []
    if node.sides == FUDGE:
        return {-1: Fraction(1, 3), 0: Fraction(1, 3), 1: Fraction(1, 3)}, notes

    n = int(node.sides)
    faces = _die_faces(node.sides)
    pmf: PMF = {f: Fraction(1, n) for f in faces}

    rerolls = [op for op in node.ops if op.kind == "reroll"]
    explodes = [op for op in node.ops if op.kind == "explode"]
    clamps = [op for op in node.ops if op.kind in ("min", "max")]

    for op in rerolls:
        matched = [f for f in faces if op.cmp.matches(f)]
        if len(matched) == len(faces):
            raise Inexact("reroll matches every face")
        if op.once:
            out: PMF = {}
            p_each = Fraction(1, n)
            for f in faces:
                if f not in matched:
                    out[f] = out.get(f, Fraction(0)) + pmf.get(f, Fraction(0))
            p_matched = sum(pmf.get(f, Fraction(0)) for f in matched)
            for f in faces:  # the one reroll lands uniformly
                out[f] = out.get(f, Fraction(0)) + p_matched * p_each
            pmf = out
        else:
            # reroll-forever: matched faces' mass redistributes over the rest
            keepers = [f for f in faces if f not in matched]
            pmf = {f: Fraction(1, len(keepers)) for f in keepers}

    if explodes:
        op = explodes[0]
        cmp = op.cmp or Cmp("=", n)
        trigger = [f for f in faces if cmp.matches(f)]
        if len(trigger) == len(faces):
            raise Inexact("explode matches every face")
        # truncated geometric chain: value = f0 + f1 + ... while f_i triggers
        p_trig = Fraction(len(trigger), n)
        out: PMF = {}
        # state: distribution over (sum so far) for chains still alive
        alive: PMF = {0: Fraction(1)}
        depth = 0
        while alive and depth <= 64:
            next_alive: PMF = {}
            for acc, p_acc in alive.items():
                for f in faces:
                    p = p_acc * Fraction(1, n)
                    if f in trigger:
                        next_alive[acc + f] = next_alive.get(acc + f, Fraction(0)) + p
                    else:
                        out[acc + f] = out.get(acc + f, Fraction(0)) + p
            alive = next_alive
            depth += 1
            if sum(alive.values(), Fraction(0)) < EXPLODE_EPS:
                # fold the vanishing tail onto its current sums (truncation, noted)
                for acc, p_acc in alive.items():
                    out[acc] = out.get(acc, Fraction(0)) + p_acc
                notes.append(f"explode: chain truncated at depth {depth} "
                             f"(residual < 1e-12) — exact-truncated")
                alive = {}
        if alive:
            for acc, p_acc in alive.items():
                out[acc] = out.get(acc, Fraction(0)) + p_acc
            notes.append("explode: chain truncated at depth 64 — exact-truncated")
        pmf = out

    for op in clamps:
        out = {}
        for v, p in pmf.items():
            if op.kind == "min":
                v = max(v, op.n)
            else:
                v = min(v, op.n)
            out[v] = out.get(v, Fraction(0)) + p
        pmf = out

    return pmf, notes


def _single_die_joint(node: Dice) -> tuple[dict[tuple[int, int], Fraction], list[str]]:
    """Joint (natural, value) distribution of ONE die — the engine's two axes:
    cs/cf reads the post-reroll NATURAL, keep/drop ranks (and sums use) the
    post-explode/post-clamp VALUE (audit F-1-design-docs-04: value-only
    collapse made analysis disagree with the engine on clamp+count combos)."""
    notes: list[str] = []
    if node.sides == FUDGE:
        raise Inexact("cs/cf on fudge dice (the engine refuses postfix ops there)")
    n = int(node.sides)
    faces = _die_faces(node.sides)
    p1 = Fraction(1, n)

    rerolls = [op for op in node.ops if op.kind == "reroll"]
    explodes = [op for op in node.ops if op.kind == "explode"]
    clamps = [op for op in node.ops if op.kind in ("min", "max")]

    nat: PMF = {f: p1 for f in faces}
    for op in rerolls:
        matched = [f for f in faces if op.cmp.matches(f)]
        if len(matched) == len(faces):
            raise Inexact("reroll matches every face")
        if op.once:
            out_nat: PMF = {}
            p_match = sum(nat.get(f, Fraction(0)) for f in matched)
            for f in faces:
                if f not in matched:
                    out_nat[f] = out_nat.get(f, Fraction(0)) + nat.get(f, Fraction(0))
                out_nat[f] = out_nat.get(f, Fraction(0)) + p_match * p1
            nat = out_nat
        else:
            keepers = [f for f in faces if f not in matched]
            nat = {f: Fraction(1, len(keepers)) for f in keepers}

    joint: dict[tuple[int, int], Fraction] = {}
    if explodes:
        op = explodes[0]
        cmp = op.cmp or Cmp("=", n)
        trigger = [f for f in faces if cmp.matches(f)]
        if len(trigger) == len(faces):
            raise Inexact("explode matches every face")
        for f0, p0 in nat.items():
            if f0 not in trigger:
                joint[(f0, f0)] = joint.get((f0, f0), Fraction(0)) + p0
                continue
            alive: PMF = {f0: p0}
            depth = 0
            while alive and depth <= 64:
                nxt: PMF = {}
                for acc, p_acc in alive.items():
                    for f in faces:
                        p = p_acc * p1
                        if f in trigger:
                            nxt[acc + f] = nxt.get(acc + f, Fraction(0)) + p
                        else:
                            key = (f0, acc + f)
                            joint[key] = joint.get(key, Fraction(0)) + p
                alive = nxt
                depth += 1
                if sum(alive.values(), Fraction(0)) < EXPLODE_EPS:
                    for acc, p_acc in alive.items():
                        joint[(f0, acc)] = joint.get((f0, acc), Fraction(0)) + p_acc
                    notes.append("explode: chain truncated (residual < 1e-12) — exact-truncated")
                    alive = {}
            if alive:
                for acc, p_acc in alive.items():
                    joint[(f0, acc)] = joint.get((f0, acc), Fraction(0)) + p_acc
                notes.append("explode: chain truncated at depth 64 — exact-truncated")
    else:
        joint = {(f, f): p for f, p in nat.items()}

    if clamps:
        out: dict[tuple[int, int], Fraction] = {}
        for (f, v), p in joint.items():
            for op in clamps:
                if op.kind == "min":
                    v = max(v, op.n)
                else:
                    v = min(v, op.n)
            out[(f, v)] = out.get((f, v), Fraction(0)) + p
        joint = out
    return joint, notes


def _group_pmf(node: Dice) -> tuple[PMF, list[str]]:
    """PMF of a whole dice group, including keep/drop and success counting."""
    die_pmf, notes = _single_die_pmf(node)
    keeps = [op for op in node.ops if op.kind in ("kh", "kl", "dh", "dl")]
    counts = [op for op in node.ops if op.kind in ("cs", "cf")]

    if not keeps and not counts:
        # plain sum — convolve count times (fast exponentiation by doubling)
        return _convolve_power(die_pmf, node.count), notes

    if counts:
        # engine-exact: rank/keep by VALUE, count successes on kept NATURALS
        # — needs the joint per-die distribution and ORDERED enumeration (the
        # engine's stable keep-sort breaks value ties by position)
        from itertools import product as _product
        joint, jnotes = _single_die_joint(node)
        notes.extend(jnotes)
        support = sorted(joint)
        if len(support) ** node.count > MAX_MULTISETS:
            raise Inexact(f"{len(support)}^{node.count} ordered joint tuples "
                          "exceeds exact guard")
        out: PMF = {}
        for combo in _product(support, repeat=node.count):
            w = Fraction(1)
            for pair in combo:
                w *= joint[pair]
            dice = [{"nat": f, "val": v, "kept": True} for f, v in combo]
            for op in keeps:
                alive = [d for d in dice if d["kept"]]
                ranked = sorted(alive, key=lambda d: d["val"])
                k = min(op.n, len(alive))
                if op.kind == "kh":
                    doomed = ranked[:-k] if k else ranked
                elif op.kind == "kl":
                    doomed = ranked[k:]
                elif op.kind == "dh":
                    doomed = ranked[len(ranked) - k:]
                else:
                    doomed = ranked[:k]
                for d in doomed:
                    d["kept"] = False
            total = 0
            for d in dice:
                if not d["kept"]:
                    continue
                for op in counts:
                    if op.cmp.matches(d["nat"]):
                        total += 1 if op.kind == "cs" else -1
            if all(op.kind == "cf" for op in counts):
                total = -total
            out[total] = out.get(total, Fraction(0)) + w
        return out, notes

    # keep/drop only — multiset enumeration: identical dice → order doesn't matter
    support = sorted(die_pmf)
    n_multisets = math.comb(len(support) + node.count - 1, node.count)
    if n_multisets > MAX_MULTISETS:
        raise Inexact(f"{n_multisets} multisets exceeds exact guard")

    out: PMF = {}
    fact = math.factorial
    cfact = fact(node.count)
    for combo in combinations_with_replacement(support, node.count):
        # multinomial weight of this multiset
        w = Fraction(cfact)
        mult: dict[int, int] = {}
        for v in combo:
            mult[v] = mult.get(v, 0) + 1
        for v, m in mult.items():
            w = w * die_pmf[v] ** m / fact(m)
        values = sorted(combo)  # ascending
        for op in keeps:
            k = min(op.n, len(values))
            if op.kind == "kh":
                values = values[-k:]
            elif op.kind == "kl":
                values = values[:k]
            elif op.kind == "dh":
                values = values[: len(values) - k]
            else:
                values = values[k:]
        total = sum(values)
        out[total] = out.get(total, Fraction(0)) + w
    return out, notes


def _convolve(a: PMF, b: PMF) -> PMF:
    if len(a) * len(b) > MAX_CONV_PAIRS:
        raise Inexact("convolution exceeds exact guard")
    out: PMF = {}
    for va, pa in a.items():
        for vb, pb in b.items():
            out[va + vb] = out.get(va + vb, Fraction(0)) + pa * pb
    if len(out) > MAX_SUPPORT:
        raise Inexact("support exceeds exact guard")
    return out


def _convolve_power(p: PMF, k: int) -> PMF:
    result: PMF = {0: Fraction(1)}
    base = dict(p)
    while k:
        if k & 1:
            result = _convolve(result, base)
        k >>= 1
        if k:
            base = _convolve(base, base)
    return result


def _combine(a: PMF, b: PMF, fn) -> PMF:
    if len(a) * len(b) > MAX_CONV_PAIRS:
        raise Inexact("combination exceeds exact guard")
    out: PMF = {}
    for va, pa in a.items():
        for vb, pb in b.items():
            v = fn(va, vb)
            out[v] = out.get(v, Fraction(0)) + pa * pb
    return out


# ---------------------------------------------------------------------------
# AST → PMF
# ---------------------------------------------------------------------------

def pmf(node: Node, *, rounding: str = "down",
        crit_effect: str = "double_dice") -> tuple[PMF, list[str]]:
    """Exact PMF of an expression. Raises Inexact when guards trip."""
    notes: list[str] = []

    def walk(n: Node) -> PMF:
        if isinstance(n, Num):
            return {n.value: Fraction(1)}
        if isinstance(n, Dice):
            p, nts = _group_pmf(n)
            notes.extend(nts)
            return p
        if isinstance(n, Neg):
            return {-v: p for v, p in walk(n.child).items()}
        if isinstance(n, Bin):
            a, b = walk(n.left), walk(n.right)
            if n.op == "+":
                return _convolve(a, b)
            if n.op == "-":
                return _convolve(a, {-v: p for v, p in b.items()})
            if n.op == "*":
                return _combine(a, b, lambda x, y: x * y)
            div = (lambda x, y: math.ceil(x / y)) if rounding == "up" \
                else (lambda x, y: math.floor(x / y))
            return _combine(a, b, div)
        if isinstance(n, Func):
            if n.name in ("adv", "dis", "ea"):
                count, keep = {"adv": (2, "kh"), "dis": (2, "kl"), "ea": (3, "kh")}[n.name]
                return walk(transform_first_die(n.args[0], count, keep))
            if n.name == "crit":
                rewritten, nts = transform_crit(n.args[0], crit_effect)
                notes.extend(nts)
                return walk(rewritten)
            if n.name == "repeat":
                return _convolve_power(walk(n.args[0]), n.args[1].value)
            if n.name == "abs":
                out: PMF = {}
                for v, p in walk(n.args[0]).items():
                    out[abs(v)] = out.get(abs(v), Fraction(0)) + p
                return out
            if n.name in ("floor", "ceil", "round"):
                return walk(n.args[0])  # integer pipeline
            if n.name in ("min", "max"):
                fn = min if n.name == "min" else max
                acc = walk(n.args[0])
                for a in n.args[1:]:
                    acc = _combine(acc, walk(a), lambda x, y: fn(x, y))
                return acc
            raise Inexact(f"no exact path for {n.name}()")
        raise TypeError(f"unknown node {n!r}")

    return walk(node), notes


def exact_mean(node: Node, *, crit_effect: str = "double_dice") -> Fraction | None:
    """Exact mean by linearity where possible — the crosscheck's workhorse.

    Handles +, -, Neg, * (independent operands), per-die ops, keep/drop
    (via group PMF when feasible). Returns None when exactness isn't cheap
    (then the caller falls back to full pmf() or MC).
    """
    def walk(n: Node) -> Fraction:
        if isinstance(n, Num):
            return Fraction(n.value)
        if isinstance(n, Dice):
            keeps_or_counts = any(op.kind in ("kh", "kl", "dh", "dl", "cs", "cf")
                                  for op in n.ops)
            if keeps_or_counts:
                p, _ = _group_pmf(n)  # may raise Inexact
                return sum((Fraction(v) * pr for v, pr in p.items()), Fraction(0))
            die, _ = _single_die_pmf(n)
            m = sum((Fraction(v) * pr for v, pr in die.items()), Fraction(0))
            return m * n.count
        if isinstance(n, Neg):
            return -walk(n.child)
        if isinstance(n, Bin):
            if n.op == "+":
                return walk(n.left) + walk(n.right)
            if n.op == "-":
                return walk(n.left) - walk(n.right)
            if n.op == "*":
                return walk(n.left) * walk(n.right)  # independent terms
            raise Inexact("mean of integer division is not linear")
        if isinstance(n, Func):
            if n.name in ("adv", "dis", "ea"):
                count, keep = {"adv": (2, "kh"), "dis": (2, "kl"), "ea": (3, "kh")}[n.name]
                return walk(transform_first_die(n.args[0], count, keep))
            if n.name == "crit":
                rewritten, _ = transform_crit(n.args[0], crit_effect)
                return walk(rewritten)
            if n.name == "repeat":
                return walk(n.args[0]) * n.args[1].value
            raise Inexact(f"mean of {n.name}() needs the full distribution")
        raise TypeError(f"unknown node {n!r}")

    try:
        return walk(node)
    except Inexact:
        try:
            p, _ = pmf(node, crit_effect=crit_effect)
            return sum((Fraction(v) * pr for v, pr in p.items()), Fraction(0))
        except Inexact:
            return None


# ---------------------------------------------------------------------------
# Stats (public)
# ---------------------------------------------------------------------------

def _mc_stats(node: Node, nf: str, *, rounding: str, crit_effect: str) -> dict:
    seed = hashlib.sha256(("modron:stats:" + nf).encode("utf-8")).digest()
    totals = []
    for i in range(MC_SAMPLES):
        r = evaluate(node, DiceStream(seed, i), rounding=rounding, crit_effect=crit_effect)
        totals.append(r.total)
    totals.sort()
    n = len(totals)
    mean = sum(totals) / n
    var = sum((t - mean) ** 2 for t in totals) / (n - 1)

    def pct(q: float) -> int:
        return totals[min(n - 1, max(0, round(q * (n - 1))))]

    return {
        "method": "monte-carlo",
        "samples": n,
        "mean": round(mean, 4),
        "stddev": round(math.sqrt(var), 4),
        "min_observed": totals[0],
        "max_observed": totals[-1],
        "percentiles": {p: pct(p / 100) for p in (5, 25, 50, 75, 95)},
        "notes": ["estimated — guards tripped on exact computation; "
                  "Monte Carlo with a fixed expression-derived seed (reproducible)"],
    }


def stats(expr: str, *, rounding: str = "down", crit_effect: str = "double_dice",
          include_pmf_rows: int = 60) -> dict:
    """Distribution summary for an expression. method ∈ exact | monte-carlo."""
    node = parse(expr)
    nf = normal_form(node)
    try:
        p, notes = pmf(node, rounding=rounding, crit_effect=crit_effect)
    except Inexact:
        out = _mc_stats(node, nf, rounding=rounding, crit_effect=crit_effect)
        out["expr"] = nf
        return out

    total = sum(p.values(), Fraction(0))
    # tolerate the explode-truncation residual fold (sums to 1 by construction)
    mean = sum((Fraction(v) * pr for v, pr in p.items()), Fraction(0)) / total
    var = sum((Fraction(v) ** 2 * pr for v, pr in p.items()), Fraction(0)) / total - mean ** 2
    support = sorted(p)
    cumulative = Fraction(0)
    pct_targets = {5: None, 25: None, 50: None, 75: None, 95: None}
    for v in support:
        cumulative += p[v] / total
        for t in pct_targets:
            if pct_targets[t] is None and cumulative >= Fraction(t, 100):
                pct_targets[t] = v
    mode = max(p, key=lambda v: p[v])

    out = {
        "expr": nf,
        "method": "exact" if not any("truncated" in s for s in notes) else "exact-truncated",
        "mean": float(mean),
        "stddev": float(math.sqrt(float(var))) if var >= 0 else 0.0,
        "min": support[0],
        "max": support[-1],
        "mode": mode,
        "percentiles": pct_targets,
    }
    if notes:
        out["notes"] = notes
    if len(support) <= include_pmf_rows:
        out["pmf"] = {v: round(float(p[v] / total), 6) for v in support}
    return out


def mean_of(expr: str) -> Fraction | None:
    """Exact mean of an expression string, or None (the crosscheck door)."""
    try:
        return exact_mean(parse(expr))
    except Exception:
        return None
