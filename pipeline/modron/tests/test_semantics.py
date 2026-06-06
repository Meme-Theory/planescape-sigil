import pytest

from modron.engine import DiceStream, seed_from_phrase
from modron.semantics import CheckError, roll_check, roll_damage

SEED = seed_from_phrase("semantics-vectors")


def _scan_for(kind, view, params, want, max_counter=400, **kw):
    """Find a counter whose roll satisfies a predicate — determinism makes this honest."""
    for i in range(max_counter):
        r = roll_check(kind, view, params, kw.get("mods"), DiceStream(SEED, i),
                       state=kw.get("state"))
        if want(r):
            return r
    raise AssertionError(f"no counter under {max_counter} satisfied the predicate")


def test_5e_attack_anatomy():
    r = roll_check("attack", "5e-2014", {"attack_bonus": 7, "ac": 15}, None,
                   DiceStream(SEED, 1))
    assert r["expr_resolved"] == "1d20+7"
    assert r["outcome"]["target"] == 15
    assert r["outcome"]["success"] == (r["total"] >= 15)
    assert 1 <= r["outcome"]["natural"] <= 20


def test_5e_nat20_crit_and_auto_hit():
    r = _scan_for("attack", "5e-2014", {"attack_bonus": 0, "ac": 30},
                  lambda r: r["outcome"].get("natural") == 20)
    assert r["outcome"]["crit"] is True
    assert r["outcome"]["success"] is True          # auto-hit beats AC 30
    assert any("automatic success" in n for n in r["notes"])


def test_5e_nat1_auto_miss():
    r = _scan_for("attack", "5e-2014", {"attack_bonus": 50, "ac": 5},
                  lambda r: r["outcome"].get("natural") == 1)
    assert r["outcome"]["fumble"] is True and r["outcome"]["success"] is False


def test_2e_thac0_hits_ac_derived():
    r = roll_check("attack", "2e", {"thac0": 7, "ac": 3}, None, DiceStream(SEED, 5))
    assert r["outcome"]["target"] == 4                      # 7 - 3
    assert r["outcome"]["hits_ac"] == 7 - r["total"]        # descending AC
    assert r["outcome"]["success"] == (r["total"] >= 4) or r["outcome"]["natural"] in (1, 20)


def test_2e_ability_roll_under():
    r = roll_check("ability", "2e", {"score": 13}, None, DiceStream(SEED, 6))
    assert r["outcome"]["op"] == "<="
    assert r["outcome"]["success"] == (r["total"] <= 13)


def test_2e_proficiency_modifies_target():
    r = roll_check("proficiency", "2e", {"score": 13, "check_mod": -2}, None,
                   DiceStream(SEED, 7))
    assert r["outcome"]["target"] == 11


def test_2e_morale_margin():
    r = roll_check("morale", "2e", {"morale": 16}, None, DiceStream(SEED, 8))
    assert 2 <= r["total"] <= 20
    assert r["outcome"]["margin"] == 16 - r["total"]


def test_2e_reaction_bands():
    """FG&G Table 10.7 is a 2D disposition matrix (audit A-1-2e-10): default
    column = indifferent, disclosed."""
    r = roll_check("reaction", "2e", {"cha_mod": 0}, None, DiceStream(SEED, 9))
    assert r["outcome"]["band"] in ("friendly", "indifferent", "cautious",
                                    "threatening", "hostile", "flight")
    assert r["outcome"]["disposition"] == "indifferent"
    assert any("default column" in n for n in r["notes"])


def test_2e_reaction_disposition_columns():
    """audit A-1-2e-10: each party-disposition column reads its own bands;
    a hostile party at low totals reads FLIGHT (FG&G p84, Table 10.7)."""
    low = _scan_for("reaction", "2e", {"cha_mod": 0, "disposition": "hostile"},
                    lambda r: r["total"] <= 5)
    assert low["outcome"]["band"] == "flight"
    assert low["outcome"]["disposition"] == "hostile"
    friendly = _scan_for("reaction", "2e", {"cha_mod": 0, "disposition": "friendly"},
                         lambda r: r["total"] <= 7)
    assert friendly["outcome"]["band"] == "friendly"
    unknown = roll_check("reaction", "2e", {"cha_mod": 0, "disposition": "confused"},
                         None, DiceStream(SEED, 11))
    assert "band" not in unknown["outcome"]
    assert any("no band column" in n for n in unknown["notes"])


def test_2e_surprise_means():
    r = roll_check("surprise", "2e", {}, None, DiceStream(SEED, 10))
    assert r["outcome"]["target"] == 3
    if r["outcome"]["success"]:
        assert r["outcome"]["success_means"] == "surprised"


def test_missing_target_param_noted_not_invented():
    r = roll_check("save", "5e-2014", {"save_bonus": 5}, None, DiceStream(SEED, 11))
    assert "success" not in r["outcome"]
    assert any("no success verdict" in n for n in r["notes"])


def test_state_on_2e_ignored_with_note():
    r = roll_check("ability", "2e", {"score": 10}, None, DiceStream(SEED, 12),
                   state="advantage")
    assert r["expr_resolved"] == "1d20"
    assert any("no d20 state machine" in n for n in r["notes"])


def test_advantage_changes_expr_and_naturals():
    r = roll_check("check", "5e-2014", {"mod": 3, "dc": 10}, None,
                   DiceStream(SEED, 13), state="advantage")
    assert r["expr_resolved"].startswith("2d20kh1")
    g = r["groups"][0]
    assert len(g["dice"]) == 2 and sum(1 for d in g["dice"] if d["kept"]) == 1


def test_unknown_kind_lists_menu():
    with pytest.raises(KeyError, match="available:"):
        roll_check("limbo-swim", "2e", {}, None, DiceStream(SEED, 14))


def test_unknown_param_type_refused():
    with pytest.raises(CheckError):
        roll_check("attack", "5e-2014", {"attack_bonus": "seven", "ac": 15}, None,
                   DiceStream(SEED, 15))


def test_damage_crit_doubles_dice_not_mods():
    r = roll_damage("2d6+4", "5e-2014", ["great-weapon-fighting"],
                    DiceStream(SEED, 16), crit=True)
    assert r["expr_resolved"] == "4d6ro<=2+4"
    assert r["crit"] is True


def test_damage_crit_2e_is_none_and_says_so():
    r = roll_damage("1d8+1", "2e", None, DiceStream(SEED, 17), crit=True)
    assert r["expr_resolved"] == "1d8+1"
    assert any("no critical effect" in n for n in r["notes"])
