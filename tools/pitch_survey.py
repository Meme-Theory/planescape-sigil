"""Pitch-survey a folder of voice clips for F5 reference selection.

Usage: f5-venv/Scripts/python.exe pitch_survey.py <folder-of-wavs>

F5 anchors each render's opening to the END of the reference clip, so a good
ref tails out in the speaker's settled register. For every clip: median f0
of voiced frames, f0 of the final second, voiced fraction, duration. Writes
<folder>/_pitch_survey.csv and prints refs worth using (5-12s, mostly voiced,
tail at-or-below median).
"""

import csv
import pathlib
import sys

import librosa
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")


def survey(path: pathlib.Path):
    y, sr = librosa.load(str(path), sr=None)
    dur = len(y) / sr
    f0, voiced, _ = librosa.pyin(y, fmin=80, fmax=500, sr=sr)
    v = f0[voiced & np.isfinite(f0)]
    if v.size < 10:
        return dur, None, None, 0.0
    frames_per_s = len(f0) / dur
    tail = f0[-int(frames_per_s):]
    tail_v = tail[np.isfinite(tail)]
    tail_med = float(np.median(tail_v)) if tail_v.size >= 5 else None
    return dur, float(np.median(v)), tail_med, float(v.size / len(f0))


def main(folder: str) -> None:
    root = pathlib.Path(folder)
    rows = []
    wavs = sorted(root.glob("*.wav"))
    for i, p in enumerate(wavs, 1):
        try:
            dur, med, tail, vfrac = survey(p)
        except Exception as e:
            print(f"FAIL {p.name}: {e}", flush=True)
            continue
        rows.append({
            "clip": p.stem, "dur_s": round(dur, 1),
            "f0_median": round(med, 1) if med else "",
            "f0_tail": round(tail, 1) if tail else "",
            "tail_minus_median": round(tail - med, 1) if (med and tail) else "",
            "voiced_frac": round(vfrac, 2),
        })
        if i % 50 == 0:
            print(f"{i}/{len(wavs)}", flush=True)

    out = root / "_pitch_survey.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out}", flush=True)

    good = [r for r in rows
            if 5.0 <= r["dur_s"] <= 12.0 and r["voiced_frac"] >= 0.5
            and r["tail_minus_median"] != "" and r["tail_minus_median"] <= 5]
    good.sort(key=lambda r: r["tail_minus_median"])
    print("\nsettled-tail ref candidates (5-12s, voiced>=50%, tail<=median+5Hz):")
    for r in good:
        print(f"  {r['clip']}: {r['dur_s']}s  median {r['f0_median']}Hz  "
              f"tail {r['f0_tail']}Hz  ({r['tail_minus_median']:+.1f})  "
              f"voiced {r['voiced_frac']}")


if __name__ == "__main__":
    main(sys.argv[1])
