"""Batch-transcribe voice clips to sidecar .txt files.

Usage: f5-venv/Scripts/python.exe transcribe_voices.py <folder-of-wavs>

Uses f5_tts's (Planescape-patched) transcribe() — whisper-large-v3-turbo on
GPU, soundfile decode. Writes <clip>.txt next to each <clip>.wav, skipping
ones that already exist (pinned transcripts are never clobbered). An empty
.txt means whisper heard no speech (gasps, laughs, death sounds) — honest
record, not a failure.
"""

import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

from f5_tts.infer.utils_infer import transcribe  # noqa: E402  (heavy import after stdout fix)


def main(folder: str) -> None:
    root = pathlib.Path(folder)
    wavs = sorted(root.glob("*.wav"))
    todo = [p for p in wavs if not p.with_suffix(".txt").exists()]
    print(f"{len(wavs)} wavs, {len(todo)} to transcribe", flush=True)
    for i, p in enumerate(todo, 1):
        try:
            text = transcribe(str(p))
        except Exception as e:  # keep sweeping; a bad clip is data too
            text = ""
            print(f"FAIL {p.name}: {e}", flush=True)
        p.with_suffix(".txt").write_text(text + "\n", encoding="utf-8")
        if i % 20 == 0 or i == len(todo):
            print(f"{i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
