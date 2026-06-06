"""Dice-notation grammar: recursive-descent parser -> typed AST -> normal form.

The grammar is the contract (MODRON.md §4). Regex never touches play; every
expression that rolls is parsed here, and the canonical normal form (what the
ledger SHA hashes) round-trips through this parser.

    expr    := term (('+'|'-') term)*
    term    := factor (('*'|'/') factor)*
    factor  := dice | number | '(' expr ')' | func | '-' factor
    dice    := [count] 'd' (sides|'%'|'F') postfix*
    postfix := khN | klN | dhN | dlN | kN | '!'['!'][cmp] | r[o]cmp
             | minN | maxN | cs cmp | cf cmp
    cmp     := ['<'|'>'|'<='|'>='|'='] N      (bare N = exact face)
    func    := name '(' expr (',' expr)* ')'

Changeability axis #5 (new notation) lands here: add a postfix to _POSTFIX_ORDER
+ a DieOp kind, or a function name to FUNCS — the evaluator registry picks it up.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Guardrails — the lawful machine refuses unbounded work (MODRON.md §4)
# ---------------------------------------------------------------------------

MAX_EXPR_LEN = 2000
MAX_DICE_COUNT = 1000
MAX_SIDES = 10000
MAX_AST_DEPTH = 50
MAX_REPEAT = 100
MAX_EXPLODE_DEPTH = 100
MAX_REROLLS = 100

FUNCS = {"adv", "dis", "ea", "crit", "repeat", "floor", "ceil", "round", "abs", "min", "max"}

# Postfix keywords, longest-match-first so 'kh' wins over 'k', 'ro' over 'r'.
_POSTFIX_ORDER = ("kh", "kl", "dh", "dl", "k", "min", "max", "ro", "r", "cs", "cf")

_CMP_OPS = ("<=", ">=", "<", ">", "=")


class DiceSyntaxError(ValueError):
    """Parse failure, with position and a caret context line."""

    def __init__(self, msg: str, text: str = "", pos: int = -1):
        self.pos = pos
        if pos >= 0 and text:
            window = text[max(0, pos - 24): pos + 24]
            caret = " " * (pos - max(0, pos - 24)) + "^"
            msg = f"{msg} (at position {pos})\n  {window}\n  {caret}"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Cmp:
    """A face comparison: op in {'<','>','<=','>=','='}, value an int face."""
    op: str
    value: int

    def matches(self, face: int) -> bool:
        return {
            "<": face < self.value,
            ">": face > self.value,
            "<=": face <= self.value,
            ">=": face >= self.value,
            "=": face == self.value,
        }[self.op]

    def normal(self) -> str:
        return f"{self.value}" if self.op == "=" else f"{self.op}{self.value}"


@dataclass(frozen=True)
class DieOp:
    """One postfix operation on a dice group.

    kind ∈ {kh, kl, dh, dl, explode, reroll, min, max, cs, cf}
      kh/kl/dh/dl : n = how many to keep/drop
      explode     : compound flag; cmp (default: max face)
      reroll      : once flag; cmp
      min/max     : n = per-die clamp
      cs/cf       : cmp = success/failure test
    """
    kind: str
    n: int | None = None
    cmp: Cmp | None = None
    compound: bool = False
    once: bool = False

    def normal(self) -> str:
        if self.kind in ("kh", "kl", "dh", "dl", "min", "max"):
            return f"{self.kind}{self.n}"
        if self.kind == "explode":
            s = "!!" if self.compound else "!"
            return s + (self.cmp.normal() if self.cmp else "")
        if self.kind == "reroll":
            return ("ro" if self.once else "r") + self.cmp.normal()
        if self.kind in ("cs", "cf"):
            return f"{self.kind}{self.cmp.normal()}"
        raise ValueError(f"unknown DieOp kind {self.kind}")


@dataclass(frozen=True)
class Node:
    pass


@dataclass(frozen=True)
class Num(Node):
    value: int


@dataclass(frozen=True)
class Dice(Node):
    count: int
    sides: int | str          # int, or 'F' for Fate/fudge dice (faces -1/0/+1)
    ops: tuple[DieOp, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Bin(Node):
    op: str                   # '+', '-', '*', '/'
    left: Node
    right: Node


@dataclass(frozen=True)
class Neg(Node):
    child: Node


@dataclass(frozen=True)
class Func(Node):
    name: str
    args: tuple[Node, ...]


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class _Parser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    # -- char-stream helpers ------------------------------------------------

    def err(self, msg: str) -> DiceSyntaxError:
        return DiceSyntaxError(msg, self.text, self.pos)

    def skip_ws(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t\r\n":
            self.pos += 1

    def peek(self, k: int = 0) -> str:
        i = self.pos + k
        return self.text[i] if i < len(self.text) else ""

    def eat(self, s: str) -> bool:
        if self.text.startswith(s, self.pos):
            self.pos += len(s)
            return True
        return False

    def eat_ci(self, s: str) -> bool:
        """Case-insensitive eat."""
        if self.text[self.pos: self.pos + len(s)].lower() == s:
            self.pos += len(s)
            return True
        return False

    def parse_int(self) -> int:
        start = self.pos
        while self.peek().isdigit():
            self.pos += 1
        if start == self.pos:
            raise self.err("expected a number")
        return int(self.text[start:self.pos])

    # -- grammar ------------------------------------------------------------

    def parse(self) -> Node:
        node = self.expr()
        self.skip_ws()
        if self.pos != len(self.text):
            raise self.err(f"unexpected trailing input {self.text[self.pos:]!r}")
        _check_depth(node)
        return node

    def expr(self) -> Node:
        node = self.term()
        while True:
            self.skip_ws()
            if self.eat("+"):
                node = Bin("+", node, self.term())
            elif self.eat("-"):
                node = Bin("-", node, self.term())
            else:
                return node

    def term(self) -> Node:
        node = self.factor()
        while True:
            self.skip_ws()
            if self.eat("*"):
                node = Bin("*", node, self.factor())
            elif self.peek() == "/" and self.peek(1) != "/":
                self.pos += 1
                node = Bin("/", node, self.factor())
            elif self.eat("//"):  # tolerated alias for '/'
                node = Bin("/", node, self.factor())
            else:
                return node

    def factor(self) -> Node:
        self.skip_ws()
        c = self.peek()
        if c == "(":
            self.pos += 1
            node = self.expr()
            self.skip_ws()
            if not self.eat(")"):
                raise self.err("expected ')'")
            return node
        if c == "-":
            self.pos += 1
            return Neg(self.factor())
        if c.isdigit():
            n = self.parse_int()
            if self.peek().lower() == "d" and _is_die_start(self.peek(1)):
                return self.dice(count=n)
            return Num(n)
        if c.lower() == "d" and _is_die_start(self.peek(1)):
            return self.dice(count=1)
        if c.isalpha():
            return self.func()
        raise self.err("expected a die, number, function, or '('")

    def dice(self, count: int) -> Node:
        if count < 1 or count > MAX_DICE_COUNT:
            raise self.err(f"dice count must be 1..{MAX_DICE_COUNT}")
        self.pos += 1  # the 'd'
        sides: int | str
        if self.eat("%"):
            sides = 100
        elif self.peek() in ("F", "f"):
            self.pos += 1
            sides = "F"
        else:
            sides = self.parse_int()
            if sides < 2 or sides > MAX_SIDES:
                raise self.err(f"sides must be 2..{MAX_SIDES}")
        ops = []
        while True:
            op = self.postfix(count, sides)
            if op is None:
                break
            ops.append(op)
            if len(ops) > 8:
                raise self.err("too many postfix operations on one dice group")
        return Dice(count, sides, tuple(ops))

    def postfix(self, count: int, sides: int | str) -> DieOp | None:
        start = self.pos
        # explode first — '!' is not a word
        if self.peek() == "!":
            self.pos += 1
            compound = self.eat("!")
            cmp = self.try_cmp()
            return DieOp("explode", cmp=cmp, compound=compound)
        # word postfixes, longest match first
        for kw in _POSTFIX_ORDER:
            if self.text[self.pos: self.pos + len(kw)].lower() == kw:
                after = self.peek(len(kw))
                if kw in ("kh", "kl", "dh", "dl", "k", "min", "max"):
                    if not after.isdigit():
                        continue  # e.g. 'd' of another die, or 'min(' function — not ours
                    self.pos += len(kw)
                    n = self.parse_int()
                    kind = "kh" if kw == "k" else kw
                    if kind in ("kh", "kl", "dh", "dl") and not (1 <= n <= count):
                        raise self.err(f"{kind}{n}: must keep/drop 1..{count} of {count} dice")
                    return DieOp(kind, n=n)
                if kw in ("ro", "r"):
                    # require a cmp/face after, else it's not a reroll ('r' alone is noise)
                    save = self.pos
                    self.pos += len(kw)
                    cmp = self.try_cmp()
                    if cmp is None:
                        self.pos = save
                        continue
                    return DieOp("reroll", cmp=cmp, once=(kw == "ro"))
                if kw in ("cs", "cf"):
                    save = self.pos
                    self.pos += len(kw)
                    cmp = self.try_cmp()
                    if cmp is None:
                        self.pos = save
                        continue
                    return DieOp(kw, cmp=cmp)
        # a bare 'd' drop (Roll20 '4d6d1') is ambiguous with a die — refuse helpfully
        if self.peek().lower() == "d" and self.peek(1).isdigit():
            # only a trap if it would otherwise dangle: lookahead for a die is fine,
            # because '2d6d1' would have been consumed as dice(2,6) then 'd1' errors
            # at factor level. Catch it here for the better message.
            raise self.err("bare 'd' drop is ambiguous with a die — use 'dl1' (drop lowest) or 'dh1'")
        self.pos = start
        return None

    def try_cmp(self) -> Cmp | None:
        for op in _CMP_OPS:
            if self.text.startswith(op, self.pos):
                self.pos += len(op)
                return Cmp(op if op != "=" else "=", self.parse_int())
        if self.peek().isdigit():
            return Cmp("=", self.parse_int())
        return None

    def func(self) -> Node:
        start = self.pos
        while self.peek().isalpha() or self.peek() == "_":
            self.pos += 1
        name = self.text[start:self.pos].lower()
        if name not in FUNCS:
            raise DiceSyntaxError(f"unknown function {name!r} (known: {', '.join(sorted(FUNCS))})",
                                  self.text, start)
        self.skip_ws()
        if not self.eat("("):
            raise self.err(f"expected '(' after {name}")
        args = [self.expr()]
        while True:
            self.skip_ws()
            if self.eat(","):
                args.append(self.expr())
            elif self.eat(")"):
                break
            else:
                raise self.err("expected ',' or ')'")
        _check_func_arity(name, args, self)
        return Func(name, tuple(args))


def _is_die_start(c: str) -> bool:
    return c.isdigit() or c in ("%", "F", "f")


def _check_func_arity(name: str, args: list[Node], p: _Parser) -> None:
    n = len(args)
    if name in ("adv", "dis", "ea", "crit", "floor", "ceil", "round", "abs") and n != 1:
        raise p.err(f"{name}() takes exactly 1 argument, got {n}")
    if name == "repeat":
        if n != 2:
            raise p.err("repeat(expr, n) takes exactly 2 arguments")
        if not isinstance(args[1], Num):
            raise p.err("repeat(expr, n): n must be a plain integer")
        if not (1 <= args[1].value <= MAX_REPEAT):
            raise p.err(f"repeat(expr, n): n must be 1..{MAX_REPEAT}")
    if name in ("min", "max") and n < 2:
        raise p.err(f"{name}(a, b, ...) takes at least 2 arguments")


def _check_depth(node: Node, depth: int = 0) -> None:
    if depth > MAX_AST_DEPTH:
        raise DiceSyntaxError(f"expression nests deeper than {MAX_AST_DEPTH}")
    if isinstance(node, Bin):
        _check_depth(node.left, depth + 1)
        _check_depth(node.right, depth + 1)
    elif isinstance(node, Neg):
        _check_depth(node.child, depth + 1)
    elif isinstance(node, Func):
        for a in node.args:
            _check_depth(a, depth + 1)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def parse(expr: str) -> Node:
    """Parse a dice expression into its AST. Raises DiceSyntaxError."""
    if not isinstance(expr, str) or not expr.strip():
        raise DiceSyntaxError("empty expression")
    if len(expr) > MAX_EXPR_LEN:
        raise DiceSyntaxError(f"expression longer than {MAX_EXPR_LEN} chars")
    return _Parser(expr).parse()


_PREC = {"+": 1, "-": 1, "*": 2, "/": 2}


def normal_form(node: Node, _parent_prec: int = 0) -> str:
    """Canonical string: lowercase, no spaces, minimal parens, explicit counts.

    normal_form(parse(x)) is the ledgered/SHA'd form; it re-parses to an
    identical AST (round-trip property, tested).
    """
    if isinstance(node, Num):
        return str(node.value)
    if isinstance(node, Dice):
        sides = "f" if node.sides == "F" else str(node.sides)
        return f"{node.count}d{sides}" + "".join(op.normal() for op in node.ops)
    if isinstance(node, Neg):
        inner = normal_form(node.child, 3)
        return f"-{inner}"
    if isinstance(node, Func):
        return f"{node.name}({','.join(normal_form(a) for a in node.args)})"
    if isinstance(node, Bin):
        p = _PREC[node.op]
        left = normal_form(node.left, p)
        # right side: bump precedence so a-(b-c) and a/(b*c) keep their parens
        right = normal_form(node.right, p + 1)
        s = f"{left}{node.op}{right}"
        return f"({s})" if p < _parent_prec else s
    raise TypeError(f"unknown node {node!r}")


def dice_groups(node: Node) -> list[Dice]:
    """All Dice nodes, left-to-right (the order the evaluator visits them)."""
    out: list[Dice] = []

    def walk(n: Node) -> None:
        if isinstance(n, Dice):
            out.append(n)
        elif isinstance(n, Bin):
            walk(n.left)
            walk(n.right)
        elif isinstance(n, Neg):
            walk(n.child)
        elif isinstance(n, Func):
            for a in n.args:
                walk(a)

    walk(node)
    return out
