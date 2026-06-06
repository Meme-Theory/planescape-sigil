#!/usr/bin/env python3
"""
Modron MCP Server — the dice engine (Mimir remembers, Mechanus rules, Modron rolls).

Ordered chance for the Planescape project: seeded/committed RNG, an append-only
roll ledger, per-edition dice conventions as data, modifier provenance, and the
rollables compiler over statblocks/tables/encounters/modules.

Design doc: pipeline/mimir/MODRON.md. Skeleton per the Ainulindale knowledge-mcp
lens (stdio, file logging, usage counter, guarded single-writer store).
"""

# Suppress warnings before any imports — stderr noise breaks MCP stdio
import warnings
import os
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

import asyncio
import json
import logging
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from modron import ENGINE_VERSION
from modron import analysis, conventions, ledger, modifiers, registry, rollables, semantics, store
from modron.engine import evaluate
from modron.grammar import DiceSyntaxError, dice_groups, normal_form, parse
from modron.modifiers import compose, resolve_mods

USAGE_COUNTER_PATH = SERVER_DIR / "usage_counter.json"

logging.basicConfig(level=logging.INFO, filename=str(SERVER_DIR / "modron_mcp.log"),
                    filemode="a", format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

server = Server("modron")


def _bump_counter(tool_name: str) -> None:
    """Per-tool usage counter (the lens pattern). Silent on I/O error."""
    import datetime as _dt
    try:
        data = {"total_calls": 0, "by_tool": {}}
        if USAGE_COUNTER_PATH.exists():
            with open(USAGE_COUNTER_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        data["total_calls"] = int(data.get("total_calls", 0)) + 1
        entry = data.setdefault("by_tool", {}).setdefault(tool_name, {"count": 0})
        entry["count"] = int(entry.get("count", 0)) + 1
        entry["last_called"] = now
        data["last_called"] = now
        tmp = USAGE_COUNTER_PATH.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, USAGE_COUNTER_PATH)
    except Exception:
        logger.exception("usage counter bump failed for %s", tool_name)


def _text(payload) -> list[types.TextContent]:
    if isinstance(payload, str):
        return [types.TextContent(type="text", text=payload)]
    return [types.TextContent(type="text",
                              text=json.dumps(payload, indent=2, ensure_ascii=False))]


def _err(msg: str) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=f"ERROR: {msg}")]


# ---------------------------------------------------------------------------
# Faces formatting — the human-readable audit line
# ---------------------------------------------------------------------------

def _faces_line(groups: list[dict]) -> str:
    parts = []
    for g in groups:
        dice_bits = []
        for d in g["dice"]:
            v = str(d["value"])
            if len(d["rolls"]) > 1:
                v = "→".join(str(r) for r in d["rolls"]) + f"={d['value']}"
            if not d.get("kept", True):
                v = f"({v} dropped)"
            dice_bits.append(v)
        parts.append(f"{g['spec']}[{', '.join(dice_bits)}]={g['value']}")
    return "  ".join(parts)


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

async def _roll(args: dict) -> list[types.TextContent]:
    expr = args["expr"]
    view = args.get("view") or ledger.session_view(args.get("session_id"))
    mods = args.get("mods") or []
    state = args.get("state")
    notes: list[str] = []

    rounding, crit_effect, d20_allowed, pack = "down", "double_dice", False, None
    if view:
        pack = conventions.get_pack(view)
        rounding = pack.get("rounding", "down")
        crit_effect = pack.get("crit_effect", "double_dice")
        d20_allowed = (pack.get("d20_states") or {}).get("advantage") is not None

    base = parse(expr)
    instances = resolve_mods(mods, view=view)
    if (state or any(e.get("op") in ("d20_state", "d20_upgrade")
                     for i in instances for e in i.effects)) and not view:
        return _err("advantage/disadvantage state needs a view (the state machine is "
                    "per-edition data) — pass view: 2e | 5e-2014 | 5e-2024")
    if state and pack:
        sources = semantics._collect_d20_sources(instances, "roll")
        die_expr, state_notes = modifiers.resolve_d20_state(sources, pack, explicit=state)
        notes.extend(state_notes)
        if die_expr != (pack.get("d20_states") or {}).get("flat", "1d20"):
            base = semantics._replace_first_die(base, parse(die_expr))
    comp = compose(base, instances, d20_allowed=d20_allowed)

    stream, meta = ledger.next_stream(args.get("session_id"))
    result = evaluate(comp.ast, stream, rounding=rounding, crit_effect=crit_effect)
    groups = [g.to_dict() for g in result.groups]
    totals = result.to_dict().get("totals")
    rec = ledger.record_roll(
        meta, expr_asked=expr, expr_resolved=normal_form(comp.ast), total=result.total,
        groups=groups, totals=totals, view=view, label=args.get("label"),
        purpose=args.get("purpose", "roll"), context_ref=args.get("context"),
        modifiers=[m for m in comp.applied], notes=notes + comp.notes + result.notes,
        rounding=rounding, crit_effect=crit_effect)

    out = {"total": result.total, "expr": expr, "expr_resolved": normal_form(comp.ast),
           "faces": _faces_line(groups), "roll_id": rec["roll_id"], "sha": rec["sha"][:16],
           "view": view, "modifiers_applied": [m["id"] for m in comp.applied]}
    if totals:
        out["set_totals"] = totals
    if comp.skipped:
        out["modifiers_skipped"] = comp.skipped
    if notes + comp.notes + result.notes:
        out["notes"] = notes + comp.notes + result.notes
    return _text(out)


