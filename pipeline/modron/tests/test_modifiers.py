import pytest

from modron.conventions import get_pack
from modron.grammar import normal_form, parse
from modron.modifiers import (ModifierError, compose, define_local, registry,
                              resolve_d20_state, resolve_mods, search)


def test_registry_loads_both_editions():
    reg = registry()
    assert "bless" in reg and "great-weapon-fighting" in reg and "bless-2e" in reg


def test_search_by_view():
    ids = [r["id"] for r in search(view="2e")]
    assert "bless-2e" in ids and "bless" not in ids


def test_unknown_modifier_lists_registry():
    with pytest.raises(ModifierError, match="unknown modifier"):
        resolve_mods(["sodding-nonsense"])


def test_inline_requires_source():
    with pytest.raises(ModifierError, match="no source"):
        resolve_mods([{"id": "x", "effects": [{"op": "add", "expr": "2"}]}])


def test_view_mismatch_refused():
    with pytest.raises(ModifierError, match="views"):
        resolve_mods(["bless"], view="2e")


def test_bless_adds_d4_and_named_stacking():
    insts = resolve_mods(["bless", "bless"], view="5e-2014")
    comp = compose(parse("1d20+7"), insts, purpose="attack")
    assert normal_form(comp.ast) == "1d20+7+1d4"
    assert [m["id"] for m in comp.applied] == ["bless"]
    assert comp.skipped and comp.skipped[0]["id"] == "bless"


def test_untyped_stacks():
    insts = resolve_mods(["rear-attack", "higher-ground"], view="2e")
    comp = compose(parse("1d20"), insts, purpose="attack")
    assert normal_form(comp.ast) == "1d20+2+1"


def test_gwf_scopes_damage_dice_only():
    insts = resolve_mods(["great-weapon-fighting"], view="5e-2014")
    comp = compose(parse("2d6+1d20+4"), insts, purpose="damage")
    assert normal_form(comp.ast) == "2d6ro<=2+1d20+4"


def test_params_fill_expr():
    insts = resolve_mods([{"id": "sneak-attack", "params": {"n": 3}}], view="5e-2014")
    comp = compose(parse("1d8+4"), insts, purpose="damage")
    assert normal_form(comp.ast) == "1d8+4+3d6"
    with pytest.raises(ModifierError, match="missing params"):
        compose(parse("1d8"), resolve_mods(["sneak-attack"], view="5e-2014"),
                purpose="damage")


def test_crit_held_effects():
    insts = resolve_mods([{"id": "brutal-critical", "params": {"n": 1, "die": 12}}],
                         view="5e-2014")
    cold = compose(parse("1d12+4"), insts, purpose="damage", crit=False)
    assert normal_form(cold.ast) == "1d12+4"
    assert any("held" in n for n in cold.notes)
    hot = compose(parse("2d12+4"), insts, purpose="damage", crit=True)
    assert normal_form(hot.ast) == "2d12+4+1d12"


def test_wraps_apply_after_adds_5e_raw():
    """V&V catch 2026-06-05: vulnerability must double added dice (brutal critical,
    sneak attack) too — 5e RAW applies resistance/vulnerability after all other
    modifiers. Wraps compose LAST."""
    insts = resolve_mods([{"id": "brutal-critical", "params": {"n": 1, "die": 12}},
                          "vulnerability"], view="5e-2014")
    comp = compose(parse("2d12+4"), insts, purpose="damage", crit=True)
    assert normal_form(comp.ast) == "(2d12+4+1d12)*2"
    insts = resolve_mods([{"id": "sneak-attack", "params": {"n": 2}}, "resistance"],
                         view="5e-2014")
    comp = compose(parse("1d8+4"), insts, purpose="damage")
    assert normal_form(comp.ast) == "(1d8+4+2d6)/2"


