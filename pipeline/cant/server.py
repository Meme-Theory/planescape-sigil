#!/usr/bin/env python3
"""
Cant MCP Server — the transmuter (Mimir remembers, Mechanus rules, Modron
rolls, dabus speaks; cant SUGGESTS). Plain English in, suggested Sigil street
talk out — sentence candidates, a term palette, and register-tagged corpus
exemplars straight from the dialog dimension.

Design doc: pipeline/cant/CANT.md. Skeleton per the family lens (stdio, file
logging — NEVER stderr, usage counter, no held store handles). The engine is
deterministic rule law over data files; the optional Haiku door opens only
when an API key env is set.
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

from cant import ENGINE_VERSION
from cant.engine import engine

USAGE_COUNTER_PATH = SERVER_DIR / "usage_counter.json"

logging.basicConfig(level=logging.INFO, filename=str(SERVER_DIR / "cant_mcp.log"),
                    filemode="a", format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

server = Server("cant")


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
# Tool handlers
# ---------------------------------------------------------------------------

async def _transmute(args: dict):
    return _text(engine().transmute(
        text=args.get("text", ""),
        density=args.get("density", "street"),
        attitude=args.get("attitude", "neutral"),
        register=args.get("register"),
        method=args.get("method", "rule"),
    ))


async def _voiceover(args: dict):
    return _text(engine().voiceover(
        text=args.get("text", ""),
        voice=args.get("voice"),
        npc=args.get("npc"),
        density=args.get("density", "street"),
        attitude=args.get("attitude", "neutral"),
        register=args.get("register", "main"),
        method=args.get("method", "rule"),
    ))


async def _decode(args: dict):
    return _text(engine().decode(args.get("text", "")))


async def _suggest_terms(args: dict):
    return _text(engine().suggest_terms(
        query=args.get("query", ""),
        cat=args.get("cat"),
        tier=args.get("tier"),
        limit=int(args.get("limit", 12)),
        semantic=bool(args.get("semantic", True)),
    ))


async def _examples(args: dict):
    return _text(engine().examples(
        register=args.get("register"),
        term=args.get("term"),
        speaker=args.get("speaker"),
        limit=int(args.get("limit", 8)),
    ))


async def _cant_info(args: dict):
    info = engine().info()
    try:
        with open(USAGE_COUNTER_PATH, "r", encoding="utf-8") as f:
            info["usage"] = json.load(f)
    except OSError:
        info["usage"] = {"total_calls": 0, "by_tool": {}}
    return _text(info)


# ---------------------------------------------------------------------------
# MCP registration
# ---------------------------------------------------------------------------

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="transmute",
            description=(
                "English sentence in → suggested Sigil-cant out. Returns 3 deterministic "
                "rule-composed candidates (light/street/heavy density), a palette of term "
                "suggestions with lexicon defs + Mimir attestations, and register-tagged "
                "corpus exemplars. method=model opens the Haiku door (needs an API key env); "
                "rule output always rides along as the reproducible witness."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "plain-English sentence(s) to transmute"},
                    "density": {"type": "string", "enum": ["light", "street", "heavy"],
                                "description": "cant thickness — light seasons, street talks, heavy patters (default street)"},
                    "attitude": {"type": "string", "enum": ["friendly", "neutral", "hostile"],
                                 "description": "stance toward the listener — picks the address term (cutter vs berk)"},
                    "register": {"type": "string", "enum": ["main", "amused", "stern", "grave"],
                                 "description": "the dialog dimension's register axis — biases corpus exemplars"},
                    "method": {"type": "string", "enum": ["rule", "model"],
                               "description": "rule = deterministic composer (default); model = Haiku dressing when a key is set"},
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="voiceover",
            description=(
                "English in → a dabus-READY utterance out (the cant→voice handoff). "
                "Transmutes the line, casts the voice (explicit pack name, or the "
                "speakers.toml cast for a Mimir npc id — uncast npcs refuse, cant never "
                "guesses a voice), maps the register onto the pack's axis ([main]/[grave]/"
                "[amused]/[stern], alias-routed, falls back to [main] with a note), and "
                "returns the EXACT dabus speak payload under `speakable`. Fire it via the "
                "dabus MCP yourself — cant performs no renders (lane law). Deterministic "
                "transmute + content-addressed renders ⇒ same ask, same WAV."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "plain-English line to transmute and stage for voice"},
                    "voice": {"type": "string", "description": "dabus voice pack name (tools/voices/<voice>.toml) — give voice OR npc, not both"},
                    "npc": {"type": "string", "description": "Mimir npc id (e.g. npc:uncaged:a-kin) — cast via dabus's speakers.toml"},
                    "density": {"type": "string", "enum": ["light", "street", "heavy"]},
                    "attitude": {"type": "string", "enum": ["friendly", "neutral", "hostile"]},
                    "register": {"type": "string", "enum": ["main", "amused", "stern", "grave"],
                                 "description": "the shared mood axis — becomes the inline [register] tag"},
                    "method": {"type": "string", "enum": ["rule", "model"]},
                },
                "required": ["text"],
            },
        ),
        types.Tool(
            name="decode",
            description=(
                "Cant in → plain English out. Glosses every recognized term inline "
                "([short def]) and lists full definitions. Loose hits on common-English "
                "collisions (case, music, box…) are flagged with ? — read in context."
            ),
            inputSchema={
                "type": "object",
                "properties": {"text": {"type": "string", "description": "cant text to gloss"}},
                "required": ["text"],
            },
        ),
        types.Tool(
            name="suggest_terms",
            description=(
                "Concept in → ranked cant terms out (def, tier, category, corpus attestation "
                "counts + an attested example line when the handbook holds one). "
                "Filter by cat or tier. The reverse dictionary."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "English concept — 'money', 'kill', 'secret information'"},
                    "cat": {"type": "string", "description": "category filter (see cant_info / response categories)"},
                    "tier": {"type": "string", "enum": ["core", "ext"],
                             "description": "core = published-glossary corroborated; ext = fan-canonical spice"},
                    "limit": {"type": "integer", "description": "max terms (default 12)"},
                    "semantic": {"type": "boolean",
                                 "description": "blend MiniLM cosine into ranking (default true; paraphrase recall — 'the payoff' finds garnish)"},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="examples",
            description=(
                "Register-tagged speech exemplars from Mimir's dialog dimension (the poured "
                "books' actual lines). Filter by register, lexicon term, or speaker. "
                "The corpus outranks invention — steal these rhythms."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "register": {"type": "string", "enum": ["main", "amused", "stern", "grave"]},
                    "term": {"type": "string", "description": "only lines attesting this lexicon term"},
                    "speaker": {"type": "string", "description": "NPC name or id fragment (e.g. \"A'kin\")"},
                    "limit": {"type": "integer", "description": "max lines (default 8)"},
                },
            },
        ),
        types.Tool(
            name="cant_info",
            description=(
                "Engine status: lexicon counts/tiers/sources, rewrite-rule counts, compiled-store "
                "freshness (STALE means a pour landed since the last harvest — re-run "
                "pipeline/cant/harvest.py), model-door state, usage counters."
            ),
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


_DISPATCH = {
    "transmute": _transmute,
    "voiceover": _voiceover,
    "decode": _decode,
    "suggest_terms": _suggest_terms,
    "examples": _examples,
    "cant_info": _cant_info,
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
    except (ValueError, KeyError, FileNotFoundError) as e:
        logger.warning("tool %s refused: %s", name, e)
        return _err(str(e))
    except Exception as e:
        logger.exception("tool %s failed", name)
        return _err(f"{type(e).__name__}: {e}")


async def main():
    logger.info("cant MCP server starting (engine v%s)", ENGINE_VERSION)
    # Semantic lane boots BEFORE stdio parks — C-extension DLL loads (ort/np)
    # deadlock once the reader thread sits on fd 0 (dabus D8 wire law).
    sem = engine().enable_semantic()
    logger.info("semantic lane: %s", json.dumps(sem))
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream,
                         server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
