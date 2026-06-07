"""Law tables vs their cited prints — spot rows verified against the PDFs by hand."""

import pytest
from fractions import Fraction

from mechanus import tables


def test_parse_cr_forms():
    assert tables.parse_cr("1/4") == Fraction(1, 4)
    assert tables.parse_cr(0.25) == Fraction(1, 4)
    assert tables.parse_cr("13") == 13
    assert tables.parse_cr(6) == 6


def test_cr_validity():
    assert tables.cr_is_valid("1/8") and tables.cr_is_valid(30) and tables.cr_is_valid(0)
    assert not tables.cr_is_valid("3/8")
    assert not tables.cr_is_valid(31)
    assert not tables.cr_is_valid("banana")


@pytest.mark.parametrize("cr,xp", [
    ("1/8", 25), ("1/4", 50), ("1/2", 100), (1, 200), (6, 2300), (9, 5000),
    (14, 11500), (17, 18000), (23, 50000), (30, 155000),
])
def test_xp_by_cr_spot_rows(cr, xp):
    """Rows read directly off SRD 5.2.1 p.256 / SRD 5.1 p.258."""
    assert tables.cr_to_xp(cr) == (xp,)


def test_cr_zero_is_zero_or_ten():
    assert tables.cr_to_xp(0) == (0, 10)


@pytest.mark.parametrize("cr,pb", [
    (0, 2), ("1/4", 2), (4, 2), (5, 3), (8, 3), (9, 4), (12, 4),
    (13, 5), (16, 5), (17, 6), (20, 6), (21, 7), (25, 8), (29, 9), (30, 9),
])
def test_pb_brackets_match_formula(cr, pb):
    """SRD 5.2.1 p.256 brackets — the accessor asserts bracket==formula itself."""
    assert tables.cr_to_pb(cr) == pb


def test_dc_ladder_is_the_printed_six():
    ladder = {r["task"]: r["dc"] for r in tables.dc_ladder()}
    assert ladder == {"Very easy": 5, "Easy": 10, "Medium": 15,
                      "Hard": 20, "Very hard": 25, "Nearly impossible": 30}


@pytest.mark.parametrize("level,diff,xp", [
    (1, "low", 50), (1, "high", 100), (3, "high", 400), (5, "moderate", 750),
    (12, "moderate", 3700), (17, "high", 11700), (20, "high", 22000),
])
def test_xp_budget_spot_rows(level, diff, xp):
    """Rows read off SRD 5.2.1 p.202 — includes the OCR-normalized 11,700."""
    assert tables.xp_budget_per_character(level, diff) == xp


@pytest.mark.parametrize("hd,thac0", [
    ("1", 19), ("2", 19), ("3", 17), ("6", 15), ("7", 13), ("9", 11),
    ("12", 9), ("16", 5), ("17", 3),
    ("6+3", 13),   # plus-bump: observed in FG&G
    ("8+8", 11),   # plus-bump
    ("4+3", 15),   # plus-bump
    ("5+1", 15),   # no bump (+1 < 3)
    ("12+24", 9),  # big plus still one bump: 13 bracket? no — 12+24 bumps to 13 -> 7
])
def test_thac0_2e_brackets(hd, thac0):
    if hd == "12+24":
        assert tables.thac0_expected_2e(hd) == 7  # bumped into 13-14 bracket
    else:
        assert tables.thac0_expected_2e(hd) == thac0


def test_parse_hd_2e():
    assert tables.parse_hd_2e("6") == (6, 0)
    assert tables.parse_hd_2e("12+24") == (12, 24)
    assert tables.parse_hd_2e("6+3") == (6, 3)


def test_law_version_is_stable_and_short():
    assert tables.law_version() == tables.law_version()
    assert len(tables.law_version()) == 16


def test_conditions_loaded_per_view():
    for view in tables.VIEWS_5E:
        c = tables.conditions(view)
        assert "Poisoned" in c and len(c) == 15


# --- 2e save matrix (F6 pour, FG&G Tables 3.2/3.9/3.12/3.13) ----------------

@pytest.mark.parametrize("group,level,expected", [
    # one pin per printed corner + interior spot-checks, all five categories
    ("warrior", 1,  {"paralyzation-poison-death": 14, "rod-staff-wand": 16,
                     "petrification-polymorph": 15, "breath-weapon": 17, "spell": 17}),
    ("warrior", 17, {"paralyzation-poison-death": 3, "rod-staff-wand": 5,
                     "petrification-polymorph": 4, "breath-weapon": 4, "spell": 6}),
    ("wizard", 5,   {"paralyzation-poison-death": 14, "rod-staff-wand": 11,
                     "petrification-polymorph": 13, "breath-weapon": 15, "spell": 12}),
    ("wizard", 21,  {"paralyzation-poison-death": 8, "rod-staff-wand": 3,
                     "petrification-polymorph": 5, "breath-weapon": 7, "spell": 4}),
    ("priest", 19,  {"paralyzation-poison-death": 2, "rod-staff-wand": 6,
                     "petrification-polymorph": 5, "breath-weapon": 8, "spell": 7}),
    ("rogue", 9,    {"paralyzation-poison-death": 11, "rod-staff-wand": 10,
                     "petrification-polymorph": 10, "breath-weapon": 14, "spell": 11}),
    ("rogue", 21,   {"paralyzation-poison-death": 8, "rod-staff-wand": 4,
                     "petrification-polymorph": 7, "breath-weapon": 11, "spell": 5}),
])
def test_saves_2e_printed_pins(group, level, expected):
    assert tables.saves_2e(group, level) == expected


def test_saves_2e_bracket_boundaries():
    # priest 3->4 boundary: ppd 10 drops to 9 (Table 3.12)
    assert tables.saves_2e("priest", 3)["paralyzation-poison-death"] == 10
    assert tables.saves_2e("priest", 4)["paralyzation-poison-death"] == 9
    with pytest.raises(ValueError):
        tables.saves_2e("warrior", 0)       # table starts at 1
    with pytest.raises(ValueError):
        tables.saves_2e("wizard", 100)      # past the 21-99 terminal bracket
    with pytest.raises(KeyError):
        tables.saves_2e("bard", 1)          # not a group — bards ride rogue


def test_saves_2e_monster_mapping():
    # HD -> warrior level (FG&G p.70); plus-bump shared with THACO (p.309)
    assert tables.saves_2e_monster("7")["paralyzation-poison-death"] == 10   # 7-8 row
    # plus-bump is next-DIE not next-bracket (the thac0 7+3->13 lesson):
    assert tables.saves_2e_monster("7+3") == tables.saves_2e("warrior", 8)   # 7->8, same row
    assert tables.saves_2e_monster("8+3")["paralyzation-poison-death"] == 8  # 8->9, 9-10 row
    assert tables.saves_2e_monster("7+1") == tables.saves_2e_monster("7")    # +1 never bumps
    assert tables.saves_2e_monster("1/2") == tables.saves_2e("warrior", 1)   # sub-1 HD floors
    assert tables.saves_2e_monster("1-1") == tables.saves_2e("warrior", 1)   # demoted floors too
    assert tables.saves_2e_monster("20")["spell"] == 6                       # 17+ terminal row