async def _roll_check(args: dict) -> list[types.TextContent]:
    view = args.get("view") or ledger.session_view(args.get("session_id"))
    if not view:
        return _err("roll_check needs a view (2e | 5e-2014 | 5e-2024) — "
                    "checks are edition procedure")
    stream, meta = ledger.next_stream(args.get("session_id"))
    rc = semantics.roll_check(args["kind"], view, args.get("params"), args.get("mods"),
                              stream, state=args.get("state"))
    pack = conventions.get_pack(view)
    rec = ledger.record_roll(
        meta, expr_asked=rc["expr_asked"], expr_resolved=rc["expr_resolved"],
        total=rc["total"], groups=rc["groups"], view=view, label=args.get("label"),
        purpose=args["kind"], context_ref=args.get("context"),
        modifiers=rc["modifiers"], outcome=rc["outcome"], notes=rc["notes"],
        rounding=pack.get("rounding", "down"),
        crit_effect=pack.get("crit_effect", "double_dice"))
    out = {"kind": rc["kind"], "view": view, "total": rc["total"],
           "outcome": rc["outcome"], "expr_resolved": rc["expr_resolved"],
           "faces": _faces_line(rc["groups"]), "roll_id": rec["roll_id"],
           "sha": rec["sha"][:16],
           "modifiers_applied": [m["id"] for m in rc["modifiers"]]}
    if rc["modifiers_skipped"]:
        out["modifiers_skipped"] = rc["modifiers_skipped"]
    if rc["notes"]:
        out["notes"] = rc["notes"]
    return _text(out)


async def _roll_damage(args: dict) -> list[types.TextContent]:
    view = args.get("view") or ledger.session_view(args.get("session_id"))
    if not view:
        return _err("roll_damage needs a view (crit law and rounding are per-edition)")
    stream, meta = ledger.next_stream(args.get("session_id"))
    rc = semantics.roll_damage(args["expr"], view, args.get("mods"), stream,
                               crit=bool(args.get("crit")))
    pack = conventions.get_pack(view)
    rec = ledger.record_roll(
        meta, expr_asked=args["expr"], expr_resolved=rc["expr_resolved"],
        total=rc["total"], groups=rc["groups"], view=view, label=args.get("label"),
        purpose="damage", context_ref=args.get("context"), modifiers=rc["modifiers"],
        outcome={"crit": rc["crit"]}, notes=rc["notes"],
        rounding=pack.get("rounding", "down"),
        crit_effect=pack.get("crit_effect", "double_dice"))
    out = {"total": rc["total"], "crit": rc["crit"], "expr_resolved": rc["expr_resolved"],
           "faces": _faces_line(rc["groups"]), "roll_id": rec["roll_id"],
           "sha": rec["sha"][:16],
           "modifiers_applied": [m["id"] for m in rc["modifiers"]]}
    if rc["notes"]:
        out["notes"] = rc["notes"]
    return _text(out)


