import pytest

from mechanus import dc_suggest, encounter_budget
from mechanus.budget import LawUnavailable


def test_budget_example_1_from_srd():
    """SRD 5.2.1 p.202 Example 1: four level-1 PCs, low -> 200 XP."""
    b = encounter_budget([1, 1, 1, 1], "low")
    assert b["budget"] == 200
    assert "p.202" in b["source"]


def test_budget_example_3_from_srd():
    """SRD 5.2.1 p.203 Example 3: six level-15 PCs, high -> 46,800 XP."""
    b = encounter_budget([15] * 6, "high")
    assert b["budget"] == 46800


def test_budget_mixed_party():
    b = encounter_budget([3, 3, 4, 5], "moderate")
    assert b["budget"] == 225 + 225 + 375 + 750


def test_budget_2014_refuses_with_reason():
    with pytest.raises(LawUnavailable, match="SRD 5.1"):
        encounter_budget([5, 5, 5, 5], "moderate", view="5e-2014")


def test_budget_rejects_garbage():
    with pytest.raises(ValueError):
        encounter_budget([0, 5], "low")
    with pytest.raises(ValueError):
        encounter_budget([5, 5], "brutal")


def test_dc_full_ladder_cited():
    d = dc_suggest(view="5e-2024")
    assert len(d["ladder"]) == 6
    assert "p.6" in d["source"]


def test_dc_single_rung():
    d = dc_suggest("medium", view="5e-2014")
    assert d["dc"] == 15
    assert "p.77" in d["source"]


def test_dc_2e_refuses():
    with pytest.raises(ValueError, match="roll-under"):
        dc_suggest("medium", view="2e")