def test_resistance_vulnerability_wraps():
    insts = resolve_mods(["resistance"], view="5e-2014")
    comp = compose(parse("8d6"), insts, purpose="damage")
    assert normal_form(comp.ast) == "8d6/2"
    insts = resolve_mods(["vulnerability"], view="5e-2014")
    comp = compose(parse("8d6"), insts, purpose="damage")
    assert normal_form(comp.ast) == "8d6*2"


def test_split_purpose_specialization():
    insts = resolve_mods(["weapon-specialization"], view="2e")
    atk = compose(parse("1d20"), insts, purpose="attack")
    dmg = compose(parse("1d8"), insts, purpose="damage")
    assert normal_form(atk.ast) == "1d20+1"
    assert normal_form(dmg.ast) == "1d8+2"


def test_d20_state_machine():
    pack = get_pack("5e-2014")
    expr, notes = resolve_d20_state({"advantage": ["x"], "disadvantage": [], "upgrades": []}, pack)
    assert expr == "2d20kh1"
    expr, notes = resolve_d20_state({"advantage": ["x"], "disadvantage": ["y"], "upgrades": []}, pack)
    assert expr == "1d20" and any("cancel" in n for n in notes)
    expr, notes = resolve_d20_state({"advantage": ["x", "y"], "disadvantage": [], "upgrades": []}, pack)
    assert expr == "2d20kh1" and any("don't stack" in n for n in notes)
    expr, notes = resolve_d20_state(
        {"advantage": ["x"], "disadvantage": [], "upgrades": ["elven_accuracy"]}, pack)
    assert expr == "3d20kh1"
    # upgrade without advantage does nothing
    expr, _ = resolve_d20_state(
        {"advantage": [], "disadvantage": [], "upgrades": ["elven_accuracy"]}, pack)
    assert expr == "1d20"


def test_define_local_roundtrip(tmp_path, monkeypatch):
    import modron.modifiers as M
    monkeypatch.setattr(M, "OVERLAY_PATH", tmp_path / "modifiers.local.json")
    define_local({"id": "house-crit-token", "label": "Crit token (+1d6)",
                  "effects": [{"op": "add", "expr": "1d6"}]})
    row = M.registry()["house-crit-token"]
    assert row["source"]["kind"] == "table"
    insts = resolve_mods(["house-crit-token"])
    comp = compose(parse("1d20"), insts)
    assert normal_form(comp.ast) == "1d20+1d6"
    with pytest.raises(ModifierError, match="unknown effect op"):
        define_local({"id": "bad", "label": "bad", "effects": [{"op": "wish", "expr": "9"}]})


def test_validate_effects_accepts_placeholder_die_sizes():
    """audit validator_placeholder_fill: '1d{die}' must validate (fill with a
    lawful die size, not 1) — the registry's own shipping shapes."""
    from modron.modifiers import _validate_effects
    _validate_effects([{"op": "add", "expr": "1d{die}"}])
    _validate_effects([{"op": "extra_crit_dice", "expr": "{n}d{die}"}])


def test_split_purpose_bare_roll_discloses_double_fire():
    """audit B-2-core-2e-07: bare roll() (no purpose) fires BOTH halves of a
    split-purpose modifier — loudly, never silently."""
    from modron.grammar import normal_form, parse
    from modron.modifiers import compose, resolve_mods
    insts = resolve_mods(["weapon-specialization"], view="2e")
    comp = compose(parse("1d20"), insts, purpose=None)
    nf = normal_form(comp.ast)
    assert "+1" in nf.replace(" ", "") and "+2" in nf.replace(" ", "")
    assert any("split-purpose" in n and "every half" in n for n in comp.notes)
    # with a purpose, only the matching half fires and no such note appears
    atk = compose(parse("1d20"), resolve_mods(["weapon-specialization"], view="2e"),
                  purpose="attack")
    nfa = normal_form(atk.ast).replace(" ", "")
    assert "+1" in nfa and "+2" not in nfa
    assert not any("split-purpose" in n for n in atk.notes)