async def _roll_table(args: dict) -> list[types.TextContent]:
    table, src = store.find_table(args["table"])
    report = rollables.validate_table(table)
    n = max(1, min(int(args.get("n", 1)), 20))
    results = []
    for _ in range(n):
        stream, meta = ledger.next_stream(args.get("session_id"))
        result = evaluate(parse(report["dice"]), stream)
        entry = rollables.resolve_table_roll(table, result.total)
        rec = ledger.record_roll(
            meta, expr_asked=report["dice"], expr_resolved=report["dice"],
            total=result.total, groups=[g.to_dict() for g in result.groups],
            view=args.get("view"), label=table.get("name") or "table roll",
            purpose="table", context_ref=args.get("context") or src,
            outcome={"entry": entry})
        item = {"rolled": result.total, "result": (entry or {}).get("result", "NO ENTRY"),
                "roll_id": rec["roll_id"]}
        # chained results ("roll twice more...") — only via explicit entry.chain
        chain = (entry or {}).get("chain")
        depth = 0
        while chain and depth < 5:
            depth += 1
            again = max(1, min(int(chain.get("again", 1)), 5))
            sub = []
            for _ in range(again):
                s2, m2 = ledger.next_stream(args.get("session_id"))
                r2 = evaluate(parse(report["dice"]), s2)
                e2 = rollables.resolve_table_roll(table, r2.total)
                if chain.get("ignore_self") and e2 is entry:
                    continue
                ledger.record_roll(m2, expr_asked=report["dice"], expr_resolved=report["dice"],
                                   total=r2.total, groups=[g.to_dict() for g in r2.groups],
                                   purpose="table", context_ref=src, outcome={"entry": e2})
                sub.append({"rolled": r2.total, "result": (e2 or {}).get("result")})
            item["chained"] = sub
            chain = None
        results.append(item)
    out = {"table": table.get("name") or src, "coverage": report, "rolls": results}
    if report["verdict"] != "ok":
        out["warning"] = "table has coverage issues — gaps/overlaps listed in coverage"
    return _text(out)


async def _rollables(args: dict) -> list[types.TextContent]:
    ref = args["entity"]

    # Door 0: the Modron rollables registry — page-cited setting substance
    # (rule-effect handoff §D). Exact id first; then used_at/query matches,
    # but only when the ref isn't also a resolvable entity.
    if isinstance(ref, str) and not ref.strip().startswith("{"):
        row = registry.get(ref.strip())
        if row is not None:
            return _text({"rollable": row["id"], "source": f"rollables-registry:{row['id']}",
                          "entry": {k: v for k, v in row.items() if k != "_file"}})
        hits = registry.search(used_at=ref.strip()) or registry.search(query=ref.strip())
        if hits:
            try:
                store.find_entity(ref)  # an entity wins the name; registry rides along
            except store.EntityNotFound:
                return _text({"registry_matches": [
                    {"id": r["id"], "kind": r["kind"], "label": r.get("label"),
                     "used_at": r.get("used_at"), "source": r.get("source")} for r in hits],
                    "note": "no entity resolves this ref; these page-cited registry "
                            "rollables match — fetch one by id for its full entry"})

    entity, src = store.find_entity(ref)
    view = args.get("view") or rollables.detect_view(entity)
    pack = conventions.get_pack(view)
    specs = rollables.compile_entity(entity, pack, view,
                                     sweep_prose=bool(args.get("sweep_prose", True)))
    crosscheck_flags = [s["crosscheck"] for s in specs
                        if s.get("crosscheck", {}).get("verdict") not in (None, "ok")]
    out = {"entity": entity.get("name", "?"), "source": src, "view": view,
           "specs": specs}
    if isinstance(ref, str):
        extra = registry.search(used_at=ref.strip())
        if extra:
            out["registry_rollables"] = [{"id": r["id"], "kind": r["kind"],
                                          "label": r.get("label")} for r in extra]
    if crosscheck_flags:
        out["lawfulness_flags"] = crosscheck_flags  # the gate's free witness (MODRON §2.4)
    return _text(out)


