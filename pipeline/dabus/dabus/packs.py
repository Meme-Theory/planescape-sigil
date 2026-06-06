"""Voice packs and rip-folder discovery.

A voice pack is a `tools/voices/<voice>.toml` in the F5 CLI's own multi-voice
shape (one source of truth — the same file drives `f5-tts_infer-cli -c`):
top-level ref_audio/ref_text = the 'main' register, each [voices.<name>] block
another register of the SAME speaker. CLI-only keys (gen_text, output_*) are
ignored here. Packs are curation: they live with the voices, not in build/.
"""

import csv
import hashlib
import tomllib
from pathlib import Path

from . import DEFAULT_MODEL, VOICES_DIR

_CLI_ONLY = {"gen_text", "gen_file", "output_dir", "output_file", "remove_silence"}


class PackError(ValueError):
    pass


def _resolve_ref(raw: str, voice_dir: Path) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = voice_dir / p
    return p


def file_sha(path: Path, n: int = 12) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


def load_pack(voice: str) -> dict:
    """Load and validate a voice pack. Refs must exist — a register whose
    reference clip is missing is refused, never silently skipped."""
    toml_path = VOICES_DIR / f"{voice}.toml"
    if not toml_path.exists():
        raise PackError(f"no voice pack {toml_path.name} in {VOICES_DIR} — "
                        f"known voices: {[p['voice'] for p in list_packs()]}")
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    registers: dict[str, dict] = {}
    if data.get("ref_audio"):
        registers["main"] = {"ref_audio": data["ref_audio"],
                             "ref_text": data.get("ref_text", ""),
                             **({"speed": data["speed"]} if "speed" in data else {})}
    for name, block in (data.get("voices") or {}).items():
        registers[name] = dict(block)

    if not registers:
        raise PackError(f"{toml_path.name}: no registers (need top-level ref_audio "
                        f"and/or [voices.<name>] blocks)")

    missing = []
    for name, reg in registers.items():
        ref = _resolve_ref(reg["ref_audio"], VOICES_DIR)
        if not ref.exists():
            missing.append(f"{name}: {ref}")
        reg["ref_audio"] = str(ref)
        reg["ref_sha"] = file_sha(ref) if ref.exists() else None
        if not reg.get("ref_text"):
            sidecar = ref.with_suffix(".txt")
            if sidecar.exists():
                reg["ref_text"] = sidecar.read_text(encoding="utf-8").strip()
    if missing:
        raise PackError(f"{toml_path.name}: missing reference clips — " + "; ".join(missing))

    aliases = dict(data.get("register_aliases") or {})
    for alias, target in aliases.items():
        if target not in registers:
            raise PackError(f"{toml_path.name}: register_aliases.{alias} -> "
                            f"{target!r}, which is not a register "
                            f"({sorted(registers)})")
        if alias in registers:
            raise PackError(f"{toml_path.name}: register_aliases.{alias} shadows "
                            f"a real register — remove one")

    return {"voice": voice, "path": str(toml_path),
            "model": data.get("model", DEFAULT_MODEL), "registers": registers,
            "register_aliases": aliases}


def resolve_register(pack: dict, register: str) -> tuple[str, bool]:
    """Map a requested register through the pack's aliases (the shared mood
    axis — Mimir says 'grave', annah.toml may route it to 'menace').
    Returns (actual_register, was_aliased). Unknown refuses with the menu."""
    if register in pack["registers"]:
        return register, False
    if register in pack["register_aliases"]:
        return pack["register_aliases"][register], True
    raise PackError(
        f"register {register!r} not in pack {pack['voice']!r} — registers "
        f"{sorted(pack['registers'])}, aliases {pack['register_aliases']}")


# ---------------------------------------------------------------- casting

def load_speakers() -> dict:
    """The casting map: Mimir speaker entity id -> voice pack name."""
    path = VOICES_DIR / "speakers.toml"
    if not path.exists():
        return {}
    with open(path, "rb") as f:
        return dict(tomllib.load(f).get("speakers") or {})


def resolve_speaker(owner: str) -> str:
    cast = load_speakers()
    if owner not in cast:
        raise PackError(
            f"no voice cast for speaker {owner!r} — add it to "
            f"{VOICES_DIR / 'speakers.toml'} (known casts: {cast or 'none'})")
    return cast[owner]


def list_packs() -> list[dict]:
    out = []
    for p in sorted(VOICES_DIR.glob("*.toml")):
        try:
            pack = load_pack(p.stem)
            out.append({"voice": p.stem, "registers": sorted(pack["registers"]),
                        "model": pack["model"], "status": "PACKED"})
        except PackError as e:
            out.append({"voice": p.stem, "status": "BROKEN", "error": str(e)})
    return out


def list_folders() -> list[dict]:
    """Rip folders under tools/voices/ with onboarding status."""
    out = []
    for d in sorted(VOICES_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        wavs = list(d.glob("*.wav"))
        if not wavs:
            continue
        out.append({
            "folder": d.name,
            "clips": len(wavs),
            "transcripts": sum(1 for w in wavs if w.with_suffix(".txt").exists()),
            "status": "ONBOARDED" if (d / "_refs.md").exists() else "RAW",
        })
    return out


def pitch_for(ref_audio: str) -> dict | None:
    """Settled-tail data for a reference clip, from its folder's survey CSV."""
    ref = Path(ref_audio)
    survey = ref.parent / "_pitch_survey.csv"
    if not survey.exists():
        return None
    with open(survey, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["clip"] == ref.stem:
                return {k: row[k] for k in
                        ("dur_s", "f0_median", "f0_tail", "tail_minus_median", "voiced_frac")}
    return None
