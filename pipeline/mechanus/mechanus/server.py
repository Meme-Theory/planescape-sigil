#!/usr/bin/env python3
"""
Mechanus MCP Server — the rules engine, v0 (invoke + ledger).

Mimir remembers, Mechanus rules, Modron rolls. This server exposes the
mechanical core and the rulings ledger. Store-backed tools (view/search/
convert/...) return an honest NOT_POURED error until Mimir's handbook.db
lands — 'not silently helpful' is doc law (MECHANUS.md §8).

Tools live:
  is_lawful          — mechanical-lawfulness docket (the gate's L3 channel)
  dc_suggest         — Typical DC ladder, page-cited per view
  encounter_budget   — XP budgets (5e-2024; honest refusal for 2014)
  attribution        — verbatim CC-BY-4.0 blocks required for SRD reuse
  planar_law         — 2e planar law families (rule-effect handoff §M):
                       per-plane magical conditions, spell/power keys,
                       seals & wards, planar-priest frame, plane-environment
                       rules, planar spells, Cage law — page-cited paraphrase
  record_ruling / overrule / precedents / house_rules / ruling_chain
  law_info / usage_stats

Tools parked (NOT_POURED): view, rule_search, rule_quote, delta, resolve,
  convert, apply_influence, answer_key
"""

# Suppress warnings before any imports — stderr noise breaks MCP stdio
import warnings
import os
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

from . import budget as budget_mod
from . import dc as dc_mod
from . import lawful as lawful_mod
from . import tables
from .ledger import DocketError, Ledger

# ---------------------------------------------------------------------------
# Paths — build/<name>/ is the derived/mutable home (Modron's convention)
# ---------------------------------------------------------------------------

BUILD_DIR = Path(__file__).resolve().parents[3] / "build" / "mechanus"
BUILD_DIR.mkdir(parents=True, exist_ok=True)
RULINGS_DB = Path(os.environ.get("MECHANUS_RULINGS_DB", BUILD_DIR / "rulings.db"))
USAGE_PATH = BUILD_DIR / "usage_counter.json"

logging.basicConfig(level=logging.INFO, filename=str(BUILD_DIR / "mechanus_mcp.log"),
                    filemode="a", format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mechanus")

server = Server("mechanus")
_ledger: Ledger | None = None


def ledger() -> Ledger:
    global _ledger
    if _ledger is None:
        _ledger = Ledger(RULINGS_DB)
    return _ledger


def _bump(tool: str) -> None:
    try:
        counts = json.loads(USAGE_PATH.read_text(encoding="utf-8")) if USAGE_PATH.exists() else {}
        counts[tool] = counts.get(tool, 0) + 1
        USAGE_PATH.write_text(json.dumps(counts, indent=1), encoding="utf-8")
    except OSError:
        pass


def _json(obj: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(obj, indent=1, ensure_ascii=False))]


def _err(msg: str, **extra) -> list[types.TextContent]:
    return _json({"error": msg, **extra})