async def _encounter_rolls(args: dict) -> list[types.TextContent]:
    spec = args["encounter"]
    if isinstance(spec, str) and spec.strip().startswith("{"):
        spec = json.loads(spec)  # inline spec that crossed the wire as a string
    if isinstance(spec, str):
        entity, src = store.find_entity(spec)
        spec = {"creature_ref": src, "creature": entity}
    view = args.get("view") or spec.get("view") or ledger.session_view(args.get("session_id"))
    if not view:
        return _err("encounter_rolls needs a view (doctrine is per-edition)")
    pack = conventions.get_pack(view)

    creature = spec.get("creature") or {}
    if spec.get("creature_ref") and not creature.get("hd"):
        # pull hd/morale from a loaded envelope
        entity, _ = store.find_entity(spec["creature_ref"])
        desc = entity.get("descriptor") or {}
        sb = entity.get("statblock") or {}
        creature = {"hd": desc.get("level_hd") or sb.get("hd"),
                    "morale": _morale_of(sb), "name": entity.get("name")}
        spec = {**spec, "creature": creature}

    plan = rollables.encounter_plan(spec, pack, view)
    if args.get("plan_only"):
        return _text({"view": view, "plan": plan,
                      "note": "plan_only: nothing rolled, nothing ledgered"})

    batch_id = "bat:" + os.urandom(4).hex()
    session_id = args.get("session_id")
    executed: list[dict] = []
    number = 1

    def roll_step(expr: str, label: str, purpose: str) -> dict:
        stream, meta = ledger.next_stream(session_id)
        result = evaluate(parse(expr), stream, rounding=pack.get("rounding", "down"))
        rec = ledger.record_roll(meta, expr_asked=expr, expr_resolved=expr,
                                 total=result.total,
                                 groups=[g.to_dict() for g in result.groups],
                                 view=view, label=label, purpose=purpose,
                                 batch_id=batch_id, context_ref=args.get("context"))
        return {"total": result.total, "roll_id": rec["roll_id"]}

    def check_step(kind: str, params: dict, label: str) -> dict:
        stream, meta = ledger.next_stream(session_id)
        rc = semantics.roll_check(kind, view, params, None, stream)
        rec = ledger.record_roll(meta, expr_asked=rc["expr_asked"],
                                 expr_resolved=rc["expr_resolved"], total=rc["total"],
                                 groups=rc["groups"], view=view, label=label,
                                 purpose=kind, batch_id=batch_id,
                                 outcome=rc["outcome"], notes=rc["notes"])
        return {"total": rc["total"], "outcome": rc["outcome"], "roll_id": rec["roll_id"]}

    for step in plan:
        kind = step["step"]
        if kind == "check":
            r = roll_step(step["expr"], step["label"], "encounter-check")
            from modron.modifiers import _parse_cmp
            happens = _parse_cmp(step["encounter_on"]).matches(r["total"])
            executed.append({**step, **r, "encounter": happens})
            if not happens and spec.get("stop_if_no_encounter", True):
                executed.append({"step": "stop", "note": "no encounter — remaining steps skipped"})
                break
        elif kind == "table":
            table, tsrc = store.find_table(step["table"])
            report = rollables.validate_table(table)
            r = roll_step(report["dice"], "encounter table", "table")
            entry = rollables.resolve_table_roll(table, r["total"])
            executed.append({**step, "table": tsrc, **r,
                             "result": (entry or {}).get("result", "NO ENTRY")})
            if entry and entry.get("number"):
                t = rollables.text_to_expr(str(entry["number"]))
                if t:
                    rn = roll_step(t["expr"], f"number appearing ({entry['number']})", "number")
                    number = rn["total"]
                    executed.append({"step": "number", "from": "table entry", **rn})
        elif kind == "number":
            r = roll_step(step["expr"], step["label"], "number")
            number = r["total"]
            executed.append({**step, **r})
        elif kind == "hp":
            n = number if step.get("per_creature") else 1
            n = max(1, min(n, 50))
            hps = [roll_step(step["expr"], f"hp {i + 1}/{n}", "hp") for i in range(n)]
            executed.append({**step, "count": n, "rolls": hps,
                             "totals": [h["total"] for h in hps]})
        elif kind in ("surprise",):
            sides = {}
            for side in step.get("sides", ["party", "monsters"]):
                sides[side] = check_step("surprise", {}, f"surprise ({side})")
            executed.append({**step, "results": sides})
        elif kind == "distance":
            executed.append({**step, **roll_step(step["expr"], step["label"], "distance")})
        elif kind in ("reaction", "initiative"):
            params = (step.get("check") or {}).get("params", {})
            label = step.get("label", kind)
            executed.append({**step, **check_step(kind, params, label)})
        elif kind == "morale":
            executed.append(step)  # armed, not pre-rolled — fires when the fiction says
    return _text({"view": view, "batch_id": batch_id, "number_appearing": number,
                  "steps": executed})


def _morale_of(sb: dict) -> int | None:
    import re as _re
    m = _re.search(r"\((\d{1,2})\)", str(sb.get("morale") or ""))
    return int(m.group(1)) if m else None


async def _parse_expr(args: dict) -> list[types.TextContent]:
    node = parse(args["expr"])
    return _text({"expr": args["expr"], "normal_form": normal_form(node),
                  "dice_groups": [normal_form(d) for d in dice_groups(node)],
                  "valid": True})


async def _dice_stats(args: dict) -> list[types.TextContent]:
    rounding, crit_effect = "down", "double_dice"
    if args.get("view"):
        pack = conventions.get_pack(args["view"])
        rounding = pack.get("rounding", "down")
        crit_effect = pack.get("crit_effect", "double_dice")
    return _text(analysis.stats(args["expr"], rounding=rounding, crit_effect=crit_effect))


async def _session_open(args: dict) -> list[types.TextContent]:
    return _text(ledger.open_session(args["label"], args.get("view"),
                                     args.get("seed_phrase")))


