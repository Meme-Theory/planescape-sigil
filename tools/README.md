# tools/ — the voice stack (and other bench gear)

Out-of-band tooling — EXCEPT that the **dabus MCP** (`pipeline/dabus/`,
design doc DABUS.md) serves from this stack: it runs on `f5-venv`'s
interpreter, reads voice packs from `voices/*.toml`, and renders into
`build/dabus/renders/`. This README is the venv/patch map dabus depends on.

## Voice stack (F5-TTS)

The goal: a voice at the table. Specifically Jennifer Hale's Fall-from-Grace
(see `voices/README.md` — the FemShep-runs-the-campaign dream).

| piece | what |
|---|---|
| `F5-TTS/` | SWivid/F5-TTS clone (tip `2ae2c9b`, 2026-05-18). Code MIT; **pretrained ckpts CC-BY-NC** → whole stack non-commercial. |
| `f5-venv/` | Python 3.12 venv (`py -3.12 -m venv`). **Space-free path is load-bearing** — rocm-sdk's loader shells out unquoted. |
| `voices/` | Reference clips + provenance README. A "voice" = ~5–10s WAV + transcript; no per-voice checkpoints. |
| `voices/_renders/` | TTS output. Derived, regenerable, never ships. |

### The AMD lane (RX 9070 XT, gfx1201)

Mainline PyTorch ROCm is Linux-only. AMD's native **Windows** wheels work:

```bash
py -3.12 -m venv tools/f5-venv   # 3.13 here is the Store stub — don't
tools/f5-venv/Scripts/python.exe -m pip install \
  "torch==2.9.1+rocmsdk20260116" "torchaudio==2.9.1+rocmsdk20260116" \
  --find-links https://repo.radeon.com/rocm/windows/rocm-rel-7.2/
tools/f5-venv/Scripts/python.exe -m pip install -e tools/F5-TTS
```

(`--find-links`, not `--index-url` — the repo is a flat listing. cp312 wheels
only. The HIP device masquerades as CUDA: `torch.cuda.is_available()→True`.)

### Patches (the rocmsdk-torch tax — re-apply on rebuild/reinstall)

1. **venv: `encodec/distrib.py`** — rocmsdk torch ships `USE_DISTRIBUTED=0`;
   `torch.distributed` has no `ReduceOp`, which encodec evaluates at import
   (default arg). Patch = guarded `_ReduceOpStub` injection right after
   `import torch`; commented in-file. Zero behavior change (every distributed
   path early-returns single-process).
2. **F5 clone: `src/f5_tts/infer/utils_infer.py`** (editable install → live) —
   torchaudio 2.9 and transformers 5.x both route audio decode through
   **torchcodec**, and torchcodec's DLLs do NOT load against rocmsdk torch:
   first missing FFmpeg shared DLLs, and after supplying matched FFmpeg 8.1
   DLLs, `WinError 127` (ABI drift vs the exotic torch build — its cause #2).
   Dead end; bypassed instead. Two seams, both marked `PATCH (Planescape)`:
   - `transcribe()` — soundfile-decode + resample to 16k mono, hand whisper
     `{"sampling_rate", "raw"}` instead of a path;
   - `infer_process()` — `sf.read(...).T` instead of `torchaudio.load`.
   Output was already `sf.write` upstream. gradio/speech_edit/socket_server
   still call `torchaudio.load/save` — patch the same way if those surfaces
   are ever wanted.
3. **venv: torchcodec is UNINSTALLED** (`pip uninstall torchcodec`) — even
   with the seams above patched, transformers' ASR pipeline imports torchcodec
   unconditionally whenever the *package is present* (an isinstance probe),
   and the import itself raises. Absent = every touch point is cleanly
   guarded by `is_torchcodec_available()`. It's in f5-tts's declared deps, so
   **any future `pip install -e tools/F5-TTS` quietly reinstalls it — uninstall
   again after.**

### Voice onboarding (the pipeline)

One command per new rip:

```bash
cd tools && PYTHONUTF8=1 ./f5-venv/Scripts/python.exe onboard_voice.py voices/<rip-folder>
```

inventory → whisper sidecar transcripts (`transcribe_voices.py`) → f0 survey
(`pitch_survey.py` → `_pitch_survey.csv`) → ranked ref report (`_refs.md`).
Cache-aware: pinned sidecars never re-transcribed, pitch cached unless
`--refresh-pitch`.

**Ref doctrine (the Annah lesson):** F5 renders are a *continuation* of the
reference clip — the opening of every render anchors to the register the ref
ENDS in. A hot/rising tail opens bright and settles late; a settled tail opens
in-register. Hence the ranking: 5–12s, voiced ≥ 50%, tail f0 ≤ median +5Hz,
most-settled first. Accent wildness (Annah's register swings ±25Hz clip to
clip) is exactly what makes a voice hard zero-shot — if no settled-tail ref
tames it, escalate: sacrificial opener ("Hmph.") sheared off in post, then
finetune on the rip (~10 min of VO suffices to attempt).

### Running

```bash
cd tools && PYTHONUTF8=1 ./f5-venv/Scripts/f5-tts_infer-cli.exe \
  --model F5TTS_v1_Base \
  --ref_audio voices/sounds-pst-fallfromgrace/FFG334A.wav \
  --ref_text "" \
  --gen_text "..." \
  --output_dir voices/_renders --output_file out.wav
```

- Empty `--ref_text` → whisper-large-v3-turbo transcribes the ref (one-time
  ~1.6GB download); once a transcript is verified, pin it as a sibling `.txt`
  and pass it to skip ASR.
- First run downloads F5TTS_v1_Base (~1.4GB) + Vocos vocoder to
  `~/.cache/huggingface`.
- Gotcha: `cmd | tail` masks the exit code — judge runs by the artifact
  (the WAV on disk), not the pipe's exit 0.