NOT_POURED = (
    "NOT_POURED: this tool reads Mimir's handbook.db, which hasn't been poured yet "
    "(MECHANUS.md §9 steps 1-4). The mechanical core and rulings ledger are live; "
    "the law library is on its way."
)
PARKED = ("view", "rule_search", "rule_quote", "delta", "resolve",
          "convert", "apply_influence", "answer_key")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    live = [
        types.Tool(
            name="is_lawful",
            description=(
                "Judge an entity's internal mechanical lawfulness (REVIEW-5E §A pack): "
                "PB==ceil(CR/4)+1, XP-by-CR, HP==mean(dice), save/skill==mod+PB, passive "
                "Perception, condition/sense enums; 2e THAC0-vs-HD and HP-in-HD-range. "
                "Returns a docket with per-check expected/actual. This is Mimir's gate L3 channel."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "object",
                               "description": "5e-bits monster JSON, Mimir envelope, or bare 2e statblock"},
                    "view": {"type": "string", "description": "5e-2014 | 5e-2024 | 2e (inferred if omitted)"},
                    "apply_known_waivers": {"type": "boolean", "default": True,
                                            "description": "apply SRD-attested print-deviation waivers (lich/night-hag/priest)"},
                },
                "required": ["entity"],
            }),
        types.Tool(
            name="dc_suggest",
            description="The Typical Difficulty Classes ladder (or one rung), page-cited per view.",
            inputSchema={
                "type": "object",
                "properties": {
                    "difficulty": {"type": "string",
                                   "description": "very easy | easy | medium | hard | very hard | nearly impossible (omit for full ladder)"},
                    "view": {"type": "string", "default": "5e-2014"},
                },
            }),
        types.Tool(
            name="encounter_budget",
            description=(
                "XP budget for a party at a difficulty (SRD 5.2.1 p.202). "
                "view=5e-2014 refuses honestly: SRD 5.1 has no encounter math."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "party_levels": {"type": "array", "items": {"type": "integer"},
                                     "description": "one entry per character, levels 1-20"},
                    "difficulty": {"type": "string", "description": "low | moderate | high"},
                    "view": {"type": "string", "default": "5e-2024"},
                },
                "required": ["party_levels", "difficulty"],
            }),
        types.Tool(
            name="attribution",
            description="Verbatim CC-BY-4.0 attribution blocks (from each SRD's legal page) that any published artifact must carry.",
            inputSchema={"type": "object", "properties": {
                "view": {"type": "string", "description": "5e-2014 | 5e-2024 (omit for both)"}}}),
        types.Tool(
            name="planar_law",
            description=(
                "2e planar law (the rule-effect handoff §M families): per-plane magical "
                "conditions, spell/power keys, seals & wards, the planar-priest frame, "
                "plane-environment rules, planar spell mechanics, and Sigil's Cage law. "
                "Every row is a page-cited PARAPHRASE of a user-purchased scan (cite-only "
                "lane — cite product+page when publishing, never paste scan text). "
                "Lookup by law_id (exact row — the ids Mimir's exhibits edges and Modron "
                "modifier sources cite), by plane (Mimir id `plane:<slug>`, bare slug, or "
                "`sigil`), or by family; no args returns the index."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "law_id": {"type": "string",
                               "description": "exact row id, e.g. law:planar-conditions:limbo:wild-magic"},
                    "plane": {"type": "string",
                              "description": "plane:<slug> | bare slug | sigil — all top-level rows touching it"},
                    "family": {"type": "string",
                               "description": "one of: " + ", ".join(tables.PLANAR_LAW_FILES)},
                },
            }),
        types.Tool(
            name="record_ruling",
            description=(
                "Append a ruling docket to the ledger (guarded: schema-forced, SHA-unique, "
                "lockfile). Docket law: ladder_path walked, candidates with exactly one "
                "ADOPTED and why for every rejected, confidence, adjudicator; rolls cite "
                "Modron roll_ids. The ONLY write path besides overrule."
            ),
            inputSchema={
                "type": "object",
                "properties": {"docket": {"type": "object"}},
                "required": ["docket"],
            }),
        types.Tool(
            name="overrule",
            description="Supersede an existing ruling with a new docket — history preserved, chain queryable.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ruling_id": {"type": "string", "description": "the ruling being overruled"},
                    "docket": {"type": "object", "description": "the new docket (gets supersedes set)"},
                },
                "required": ["ruling_id", "docket"],
            }),
        types.Tool(
            name="precedents",
            description="FTS over recorded rulings — what has this table already ruled? Overruled rulings resolve to their head.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "scope": {"type": "string", "description": "campaign:<id> | table:<id> (global rulings always reach)"},
                    "limit": {"type": "integer", "default": 10},
                },
                "required": ["topic"],
            }),
        types.Tool(
            name="house_rules",
            description="List active house rules (kind=house-rule, unsuperseded), optionally scoped.",
            inputSchema={"type": "object", "properties": {"scope": {"type": "string"}}}),
        types.Tool(
            name="ruling_chain",
            description="A ruling's full supersedes chain, oldest first, plus the head docket.",
            inputSchema={
                "type": "object",
                "properties": {"ruling_id": {"type": "string"}},
                "required": ["ruling_id"],
            }),
        types.Tool(
            name="law_info",
            description="law_version (content-address of every law table) + per-table source citations + known deviations.",
            inputSchema={"type": "object", "properties": {}}),
        types.Tool(
            name="usage_stats",
            description="Tool-call counts for this server.",
            inputSchema={"type": "object", "properties": {}}),
    ]
    parked = [
        types.Tool(
            name=name,
            description=f"[PARKED — returns NOT_POURED until Mimir's handbook.db lands] {name} per MECHANUS.md §7.",
            inputSchema={"type": "object", "properties": {}, "additionalProperties": True})
        for name in PARKED
    ]
    return live + parked


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    args = arguments or {}
    _bump(name)
    logger.info("tool=%s args_keys=%s", name, sorted(args))
    try:
        if name in PARKED:
            return _err(NOT_POURED, tool=name)

        if name == "is_lawful":
            entity = args["entity"]
            waivers = None
            if args.get("apply_known_waivers", True):
                key = entity.get("index") or entity.get("name") or ""
                waivers = lawful_mod.known_waivers(key)
            return _json(lawful_mod.is_lawful(entity, args.get("view"), waivers=waivers))

        if name == "dc_suggest":
            return _json(dc_mod.dc_suggest(args.get("difficulty"), args.get("view", "5e-2014")))

        if name == "encounter_budget":
            try:
                return _json(budget_mod.encounter_budget(
                    args["party_levels"], args["difficulty"], args.get("view", "5e-2024")))
            except budget_mod.LawUnavailable as e:
                return _err(str(e), kind="LawUnavailable")

        if name == "attribution":
            data = json.loads((tables.LAW_DIR / "attribution.json").read_text(encoding="utf-8"))
            view = args.get("view")
            blocks = {view: data[view]} if view else {k: v for k, v in data.items() if not k.startswith("_")}
            return _json({"attribution": blocks,
                          "note": "verbatim from each SRD's legal page; ship with anything that quotes the law"})

        if name == "planar_law":
            stamp = {"law_version": tables.law_version(),
                     "license": ("cite-only paraphrase of user-purchased scans — "
                                 "cite product+page in published artifacts")}
            if args.get("law_id"):
                try:
                    return _json({**stamp, "row": tables.planar_law(args["law_id"])})
                except KeyError:
                    return _err(f"unknown law_id: {args['law_id']}",
                                families=list(tables.PLANAR_LAW_FILES))
            if args.get("plane"):
                rows = tables.planar_law_for_plane(args["plane"])
                if not rows:
                    return _err(f"no planar law rows touch {args['plane']!r} — "
                                "Great Ring + sigil + the 18 Inner Planes are poured; "
                                "the Outlands and the Astral await their own pours",
                                planes_poured=sorted({p for f in tables.PLANAR_LAW_FILES
                                                      for r in tables._planar_rows(f)
                                                      for p in tables._row_planes(f, r)}))
                return _json({**stamp, "plane": args["plane"], "rows": rows})
            if args.get("family"):
                fam = args["family"]
                if fam not in tables.PLANAR_LAW_FILES:
                    return _err(f"unknown family: {fam}", families=list(tables.PLANAR_LAW_FILES))
                return _json({**stamp, "family": fam, "law_ids": tables.planar_law_index()[fam]})
            return _json({**stamp,
                          "families": {f: len(ids) for f, ids in tables.planar_law_index().items()},
                          "id_scheme": ("law:<family-tail>:<plane-or-topic>[:<school|spell|power|rule>] — "
                                        "plane slugs match Mimir's plane:* ids; sigil rides as 'sigil'"),
                          "handoff": ("build/family/rule-effect-handoff.md §M poured — M1-M6/M8 as §3a; "
                                      "M7 = law:inner-survival (§M7-UNPARK, poured 2026-06-06)")})

        if name == "record_ruling":
            try:
                return _json(ledger().record_ruling(args["docket"]))
            except DocketError as e:
                return _err(str(e), kind="DocketError")

        if name == "overrule":
            try:
                return _json(ledger().overrule(args["ruling_id"], args["docket"]))
            except DocketError as e:
                return _err(str(e), kind="DocketError")

        if name == "precedents":
            return _json(ledger().precedents(args["topic"], args.get("scope"),
                                             args.get("limit", 10)))

        if name == "house_rules":
            return _json(ledger().house_rules(args.get("scope")))

        if name == "ruling_chain":
            chain = ledger().chain(args["ruling_id"])
            return _json({"chain": chain, "head": ledger().get(chain[-1], follow=False) if chain else None})

        if name == "law_info":
            sources = {}
            for p in sorted(tables.LAW_DIR.glob("*.json")):
                doc = json.loads(p.read_text(encoding="utf-8"))
                sources[p.stem] = doc.get("_source", "—")
            return _json({"law_version": tables.law_version(), "tables": sources})

        if name == "usage_stats":
            counts = json.loads(USAGE_PATH.read_text(encoding="utf-8")) if USAGE_PATH.exists() else {}
            return _json(counts)

        return _err(f"unknown tool: {name}")
    except KeyError as e:
        return _err(f"missing required argument: {e}", tool=name)
    except Exception as e:  # last resort — never crash the stdio loop
        logger.exception("tool %s failed", name)
        return _err(f"{type(e).__name__}: {e}", tool=name)


async def main() -> None:
    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