async def _session_close(args: dict) -> list[types.TextContent]:
    return _text(ledger.close_session(args["session_id"],
                                      bool(args.get("reveal", False))))


async def _history(args: dict) -> list[types.TextContent]:
    rows = ledger.history(args.get("session_id"), args.get("purpose"),
                          args.get("batch_id"), int(args.get("limit", 20)))
    slim = []
    for r in rows:
        slim.append({k: r[k] for k in ("roll_id", "session_id", "label", "purpose", "view",
                                       "expr_resolved", "total", "method", "ts")
                     if r.get(k) is not None})
        if r.get("outcome_json"):
            slim[-1]["outcome"] = json.loads(r["outcome_json"])
    return _text({"count": len(slim), "rolls": slim})


async def _verify(args: dict) -> list[types.TextContent]:
    if args.get("roll_id"):
        return _text(ledger.verify_roll(args["roll_id"]))
    if args.get("session_id"):
        return _text(ledger.verify_session(args["session_id"]))
    return _err("verify needs roll_id or session_id")


async def _force(args: dict) -> list[types.TextContent]:
    rec = ledger.record_fiat(int(args["value"]), reason=args["reason"],
                             expr=args.get("expr"), session_id=args.get("session_id"),
                             label=args.get("label"), view=args.get("view"),
                             context_ref=args.get("context"))
    return _text({**rec, "method": "fiat",
                  "note": "ledgered as FIAT — a forced value never wears a rolled costume"})


async def _conventions(args: dict) -> list[types.TextContent]:
    if args.get("view"):
        return _text(conventions.get_pack(args["view"]))
    return _text({"views": conventions.list_views(),
                  "note": "pass view for the full pack (overlays always disclosed)"})


async def _modifiers(args: dict) -> list[types.TextContent]:
    rows = modifiers.search(args.get("query", ""), args.get("view"))
    return _text({"count": len(rows), "modifiers": rows})


async def _define_modifier(args: dict) -> list[types.TextContent]:
    spec = modifiers.define_local(args["spec"])
    return _text({"defined": spec["id"], "overlay": str(modifiers.OVERLAY_PATH),
                  "note": "local overlay (house dice tech) — when Mechanus's rulings.db "
                          "lands, scoped rulings supersede this channel"})


async def _usage_stats(args: dict) -> list[types.TextContent]:
    if USAGE_COUNTER_PATH.exists():
        with open(USAGE_COUNTER_PATH, "r", encoding="utf-8") as f:
            return _text(json.load(f))
    return _text({"total_calls": 0, "by_tool": {}})


# ---------------------------------------------------------------------------
# MCP wiring
# ---------------------------------------------------------------------------

_VIEW_DESC = "Edition view: '2e' | '5e-2014' | '5e-2024' (conventions are per-edition data)"
_MODS_DESC = ("Modifiers: registry ids ('bless', {'id':'sneak-attack','params':{'n':3}}) "
              "and/or inline effects with a REQUIRED source, e.g. "
              "{'id':'high-ground','effects':[{'op':'add','expr':'2'}],"
              "'source':{'kind':'fiat','ref':'dm','reason':'high ground'}} — "
              "every modifier names its asserter (kind: core|mimir|mechanus|table|fiat)")
