import collections

import pytest

from modron.engine import (DiceRangeError, DiceStream, evaluate, new_seed,
                           roll_expression, seed_from_phrase, transform_crit,
                           transform_first_die)
from modron.grammar import normal_form, parse

SEED = seed_from_phrase("test-vector")


def test_determinism_same_seed_same_counter():
    a = roll_expression("10d20+4d6kh3!", SEED, 42)
    b = roll_expression("10d20+4d6kh3!", SEED, 42)
    assert a.to_dict() == b.to_dict()


def test_counters_independent():
    totals = {roll_expression("3d10000", SEED, i).total for i in range(50)}
    assert len(totals) > 45  # collisions astronomically unlikely


def test_uniformity_smoke():
    stream = DiceStream(SEED, 0)
    counts = collections.Counter(stream.draw(6) for _ in range(6000))
    assert set(counts) == {1, 2, 3, 4, 5, 6}
    for face, n in counts.items():
        assert 850 <= n <= 1150, f"face {face} count {n} suspicious"


def test_keep_drop():
    r = roll_expression("4d6kh3", SEED, 7)
    dice = r.groups[0].dice
    values = sorted(d.value for d in dice)
    kept = sorted(d.value for d in dice if d.kept)
    assert len(kept) == 3 and kept == values[1:]
    assert r.total == sum(kept)

    r = roll_expression("4d6dl1", SEED, 7)  # same stream -> same faces
    assert r.total == sum(sorted(d.value for d in r.groups[0].dice)[1:])


def test_reroll_once_and_forever():
    r = roll_expression("20d6ro<3", SEED, 11)
    for d in r.groups[0].dice:
        if len(d.rolls) > 1:
            assert d.rolls[0] < 3 and d.rerolled == 1
    r = roll_expression("20d6r1", SEED, 12)
    assert all(d.natural != 1 for d in r.groups[0].dice)


def test_explode_and_compound():
    r = roll_expression("30d6!", SEED, 13)
    exploded = [d for d in r.groups[0].dice if d.exploded]
    assert exploded, "30 dice with no explosion would be (5/6)^30 ≈ 0.4% luck"
    for d in exploded:
        assert d.rolls[0] == 6 and d.value == sum(d.rolls) if d.rerolled == 0 else True
    with pytest.raises(DiceRangeError):
        roll_expression("1d6!>=1", SEED, 14)   # explodes every face
    with pytest.raises(DiceRangeError):
        roll_expression("1d6r<=6", SEED, 14)   # rerolls every face


def test_clamps():
    r = roll_expression("40d20min10", SEED, 15)
    assert all(d.value >= 10 for d in r.groups[0].dice)
    assert any(d.clamped for d in r.groups[0].dice)
    r = roll_expression("40d20max5", SEED, 15)
    assert all(d.value <= 5 for d in r.groups[0].dice)


def test_success_pools():
    r = roll_expression("50d10cs>=8", SEED, 16)
    g = r.groups[0]
    assert g.counted
    assert g.value == sum(1 for d in g.dice if d.natural >= 8)


def test_fudge():
    r = roll_expression("4df", SEED, 17)
    assert -4 <= r.total <= 4
    assert all(d.value in (-1, 0, 1) for d in r.groups[0].dice)
    with pytest.raises(DiceRangeError):
        roll_expression("4dfkh2", SEED, 17)  # postfixes undefined on fudge


def test_crit_transforms():
    node = parse("2d8+1d6+5")
    doubled, _ = transform_crit(node, "double_dice")
    assert normal_form(doubled) == "4d8+2d6+5"          # dice doubled, mod untouched
    total2, _ = transform_crit(node, "double_total")
    assert normal_form(total2) == "(2d8+1d6+5)*2"
    maxed, _ = transform_crit(node, "max_dice_plus_roll")
    assert normal_form(maxed) == "16+2d8+(6+1d6)+5"
    same, notes = transform_crit(node, "none")
    assert normal_form(same) == "2d8+1d6+5" and notes


def test_adv_transform_rules():
    assert normal_form(transform_first_die(parse("1d20+7"), 2, "kh")) == "2d20kh1+7"
    assert normal_form(transform_first_die(parse("1d20+7"), 3, "kh")) == "3d20kh1+7"
    with pytest.raises(DiceRangeError):
        transform_first_die(parse("2d20kh1+7"), 2, "kh")  # already manipulated = law question
    with pytest.raises(DiceRangeError):
        transform_first_die(parse("7+3"), 2, "kh")


def test_division_rounding():
    seven = parse("7/2")
    assert evaluate(seven, DiceStream(SEED, 0), rounding="down").total == 3
    assert evaluate(seven, DiceStream(SEED, 0), rounding="up").total == 4
    with pytest.raises(ZeroDivisionError):
        evaluate(parse("1d6/(1-1)"), DiceStream(SEED, 0))


def test_repeat_sets():
    r = roll_expression("repeat(4d6kh3,6)", SEED, 18)
    assert len(r.sets) == 6
    assert r.total == sum(s.total for s in r.sets)
    assert all(3 <= s.total <= 18 for s in r.sets)


def test_audit_totals_reconcile():
    r = roll_expression("2d20kh1+4d6dl1+3", SEED, 19)
    dice_sum = sum(g.value for g in r.groups)
    assert r.total == dice_sum + 3


def test_seed_hygiene():
    assert len(new_seed()) == 32
    assert seed_from_phrase("x") != seed_from_phrase("y")
    with pytest.raises(ValueError):
        DiceStream(b"short", 0)
