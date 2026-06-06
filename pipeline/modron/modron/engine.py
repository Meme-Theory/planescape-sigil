"""The roll engine: ordered chance (MODRON.md §3).

DiceStream — deterministic, auditable randomness. Engine v1 derivation, pinned:

    draw = sha256(seed ‖ u64be(roll_counter) ‖ u64be(draw_index) ‖ u32be(chunk))
           → first 8 bytes as u64 → rejection-sampled mod sides (no modulo bias)

Same (seed, roll_counter) → same faces, forever. Sessions commit sha256(seed)
before any die falls; the on-demand reveal makes the whole night recomputable.

evaluate() — walks the grammar AST drawing from the stream, keeping a per-die
audit trail (every raw face, every fate: kept/dropped/rerolled/exploded/clamped).
Postfix pipeline order is FIXED and documented: reroll → explode → clamp(min/max)
→ keep/drop → count-successes. Rerolls apply to the initial face only; explosion
chain dice neither reroll nor re-clamp the chain trigger. Count-successes reads
the KEPT dice's NATURALS — the post-reroll standing face, pre-explosion-sum,
pre-clamp (keep/drop itself ranks by VALUE); analysis mirrors this exactly
(audit F-1-design-docs-04).
"""

from __future__ import annotations

import hashlib
import math
import os
import struct
from dataclasses import dataclass, field

from .grammar import (MAX_EXPLODE_DEPTH, MAX_REROLLS, Bin, Cmp, Dice, DieOp,
                      Func, Neg, Node, Num, normal_form, parse)

FUDGE = "F"  # Fate dice: faces -1, 0, +1


# ---------------------------------------------------------------------------
# The stream
# ---------------------------------------------------------------------------

def new_seed() -> bytes:
    """32 fresh OS-entropy bytes."""
    return os.urandom(32)


def seed_from_phrase(phrase: str) -> bytes:
    """Deterministic seed from a passphrase (table ceremony: pick the phrase together)."""
    return hashlib.sha256(("modron:seed:" + phrase).encode("utf-8")).digest()


def commitment(seed: bytes) -> str:
    """The published commitment: sha256 hex of the seed."""
    return hashlib.sha256(seed).hexdigest()


