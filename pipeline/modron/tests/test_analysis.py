from fractions import Fraction

import pytest

from modron.analysis import exact_mean, mean_of, pmf, stats
from modron.grammar import parse


def test_2d6_triangle():
    p, _ = pmf(parse("2d6"))
    assert p[2] == Fraction(1, 36) and p[7] == Fraction(6, 36) and p[12] == Fraction(1, 36)
    assert sum(p.values()) == 1


def test_known_means():
    assert exact_mean(parse("2d8+5")) == Fraction(14)
    assert exact_mean(parse("16d10+48")) == Fraction(136)         # the 5e printed-avg pair
    assert exact_mean(parse("adv(1d20)")) == Fraction(553, 40)    # 13.825 exactly
    assert exact_mean(parse("1d20min10")) == Fraction(255, 20)    # 12.75
    assert exact_mean(parse("1d6r1")) == Fraction(4)              # uniform 2..6
    # GWF: E(d6 reroll 1-2 once) = 25/6 each
    assert exact_mean(parse("2d6ro<3")) == Fraction(25, 3)
    # exploding d6: 3.5 * 6/5
    assert exact_mean(parse("1d6!")) == pytest.approx(4.2, abs=1e-9)
    # 4d6 drop lowest — the classic
    assert float(exact_mean(parse("4d6kh3"))) == pytest.approx(12.244598765, abs=1e-8)


def test_crit_double_dice_mean():
    assert exact_mean(parse("crit(2d8+5)")) == Fraction(23)  # 4d8+5


def test_stats_exact_shape():
    s = stats("2d6")
    assert s["method"] == "exact"
    assert s["mean"] == 7.0 and s["min"] == 2 and s["max"] == 12 and s["mode"] == 7
    assert s["percentiles"][50] == 7
    assert abs(sum(s["pmf"].values()) - 1.0) < 1e-4  # pmf rows are display-rounded


def test_stats_keep_drop_exact():
    s = stats("4d6kh3")
    assert s["method"] == "exact"
    assert s["min"] == 3 and s["max"] == 18


def test_stats_explode_truncated_flagged():
    s = stats("1d6!")
    assert s["method"] == "exact-truncated"
    assert any("truncated" in n for n in s["notes"])


def test_stats_mc_fallback_flagged():
    s = stats("30d20kh3")
    assert s["method"] == "monte-carlo"
    assert s["samples"] == 100000
    assert any("estimated" in n for n in s["notes"])
    # 3 highest of 30 d20s: mean lives in the mid-50s
    assert 52.0 <= s["mean"] <= 60.0


def test_mc_reproducible():
    assert stats("30d20kh3")["mean"] == stats("30d20kh3")["mean"]


def test_division_pmf_rounding():
    p, _ = pmf(parse("7/2"))
    assert p == {3: Fraction(1)}
    p, _ = pmf(parse("1d4/2"))
    assert p == {0: Fraction(1, 4), 1: Fraction(2, 4), 2: Fraction(1, 4)}


def test_success_pool_pmf():
    p, _ = pmf(parse("2d10cs>=8"))
    assert p[0] == Fraction(49, 100) and p[1] == Fraction(42, 100) and p[2] == Fraction(9, 100)


def test_mean_of_door():
    assert mean_of("2d8+5") == Fraction(14)
    assert mean_of("not dice") is None
