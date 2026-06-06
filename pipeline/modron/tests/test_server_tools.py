"""Server-level integration: the tool handlers end-to-end (no stdio transport)."""

import asyncio
import json
from pathlib import Path

import pytest

import server as srv

AKIN_PATH = (Path(__file__).resolve().parents[3]
             / "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/npc/a-kin.json")


@pytest.fixture(autouse=True)
def tmp_ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("MODRON_LEDGER", str(tmp_path / "rolls.db"))


def call(handler, args):
    out = asyncio.run(handler(args))
    text = out[0].text
    assert not text.startswith("ERROR"), text
    return json.loads(text)


def test_tool_list_is_complete():
    tools = asyncio.run(srv.handle_list_tools())
    names = {t.name for t in tools}
    assert names == set(srv._DISPATCH)
    assert len(names) == 17


def test_roll_tool_full_loop():
    ses = call(srv._session_open, {"label": "pytest-night", "view": "5e-2014"})
    r = call(srv._roll, {"expr": "4d6kh3", "session_id": ses["session_id"],
                         "label": "STR"})
    assert 3 <= r["total"] <= 18 and r["roll_id"].startswith("rol:pytest-night")
    v = call(srv._verify, {"roll_id": r["roll_id"]})
    assert v["verdict"] == "PASS"
    closed = call(srv._session_close, {"session_id": ses["session_id"]})
    assert "seed_revealed_hex" not in closed          # withheld by default (Q1)
    sweep = call(srv._verify, {"session_id": ses["session_id"]})
    assert sweep["verdict"] == "PASS"                 # verify needs no reveal
    revealed = call(srv._session_close, {"session_id": ses["session_id"],
                                         "reveal": True})
    assert revealed["seed_revealed_hex"]              # on-demand, post-close


def test_roll_check_and_damage_tools():
    r = call(srv._roll_check, {"kind": "attack", "view": "2e",
                               "params": {"thac0": 7, "ac": 3}})
    assert "hits_ac" in r["outcome"]
    d = call(srv._roll_damage, {"expr": "2d6+4", "view": "5e-2014", "crit": True,
                                "mods": ["great-weapon-fighting"]})
    assert d["expr_resolved"] == "4d6ro<=2+4"


def test_roll_needs_view_for_state():
    out = asyncio.run(srv._roll({"expr": "1d20", "state": "advantage"}))
    assert out[0].text.startswith("ERROR")


def test_roll_table_tool():
    table = {"name": "Hive ward trouble", "dice": "1d6",
             "entries": [{"roll": "1-3", "result": "razorvine"},
                         {"roll": "4-5", "result": "cranium rats", "number": "2d4"},
                         {"roll": "6", "result": "collectors", "chain": {"again": 1}}]}
    r = call(srv._roll_table, {"table": table, "n": 3})
    assert r["coverage"]["verdict"] == "ok"
    assert len(r["rolls"]) == 3


def test_rollables_tool_inline_and_file():
    inline = {"name": "Test fiend", "descriptor": {"level_hd": "8+3"},
              "statblock": {"thac0": "13", "damage": "2-12",
                            "morale": "elite (14)", "hp": "40"}}
    r = call(srv._rollables, {"entity": inline})
    keys = {s["key"]: s for s in r["specs"]}
    assert keys["hp"]["expr"] == "8d8+3"
    assert keys["damage.1"]["expr"] == "2d6"          # range inverted
    assert keys["damage.1"]["ambiguous"] is False or "alternatives" in keys["damage.1"]
    if AKIN_PATH.exists():
        r = call(srv._rollables, {"entity": "a-kin"})
        assert r["entity"] == "A'kin" and r["view"] == "2e"
        assert any(s["key"] == "hp" and s["expr"] == "12d8+24" for s in r["specs"])


def test_encounter_tool_plan_and_execute():
    spec = {"check": {"expr": "1d10", "encounter_on": "<=10"},  # always meets
            "number_appearing": "2d4",
            "creature": {"hd": "8+3", "morale": 12}}
    plan = call(srv._encounter_rolls, {"encounter": spec, "view": "2e",
                                       "plan_only": True})
    assert [p["step"] for p in plan["plan"]][0] == "check"
    run = call(srv._encounter_rolls, {"encounter": spec, "view": "2e"})
    assert run["batch_id"].startswith("bat:")
    hp_step = next(s for s in run["steps"] if s["step"] == "hp")
    assert len(hp_step["totals"]) == run["number_appearing"]
    hist = call(srv._history, {"batch_id": run["batch_id"], "limit": 100})
    assert hist["count"] >= len(run["steps"]) - 2


def test_stats_parse_conventions_modifiers_tools():
    s = call(srv._dice_stats, {"expr": "2d6"})
    assert s["method"] == "exact" and s["mean"] == 7.0
    p = call(srv._parse_expr, {"expr": "adv(1d20+7)"})
    assert p["normal_form"] == "adv(1d20+7)"
    c = call(srv._conventions, {})
    assert set(c["views"]) == {"2e", "2e-planescape", "5e-2014", "5e-2024"}
    m = call(srv._modifiers, {"view": "5e-2014", "query": "reroll"})
    assert any(r["id"] == "great-weapon-fighting" for r in m["modifiers"])


def test_inline_json_as_string_over_the_wire():
    """V&V catch 2026-06-05: MCP transport can deliver inline objects as strings."""
    ent = json.dumps({"name": "Wire Guard", "statblock": {"thac0": "19", "damage": "1d8"}})
    r = call(srv._rollables, {"entity": ent})
    assert r["entity"] == "Wire Guard"
    tbl = json.dumps({"dice": "1d6", "entries": [{"roll": "1-6", "result": "rats"}]})
    r = call(srv._roll_table, {"table": tbl})
    assert r["rolls"][0]["result"] == "rats"
    enc = json.dumps({"number_appearing": "1d2", "creature": {"hd": "2"}})
    r = call(srv._encounter_rolls, {"encounter": enc, "view": "2e"})
    assert r["batch_id"].startswith("bat:")


def test_force_tool_is_labeled():
    f = call(srv._force, {"value": 20, "reason": "dramatic necessity", "expr": "1d20"})
    assert f["method"] == "fiat"
    v = call(srv._verify, {"roll_id": f["roll_id"]})
    assert v["verdict"] == "FIAT"