class DiceStream:
    """Draws for one roll: position (roll_counter) in a session's stream."""

    def __init__(self, seed: bytes, roll_counter: int):
        if not isinstance(seed, bytes) or len(seed) < 16:
            raise ValueError("seed must be >=16 bytes")
        self.seed = seed
        self.roll_counter = roll_counter
        self.draw_index = 0

    def draw(self, sides: int) -> int:
        """One uniform face in 1..sides via rejection sampling."""
        if sides < 1:
            raise ValueError("sides must be >= 1")
        limit = (2 ** 64 // sides) * sides
        chunk = 0
        while True:
            digest = hashlib.sha256(
                self.seed
                + struct.pack(">Q", self.roll_counter)
                + struct.pack(">Q", self.draw_index)
                + struct.pack(">I", chunk)
            ).digest()
            v = struct.unpack(">Q", digest[:8])[0]
            if v < limit:
                self.draw_index += 1
                return (v % sides) + 1
            chunk += 1  # rejected — same draw_index, next chunk (rare: P < sides/2^64)


# ---------------------------------------------------------------------------
# Audit structures
# ---------------------------------------------------------------------------

@dataclass
class DieAudit:
    """One physical die's story."""
    sides: int | str
    rolls: list[int] = field(default_factory=list)   # every raw face, in order
    natural: int = 0      # the face that stood after rerolls (pre-clamp, pre-explosion-sum)
    value: int = 0        # contribution after explode-sum and clamps
    kept: bool = True
    rerolled: int = 0     # rerolls consumed
    exploded: int = 0     # explosion chain length
    clamped: bool = False
    success: bool | None = None

    def to_dict(self) -> dict:
        d = {"sides": self.sides, "rolls": self.rolls, "natural": self.natural,
             "value": self.value, "kept": self.kept}
        if self.rerolled:
            d["rerolled"] = self.rerolled
        if self.exploded:
            d["exploded"] = self.exploded
        if self.clamped:
            d["clamped"] = True
        if self.success is not None:
            d["success"] = self.success
        return d


@dataclass
class DiceGroup:
    """One Dice node's outcome: the dice, their fates, the group value."""
    spec: str                      # normal form of the Dice node, e.g. '4d6kh3'
    dice: list[DieAudit] = field(default_factory=list)
    value: int = 0
    counted: bool = False          # True when cs/cf turned the group into a count

    def naturals(self) -> list[int]:
        return [d.natural for d in self.dice]

    def kept_naturals(self) -> list[int]:
        return [d.natural for d in self.dice if d.kept]

    def to_dict(self) -> dict:
        return {"spec": self.spec, "value": self.value,
                "counted": self.counted, "dice": [d.to_dict() for d in self.dice]}


@dataclass
class EvalResult:
    total: int = 0
    groups: list[DiceGroup] = field(default_factory=list)
    sets: list["EvalResult"] | None = None   # repeat() arrays
    notes: list[str] = field(default_factory=list)

    def draws(self) -> int:
        return sum(len(d.rolls) for g in self.groups for d in g.dice)

    def to_dict(self) -> dict:
        d = {"total": self.total, "groups": [g.to_dict() for g in self.groups]}
        if self.sets is not None:
            d["sets"] = [s.to_dict() for s in self.sets]
            d["totals"] = [s.total for s in self.sets]
        if self.notes:
            d["notes"] = self.notes
        return d


class DiceRangeError(ValueError):
    """An op would never terminate (e.g. exploding on every face)."""


# ---------------------------------------------------------------------------
# Crit transforms — pack-selected (conventions own WHICH one applies)
# ---------------------------------------------------------------------------

def transform_crit(node: Node, effect: str) -> tuple[Node, list[str]]:
    """Rewrite an AST per a crit effect. Returns (new_ast, notes).

    Effects (data-selected by the convention pack, MODRON.md §5):
      double_dice         — every dice group rolls twice the dice (5e RAW)
      double_total        — roll normally, multiply the total by 2
      max_dice_plus_roll  — max of the dice + a normal roll of them (house classic)
      none                — unchanged (e.g. 2e RAW has no crits)
    """
    notes: list[str] = []
    if effect == "none":
        notes.append("crit: convention pack defines no critical effect; expression unchanged")
        return node, notes
    if effect == "double_total":
        return Bin("*", node, Num(2)), notes
    if effect == "double_dice":
        def dbl(n: Node) -> Node:
            if isinstance(n, Dice):
                return Dice(n.count * 2, n.sides, n.ops)
            if isinstance(n, Bin):
                return Bin(n.op, dbl(n.left), dbl(n.right))
            if isinstance(n, Neg):
                return Neg(dbl(n.child))
            if isinstance(n, Func):
                return Func(n.name, tuple(dbl(a) for a in n.args))
            return n
        return dbl(node), notes
    if effect == "max_dice_plus_roll":
        def maxed(n: Node) -> Node:
            if isinstance(n, Dice):
                if n.sides == FUDGE:
                    raise DiceRangeError("max_dice_plus_roll undefined for fudge dice")
                return Bin("+", Num(n.count * int(n.sides)), n)
            if isinstance(n, Bin):
                return Bin(n.op, maxed(n.left), maxed(n.right))
            if isinstance(n, Neg):
                return Neg(maxed(n.child))
            if isinstance(n, Func):
                return Func(n.name, tuple(maxed(a) for a in n.args))
            return n
        return maxed(node), notes
    raise ValueError(f"unknown crit effect {effect!r}")


def transform_first_die(node: Node, count: int, keep: str) -> Node:
    """adv/dis/ea: rewrite the FIRST plain single die to e.g. 2dXkh1.

    Refuses dice that already carry keep/reroll machinery — advantage on a
    manipulated die is a law question, not a notation question.
    """
    done = False

    def walk(n: Node) -> Node:
        nonlocal done
        if done:
            return n
        if isinstance(n, Dice):
            if n.count == 1 and not n.ops:
                done = True
                return Dice(count, n.sides, (DieOp(keep, n=1),))
            raise DiceRangeError(
                f"adv/dis/ea need a single plain die to transform; got {normal_form(n)}")
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
        raise DiceRangeError("adv/dis/ea found no die to transform")
    return out


# ---------------------------------------------------------------------------
# The evaluator
# ---------------------------------------------------------------------------

def _round_div(num: int, den: int, rounding: str) -> int:
    if den == 0:
        raise ZeroDivisionError("division by zero in dice expression")
    q = num / den
    if rounding == "up":
        return math.ceil(q)
    return math.floor(q)  # 'down' — the D&D default


def _face_range(sides: int | str) -> tuple[int, int]:
    return (1, 3) if sides == FUDGE else (1, int(sides))


def _covers_all_faces(cmp: Cmp, sides: int | str) -> bool:
    lo, hi = _face_range(sides)
    return all(cmp.matches(f) for f in range(lo, hi + 1))


def _fudge_value(face: int) -> int:
    return face - 2  # 1,2,3 -> -1,0,+1


def _roll_group(node: Dice, stream: DiceStream) -> DiceGroup:
    lo, hi = _face_range(node.sides)
    nfaces = hi
    group = DiceGroup(spec=normal_form(node))

    rerolls = [op for op in node.ops if op.kind == "reroll"]
    explodes = [op for op in node.ops if op.kind == "explode"]
    clamps = [op for op in node.ops if op.kind in ("min", "max")]
    keeps = [op for op in node.ops if op.kind in ("kh", "kl", "dh", "dl")]
    counts = [op for op in node.ops if op.kind in ("cs", "cf")]

    if node.sides == FUDGE and (rerolls or explodes or clamps or keeps or counts):
        # fudge faces are -1/0/+1; cmp semantics on raw faces would mislead
        raise DiceRangeError("postfix operations are not defined on fudge dice")

    for op in rerolls:
        if _covers_all_faces(op.cmp, node.sides):
            raise DiceRangeError(f"reroll {op.normal()} matches every face — never terminates")
    for op in explodes:
        cmp = op.cmp or Cmp("=", nfaces)
        if _covers_all_faces(cmp, node.sides):
            raise DiceRangeError(f"explode {op.normal()} matches every face — never terminates")

    for _ in range(node.count):
        die = DieAudit(sides=node.sides)
        face = stream.draw(nfaces)
        die.rolls.append(face)

        # 1) reroll — initial face only
        for op in rerolls:
            spent = 0
            while op.cmp.matches(face):
                face = stream.draw(nfaces)
                die.rolls.append(face)
                die.rerolled += 1
                spent += 1
                if op.once or spent >= MAX_REROLLS:
                    break
        die.natural = face

        # 2) explode — on the standing face; chain dice don't reroll
        total = face
        for op in explodes:
            cmp = op.cmp or Cmp("=", nfaces)
            trigger, depth = face, 0
            while cmp.matches(trigger) and depth < MAX_EXPLODE_DEPTH:
                extra = stream.draw(nfaces)
                die.rolls.append(extra)
                die.exploded += 1
                depth += 1
                total += extra
                trigger = extra
            break  # one explode op governs a group; seconds are parse-legal but inert

        # 3) clamp
        value = _fudge_value(total) if node.sides == FUDGE else total
        for op in clamps:
            if op.kind == "min" and value < op.n:
                value, die.clamped = op.n, True
            elif op.kind == "max" and value > op.n:
                value, die.clamped = op.n, True
        die.value = value
        group.dice.append(die)

    # 4) keep/drop — sequential over the surviving set
    for op in keeps:
        alive = [d for d in group.dice if d.kept]
        ranked = sorted(alive, key=lambda d: d.value)
        n = min(op.n, len(alive))
        if op.kind == "kh":
            doomed = ranked[:-n] if n else ranked
        elif op.kind == "kl":
            doomed = ranked[n:]
        elif op.kind == "dh":
            doomed = ranked[len(ranked) - n:]
        else:  # dl
            doomed = ranked[:n]
        for d in doomed:
            d.kept = False

    kept = [d for d in group.dice if d.kept]

    # 5) cs/cf — the group becomes a count
    if counts:
        value = 0
        for d in kept:
            for op in counts:
                if op.cmp.matches(d.natural):
                    d.success = (op.kind == "cs")
                    value += 1 if op.kind == "cs" else -1
        # only-cf pools read as positive failure counts
        if all(op.kind == "cf" for op in counts):
            value = -value
        group.value = value
        group.counted = True
    else:
        group.value = sum(d.value for d in kept)

    return group


def evaluate(node: Node, stream: DiceStream, *, rounding: str = "down",
             crit_effect: str = "double_dice") -> EvalResult:
    """Evaluate an AST on a stream. Every die lands in the audit trail."""
    result = EvalResult()

    def walk(n: Node) -> int:
        if isinstance(n, Num):
            return n.value
        if isinstance(n, Dice):
            g = _roll_group(n, stream)
            result.groups.append(g)
            return g.value
        if isinstance(n, Neg):
            return -walk(n.child)
        if isinstance(n, Bin):
            left = walk(n.left)
            right = walk(n.right)
            if n.op == "+":
                return left + right
            if n.op == "-":
                return left - right
            if n.op == "*":
                return left * right
            return _round_div(left, right, rounding)
        if isinstance(n, Func):
            if n.name in ("adv", "dis", "ea"):
                count, keep = {"adv": (2, "kh"), "dis": (2, "kl"), "ea": (3, "kh")}[n.name]
                return walk(transform_first_die(n.args[0], count, keep))
            if n.name == "crit":
                rewritten, notes = transform_crit(n.args[0], crit_effect)
                result.notes.extend(notes)
                return walk(rewritten)
            if n.name == "repeat":
                raise DiceRangeError("repeat() is only allowed at the top level")
            if n.name == "floor":
                return walk(n.args[0])      # integer math: already floored by '/'
            if n.name == "ceil":
                return walk(n.args[0])
            if n.name == "round":
                return walk(n.args[0])
            if n.name == "abs":
                return abs(walk(n.args[0]))
            if n.name == "min":
                return min(walk(a) for a in n.args)
            if n.name == "max":
                return max(walk(a) for a in n.args)
            raise ValueError(f"unhandled function {n.name}")
        raise TypeError(f"unknown node {n!r}")

    if isinstance(node, Func) and node.name == "repeat":
        times = node.args[1].value  # arity/range checked at parse
        result.sets = []
        for _ in range(times):
            # shares the stream (draw_index advances), audits into its own set
            inner = evaluate(node.args[0], stream, rounding=rounding, crit_effect=crit_effect)
            result.sets.append(inner)
            result.groups.extend(inner.groups)
        result.total = sum(s.total for s in result.sets)
        result.notes.append(f"repeat: {times} sets; total is their sum, see totals[]")
        return result

    result.total = walk(node)
    return result


def roll_expression(expr: str, seed: bytes, roll_counter: int, *,
                    rounding: str = "down", crit_effect: str = "double_dice") -> EvalResult:
    """Parse + evaluate in one move (the engine's plain-text door)."""
    return evaluate(parse(expr), DiceStream(seed, roll_counter),
                    rounding=rounding, crit_effect=crit_effect)
