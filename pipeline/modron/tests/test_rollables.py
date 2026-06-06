from modron.conventions import get_pack
from modron.rollables import (avg_crosscheck, encounter_plan, hp_range_crosscheck,
                              parse_class_hp, parse_hd, prose_sweep, range_to_dice,
                              resolve_table_roll, statblock_2e, statblock_5e,
                              text_to_expr, validate_table)

PACK_2E = get_pack("2e")
PACK_5E = get_pack("5e-2014")


def test_range_inversions():
    assert range_to_dice(3, 18)["expr"] == "3d6"
    assert range_to_dice(2, 12)["expr"] == "2d6"
    assert range_to_dice(1, 6)["expr"] == "1d6"
    assert range_to_dice(2, 8)["expr"] == "2d4"
    r = range_to_dice(5, 8)
    assert r["expr"] == "1d4+4" and r["ambiguous"] and r["alternatives"]
    assert range_to_dice(6, 5) is None
    assert range_to_dice(0, 5) is None


def test_text_to_expr_paths():
    assert text_to_expr("2d6+1")["expr"] == "2d6+1"
    assert text_to_expr("3-18")["expr"] == "3d6"
    assert text_to_expr("3-18")["inverted_from_range"] == [3, 18]
    assert text_to_expr("Id4")["expr"] == "1d4"        # OCR leniency
    assert text_to_expr("ld6 + 2")["expr"] == "1d6+2"
    assert text_to_expr("gibberish") is None


def test_parse_hd_forms():
    assert parse_hd("12+24", PACK_2E)["expr"] == "12d8+24"
    assert parse_hd("8", PACK_2E)["expr"] == "8d8"
    assert parse_hd("1-1", PACK_2E)["expr"] == "1d8-1"
    assert parse_hd("1/2", PACK_2E)["expr"] == "2d2"   # FG&G printed 283 (audit court-fgg)
    assert parse_hd("variable", PACK_2E) is None
    explicit = parse_hd("9d4+23", PACK_2E)             # audit G-2-npc-a-05
    assert explicit["expr"] == "9d4+23" and "explicit" in explicit["note"]


def test_crosschecks_honest():
    assert avg_crosscheck(14, "2d8+5")["verdict"] == "ok"
    bad = avg_crosscheck(19, "2d8+5")
    assert bad["verdict"] == "MISMATCH" and bad["floor_mean"] == 14
    assert hp_range_crosscheck(92, "12d8+24")["verdict"] == "ok"
    assert hp_range_crosscheck(200, "12d8+24")["verdict"] == "OUT_OF_RANGE"


AKIN_MIN = {
    "type": "npc", "name": "A'kin",
    "descriptor": {"level_hd": "12+24"},
    "statblock": {"ac": "-8", "hp": "92", "thac0": "7", "num_attacks": "3",
                  "damage": "1d4/1d4/2d6 (claw/claw/bite)",
                  "magic_resistance": "60%", "morale": "champion (16)"},
    "sections": {"SPELLS": "gate (I/day; Id6 mezzoloths, Id2 dergholoths; "
                           "40% chance of success)"},
}


def test_statblock_2e_compiles_the_arcanaloth():
    specs = statblock_2e(AKIN_MIN, PACK_2E)
    by_key = {s["key"]: s for s in specs}
    assert by_key["attack"]["check"]["params"]["thac0"] == 7
    assert by_key["damage.1"]["expr"] == "1d4" and by_key["damage.1"]["label"] == "claw"
    assert by_key["damage.3"]["expr"] == "2d6" and by_key["damage.3"]["label"] == "bite"
    assert by_key["magic_resistance"]["check"]["params"]["pct"] == 60
    assert by_key["morale"]["check"]["params"]["morale"] == 16
    assert by_key["hp"]["expr"] == "12d8+24"
    assert by_key["hp"]["crosscheck"]["verdict"] == "ok"
    assert "save" in by_key and by_key["save"]["needs"]


def test_prose_sweep_ocr_and_percent():
    specs = prose_sweep(AKIN_MIN)
    exprs = {s.get("expr") for s in specs if "expr" in s}
    assert "1d6" in exprs and "1d2" in exprs
    pcts = [s["check"]["params"]["pct"] for s in specs if s.get("check")]
    assert 40 in pcts
    assert all(s["requires_confirmation"] for s in specs)


