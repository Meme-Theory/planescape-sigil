"""The performance engine — F5-TTS held warm, registers as direction.

Heavy imports (torch, f5_tts) happen INSIDE functions: the server handshake
must stay instant, and stdout must stay protocol-clean (every render runs
under redirect_stdout into the file log — torch/F5 print progress to stdout,
which would corrupt MCP stdio).
"""

import io
import logging
import os
import re
import sys
from contextlib import contextmanager, redirect_stdout

from . import BUILD_DIR, DEFAULT_MODEL, LANE
from . import packs
from . import store
from .packs import load_pack

logger = logging.getLogger(__name__)


@contextmanager
def os_stdio_guard():
    """Shield the MCP wire from heavy loads — WITHOUT touching fd 0.

    Two hazards, two mechanisms (the 2026-06-05 fault dumps, in order):
    1. Subprocesses (rocm-sdk's offload-arch.exe) inherit the Win32 std-handle
       SLOTS — a child reading protocol stdin or chattering into protocol
       stdout corrupts/wedges the wire. Children get their handles from
       GetStdHandle slots, so SetStdHandle (devnull in, chatter log out)
       protects them without touching our fd table.
    2. NEVER os.dup/dup2 fd 0 here: the Windows CRT locks an fd for the
       duration of any operation, and anyio's stdin-reader thread is parked
       in a blocking _read(0) between client messages — dup(0) therefore
       blocks until the NEXT request arrives (the 300s-quantized hangs in
       smoke #2-#4). fd1 dup2 is safe: nothing parks blocking ops on it
       while the handler holds the event loop.
    Python-level prints are the caller's business (redirect_stdout)."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    chatter_path = BUILD_DIR / "engine_chatter.log"
    sys.stdout.flush()
    sys.stderr.flush()
    devnull = os.open(os.devnull, os.O_RDONLY)
    chatter = os.open(str(chatter_path),
                      os.O_CREAT | os.O_APPEND | os.O_WRONLY)
    saved_out_fd = os.dup(1)
    if os.name == "nt":
        import ctypes
        import msvcrt
        k32 = ctypes.windll.kernel32
        STD_IN, STD_OUT = -10, -11
        saved_in_h = k32.GetStdHandle(STD_IN)
        saved_out_h = k32.GetStdHandle(STD_OUT)
        k32.SetStdHandle(STD_IN, msvcrt.get_osfhandle(devnull))
        k32.SetStdHandle(STD_OUT, msvcrt.get_osfhandle(chatter))
    os.dup2(chatter, 1)  # our own C-level writes (torch/rocm printf)
    try:
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved_out_fd, 1)
        if os.name == "nt":
            k32.SetStdHandle(STD_IN, saved_in_h)
            k32.SetStdHandle(STD_OUT, saved_out_h)
        for fd in (saved_out_fd, devnull, chatter):
            try:
                os.close(fd)
            except OSError:
                pass

_F5 = None
_F5_MODEL: str | None = None

_TAG = re.compile(r"\[([A-Za-z][\w-]*)\]")
_GAP_S = 0.25          # silence between register segments of one speech
_CUE_GAP_S = 0.40      # default silence between dialogue cues

DEFAULT_KNOBS = {"nfe_step": 32, "speed": 1.0}


class RenderError(ValueError):
    """Refusal-grade: bad register, empty text, malformed cues."""


# ---------------------------------------------------------------- model

def ensure_model(model: str = DEFAULT_MODEL):
    """Lazy-load F5 (and vocoder) once; swap if a pack names another model."""
    global _F5, _F5_MODEL
    if _F5 is not None and _F5_MODEL == model:
        return _F5
    buf = io.StringIO()
    logger.info("loading F5 model %s (fd-guarded)...", model)
    with os_stdio_guard(), redirect_stdout(buf):
        from f5_tts.api import F5TTS
        if _F5 is not None:
            unload()
        _F5 = F5TTS(model=model)
        _F5_MODEL = model
    if buf.getvalue():
        logger.info("model load chatter:\n%s", buf.getvalue())
    logger.info("F5 model %s loaded on %s", model, _F5.device)
    return _F5


def model_state() -> dict:
    return {"loaded": _F5 is not None, "model": _F5_MODEL,
            "device": getattr(_F5, "device", None)}


def unload() -> dict:
    global _F5, _F5_MODEL
    state = model_state()
    if _F5 is not None:
        _F5 = None
        _F5_MODEL = None
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return {"was": state, "now": model_state()}


# ---------------------------------------------------------------- direction

def split_registers(text: str, registers: dict, default: str = "main") -> list[dict]:
    """Split '[stern] Steel out. [amused] Relax.' into register segments.
    Unknown tags REFUSE with the pack's register list — never guessed."""
    if default not in registers:
        raise RenderError(f"register {default!r} not in pack ({sorted(registers)})")
    segments: list[dict] = []
    pos, current = 0, default
    for m in _TAG.finditer(text):
        chunk = text[pos:m.start()].strip()
        if chunk:
            segments.append({"register": current, "text": chunk})
        tag = m.group(1)
        if tag not in registers:
            raise RenderError(f"unknown register [{tag}] — this pack has "
                              f"{sorted(registers)}")
        current = tag
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        segments.append({"register": current, "text": tail})
    if not segments:
        raise RenderError("no text to speak after tag parsing")
    return segments


