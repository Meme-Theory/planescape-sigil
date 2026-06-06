"""Rule-effect handoff §D — the Planescape setting substance (2026-06-06).

Pins: the 2e-planescape setting pack (extends 2e), the plane-scoped check
kinds (D1/D5/D6), the mechanus-seam modifiers (D2/D6), the rollables registry
(D1/D4/D7/D8/D9) and its resolution doors. Witnesses are official TSR scans:
the data files carry paraphrased mechanics + page cites, never prose — these
tests also pin THAT (cite-only law).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modron import conventions, registry, semantics, store  # noqa: E402
from modron.engine import DiceStream  # noqa: E402
from modron.grammar import parse  # noqa: E402
from modron.rollables import validate_table  # noqa: E402

SEED = b"planescape-tests-seed-0001"


def stream(counter: int = 0) -> DiceStream:
    return DiceStream(SEED, counter)


# ---------------------------------------------------------------------------
# The setting pack (Q2 ruling: extends-chain, not base-pack edit, not overlay)
# ---------------------------------------------------------------------------

def test_setting_pack_extends_2e_base():
    pack = conventions.get_pack("2e-planescape")
    # base 2e law inherited untouched
    assert pack["rounding"] == "down"
    assert pack["crit_effect"] == "none"
    assert pack["hp_from_hd"]["die"] == 8
    assert "attack" in pack["checks"] and "morale" in pack["checks"]
    # the setting kinds ride on top
    for kind in ("limbo_casting", "limbo_alteration", "limbo_miniflux",
                 "wind_madness", "styx_memory", "wasting_contraction"):
        assert kind in pack["checks"], kind
    # and the BASE pack stays pure — no setting kinds leak into plain 2e
    base = conventions.get_pack("2e")
    assert "limbo_casting" not in base["checks"]
    assert "wasting_contraction" not in base["checks"]


def test_setting_pack_is_not_an_overlay():
    """Setting law is printed law, not a house rule — it must NOT ride the
    overlay channel (overlays are disclosed as house variants)."""
    pack = conventions.get_pack("2e-planescape")
    assert pack["_overlays"] == []


# ---------------------------------------------------------------------------
# D1 — Limbo: casting test, alteration drift (sub-arithmetic + bands)
# ---------------------------------------------------------------------------

def test_limbo_casting_roll_under_with_nat20_fumble():
    rc = semantics.roll_check("limbo_casting", "2e-planescape", {"score": 17},
                              None, stream(1))
    out = rc["outcome"]
    assert out["op"] == "<=" and out["target"] == 17
    nat = out["natural"]
    if nat == 20:
        assert out["fumble"] is True and out["success"] is False
    else:
        assert out["success"] == (rc["total"] <= 17)


def test_limbo_casting_nat20_always_fails():
    """Natural 20 = fail + wild surge even when the score would cover it
    (chaos reflow p72): nat_fumble_auto_misses pins it."""
    spec, _ = conventions.get_check_spec("2e-planescape", "limbo_casting")
    assert spec["fumble_nat"] == [20]
    assert spec["nat_fumble_auto_misses"] is True
    # hunt a natural 20 on the stream to prove the override fires
    for counter in range(200):
        rc = semantics.roll_check("limbo_casting", "2e-planescape",
                                  {"score": 21}, None, stream(counter))
        if rc["outcome"]["natural"] == 20:
            assert rc["outcome"]["success"] is False
            assert rc["outcome"]["fumble"] is True
            return
    pytest.fail("no natural 20 in 200 draws — stream is broken")


def test_limbo_alteration_arithmetic_and_bands():
    """TABLE IV: 1d100 + spell_level - caster_level, banded. The 'sub' pack
    key (added for this kind) must subtract caster_level."""
    rc = semantics.roll_check("limbo_alteration", "2e-planescape",
                              {"spell_level": 3, "caster_level": 9}, None, stream(2))
    assert rc["expr_resolved"] == "1d100+3-9"
    assert rc["outcome"].get("band")  # a band always lands (-999..999 coverage)
    # band edges per the witness
    spec, _ = conventions.get_check_spec("2e-planescape", "limbo_alteration")
    bands = {(b["min"], b["max"]): b["label"] for b in spec["bands"]}
    assert bands[(-999, 20)] == "no special effect"
    assert bands[(81, 999)] == "highly modified appearance and properties"


def test_limbo_alteration_low_caster_high_spell_skews_up():
    """A tyro's toughest spell (9th at level 1) adds +8 net — the band math
    must reflect the printed direction (modest spells by experts are safer)."""
    rc = semantics.roll_check("limbo_alteration", "2e-planescape",
                              {"spell_level": 9, "caster_level": 1}, None, stream(3))
    assert rc["expr_resolved"] == "1d100+9-1"
    assert rc["total"] == rc["groups"][0]["value"] + 8


def test_d1_lookups_served_not_rolled():
    """TABLE III (terrain) and TABLE V (outcome matrix) are diceless lookups:
    served by the registry, REFUSED by the table-roll door (no invented dice)."""
    terrain = registry.get("lkp:2e:limbo:terrain-maintenance")
    assert terrain and terrain["kind"] == "lookup"
    assert len(terrain["rows"]) == 5
    with pytest.raises(store.EntityNotFound, match="never rolled"):
        store.find_table("lkp:2e:limbo:terrain-maintenance")


# ---------------------------------------------------------------------------
# D2 — school-alteration deltas cite the Mechanus seam (Q3 standardized)
# ---------------------------------------------------------------------------

def test_d2_modifiers_cite_mechanus_minted():
    """The D2 asserter seam, post-mint: refs are bare resolvable law ids
    (upgraded from 'pending M* mint' by audit court-mechanus, 2026-06-06);
    the page witness rides the notes."""
    from modron.modifiers import registry as mod_registry
    reg = mod_registry()
    for mid in ("enhanced-school-save-penalty", "enhanced-school-protection-bonus",
                "spell-key-casting-delay"):
        row = reg[mid]
        assert row["source"]["kind"] == "mechanus", mid
        assert row["source"]["ref"].startswith("law:"), mid
        assert "pending" not in row["source"]["ref"], mid
        assert "witness" in row["notes"], mid               # page rides the notes


def test_d2_save_penalty_composes():
    rc = semantics.roll_check("save", "2e-planescape", {"target": 13},
                              ["enhanced-school-save-penalty"], stream(4))
    assert rc["expr_resolved"] == "1d20-1"
    assert [m["id"] for m in rc["modifiers"]] == ["enhanced-school-save-penalty"]


def test_d2_spell_key_delay_is_initiative_penalty():
    rc = semantics.roll_check("initiative", "2e-planescape", {},
                              ["spell-key-casting-delay"], stream(5))
    assert rc["expr_resolved"] == "1d10+1"      # 2e: low wins — +1 is a penalty
    assert rc["outcome"]["order"] == "asc"


# ---------------------------------------------------------------------------
# D5 / D6 — Wasting + wind madness
# ---------------------------------------------------------------------------

def test_wasting_contraction_fixed_ten_percent():
    rc = semantics.roll_check("wasting_contraction", "2e-planescape", {}, None, stream(6))
    out = rc["outcome"]
    assert out["target"] == 10 and out["op"] == "<="
    assert out["success_means"] == "contracted the Wasting"
    assert out["success"] == (rc["total"] <= 10)


def test_wind_madness_save_margin_reads_per_pack():
    rc = semantics.roll_check("wind_madness", "2e-planescape", {"target": 13},
                              None, stream(7))
    out = rc["outcome"]
    assert out["op"] == ">="
    # hysteria duration = margin of failure: pinned via margin sign convention
    assert out["margin"] == rc["total"] - 13


def test_wind_madness_stage_modifiers():
    # stage 1: -1 Wis/Int encoded as +1 on the roll-under d20
    rc = semantics.roll_check("ability", "2e-planescape", {"score": 14},
                              ["wind-madness-frustration"], stream(8))
    assert rc["expr_resolved"] == "1d20+1"
    assert rc["outcome"]["target"] == 14
    # stage 2: +1 attack / +1 damage, split-purpose
    atk = semantics.roll_check("attack", "2e-planescape", {"thac0": 17, "ac": 5},
                               ["wind-madness-despair"], stream(9))
    assert atk["expr_resolved"] == "1d20+1"
    dmg = semantics.roll_damage("1d8", "2e-planescape",
                                ["wind-madness-despair"], stream(10))
    assert dmg["expr_resolved"] == "1d8+1"


def test_styx_memory_success_still_costs():
    """The styx_memory kind: success = lose the past day (the notes carry it);
    procedure is a plain save vs supplied target."""
    rc = semantics.roll_check("styx_memory", "2e-planescape", {"target": 14},
                              None, stream(11))
    assert rc["outcome"]["op"] == ">="
    assert any("past day" in n for n in rc["notes"])


# ---------------------------------------------------------------------------
# Registry: load law, doors, D4/D7/D8/D9 content
# ---------------------------------------------------------------------------

def test_registry_loads_and_every_entry_is_sourced():
    reg = registry.registry()
    assert len(reg) >= 30
    for rid, row in reg.items():
        src = row["source"]
        assert src.get("product") and src.get("page"), rid
        assert src.get("cite_only") is True, rid    # official scans: cite-only


def test_registry_refuses_unsourced_entries(tmp_path, monkeypatch):
    bad = tmp_path / "bad.json"
    bad.write_text('[{"id": "x", "kind": "spec", "spec": {"expr": "1d6"}}]',
                   encoding="utf-8")
    monkeypatch.setattr(registry, "ROLLABLES_DIR", tmp_path)
    with pytest.raises(registry.RegistryError, match="no source"):
        registry.registry()


def test_registry_tables_validate_coverage_at_load():
    for row in registry.search(kind="table"):
        assert validate_table(row["table"])["verdict"] == "ok", row["id"]


def test_registry_spec_exprs_parse():
    for row in registry.search(kind="spec"):
        expr = row["spec"].get("expr")
        if expr:
            parse(expr)  # raises on garbage


def test_d4_slags_vortex_table_via_find_table():
    t, src = store.find_table("tbl:2e:sigil:slags-vortex-type")
    assert src == "rollables-registry:tbl:2e:sigil:slags-vortex-type"
    assert t["dice"] == "1d4"
    report = validate_table(t)
    assert report["verdict"] == "ok" and report["range"] == [1, 4]
    # the secret-roll split: 1-3 portal, 4 hurl
    rows = {e["roll"]: e["result"] for e in t["entries"]}
    assert "Prime" in rows["1-3"]
    assert "1d6 x 10 feet" in rows["4"]


def test_d4_ooze_portal_bundle():
    save = registry.get("spc:2e:sigil:ooze-portal-save")
    assert save["spec"]["check"]["kind"] == "save"
    rescue = registry.get("spc:2e:sigil:ooze-portal-rescue")
    assert rescue["spec"]["check"] == {"kind": "proficiency", "params": {"check_mod": -2}}
    vanish = registry.get("spc:2e:sigil:ooze-portal-vanish")
    assert vanish["spec"]["expr"] == "1d4+1"


def test_d7_hazard_damage_specs():
    fire = registry.get("dmg:2e:inner:fire-pocket")
    assert fire["spec"] == {"purpose": "damage", "expr": "1d20",
                            "label": "fire pocket, unprotected / round"}
    neg = registry.get("dmg:2e:inner:negative-energy-drain")
    assert neg["spec"]["expr"] == "2d6"
    pos = registry.get("spc:2e:inner:positive-energy-gain")
    assert pos["spec"]["purpose"] == "healing"   # gain is healing, honestly typed
    magma = registry.get("lkp:2e:inner:magma-ambient-by-ac")
    assert magma["kind"] == "lookup"
    exprs = {r["key"]: r["expr"] for r in magma["rows"]}
    # full seven-band chart, keyed to NATURAL AC (audit C-4-inner-b-01/-02)
    assert exprs["natural AC 10 to 8"] == "6d8"
    assert exprs["natural AC 4 to 2"] == "4d8"
    assert exprs["natural AC -8 to -10"] == "none"
    assert len(magma["rows"]) == 7


def test_d8_acheron_landing():
    row = registry.get("dmg:2e:acheron:freefloat-landing")
    assert row["spec"]["expr"] == "20d6"
    assert "no dice" in row["notes"]             # collision amendment recorded


def test_d9_harmonium_patrol_encounter_compiles():
    from modron.rollables import encounter_plan
    row = registry.get("enc:2e:sigil:harmonium-patrol")
    pack = conventions.get_pack("2e-planescape")
    plan = encounter_plan(row["encounter"], pack, "2e-planescape")
    steps = [p["step"] for p in plan]
    assert "number" in steps and "reaction" in steps and "initiative" in steps
    number = next(p for p in plan if p["step"] == "number")
    # '2-4' inverts bonus-free-first (rank law): 2d2, with 1d3+1 surfaced
    assert number["expr"] == "2d2"
    assert "1d3+1" in number.get("alternatives", [])
    assert "morale" not in steps                  # no printed morale — never invented


def test_d9_mancatcher_specs():
    grab = registry.get("spc:2e:sigil:mancatcher-struggle")
    assert grab["spec"]["expr"] == "1d2"
    shock = registry.get("spc:2e:sigil:mancatcher-shift-shock")
    assert shock["spec"]["expr"] == "1d10"
    assert "cumulative 1%" in shock["notes"]


def test_registry_search_by_used_at():
    limbo = registry.search(used_at="plane:limbo")
    assert {r["id"] for r in limbo} >= {
        "lkp:2e:limbo:terrain-maintenance", "lkp:2e:limbo:spellcasting-outcomes",
        "spc:2e:limbo:guidon-malfunction"}
    hive = registry.search(used_at="location:sigil:hive-ward")
    assert len(hive) == 4


def test_ocr_adjudicated_entry_carries_the_ruling():
    """The illusion-real 'IOOfo' was adjudicated 10% CONFIRMED (audit
    C-1-chaos-law-02): the requires_confirmation flag retires and the
    adjudication rides the notes."""
    row = registry.get("spc:2e:limbo:illusion-becomes-real")
    assert "requires_confirmation" not in row
    assert "adjudicated 10%" in row["notes"] and "OCR" in row["notes"]


# ---------------------------------------------------------------------------
# server-door integration (the rollables tool's registry branch)
# ---------------------------------------------------------------------------

def test_server_rollables_serves_registry_ids_and_used_at():
    import asyncio
    import json as _json
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import server as srv

    def call(handler, args):
        out = asyncio.get_event_loop().run_until_complete(handler(args))
        return _json.loads(out[0].text)

    by_id = call(srv._rollables, {"entity": "dmg:2e:inner:fire-pocket"})
    assert by_id["rollable"] == "dmg:2e:inner:fire-pocket"
    assert by_id["entry"]["source"]["cite_only"] is True

    # plane:limbo IS a poured Mimir entity — the entity wins the name and the
    # registry's used_at matches ride along (the designed precedence)
    by_place = call(srv._rollables, {"entity": "plane:limbo"})
    assert by_place["entity"] == "Limbo"
    assert any(m["id"] == "lkp:2e:limbo:terrain-maintenance"
               for m in by_place["registry_rollables"])

    # a used_at ref that is NOT a resolvable entity (Inner Planes aren't
    # poured yet) falls to registry_matches
    by_plane = call(srv._rollables, {"entity": "plane:salt"})
    assert "registry_matches" in by_plane
    assert any(m["id"] == "dmg:2e:inner:salt-dehydration"
               for m in by_plane["registry_matches"])