VROCK_5E = {
    "name": "Vrock", "edition": "5e-2014",
    "statblock": {
        "hp": "104 (11d10+44)",
        "actions": [
            {"name": "Beak", "text": "Melee Weapon Attack: +6 to hit, reach 5 ft. "
                                     "Hit: 10 (2d6+3) piercing damage."},
            {"name": "Talons", "text": "Melee Weapon Attack: +6 to hit. "
                                       "Hit: 14 (2d10+3) slashing damage."},
            {"name": "Spores (Recharge 6)", "text": "Each creature within 15 feet must "
                                                    "succeed on a DC 14 Constitution saving throw."},
            {"name": "Stunning Screech (1/Day)", "text": "DC 14 Constitution saving throw "
                                                         "or be stunned."},
        ],
    },
}


def test_statblock_5e_compiles_the_vrock():
    specs = statblock_5e(VROCK_5E, PACK_5E)
    by_key = {s["key"]: s for s in specs}
    assert by_key["hp"]["expr"] == "11d10+44"
    assert by_key["hp"]["crosscheck"]["verdict"] == "ok"     # mean 104.5 -> floor 104
    assert by_key["attack.Beak"]["check"]["params"]["attack_bonus"] == 6
    assert by_key["damage.Beak"]["expr"] == "2d6+3"
    assert by_key["damage.Beak"]["crosscheck"]["verdict"] == "ok"
    assert by_key["save.Spores (Recharge 6)"]["check"]["params"]["dc"] == 14
    assert by_key["recharge.Spores (Recharge 6)"]["check"]["params"]["threshold"] == 6


def test_statblock_5e_versatile_and_mismatch():
    ent = {"name": "Guard", "statblock": {"actions": [
        {"name": "Spear", "text": "Melee or Ranged Weapon Attack: +3 to hit. "
                                  "Hit: 4 (1d6+1) piercing damage, or 5 (1d8+1) "
                                  "if used with two hands."},
        {"name": "Lyingblade", "text": "Hit: 19 (2d8+5) slashing damage."},
    ]}}
    specs = statblock_5e(ent, PACK_5E)
    by_key = {s["key"]: s for s in specs}
    assert by_key["damage.Spear"]["expr"] == "1d6+1"
    assert by_key["damage.Spear.versatile"]["expr"] == "1d8+1"
    assert by_key["damage.Lyingblade"]["crosscheck"]["verdict"] == "MISMATCH"


def test_table_validation_and_resolution():
    t = {"dice": "1d100", "entries": [
        {"roll": "01-50", "result": "razorvine"},
        {"roll": "51-90", "result": "cranium rats"},
        {"roll": "97-00", "result": "the Lady's shadow"},
    ]}
    report = validate_table(t)
    assert report["verdict"] == "COVERAGE_ISSUES"
    assert report["gaps"] == [[91, 96]]
    assert resolve_table_roll(t, 100)["result"] == "the Lady's shadow"   # 00 -> 100
    assert resolve_table_roll(t, 1)["result"] == "razorvine"
    assert resolve_table_roll(t, 93) is None

    full = {"dice": "1d6", "entries": [{"roll": "1-3", "result": "a"},
                                       {"roll": "4-6", "result": "b"}]}
    assert validate_table(full)["verdict"] == "ok"
    overlap = {"dice": "1d6", "entries": [{"roll": "1-4", "result": "a"},
                                          {"roll": "4-6", "result": "b"}]}
    assert validate_table(overlap)["overlaps"]


def test_class_hp_and_hd_tripwires():
    """Family-integration catches G4 + the Cirily tripwire (2026-06-05)."""
    from modron.rollables import parse_class_hp
    f9 = parse_class_hp("F9", "9")
    assert f9["expr"] == "9d10" and f9["con_allowance"] == 36   # warrior: up to +4/die
    m12 = parse_class_hp("M12", None)
    assert m12["expr"] == "10d4+2"     # wizards gain dice to 10 (FG&G p20; audit court-fgg)
    assert parse_class_hp("O-level", None)["expr"] == "1d6"
    assert parse_class_hp(None, "9") is None
    fused = parse_hd("740", PACK_2E)                             # OCR ate '+': 7+10 → 740
    assert fused["suspect"] and "implausible" in fused["note"]

    tarholt = {"name": "Tarholt", "descriptor": {"level_hd": "9", "char_class": "F9"},
               "statblock": {"hp": "76"}}
    specs = statblock_2e(tarholt, PACK_2E)
    hp = next(s for s in specs if s["key"] == "hp")
    assert hp["expr"] == "9d10"
    assert hp["crosscheck"]["verdict"] == "ok"                   # 76 ∈ [9,90]+Con allowance
    no_hd = {"name": "Estavan", "statblock": {"hp": "34"}}
    hp = next(s for s in statblock_2e(no_hd, PACK_2E) if s["key"] == "hp")
    assert hp["purpose"] == "info" and hp["printed_hp"] == 34    # visible, never silent


