import pytest

from modron.grammar import (DiceSyntaxError, Dice, Func, Num, dice_groups,
                            normal_form, parse)

ROUND_TRIPS = [
    "3d6+2", "4d6kh3", "2d20kh1+5", "2d20kl1", "4d6dl1", "4d6dh1", "2d6ro<3",
    "1d6!", "2d6!!", "3d6!>=5", "2d6r1", "1d20min10", "1d20max15", "8d6/2",
    "1d100", "4df", "10d10cs>=8", "6d10cf1", "adv(1d20+7)", "dis(1d20)",
    "ea(1d20+11)", "crit(2d8+5)", "repeat(4d6kh3,6)", "floor(7d6/2)",
    "abs(1d6-1d6)", "min(2d6,1d12)", "max(1d8,1d8)", "(1d8+1)*2-3",
    "1d4+1d4+2d6", "-1d4+10", "100d6",
]


@pytest.mark.parametrize("expr", ROUND_TRIPS)
def test_normal_form_round_trips(expr):
    nf = normal_form(parse(expr))
    assert normal_form(parse(nf)) == nf


def test_conveniences():
    assert normal_form(parse("d6")) == "1d6"
    assert normal_form(parse("d%")) == "1d100"
    assert normal_form(parse("1D6")) == "1d6"
    assert normal_form(parse("2dF")) == "2df"
    assert normal_form(parse("4d6k3")) == "4d6kh3"  # bare k = keep highest


def test_precedence_parens():
    assert normal_form(parse("(1d6+2)*3")) == "(1d6+2)*3"
    assert normal_form(parse("1d6+2*3")) == "1d6+2*3"
    assert normal_form(parse("12-(2-1)")) == "12-(2-1)"
    assert normal_form(parse("8d6/(1+1)")) == "8d6/(1+1)"


def test_dice_groups_walk():
    groups = dice_groups(parse("1d20+2d6+3"))
    assert [normal_form(g) for g in groups] == ["1d20", "2d6"]


@pytest.mark.parametrize("bad", [
    "", "  ", "d", "1d", "2d6d1",          # bare-d drop is refused with guidance
    "1d20kh2",                              # keep more than rolled... kh2 of 1
    "frob(1d6)", "repeat(1d6, 1d4)",        # unknown func; non-literal repeat n
    "1001d6", "1d10001", "0d6", "1d1",
    "4d6kh0", "1d6+", "(1d6", "repeat(1d6,101)",
])
def test_rejects(bad):
    with pytest.raises(DiceSyntaxError):
        parse(bad)


def test_error_carries_position_context():
    with pytest.raises(DiceSyntaxError) as e:
        parse("1d6 + frub(2)")
    assert "^" in str(e.value)


def test_cmp_forms():
    d = parse("3d6r<=2")
    assert isinstance(d, Dice) and d.ops[0].cmp.op == "<=" and d.ops[0].cmp.value == 2
    d = parse("3d6r2")
    assert d.ops[0].cmp.op == "=" and d.ops[0].cmp.value == 2


def test_repeat_top_level_shape():
    node = parse("repeat(2d6+1,3)")
    assert isinstance(node, Func) and node.name == "repeat"
    assert isinstance(node.args[1], Num) and node.args[1].value == 3