# ---------------------------------------------------------------- rendering

def _render_segments(pack: dict, segments: list[dict], knobs: dict,
                     seed: int | None) -> tuple["object", int, list[int]]:
    """Render each register segment and concatenate with short gaps.
    Returns (wave float32 np array, sample_rate, per-segment seeds)."""
    import numpy as np

    f5 = ensure_model(pack["model"])
    waves, seeds = [], []
    sr = f5.target_sample_rate
    gap = np.zeros(int(_GAP_S * sr), dtype="float32")
    for i, seg in enumerate(segments):
        reg = pack["registers"][seg["register"]]
        seg_knobs = dict(knobs)
        if "speed" in reg and "speed" not in seg_knobs.get("_explicit", ()):
            seg_knobs["speed"] = reg["speed"]
        seg_knobs.pop("_explicit", None)
        buf = io.StringIO()
        with os_stdio_guard(), redirect_stdout(buf):
            wav, got_sr, _ = f5.infer(
                ref_file=reg["ref_audio"], ref_text=reg["ref_text"],
                gen_text=seg["text"], nfe_step=int(seg_knobs["nfe_step"]),
                speed=float(seg_knobs["speed"]),
                seed=(seed + i) if seed is not None else None,
                show_info=lambda *a, **k: None, file_wave=None)
        if buf.getvalue():
            logger.debug("infer chatter [%s]: %s", seg["register"], buf.getvalue()[-500:])
        sr = got_sr
        seeds.append(int(f5.seed))
        if waves:
            waves.append(gap)
        waves.append(wav.astype("float32") if hasattr(wav, "astype") else wav)
    return np.concatenate(waves), sr, seeds


def speak(voice: str, text: str, register: str | None = None,
          nfe_step: int | None = None, speed: float | None = None,
          seed: int | None = None, force_render: bool = False,
          source_ref: str | None = None, provenance: dict | None = None) -> dict:
    """Render (or smartly provide) one speaker's speech. Text may carry
    [register] tags; `register` sets the opening register (default 'main',
    resolved through the pack's register_aliases — disclosed when aliased)."""
    pack = load_pack(voice)
    opening, aliased = packs.resolve_register(pack, register or "main")
    segments = split_registers(text, pack["registers"], opening)
    for seg in segments:
        reg = pack["registers"][seg["register"]]
        seg["ref_sha"] = reg["ref_sha"]
        seg["ref_text"] = reg["ref_text"]

    knobs = dict(DEFAULT_KNOBS)
    explicit = set()
    if nfe_step is not None:
        knobs["nfe_step"] = int(nfe_step)
        explicit.add("nfe_step")
    if speed is not None:
        knobs["speed"] = float(speed)
        explicit.add("speed")

    sha = store.cache_key(model=pack["model"], voice=voice, segments=segments,
                          knobs=knobs, seed=seed)
    alias_note = ({"register_aliased": {register or "main": opening}}
                  if aliased else {})
    cached = store.get_by_sha(sha)
    if cached and not force_render:
        from pathlib import Path
        if Path(cached["file"]).exists():
            store.bump_hit(sha)
            return {**_payload(cached), "cached": True, **alias_note,
                    "note": "smart provision — identical ask already rendered "
                            "(force_render=true for a fresh take)"}
        logger.warning("ledger row %s lost its file %s — re-rendering",
                       cached["render_id"], cached["file"])
        force_render = True

    import soundfile as sf
    wave, sr, seeds = _render_segments(
        pack, segments, {**knobs, "_explicit": explicit}, seed)
    if source_ref:
        # the Mimir join-key names the file: re-pours won't move the id, and a
        # re-poured TEXT gets a new sha-suffixed file beside the old, no clobber
        d = store.RENDERS_DIR / voice
        d.mkdir(parents=True, exist_ok=True)
        out = d / f"{store.slug(source_ref, 48)}__{sha[:8]}.wav"
    else:
        out = store.render_path(voice, sha, segments[0]["text"])
    sf.write(str(out), wave, sr)
    duration = round(len(wave) / sr, 2)

    row = store.record(
        sha=sha, kind="render", voice=voice,
        registers=[s["register"] for s in segments],
        text=" ".join(s["text"] for s in segments),
        params={"model": pack["model"], "knobs": knobs, "pack": pack["path"],
                "segments": [{k: s[k] for k in ("register", "ref_sha", "text")}
                             for s in segments],
                "seed_policy": "explicit" if seed is not None else "random-take",
                **({"mimir": provenance} if provenance else {})},
        file=str(out), duration_s=duration, seeds=seeds,
        retake=bool(cached), source_ref=source_ref)
    return {**_payload(row), "cached": False, **alias_note}