def test_damage_modes_and_multipliers():
    """G3: ' or ' alternative modes + xN multiplied attacks (Ly'kritch idiom)."""
    specs = _split_for_test("1d6/1d6/1d8 (claw/claw/bite) or 1d6x4 (clawx4)")
    by_key = {s["key"]: s for s in specs}
    assert by_key["damage.1.3"]["expr"] == "1d8"                 # mode 1: bite
    x4 = [s for s in specs if s["key"].startswith("damage.2.")]
    assert len(x4) == 4 and all(s["expr"] == "1d6" for s in x4)
    assert "[mode 2]" in x4[0]["label"]


def _split_for_test(damage):
    from modron.rollables import _split_damage
    return _split_damage(damage)


def test_mimir_envelope_unwrap_parity():
    """Family-integration catch G1 (2026-06-05): handbook.db rows nest payload
    under `fields`; the compiler must see through it. Envelope and flat shapes
    must compile to identical specs."""
    from modron.rollables import compile_entity, detect_view, unwrap_envelope
    enveloped = {"type": "npc", "name": AKIN_MIN["name"], "edition": "2e",
                 "confidence": 0.92,
                 "fields": {k: v for k, v in AKIN_MIN.items()
                            if k in ("descriptor", "statblock", "sections")}}
    assert detect_view(enveloped) == "2e"
    flat_specs = compile_entity(AKIN_MIN, PACK_2E, "2e")
    env_specs = compile_entity(enveloped, PACK_2E, "2e")
    assert [s["key"] for s in env_specs] == [s["key"] for s in flat_specs]
    assert any(s["key"] == "hp" and s["expr"] == "12d8+24" for s in env_specs)
    # entity-level keys win on collision; no-fields shape is a no-op
    assert unwrap_envelope(AKIN_MIN) is AKIN_MIN or unwrap_envelope(AKIN_MIN) == AKIN_MIN


def test_encounter_plan_2e_doctrine():
    spec = {"check": {"expr": "1d10", "encounter_on": "<=1"},
            "number_appearing": "2d4",
            "creature": {"hd": "8+3", "morale": 12},
            "distance": "10d10",
            "reaction": {"cha_mod": 0}}
    plan = encounter_plan(spec, PACK_2E, "2e")
    steps = [p["step"] for p in plan]
    assert steps == ["check", "number", "hp", "surprise", "distance", "reaction",
                     "initiative", "initiative", "morale"]
    hp = next(p for p in plan if p["step"] == "hp")
    assert hp["expr"] == "8d8+3" and hp["per_creature"]
    morale = next(p for p in plan if p["step"] == "morale")
    assert morale["armed"] is True


def test_encounter_plan_5e_doctrine_minimal():
    plan = encounter_plan({"number_appearing": "1d4+1",
                           "creature": {"hp_expr": "11d10+44"}}, PACK_5E, "5e-2014")
    steps = [p["step"] for p in plan]
    assert steps == ["number", "hp", "initiative", "initiative"]


def test_encounter_initiative_sides_override():
    """§12 Q2 (Ryan, 2026-06-05): both sides by default; spec omits a side."""
    spec = {"steps": ["initiative"],
            "initiative": {"sides": ["monsters"], "monsters": {"mod": 1}}}
    plan = encounter_plan(spec, PACK_2E, "2e")
    assert [p["side"] for p in plan] == ["monsters"]
    assert plan[0]["check"]["params"] == {"mod": 1}
    both = encounter_plan({"steps": ["initiative"]}, PACK_2E, "2e")
    assert [p["side"] for p in both] == ["party", "monsters"]


# ---------------------------------------------------------------------------
# Audit round 2 regressions (correction-docket 2026-06-06, lane L4)
# ---------------------------------------------------------------------------

BURAQ_FLAT = {
    "type": "creature", "name": "Buraq", "edition": "2e",
    "thac0": "13", "hit_dice": "7+7", "damage_attack": "1d4/1d4",
    "no_of_attacks": "2", "magic_resistance": "30%", "morale": "elite (14)",
    "armor_class": "2",
}


