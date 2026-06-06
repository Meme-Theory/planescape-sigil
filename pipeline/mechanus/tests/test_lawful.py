"""is_lawful against real SRD monsters — and against deliberately broken ones.

The four halved-XP fixtures (dretch, riding-horse, svirfneblin, wyrmling) are
the upstream 5e-bits bug discovered during extraction: is_lawful must flag
each via xp_matches_cr (soft), while passing them on every hard check.
"""

import pytest

from mechanus import is_lawful


def _check(verdict, name):
    return next(c for c in verdict["checks"] if c["name"] == name)


def test_vrock_is_lawful(vrock):
    v = is_lawful(vrock)
    assert v["lawful"], v["summary"]
    assert v["view"] == "5e-2014"
    assert v["shape"] == "5e-bits-monster"
    assert not v["summary"]["soft_fails"]
    # the load-bearing checks actually ran (PB 3, XP 2300, HP 104 = ⌊11d10+44⌋)
    for name in ("pb_matches_cr", "xp_matches_cr", "hp_matches_roll",
                 "save_bonuses_math", "passive_perception_math"):
        assert _check(v, name)["result"] == "pass", name


def test_balor_is_lawful(balor):
    v = is_lawful(balor)
    assert v["lawful"], v["summary"]


@pytest.mark.parametrize("index", ["dretch", "riding-horse", "deep-gnome-svirfneblin", "brass-dragon-wyrmling"])
def test_halved_xp_bug_is_flagged_soft(monsters, index):
    """The witness catch, regression-pinned: upstream XP is exactly half the table."""
    v = is_lawful(monsters[index])
    assert v["lawful"], f"{index} must still pass hard checks: {v['summary']}"
    assert "xp_matches_cr" in v["summary"]["soft_fails"], index
    c = _check(v, "xp_matches_cr")
    assert c["actual"] * 2 in c["expected"], "the halving pattern itself"


def test_corrupt_pb_fails_hard(vrock):
    vrock["proficiency_bonus"] = 4  # CR 6 demands +3
    v = is_lawful(vrock)
    assert not v["lawful"]
    assert "pb_matches_cr" in v["summary"]["hard_fails"]


def test_corrupt_hp_fails_hard(vrock):
    vrock["hit_points"] = 140  # ⌊mean(11d10+44)⌋ = 104
    v = is_lawful(vrock)
    assert "hp_matches_roll" in v["summary"]["hard_fails"]


def test_ocr_class_skill_typo_fails_hard(balor):
    # simulate Id6-class transcription slip on a save bonus
    for p in balor["proficiencies"]:
        p["value"] += 1
    v = is_lawful(balor)
    assert "save_bonuses_math" in v["summary"]["hard_fails"] or \
           "skill_bonuses_math" in v["summary"]["hard_fails"]


def test_unknown_condition_fails_hard(vrock):
    vrock["condition_immunities"].append({"index": "befuddled", "name": "Befuddled"})
    v = is_lawful(vrock)
    assert "conditions_known" in v["summary"]["hard_fails"]


def test_speed_not_multiple_of_5(vrock):
    vrock["speed"]["walk"] = "42 ft."
    v = is_lawful(vrock)
    assert "speeds_multiple_of_5" in v["summary"]["hard_fails"]


def test_envelope_5e_shape():
    e = {"type": "creature", "edition": "5e-2014", "name": "Test Wight",
         "fields": {"statblock": {
             "ac": 14, "hp": 45, "hp_roll": "6d8+18", "cr": 3, "proficiency_bonus": 2,
             "abilities": {"strength": 15, "dexterity": 14, "constitution": 16,
                           "intelligence": 10, "wisdom": 13, "charisma": 15},
             "speeds": {"walk": 30},
             "saving_throws": {}, "skills": {"perception": 3},
             "senses": {"passive_perception": 13},
             "condition_immunities": ["poisoned"]}}}
    v = is_lawful(e)
    assert v["shape"] == "envelope-5e"
    assert v["lawful"], v["summary"]


# --- 2e ---

OTYUGH = {  # For Gold & Glory bestiary, harvested values
    "name": "Otyugh", "thac0": 15, "level_hd": "6", "hp": 27, "ac": 3,
    "morale": "14", "magic_resistance": "None",
}


def test_otyugh_2e_lawful():
    v = is_lawful(OTYUGH)
    assert v["shape"] == "bare-2e"
    assert v["lawful"], v["summary"]
    assert not v["summary"]["soft_fails"]


def test_2e_thac0_mismatch_is_soft():
    bad = dict(OTYUGH, thac0=11)
    v = is_lawful(bad)
    assert v["lawful"]  # soft never blocks
    assert "thac0_vs_hd" in v["summary"]["soft_fails"]


def test_2e_hp_out_of_hd_range_fails_hard():
    bad = dict(OTYUGH, hp=60)  # 6 HD (d8) caps at 48
    v = is_lawful(bad)
    assert "hp_in_hd_range" in v["summary"]["hard_fails"]