def dialogue(cues: list[dict], stitch: bool = True,
             gap_s: float = _CUE_GAP_S) -> dict:
    """Render a multi-voice scene: cues = [{voice, text, register?, nfe_step?,
    speed?, seed?}]. Each cue caches independently; stitch=true also writes
    the assembled scene WAV (its own ledger row, components cited)."""
    if not cues:
        raise RenderError("dialogue needs at least one cue")
    rendered = []
    for i, cue in enumerate(cues):
        if not cue.get("voice") or not cue.get("text"):
            raise RenderError(f"cue {i}: voice and text are required")
        rendered.append(speak(cue["voice"], cue["text"], cue.get("register"),
                              cue.get("nfe_step"), cue.get("speed"),
                              cue.get("seed")))
    result = {"cues": rendered, "lane": LANE}
    if stitch and len(rendered) > 1:
        import numpy as np
        import soundfile as sf
        comp_shas = [r["sha"] for r in rendered]
        sha = store.cache_key(model="stitch", voice="scene",
                              segments=[{"register": "cue", "ref_sha": s,
                                         "ref_text": "", "text": ""}
                                        for s in comp_shas],
                              knobs={"gap_s": gap_s}, seed=None)
        cached = store.get_by_sha(sha)
        from pathlib import Path
        if cached and Path(cached["file"]).exists():
            store.bump_hit(sha)
            result["scene"] = {**_payload(cached), "cached": True}
            return result
        waves, sr = [], None
        for r in rendered:
            w, sr = sf.read(r["file"], dtype="float32")
            if waves:
                waves.append(np.zeros(int(gap_s * sr), dtype="float32"))
            waves.append(w)
        scene_wave = np.concatenate(waves)
        text = " / ".join(f"[{r['voice']}] {r['text'][:60]}" for r in rendered)
        out = store.render_path("scene", sha, text)
        sf.write(str(out), scene_wave, sr)
        row = store.record(
            sha=sha, kind="stitch", voice="scene",
            registers=[r["voice"] for r in rendered], text=text,
            params={"components": comp_shas, "gap_s": gap_s},
            file=str(out), duration_s=round(len(scene_wave) / sr, 2),
            seeds=None, retake=bool(cached))
        result["scene"] = {**_payload(row), "cached": False}
    return result


def _payload(row: dict) -> dict:
    out = {"render_id": row["render_id"], "sha": row["sha"][:16],
           "file": row["file"], "duration_s": row["duration_s"],
           "voice": row["voice"], "registers": row["registers"],
           "text": row["text"], "seeds": row.get("seeds"),
           "hits": row.get("hits", 0), "retakes": row.get("retakes", 0),
           "lane": row.get("lane", LANE)}
    if row.get("source_ref"):
        out["source_ref"] = row["source_ref"]
    return out


# ---------------------------------------------------------------- the Mimir seam

def speak_dialog(ref: str, nfe_step: int | None = None, speed: float | None = None,
                 seed: int | None = None, force_render: bool = False,
                 limit: int = 0) -> dict:
    """Perform handbook dialog: ref = a dialog node id (one line) or an npc id
    (the whole script, page-ordered). Mimir hands text + register + owner +
    page; dabus resolves the cast (speakers.toml) and the register (pack
    aliases), renders with the dialog id as join-key, and records the page
    witness in provenance. Unknown casts refuse — recast in speakers.toml."""
    from . import mimir_seam

    nodes = ([mimir_seam.dialog_node(ref)] if ref.startswith("dialog:")
             else mimir_seam.npc_dialog(ref))
    if not nodes:
        raise RenderError(f"{ref!r} has no dialog in the handbook")
    if limit and limit > 0:
        nodes = nodes[:limit]

    out: dict = {"ref": ref, "lines": [], "lane": LANE}
    for node in nodes:
        voice = packs.resolve_speaker(node["owner"])
        provenance = {"dialog_id": node["dialog_id"], "owner": node["owner"],
                      "page": node["page"], "source_sha": node["source_sha"],
                      "attribution": node["attribution"], "verb": node["verb"]}
        rendered = speak(voice, node["text"], node["register"],
                         nfe_step, speed, seed, force_render,
                         source_ref=node["dialog_id"], provenance=provenance)
        line = {**rendered, "mimir": provenance}
        if node.get("verb") and node["verb"] not in ("say", "says"):
            line["direction_note"] = (f"the book has this line {node['verb']!r}d — "
                                      f"delivery hint, not yet a knob")
        if node.get("register_defaulted"):
            line["register_defaulted"] = True
        out["lines"].append(line)
    out["count"] = len(out["lines"])
    return out
