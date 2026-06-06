"""Onboard a voice rip for F5-TTS: inventory -> transcripts -> pitch -> ranked refs.

Usage: f5-venv/Scripts/python.exe onboard_voice.py <folder-of-wavs> [--refresh-pitch]

One command per new voice folder. Steps (each skipped when already done):
  1. inventory   — formats + durations (wave module, stdlib)
  2. transcripts — whisper sidecar .txt per clip (transcribe_voices.py; pinned
                   sidecars are never clobbered)
  3. pitch       — f0 survey -> _pitch_survey.csv (pitch_survey.py; cached
                   unless --refresh-pitch)
  4. report      — _refs.md: ranked reference candidates joining duration,
                   pitch, and transcript

Ref doctrine (the Annah lesson, 2026-06-05): F5 anchors a render's OPENING to
the register the reference clip ENDS in — so candidates must tail out settled:
5-12s, voiced >= 50%, tail f0 <= median + 5Hz. Sorted most-settled first.
"""

import collections
import csv
import datetime
import pathlib
import sys
import wave

sys.stdout.reconfigure(encoding="utf-8")

CRITERIA = "5-12s · voiced ≥ 50% · tail f0 ≤ median +5Hz"


def inventory(root: pathlib.Path) -> dict[str, float]:
    fmts, durs = collections.Counter(), {}
    for p in sorted(root.glob("*.wav")):
        with wave.open(str(p)) as w:
            fmts[(w.getframerate(), w.getnchannels(), w.getsampwidth() * 8)] += 1
            durs[p.stem] = w.getnframes() / w.getframerate()
    total = sum(durs.values())
    print(f"inventory: {len(durs)} wavs, {total/60:.1f} min speech, formats {dict(fmts)}", flush=True)
    return durs


def ensure_transcripts(root: pathlib.Path) -> None:
    todo = [p for p in root.glob("*.wav") if not p.with_suffix(".txt").exists()]
    if not todo:
        print("transcripts: all sidecars present", flush=True)
        return
    print(f"transcripts: {len(todo)} to transcribe (loading whisper)...", flush=True)
    import transcribe_voices  # heavy import (torch/whisper) only when needed

    transcribe_voices.main(str(root))


def ensure_pitch(root: pathlib.Path, refresh: bool) -> list[dict]:
    out = root / "_pitch_survey.csv"
    if out.exists() and not refresh:
        print(f"pitch: using cached {out.name}", flush=True)
    else:
        print("pitch: surveying (librosa pyin)...", flush=True)
        import pitch_survey  # heavy import only when needed

        pitch_survey.main(str(root))
    with out.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:  # CSV strings -> numbers (blank = None)
        for k in ("dur_s", "f0_median", "f0_tail", "tail_minus_median", "voiced_frac"):
            r[k] = float(r[k]) if r[k] not in ("", None) else None
    return rows


def write_report(root: pathlib.Path, rows: list[dict]) -> None:
    for r in rows:
        txt = root / f"{r['clip']}.txt"
        r["text"] = txt.read_text(encoding="utf-8").strip() if txt.exists() else ""

    good = [r for r in rows
            if r["dur_s"] and 5.0 <= r["dur_s"] <= 12.0
            and (r["voiced_frac"] or 0) >= 0.5
            and r["tail_minus_median"] is not None and r["tail_minus_median"] <= 5
            and r["text"]]
    good.sort(key=lambda r: r["tail_minus_median"])

    today = datetime.date.today().isoformat()
    lines = [
        f"# Ref-candidate report — {root.name}",
        "",
        f"Generated {today} by `tools/onboard_voice.py`. Criteria: {CRITERIA}",
        "(F5 anchors a render's opening to the ref clip's TAIL register —",
        "settled tails open in-register; see tools/README.md doctrine.)",
        "",
        "| clip | dur | f0 median | tail Δ | voiced | transcript |",
        "|---|---|---|---|---|---|",
    ]
    for r in good:
        text = r["text"].replace("|", "\\|")
        if len(text) > 110:
            text = text[:107] + "..."
        lines.append(
            f"| {r['clip']} | {r['dur_s']}s | {r['f0_median']:.0f}Hz "
            f"| {r['tail_minus_median']:+.1f} | {r['voiced_frac']:.2f} | {text} |"
        )
    lines += ["", f"{len(good)} candidates of {len(rows)} clips. "
              "Full data: `_pitch_survey.csv`; transcripts: sidecar `.txt`."]
    report = root / "_refs.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"report: {report} ({len(good)} candidates)", flush=True)
    for line in lines[6:]:
        print(line, flush=True)


def main() -> None:
    root = pathlib.Path(sys.argv[1])
    refresh = "--refresh-pitch" in sys.argv[2:]
    inventory(root)
    ensure_transcripts(root)
    rows = ensure_pitch(root, refresh)
    write_report(root, rows)


if __name__ == "__main__":
    main()