def test_2e_akin_style_plus_hd():
    akin = {"name": "A'kin", "thac0": 7, "level_hd": "12+24", "hp": 92, "ac": 0}
    v = is_lawful(akin)
    # 12+24 bumps to the 13-14 bracket -> THAC0 7; hp 92 in [36, 120]
    assert v["lawful"], v["summary"]
    assert not v["summary"]["soft_fails"]


# --- waivers ---

def test_lich_waived_with_witness(monsters):
    from mechanus import known_waivers
    lich = monsters["lich"]
    v = is_lawful(lich)
    assert "skill_bonuses_math" in v["summary"]["hard_fails"]  # un-waived: fails
    w = known_waivers("lich")
    assert w and "p.325" in w[0]["witness"]
    v2 = is_lawful(lich, waivers=w)
    assert v2["lawful"]
    assert v2["summary"]["waived"] == ["skill_bonuses_math"]
    waived_check = next(c for c in v2["checks"] if c["name"] == "skill_bonuses_math")
    assert waived_check["result"] == "waived" and "witness" in waived_check["waiver"]


def test_waiver_without_witness_is_ignored(monsters):
    v = is_lawful(monsters["lich"], waivers=[{"check": "skill_bonuses_math", "reason": "trust me"}])
    assert not v["lawful"]  # a waiver without a witness is a blindfold


def test_curated_waiver_rides_in_envelope(monsters):
    lich = dict(monsters["lich"])
    lich["curated"] = {"lawful_waivers": [
        {"check": "skill_bonuses_math", "witness": "SRD 5.1 p.325", "reason": "print-attested"}]}
    assert is_lawful(lich)["lawful"]


def test_bits_bugs_stay_flagged_even_with_waiver_lookup(monsters):
    from mechanus import known_waivers
    for index in ("spider", "blink-dog", "black-bear", "swarm-of-ravens"):
        v = is_lawful(monsters[index], waivers=known_waivers(index))
        assert not v["lawful"], f"{index} is an upstream bug, not a deviation"
        assert "passive_perception_math" in v["summary"]["hard_fails"]


# --- V&V findings, pinned (2026-06-05 live-transport audit) ---

def test_f1_fractional_hd_is_lawful():
    """F1: '1/2' HD monsters are real 2e; <1 bracket -> THAC0 20, hp in [1,4]."""
    v = is_lawful({"name": "giant rat", "thac0": 20, "level_hd": "1/2", "hp": 3, "ac": 7})
    assert v["lawful"], v["summary"]
    assert not v["summary"]["soft_fails"]


def test_f2_minus_hd_demotes_at_one():
    """F2: '1-1 or less: 20' — the kobold row."""
    v = is_lawful({"name": "kobold", "thac0": 20, "level_hd": "1-1", "hp": 4, "ac": 7})
    assert v["lawful"], v["summary"]
    assert not v["summary"]["soft_fails"]


def test_f3_pb_corruption_cascades_by_design(vrock):
    """F3: a corrupted PB also un-derives save/skill math — intended cascade.
    Checks trust the STATED PB; a wrong PB makes the whole block unlawful."""
    vrock["proficiency_bonus"] = 4
    v = is_lawful(vrock)
    assert "pb_matches_cr" in v["summary"]["hard_fails"]
    assert "save_bonuses_math" in v["summary"]["hard_fails"]  # the cascade


# --- cross-validation gaps G1/G6, pinned (2026-06-05 three-skull seam audit) ---

SERVED_AKIN = {  # the shape Mimir's handbook.db actually serves (string numerics, HD in descriptor)
    "type": "npc", "name": "A'kin", "edition": "2e",
    "fields": {
        "descriptor": {"race": "arcanaloth", "level_hd": "12+24", "alignment": "NE"},
        "statblock": {"name": "A'kin", "ac": "-8", "hp": "92", "thac0": "7",
                      "num_attacks": "3", "damage": "1d4/1d4/2d6 (claw/claw/bite)",
                      "magic_resistance": "60%", "morale": "champion (16)", "xp": "20,000"}},
    "curated": {}, "confidence": 0.92,
}


def test_g1_served_envelope_runs_all_checks():
    """G1: string numerics coerce; level_hd found in descriptor — nothing skips."""
    v = is_lawful(SERVED_AKIN)
    assert v["shape"] == "envelope-2e"
    assert v["lawful"] and v["applicable"], v["summary"]
    assert v["summary"]["checks_run"] == 5 and v["summary"]["skipped"] == 0
    # THAC0 7 via 12+24 plus-bump; hp 92 in [36,120]; ac -8 in range
    for name in ("thac0_vs_hd", "hp_in_hd_range", "ac_2e_range"):
        assert _check(v, name)["result"] == "pass", name


def test_g6_statless_entity_is_inapplicable_not_lawful():
    """G6: an entity with no judgeable fields must say applicable=False —
    the gate treats that as 'no witness', never as confirmation."""
    faction_ish = {"type": "faction", "name": "Fraternity of Order", "edition": "2e",
                   "fields": {"philosophy": "the multiverse runs on laws"}}
    v = is_lawful(faction_ish)
    assert v["lawful"] is True          # no hard fails...
    assert v["applicable"] is False     # ...but no confirmation either
    assert v["summary"]["checks_run"] == 0
