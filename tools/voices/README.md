# Reference voice clips (F5-TTS)

Curated voice-cloning reference samples for F5-TTS (`tools/F5-TTS/`).
A "voice" in F5 terms = a ~5–10s WAV + its transcript; there are no
per-voice checkpoints.

## Provenance

- Source: https://github.com/erew123/alltalk_tts `voices/` folder
  (sparse-checkout, commit `3d4b94b`, 2025-03-19), pulled 2026-06-05.
- `*.txt` files are the matching transcripts — pass as `ref_text` so
  inference skips the ASR transcription step (and its model download).
  Clips without a transcript get auto-transcribed at first use.
- `female_01.wav` is the studio-quality sample the XTTS model was
  trained on; `female/male_*.wav` are generic studio voices.

## License lane

- The named clips (Attenborough, Eastwood, Freeman, James Earl Jones,
  Arnold, Sophie Anderson) are real people's voices: **local-only,
  table use only, never ships in any published artifact** — same lane
  as `content/official/`.
- `sounds-pst-fallfromgrace/` is copyrighted game audio AND a real
  actor's voice (see below) — deepest shelf of the same lane.
- The F5-TTS pretrained checkpoints are CC-BY-NC regardless, so the
  whole voice stack stays non-commercial.

## sounds-pst-fallfromgrace/ — Fall-from-Grace (Planescape: Torment)

Jennifer Hale's complete Fall-from-Grace VO: 165 WAVs (`FFG###`
dialog ids), 22,050 Hz mono 16-bit PCM, ~7 min total speech. Sound
rip hosted by The Phrozen Keep (`ThePhrozenKeep.txt` is their host
note). Copyright: Planescape: Torment (Black Isle/Interplay; EE by
Beamdog) — local-only, table-only.

F5 reference-clip candidates (5–15s continuous speech; transcripts
TBD — leave `ref_text` empty for ASR, then pin the verified text as
a sibling `.txt`):

| clip | dur |
|---|---|
| FFG334A.wav | 8.5s |
| FFG319A.wav | 7.0s |
| FFG144.wav | 6.9s |
| FFG304.wav | 6.3s |
| FFG309.wav | 6.2s |
| FFG074.wav | 6.0s |

(17 clips total in the sweet spot; full ranking reproducible with the
`wave`-module sweep — see git-less provenance: pulled 2026-06-05.)

## sounds-pst-annah/ — Annah-of-the-Shadows (Planescape: Torment)

Sheena Easton's complete Annah VO: 225 WAVs (`ANA###` ids), same IE rip
format (22,050 Hz mono 16-bit), ~9.5 min speech, same Phrozen Keep host
note. Same copyright lane: local-only, table-only. **The accent stress
test** — heavy brogue; F5 is grapheme-based, so accent rides on ref audio
+ dialect spelling in gen_text.

All 225 transcripts whisper-pinned as sidecars (brogue survives mostly
intact — "donna trust that succubus... so she is"; deep cant garbles).
Ref candidates: ANA607C (8.5s, the pike threat — proven smoke ref),
ANA594A (7.4s wary), ANA606A (6.8s threat), ANA107A (5.9s sarcasm),
ANA602A (19.1s anti-Grace rant — too long for a ref, trim first).

## Inventory (24 files, 8.9M)

| voice | transcript |
|---|---|
| female_01 … female_07 | — |
| male_01 … male_05 | — |
| arnold | — |
| Clint_Eastwood CC3 (+enhanced variant) | yes |
| David_Attenborough CC3 | yes |
| James_Earl_Jones CC3 | yes |
| Morgan_Freeman CC3 | yes |
| Sophie_Anderson CC3 | yes |