_SESSION_DESC = ("Session id from session_open. With it, rolls draw from the session's "
                 "committed seed stream (verifiable fairness); without, an ephemeral "
                 "recorded seed (still reproducible)")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="roll",
            description=(
                "THE dice tool. Parse a dice expression, compose modifiers, roll on the "
                "auditable stream, ledger it. Full notation: 3d6+2, 4d6kh3 (keep highest), "
                "2d20kl1, 4d6dl1 (drop lowest), d6! (explode), 2d6!! (compound), 2d6ro<3 "
                "(reroll once), 1d20min10, 8d6/2 (integer, edition rounding), d%, 4dF (Fate), "
                "10d10cs>=8 (success pool), adv(1d20+7), dis(...), ea(...) (Elven Accuracy), "
                "crit(2d8+5) (edition crit law), repeat(4d6kh3,6) (ability array), "
                "floor/ceil/abs/min/max. Every die face returned with its fate "
                "(kept/dropped/rerolled/exploded). Returns roll_id + sha (content address)."),
            inputSchema={
                "type": "object",
                "properties": {
                    "expr": {"type": "string", "description": "Dice expression"},
                    "view": {"type": "string", "description": _VIEW_DESC},
                    "session_id": {"type": "string", "description": _SESSION_DESC},
                    "mods": {"type": "array", "description": _MODS_DESC},
                    "state": {"type": "string", "enum": ["advantage", "disadvantage", "flat"],
                              "description": "d20 state (needs view; pack's state machine "
                                             "applies: adv+dis cancel, no stacking)"},
                    "label": {"type": "string", "description": "Human label for the ledger"},
                    "purpose": {"type": "string", "description": "Roll purpose tag (ledger filter)"},
                    "context": {"type": "string",
                                "description": "Provenance ref: entity id / file / encounter"},
                },
                "required": ["expr"],
            },
        ),
        types.Tool(
            name="roll_check",
            description=(
                "Semantic roll per the view's convention pack: kind = attack | save | check | "
                "initiative | morale (2e) | reaction (2e) | surprise (2e) | ability (2e "
                "roll-under) | proficiency (2e) | thief_skill (2e) | percent | death_save (5e) | "
                "recharge (5e). The pack supplies procedure (THAC0 math, roll-under, crit "
                "naturals, reaction bands, low-wins initiative); YOU supply values via params: "
                "attack_bonus+ac (5e attack), thac0+ac (2e attack), save_bonus+dc, mod+dc, "
                "score (2e ability), morale, pct, dex_mod. Returns outcome: success/margin/"
                "crit/fumble/hits_ac/band. Modifiers compose with provenance; advantage state "
                "machine per pack (cancel/no-stack/elven-accuracy upgrade)."),
            inputSchema={
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "description": "Check kind (see conventions(view))"},
                    "view": {"type": "string", "description": _VIEW_DESC},
                    "params": {"type": "object",
                               "description": "Values the pack needs (ints): e.g. "
                                              "{thac0:7, ac:3} or {attack_bonus:7, ac:15}"},
                    "mods": {"type": "array", "description": _MODS_DESC},
                    "state": {"type": "string", "enum": ["advantage", "disadvantage", "flat"]},
                    "session_id": {"type": "string", "description": _SESSION_DESC},
                    "label": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["kind", "view"],
            },
        ),
        types.Tool(
            name="roll_damage",
            description=(
                "Damage roll under edition law: crit=true applies the view's crit effect "
                "(5e: double the DICE, never the modifiers; 2e: none — noted) plus any "
                "applies_when:'crit' mods (brutal-critical). Modifiers compose: "
                "great-weapon-fighting (reroll 1-2 once), sneak-attack {n}, resistance "
                "(half, round down), vulnerability (double), dueling, rage-damage {n}..."),
            inputSchema={
                "type": "object",
                "properties": {
                    "expr": {"type": "string", "description": "Base damage dice, e.g. 2d8+5"},
                    "view": {"type": "string", "description": _VIEW_DESC},
                    "crit": {"type": "boolean", "description": "Apply the view's critical law"},
                    "mods": {"type": "array", "description": _MODS_DESC},
                    "session_id": {"type": "string", "description": _SESSION_DESC},
                    "label": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["expr", "view"],
            },
        ),
        types.Tool(
            name="roll_table",
            description=(
                "Roll on a table (dim:table shape: {dice, entries:[{roll:'01-05'|'97-00'|'6', "
                "result, number?, chain?}]}). Accepts inline JSON, a Modron rollables-registry "
                "id (page-cited setting tables, e.g. 'tbl:2e:sigil:slags-vortex-type'), a "
                "build/ file path, or a handbook id. Validates coverage FIRST — gaps and "
                "overlaps are reported, never papered over. '00' reads 100 on percentile. "
                "Explicit entry.chain {again:N, ignore_self} follows 'roll twice more' "
                "directives."),
            inputSchema={
                "type": "object",
                "properties": {
                    "table": {"description": "Inline table object, file path, or entity ref"},
                    "n": {"type": "integer", "description": "Rolls to make (1-20)", "default": 1},
                    "session_id": {"type": "string", "description": _SESSION_DESC},
                    "view": {"type": "string", "description": _VIEW_DESC},
                    "context": {"type": "string"},
                },
                "required": ["table"],
            },
        ),
        types.Tool(
            name="rollables",
            description=(
                "THE module/encounter prep tool: compile an entity into its roll specs "
                "WITHOUT rolling. Resolves refs handbook-FIRST (Mimir's admitted+cured "
                "store, by id 'npc:uncaged:a-kin' or exact name 'Cirily', via her store "
                "lib); raw build/**.json only as a flagged last resort (UNCURED). Inline "
                "dicts/JSON-strings always work. 2e statblocks: THAC0→attack, damage "
                "strings ('1d4/1d4/2d6 (claw/claw/bite)')→labeled specs, MR%→percent-under, "
                "morale 'champion (16)'→morale-vs-16, HD '12+24'→12d8+24 hp with printed-HP "
                "range crosscheck. 5e: '+7 to hit', 'Hit: 14 (2d8+5)' (with printed-average "
                "crosscheck — a MISMATCH is a transcription smell, the gate's free witness), "
                "DC saves, Recharge 5-6. Ranges like '3-18' invert to 3d6 with alternatives "
                "listed. Prose dice (OCR-lenient: Id6→1d6) surface flagged from_prose + "
                "requires_confirmation. Pass any spec's expr/check straight to roll/roll_check. "
                "Also serves the Modron rollables registry (page-cited Planescape substance, "
                "rule-effect handoff §D): pass a registry id ('dmg:2e:inner:fire-pocket', "
                "'lkp:2e:limbo:terrain-maintenance') for the full entry, or a used_at ref "
                "('plane:limbo', 'location:sigil:hive-ward') to list what's rollable there."),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"description": "Entity: inline dict, file path under build/, "
                                              "bare name ('a-kin'), or handbook id"},
                    "view": {"type": "string", "description": _VIEW_DESC + " (default: detected)"},
                    "sweep_prose": {"type": "boolean", "default": True,
                                    "description": "Also sweep prose fields for dice/percents"},
                },
                "required": ["entity"],
            },
        ),
        types.Tool(
            name="encounter_rolls",
            description=(
                "Orchestrate an encounter's dice per the view's doctrine (2e wandering: "
                "check→table→number→hp→surprise→distance→reaction→initiative; 5e: "
                "number→hp→initiative). plan_only=true returns the plan unrolled — see what "
                "the night will ask before it asks. Executed plans share a batch_id in the "
                "ledger. Encounter spec: {check?:{expr,encounter_on}, table?, "
                "number_appearing?:'2d4', creature?:{hd:'8+3',morale:12}|creature_ref:'a-kin', "
                "distance?:'10d10', initiative?:{sides:['monsters'], party:{mod:0}, "
                "monsters:{mod:0}} (both sides by default — omit a side via sides), "
                "steps?:[...], stop_if_no_encounter?:true}. Morale specs "
                "come back ARMED, not pre-rolled — they fire when the fiction says."),
            inputSchema={
                "type": "object",
                "properties": {
                    "encounter": {"description": "Encounter spec object, or an entity ref "
                                                 "(builds a creature-only spec)"},
                    "view": {"type": "string", "description": _VIEW_DESC},
                    "plan_only": {"type": "boolean", "default": False},
                    "session_id": {"type": "string", "description": _SESSION_DESC},
                    "context": {"type": "string"},
                },
                "required": ["encounter"],
            },
        ),
        types.Tool(
            name="parse_expr",
            description="Parse a dice expression: AST validity, normal form (what the ledger "
                        "SHAs), dice groups. Nothing rolls.",
            inputSchema={"type": "object",
                         "properties": {"expr": {"type": "string"}},
                         "required": ["expr"]},
        ),
        types.Tool(
            name="dice_stats",
            description=(
                "Distribution of an expression WITHOUT rolling: exact (convolution/multiset "
                "enumeration, fractions) where feasible — mean/stddev/min/max/mode/percentiles"
                "/pmf; Monte Carlo (flagged 'monte-carlo', fixed reproducible seed) past the "
                "guards. Estimated never dresses as exact. Use for DPR math, table odds, "
                "'should they risk it' calls."),
            inputSchema={"type": "object",
                         "properties": {"expr": {"type": "string"},
                                        "view": {"type": "string", "description": _VIEW_DESC}},
                         "required": ["expr"]},
        ),
        types.Tool(
            name="session_open",
            description=(
                "Open a play session: a seed is drawn (or derived from a table-chosen "
                "seed_phrase), and sha256(seed) is PUBLISHED as the commitment before any die "
                "falls. All session rolls derive from (seed, counter); the seed stays withheld "
                "until revealed ON DEMAND (session_close reveal=true) — then the whole night "
                "recomputes. Auditable fairness, zero friction."),
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Session label, e.g. 'tofw-night-12'"},
                    "view": {"type": "string", "description": _VIEW_DESC + " (session default)"},
                    "seed_phrase": {"type": "string",
                                    "description": "Optional table-chosen phrase the seed "
                                                   "derives from (ceremony beats entropy)"},
                },
                "required": ["label"],
            },
        ),
        types.Tool(
            name="session_close",
            description="Close a session (seals the stream). The seed stays WITHHELD by "
                        "default — on-demand cadence: pass reveal=true at close, or call "
                        "again on the closed session with reveal=true when the table asks. "
                        "Once revealed, players verify sha256(seed)==commitment; "
                        "verify(session_id) recomputes every roll DM-side either way.",
            inputSchema={"type": "object",
                         "properties": {"session_id": {"type": "string"},
                                        "reveal": {"type": "boolean", "default": False,
                                                   "description": "Publish the seed now "
                                                   "(table-facing verification)"}},
                         "required": ["session_id"]},
        ),
        types.Tool(
            name="history",
            description="Read the roll ledger: filter by session_id, purpose (attack/damage/"
                        "save/table/hp/fiat/...), or batch_id (one encounter's rolls).",
            inputSchema={"type": "object",
                         "properties": {"session_id": {"type": "string"},
                                        "purpose": {"type": "string"},
                                        "batch_id": {"type": "string"},
                                        "limit": {"type": "integer", "default": 20}}},
        ),
        types.Tool(
            name="verify",
            description=(
                "Re-derive and re-check ledgered rolls: verify(roll_id) recomputes the faces "
                "from (seed, counter) and re-hashes; verify(session_id) sweeps the night. "
                "PASS, or the exact diff. Fiat rows report FIAT (they have no dice — that's "
                "the point of labeling them)."),
            inputSchema={"type": "object",
                         "properties": {"roll_id": {"type": "string"},
                                        "session_id": {"type": "string"}}},
        ),
        types.Tool(
            name="force",
            description=(
                "DM fiat: record a chosen value in the ledger as method='fiat' with a REQUIRED "
                "reason. It never wears a rolled costume — no faces, no seed, labeled forever. "
                "The honest override for 'the story needs this'."),
            inputSchema={
                "type": "object",
                "properties": {
                    "value": {"type": "integer", "description": "The decreed value"},
                    "reason": {"type": "string", "description": "Why (required — the rogue "
                                                                "modron is labeled)"},
                    "expr": {"type": "string", "description": "What it stands in for, e.g. 2d6"},
                    "session_id": {"type": "string"},
                    "label": {"type": "string"},
                    "view": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["value", "reason"],
            },
        ),
        types.Tool(
            name="conventions",
            description="List edition views, or show one view's full convention pack "
                        "(check procedures, d20 state machine, crit law, HD rules, encounter "
                        "doctrine) — overlays always disclosed.",
            inputSchema={"type": "object",
                         "properties": {"view": {"type": "string", "description": _VIEW_DESC}}},
        ),
        types.Tool(
            name="modifiers",
            description="Search the named-modifier registry (bless, great-weapon-fighting, "
                        "halfling-luck, resistance, brutal-critical {n,die}, sneak-attack {n}, "
                        "2e specialization...). Each carries effects, stacking law, and source.",
            inputSchema={"type": "object",
                         "properties": {"query": {"type": "string"},
                                        "view": {"type": "string", "description": _VIEW_DESC}}},
        ),
        types.Tool(
            name="define_modifier",
            description=(
                "Define/update a named modifier in the LOCAL overlay (house dice tech): spec "
                "needs {id, label, effects:[{op: add|sub|d20_state|d20_upgrade|reroll|min_die|"
                "max_die|explode|mult_total|div_total|extra_crit_dice, ...}], stacking?, "
                "views?, applies_to?, source?}. Effects are validated before write. "
                "Law-grade house RULES belong in Mechanus's rulings ledger when it lands; "
                "this overlay is for dice mechanics."),
            inputSchema={"type": "object",
                         "properties": {"spec": {"type": "object"}},
                         "required": ["spec"]},
        ),
        types.Tool(
            name="usage_stats",
            description="Per-tool usage counters for this server.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


_DISPATCH = {
    "roll": _roll,
    "roll_check": _roll_check,
    "roll_damage": _roll_damage,
    "roll_table": _roll_table,
    "rollables": _rollables,
    "encounter_rolls": _encounter_rolls,
    "parse_expr": _parse_expr,
    "dice_stats": _dice_stats,
    "session_open": _session_open,
    "session_close": _session_close,
    "history": _history,
    "verify": _verify,
    "force": _force,
    "conventions": _conventions,
    "modifiers": _modifiers,
    "define_modifier": _define_modifier,
    "usage_stats": _usage_stats,
}


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    args = arguments or {}
    _bump_counter(name)
    handler = _DISPATCH.get(name)
    if handler is None:
        return _err(f"unknown tool {name!r}")
    try:
        return await handler(args)
    except (DiceSyntaxError, ValueError, KeyError, ledger.LedgerError,
            store.EntityNotFound) as e:
        logger.warning("tool %s refused: %s", name, e)
        return _err(str(e))
    except Exception as e:
        logger.exception("tool %s failed", name)
        return _err(f"{type(e).__name__}: {e}")


async def main():
    logger.info("modron MCP server starting (engine v%s)", ENGINE_VERSION)
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream,
                         server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
