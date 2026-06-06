#!/usr/bin/env python3
"""
dabus MCP Server — the voice engine (Mimir remembers, Mechanus rules, Modron
rolls, dabus speaks).

The silent servitor taught to talk: F5-TTS held warm over the tools/voices/
packs, every render content-addressed and ledgered, identical asks served
from cache. Runs on the f5-venv interpreter (DABUS.md D1) — the model lives
in-process. Design doc: pipeline/dabus/DABUS.md. Skeleton per the family lens
(stdio, file logging, usage counter, guarded single-writer store).
"""

# Quiet the stack before any imports — stdout is protocol, stderr is noise
import warnings
import os
warnings.filterwarnings("ignore")
os.environ.setdefault("PYTHONWARNINGS", "ignore")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("PYTHONUTF8", "1")
# OFFLINE: the server never phones home. Everything (F5, vocos, whisper) is
# in the HF cache; cached_path's online etag checks got rate-limited into a
# 5-MINUTE model load (9s offline — 2026-06-05 timeline in dabus_mcp.log).
# Missing models error fast and honestly: download once via the CLI instead.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import asyncio
import io
import json
import logging
import sys
from contextlib import redirect_stdout
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))
sys.path.insert(0, str(SERVER_DIR.parent.parent / "tools"))  # onboard_voice et al.

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

# EAGER preload of the ENTIRE heavy import chain — before the stdio reader
# exists. Wire law (three fault dumps, 2026-06-05): once anyio's stdin-reader
# thread parks in a blocking read, ANY C-extension DLL load (numpy, then
# scipy, then whoever's next in F5's lazy chain) deadlocks until the next
# client message arrives — hangs quantized to the client's timeout. So every
# DLL loads NOW, pre-loop, or never. Model WEIGHTS stay lazy (ensure_model):
# an idle dabus holds no VRAM. Boot pays ~10s; the wire stays alive.
import numpy as _numpy_preload  # noqa: F401
import soundfile as _soundfile_preload  # noqa: F401

from dabus.engine import os_stdio_guard as _boot_guard  # noqa: E402

with _boot_guard(), redirect_stdout(io.StringIO()):
    import f5_tts.api as _f5_preload  # noqa: F401  (torch/scipy/librosa/transformers/vocos)

from dabus import ENGINE_VERSION, LANE, VOICES_DIR
from dabus import packs, store

USAGE_COUNTER_PATH = SERVER_DIR / "usage_counter.json"