def test_mc_flat_creature_compiles_fully():
    """audit G-1-creatures-01: MC flat fields alias into statblock shape —
    THAC0/damage/MR/morale/HD must all compile, never the 1-spec ghost."""
    specs = statblock_2e(BURAQ_FLAT, PACK_2E)
    keys = {s["key"] for s in specs}
    assert "attack" in keys and "hp" in keys and "morale" in keys \
        and "magic_resistance" in keys
    hp = next(s for s in specs if s["key"] == "hp")
    assert hp["expr"] == "7d8+7"
    atk = next(s for s in specs if s["key"] == "attack")
    assert atk["check"]["params"]["thac0"] == 13
    # provenance keeps the FLAT field names (the envelope's truth)
    assert atk["provenance"]["field"] == "thac0"
    assert hp["provenance"]["field"] == "descriptor.level_hd" or \
        hp["provenance"]["raw"] == "7+7"
    dmg = [s for s in specs if s["purpose"] == "damage"]
    assert len(dmg) == 2
    # nested statblock still wins when present (npc shape untouched)
    nested = statblock_2e(AKIN_MIN, PACK_2E)
    assert next(s for s in nested if s["key"] == "attack")["provenance"]["field"] \
        == "statblock.thac0"


def test_class_hp_specialist_illusionist_never_monster_d8():
    """audit G-5-clean-sample-01: 'Ill 12' is a specialist wizard — d4 group,
    dice cap 10 — never 12d8 monster dice."""
    ill = parse_class_hp("Ill 12", "12")
    assert ill is not None and ill["expr"] == "10d4+2"
    kesto = {"name": "Kesto", "descriptor": {"char_class": "Ill 12", "level_hd": "12"},
             "statblock": {"hp": "27"}}
    hp = next(s for s in statblock_2e(kesto, PACK_2E) if s["key"] == "hp")
    assert hp["expr"] == "10d4+2"


def test_class_hp_per_class_dice_caps():
    """audit court-fgg _provisional:class-hd: rogues/wizards gain dice to 10."""
    assert parse_class_hp("T10", None)["expr"] == "10d6"
    assert parse_class_hp("T11", None)["expr"] == "10d6+2"
    assert parse_class_hp("M10", None)["expr"] == "10d4"
    assert parse_class_hp("F10", None)["expr"] == "9d10+3"
    assert parse_class_hp("C10", None)["expr"] == "9d8+2"


def test_multiclass_never_silent():
    """audit G-2-npc-a-09: 'F7,M4' must not silently degrade to monster d8s."""
    djhek = {"name": "Djhek", "descriptor": {"char_class": "F7,M4", "level_hd": "7"},
             "statblock": {"hp": "39"}}
    hp = next(s for s in statblock_2e(djhek, PACK_2E) if s["key"] == "hp")
    assert hp.get("requires_confirmation") is True
    assert "component class HD: 7d10, 4d4" in hp["note"]
    assert "SUSPECT" in hp["note"]


def test_zero_level_digit_door():
    """audit G-4-hp-roster-06: '0-level' (digit zero) == 'O-level' (letter O)."""
    o = parse_class_hp("O-level", None)
    z = parse_class_hp("0-level", None)
    assert o and z and o["expr"] == z["expr"] == "1d6"
    assert "per-profession" in z["note"]


def test_morale_band_name_visible_not_silent():
    """audit G-2-npc-a-13: a printed morale with no parseable rating emits a
    VISIBLE flagged spec, never silence."""
    kylie = {"name": "Kylie", "statblock": {"morale": "champion"}}
    specs = statblock_2e(kylie, PACK_2E)
    m = next(s for s in specs if s["key"] == "morale")
    assert m["purpose"] == "info" and m["requires_confirmation"] is True
    assert m["raw_morale"] == "champion"


def test_prose_sweep_stat_array_guard():
    """audit G-2/G-3 (seven denied specs): ' D 13' inside a 2e ability array
    must not parse as 1d13."""
    npc = {"name": "Adamok", "sections": {
        "SOURCE": "Uncaged page. S 16, D 13, C 16, I 15, W 14, Ch 8. More prose.",
        "TACTICS": "Her blade deals 2d6 damage in melee.",
    }}
    specs = prose_sweep(npc)
    exprs = [s.get("expr") for s in specs if s.get("expr")]
    assert "1d13" not in exprs and "1d15" not in exprs and "1d16" not in exprs
    assert "2d6" in exprs       # real prose dice still sweep (flagged)