logging.basicConfig(level=logging.INFO, filename=str(SERVER_DIR / "dabus_mcp.log"),
                    filemode="a", format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Debug rig: DABUS_DEBUG_FAULT=<seconds> dumps ALL thread stacks to
# dabus_fault.log after N seconds — the dead-man confession for hangs.
if os.environ.get("DABUS_DEBUG_FAULT"):
    import faulthandler
    _fault_file = open(SERVER_DIR / "dabus_fault.log", "a", encoding="utf-8")
    faulthandler.enable(_fault_file)
    faulthandler.dump_traceback_later(int(os.environ["DABUS_DEBUG_FAULT"]),
                                      file=_fault_file)

server = Server("dabus")


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

async def _list_voices(args: dict) -> list[types.TextContent]:
    return _text({"packs": packs.list_packs(), "folders": packs.list_folders(),
                  "voices_dir": str(VOICES_DIR), "lane": LANE,
                  "note": "PACKED = renderable now; ONBOARDED = has _refs.md, "
                          "needs a <voice>.toml; RAW = run onboard_voice first"})


async def _voice_info(args: dict) -> list[types.TextContent]:
    pack = packs.load_pack(args["voice"])
    registers = {}
    for name, reg in pack["registers"].items():
        registers[name] = {
            "ref_clip": Path(reg["ref_audio"]).name,
            "ref_sha": reg["ref_sha"],
            "ref_text": reg["ref_text"],
            **({"speed": reg["speed"]} if "speed" in reg else {}),
            "pitch": packs.pitch_for(reg["ref_audio"]),
        }
    return _text({"voice": pack["voice"], "pack": pack["path"],
                  "model": pack["model"], "registers": registers, "lane": LANE})


async def _onboard_voice(args: dict) -> list[types.TextContent]:
    folder = Path(args["folder"])
    if not folder.is_absolute():
        folder = VOICES_DIR / folder
    if not folder.is_dir():
        return _err(f"{folder} is not a directory")
    import onboard_voice as ob  # tools/ module; whisper loads only if needed
    from dabus.engine import os_stdio_guard
    buf = io.StringIO()
    with os_stdio_guard(), redirect_stdout(buf):
        ob.inventory(folder)
        ob.ensure_transcripts(folder)
        rows = ob.ensure_pitch(folder, bool(args.get("refresh_pitch")))
        ob.write_report(folder, rows)
    logger.info("onboarded %s", folder)
    return _text({"folder": str(folder), "report": str(folder / "_refs.md"),
                  "log": buf.getvalue(),
                  "next": f"write tools/voices/<voice>.toml choosing refs from "
                          f"_refs.md (settled-tail doctrine), then speak()"})


async def _speak(args: dict) -> list[types.TextContent]:
    from dabus import engine
    out = engine.speak(args["voice"], args["text"], args.get("register"),
                       args.get("nfe_step"), args.get("speed"), args.get("seed"),
                       bool(args.get("force_render")))
    return _text(out)


async def _speak_dialog(args: dict) -> list[types.TextContent]:
    from dabus import engine
    out = engine.speak_dialog(args["ref"], args.get("nfe_step"),
                              args.get("speed"), args.get("seed"),
                              bool(args.get("force_render")),
                              int(args.get("limit", 0)))
    return _text(out)


async def _dialogue(args: dict) -> list[types.TextContent]:
    from dabus import engine
    cues = args["cues"]
    if isinstance(cues, str) and cues.strip().startswith("["):
        cues = json.loads(cues)  # inline JSON that crossed the wire as a string
    out = engine.dialogue(cues, bool(args.get("stitch", True)),
                          float(args.get("gap_s", 0.4)))
    return _text(out)


async def _find_renders(args: dict) -> list[types.TextContent]:
    rows = store.search(args.get("query"), args.get("voice"),
                        int(args.get("limit", 20)))
    slim = [{k: r[k] for k in ("render_id", "voice", "registers", "text", "file",
                               "duration_s", "hits", "created_utc")}
            for r in rows]
    return _text({"count": len(slim), "renders": slim,
                  "note": "pass render_id to render_info for full provenance"})


async def _render_info(args: dict) -> list[types.TextContent]:
    row = store.lookup(args["ref"])
    if not row:
        return _err(f"no render matching {args['ref']!r} (render_id, sha/prefix, "
                    f"or exact file path)")
    row["file_exists"] = Path(row["file"]).exists()
    return _text(row)


async def _stack_status(args: dict) -> list[types.TextContent]:
    import shutil
    out = {"engine_version": ENGINE_VERSION, "python": sys.version.split()[0],
           "venv": sys.prefix, "lane": LANE}
    try:
        import torch
        out["torch"] = torch.__version__
        out["gpu"] = (torch.cuda.get_device_name(0)
                      if torch.cuda.is_available() else "NONE (cpu fallback)")
    except Exception as e:
        out["torch"] = f"IMPORT FAILED: {e}"
    from dabus import engine
    out["model"] = engine.model_state()
    out["ffmpeg"] = shutil.which("ffmpeg") or "NOT FOUND (pydub clipping needs it)"
    out["voices"] = {p["voice"]: p["status"] for p in packs.list_packs()}
    out["ledger"] = store.stats()
    return _text(out)


async def _unload_model(args: dict) -> list[types.TextContent]:
    from dabus import engine
    return _text({**engine.unload(),
                  "note": "VRAM released; next speak() reloads (~10-20s)"})


async def _usage_stats(args: dict) -> list[types.TextContent]:
    if USAGE_COUNTER_PATH.exists():
        with open(USAGE_COUNTER_PATH, "r", encoding="utf-8") as f:
            return _text(json.load(f))
    return _text({"total_calls": 0, "by_tool": {}})


# ---------------------------------------------------------------------------
# MCP wiring
# ---------------------------------------------------------------------------

_KNOB_PROPS = {
    "register": {"type": "string",
                 "description": "Opening register (default 'main'); text may "
                                "switch mid-speech with [register] tags"},
    "nfe_step": {"type": "integer",
                 "description": "ODE steps (default 32; 64 = smoother, slower)"},
    "speed": {"type": "number",
              "description": "Pace (default 1.0, or the register's override)"},
    "seed": {"type": "integer",
             "description": "Name a specific take (joins the cache key). Omit "
                            "for 'whatever take' — random seed, recorded, "
                            "EXCLUDED from key so repeats hit cache"},
}


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="speak",
            description=(
                "Render one speaker's speech to a WAV (or smartly provide the "
                "existing file — identical asks are content-addressed and served "
                "from cache with the hit counted). Text may shift mood mid-speech "
                "via [register] tags from the voice's pack, e.g. "
                "'[grave] This is not a place for the living. [amused] Mostly.' "
                "Unknown registers refuse with the pack's list. Returns render_id, "
                "sha, file path, duration, per-segment seeds, lane stamp."),
            inputSchema={
                "type": "object",
                "properties": {
                    "voice": {"type": "string", "description": "Pack name (list_voices)"},
                    "text": {"type": "string", "description": "What to say; [register] tags allowed"},
                    **_KNOB_PROPS,
                    "force_render": {"type": "boolean", "default": False,
                                     "description": "Fresh take even on cache hit "
                                                    "(supersedes the row, retakes++)"},
                },
                "required": ["voice", "text"],
            },
        ),
        types.Tool(
            name="dialogue",
            description=(
                "Render a multi-voice scene: cues=[{voice, text, register?, seed?, "
                "nfe_step?, speed?}...]. Each cue renders (or cache-hits) "
                "independently; stitch=true (default) also assembles one scene WAV "
                "with gap_s silence between cues — its own ledger row citing "
                "component shas. The table-prep tool: an encounter's set-piece "
                "lines in one call."),
            inputSchema={
                "type": "object",
                "properties": {
                    "cues": {"type": "array", "description": "Ordered cue list"},
                    "stitch": {"type": "boolean", "default": True},
                    "gap_s": {"type": "number", "default": 0.4,
                              "description": "Silence between cues (seconds)"},
                },
                "required": ["cues"],
            },
        ),
        types.Tool(
            name="speak_dialog",
            description=(
                "Perform HANDBOOK dialog (the Mimir seam, read sibling-way — "
                "store lib readonly, no MCP-over-MCP): ref = a dialog node id "
                "('dialog:uncaged:...') for one line, or an npc id "
                "('npc:uncaged:a-kin') for the whole script page-ordered "
                "(limit caps it). Mimir hands text + register + owner + page; "
                "dabus resolves the cast via tools/voices/speakers.toml "
                "(unknown speakers REFUSE — casting is curation) and the "
                "register via pack aliases (disclosed). The dialog id is the "
                "WAV join-key: it names the file, lands in source_ref, and "
                "render_info/find_renders answer to it. Page witness + "
                "admission sha recorded in provenance."),
            inputSchema={
                "type": "object",
                "properties": {
                    "ref": {"type": "string",
                            "description": "dialog:<...> id or npc:<...> id"},
                    "limit": {"type": "integer", "default": 0,
                              "description": "Max lines for an npc script (0 = all)"},
                    "nfe_step": _KNOB_PROPS["nfe_step"],
                    "speed": _KNOB_PROPS["speed"],
                    "seed": _KNOB_PROPS["seed"],
                    "force_render": {"type": "boolean", "default": False},
                },
                "required": ["ref"],
            },
        ),
        types.Tool(
            name="list_voices",
            description=(
                "The roster: voice packs (PACKED = renderable), onboarded rip "
                "folders awaiting a pack, raw folders awaiting onboard_voice. "
                "Every voice is local-only — the lane ships with the answer."),
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="voice_info",
            description=(
                "One voice's full dossier: registers with reference clips, "
                "transcripts, ref shas, and settled-tail pitch data (the Annah "
                "doctrine — F5 anchors a render's opening to the ref's tail "
                "register, so tails matter)."),
            inputSchema={"type": "object",
                         "properties": {"voice": {"type": "string"}},
                         "required": ["voice"]},
        ),
        types.Tool(
            name="onboard_voice",
            description=(
                "Build a voice from a directory of WAV files: inventory -> whisper "
                "sidecar transcripts (pinned, never clobbered) -> f0 pitch survey -> "
                "_refs.md ranked reference candidates (settled-tail doctrine: "
                "5-12s, voiced >= 50%, tail <= median+5Hz). Cache-aware; pass "
                "refresh_pitch=true to resurvey. Folder = absolute path or a name "
                "under tools/voices/. Next step after: write the <voice>.toml pack."),
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {"type": "string"},
                    "refresh_pitch": {"type": "boolean", "default": False},
                },
                "required": ["folder"],
            },
        ),
        types.Tool(
            name="find_renders",
            description=(
                "Search the render ledger (FTS over text, optional voice filter) — "
                "'do we already have this line?' before asking for it. No query = "
                "most recent renders."),
            inputSchema={"type": "object",
                         "properties": {"query": {"type": "string"},
                                        "voice": {"type": "string"},
                                        "limit": {"type": "integer", "default": 20}}},
        ),
        types.Tool(
            name="render_info",
            description=(
                "Full provenance of one render: by render_id ('rnd:...'), sha "
                "(>=8 char prefix), or exact file path. Params, segments with ref "
                "shas, seeds, knobs, hits/retakes, lane, file_exists check."),
            inputSchema={"type": "object",
                         "properties": {"ref": {"type": "string"}},
                         "required": ["ref"]},
        ),
        types.Tool(
            name="stack_status",
            description="Health of the voice stack: torch/GPU, model loaded state, "
                        "ffmpeg, voice packs, ledger stats. The doctor tool.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="unload_model",
            description="Release the F5 model and GPU VRAM (the 9070 XT has other "
                        "jobs). Next speak() reloads warm-start from HF cache.",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="usage_stats",
            description="Per-tool usage counters for this server.",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


_DISPATCH = {
    "speak": _speak,
    "speak_dialog": _speak_dialog,
    "dialogue": _dialogue,
    "list_voices": _list_voices,
    "voice_info": _voice_info,
    "onboard_voice": _onboard_voice,
    "find_renders": _find_renders,
    "render_info": _render_info,
    "stack_status": _stack_status,
    "unload_model": _unload_model,
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
    except (ValueError, KeyError, store.StoreError) as e:
        logger.warning("tool %s refused: %s", name, e)
        return _err(str(e))
    except Exception as e:
        logger.exception("tool %s failed", name)
        return _err(f"{type(e).__name__}: {e}")


async def main():
    logger.info("dabus MCP server starting (engine v%s, python %s)",
                ENGINE_VERSION, sys.version.split()[0])
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream,
                         server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
