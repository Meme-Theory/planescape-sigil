# DABUS — the voice engine

*Mimir remembers. Mechanus rules. Modron rolls. **dabus speaks.***

The dabus are the Lady's silent servitors — they communicate in floating
rebuses and have never been heard to speak. This one was taught to talk
(origin story: the 2026-06-05 session, where the irony was declared
statistically impossible and then made load-bearing). dabus is the MCP over
the `tools/` F5-TTS voice stack: voice packs in, content-addressed WAVs out.

## §1 Seat in the family & boundary

| | Mimir | Mechanus | Modron | **dabus** |
|---|---|---|---|---|
| knows | what **is** | what **governs** | what the dice **said** | what was **said aloud** |
| owns | handbook.db | rulings.db | rolls.db | renders.db + voice packs |

**dabus performs; it does not decide.** No law (what a voice *may* say at a
licensed table is Mechanus/DM business), no dice, no fiat, no entity facts.
Text comes in as an input from the caller/DM; audio goes out with provenance.
The one rule dabus enforces itself is the **lane**: every render row and
every response is stamped local-only (PST rips + living actors' voices +
CC-BY-NC F5 checkpoints) — a render never ships in a published artifact.

## §2 Stores & packs

- **`build/dabus/`** (mutable, family law): `renders.db` (ledger + FTS5,
  O_EXCL lockfile on writes), `renders/<voice>/<sha12>__<slug>.wav`.
- **Voice packs are curation, not state**: `tools/voices/<voice>.toml`, the
  F5 CLI's own multi-voice shape — top-level ref = `main` register, each
  `[voices.<name>]` block another register of the same speaker. One file
  drives both dabus and `f5-tts_infer-cli -c`. Refs prefer voices-dir-relative
  paths (dabus resolves against `tools/voices/`; CLI use then wants that cwd).
  Missing ref clips refuse the pack — never silently skipped. Empty
  `ref_text` falls back to the clip's sidecar `.txt` (the onboarding pin).
- **Rip folders** (`tools/voices/<rip>/`) carry their own artifacts from
  onboarding: sidecar transcripts, `_pitch_survey.csv`, `_refs.md`.

## §3 Render law (cache + provenance)

- **Content address:** sha256 over the canonical ask —
  `{engine_version, model, voice, segments[{register, ref_sha, ref_text,
  text}], knobs}`. Swapping a reference clip or editing its transcript
  changes every dependent sha (the `law_version` analogue).
- **Smart provision:** identical ask ⇒ existing WAV served, `hits` counted,
  `cached: true` disclosed. `force_render` re-renders and SUPERSEDES the row
  (`retakes`++) — same sha, new take, old file overwritten (renders are
  derived artifacts; the rip + pack can always regenerate).
- **Seed policy:** omitted seed = "this line, whatever take" — F5 draws a
  random seed which is RECORDED per segment but EXCLUDED from the key, so
  repeats cache-hit. An explicit seed names a specific take and joins the
  key. (ROCm nondeterminism means seed replay is best-effort, not a Modron
  commitment — dabus makes no fairness claims, only records.)
- **Registers as direction:** text may shift mood mid-speech via
  `[register]` tags (F5 CLI convention). Unknown tags refuse with the pack's
  register list. Segments render separately and concatenate with 0.25s gaps;
  `dialogue` stitches cross-voice cues with 0.4s gaps into a scene WAV whose
  ledger row cites component shas.

## §4 Tool surface (11)

`speak` · `speak_dialog` (the Mimir seam — see §4a) · `dialogue` ·
`list_voices` · `voice_info` · `onboard_voice` (in-process run of the tools/
pipeline: inventory → whisper sidecars → f0 survey → `_refs.md`) ·
`find_renders` (FTS) · `render_info` · `stack_status` · `unload_model` ·
`usage_stats`.

## §4a The Mimir seam (`dabus/mimir_seam.py`)

Dialog nodes read the sibling way: `store.py` loaded via importlib as
`mimir_store` (dodges our own store.py), opened READONLY, **opened and closed
per call** (Mimir V&V D3 / the Windows lock gotcha — dabus must never block a
re-pour). No MCP-over-MCP. Contract per the Mimir design session
(2026-06-05, accepted §9 Δ1):

- **`id`** is content-addressed and stable across re-pours → the WAV
  **join-key**: it names the render file
  (`renders/<voice>/<dialog-id-slug>__<sha8>.wav`), lands in the ledger's
  `source_ref` column (indexed), and `render_info`/`lookup` answer to it
  (newest render wins — a re-poured TEXT changes the content sha, so the new
  file lands beside the old, never clobbering).
- **`fields.text`** → gen_text; **`fields.owner`** → cast via
  `tools/voices/speakers.toml` (a cast is DM curation — unknown speakers
  REFUSE, never guessed); **`fields.register`** → the shared mood axis
  {main, grave, amused, stern}, routed through per-pack `[register_aliases]`
  (e.g. annah: grave→menace) and disclosed when aliased;
  **`fields.page`** + `source_sha` → recorded in render provenance.
- `fields.verb` (rasp/hiss/say…) is recorded and surfaced as a
  `direction_note` — a delivery hint, not yet a knob (candidate future axis:
  verb-conditioned register selection).

## §4b Debug rig

`DABUS_DEBUG_FAULT=<seconds>` (env) arms a faulthandler dead-man: all thread
stacks dump to `dabus_fault.log` after N seconds. This is how every D8 layer
was caught — when a tool call hangs, arm it, rerun, read the confession.
The smoke harness reads via a pump thread (a bare `readline()` can't be
timeboxed and masks exactly these hangs).

## §5 Doctrine inherited from the bench (2026-06-05 session)

- **Settled-tail ref law:** F5 anchors a render's opening to the register the
  ref clip ENDS in. Onboarding ranks candidates by tail-vs-median; packs cite
  the survey. (Annah take 1 flew five octaves on a rising tail; take 3 on a
  −28Hz tail was judged workable.)
- **Accent = OOD:** studio register (Grace/Hale) is in-distribution and easy;
  real brogue (Annah/Easton) drifts. Escalation: re-roll → settled-tail ref →
  smoothing knobs (nfe 64, speed 0.95) → finetune on the rip (~10 min VO).
- **Three rocmsdk patch layers** keep the venv viable — documented in
  `tools/README.md`; any venv rebuild must re-apply (esp. torchcodec stays
  UNINSTALLED).

## §6 Decisions ledger

| # | date | decision | why |
|---|---|---|---|
| D1 | 2026-06-05 | dabus runs on **f5-venv's python** (3.12 + rocmsdk torch), not `py -3.13` | the model must live in-process for warm renders; keeps the registration law's spirit (full-path real interpreter, no Store stub) while amending its letter — recorded here per own-doc reconciliation |
| D2 | 2026-06-05 | packs = the F5 CLI toml shape, living in `tools/voices/` | one source of truth, hand-editable curation; build/ holds only derived state |
| D3 | 2026-06-05 | content-addressed renders, random seeds excluded from the key | "smart provision of preexisting files" — the ask is the address; named seeds remain available for specific takes |
| D4 | 2026-06-05 | lazy model load; stdout hard-redirected to file log around all heavy calls | instant handshake; stdout is MCP protocol (family wire law) |
| D5 | 2026-06-05 | lane stamp on every row and response | licensing enforced in code, not vibes — same ethos as Mechanus's refusals |
| D6 | 2026-06-05 | per-pack `[register_aliases]` route the shared mood axis onto a voice's own registers | Mimir hands {main,grave,amused,stern}; a pack like annah has its own register names — aliases are curation, disclosed at render time; unknown registers still refuse |
| D7 | 2026-06-05 | Mimir join-key: dialog id names the WAV, lands in indexed `source_ref`, lookup answers to it newest-first | "name the render by it; re-pours won't move it" — content sha keeps takes honest, source_ref keeps the join stable |
| D8 | 2026-06-05 | **In-process-model wire law** (three fault dumps): (a) the FULL heavy import chain preloads at boot, before the stdio reader exists — once anyio's stdin reader parks in a blocking read, any C-extension DLL load (numpy → scipy → next) deadlocks until the next client message, hangs quantized to the client timeout; (b) the os_stdio_guard NEVER touches fd 0 (CRT fd-lock vs the parked read — same deadlock), children are shielded via Win32 SetStdHandle slots + fd1 dup2; (c) HF_HUB_OFFLINE=1 — cached_path's online etag checks got rate-limited into 5-minute model loads (9s offline); models download via CLI, the server never phones home | each layer was invisible until the one above it fell; weights stay lazy so an idle dabus holds no VRAM — boot pays ~10s of imports instead |

## §6a Sibling deltas (own-doc reconciliation)

| Δ | date | from | delta | disposition |
|---|---|---|---|---|
| Δ1 | 2026-06-05 | Mimir design session | dialog dimension poured (100 nodes, `spoken_by` edges); dabus to read via store lib readonly; per-node contract id/text/register/owner/page; dabus owns speaker→voice and register→ref maps | **ACCEPTED** — `mimir_seam.py` + `speak_dialog` + `speakers.toml` + D6/D7; register axis confirmed already grace.toml's |

## §7 V&V

`tests/test_dabus.py` — pure-stdlib unit pack (pack parsing, register
splitting, cache-key canon incl. seed policy, ledger insert/dedup/retake/FTS,
slug/path law) runnable under any py ≥3.11. Live smoke: `smoke_server.py`
through the exact configured spawn (f5-venv python, stdio handshake,
list_voices → voice_info → speak cached/uncached round-trip). First full
V&V report lands after the first live table use.

## §8 Open questions (addressed to Meme)

1. **Table-shape:** prep-time `dialogue` batches per encounter artifact
   (R1-style under `build/encounters/<slug>/voice/`?) vs ad-hoc `speak` at
   the live table — or both, with the encounter skill citing render_ids?
   *Half-answered by Δ1:* handbook dialog pre-renders via
   `speak_dialog(npc_id)` with stable join-keys; the open half is whether
   `/encounter-plan` should call it during staging.
2. **Finetune rung:** when zero-shot Annah's drift annoys enough, a
   `finetune` story (F5's train surface) could become a dabus-adjacent
   pipeline — separate session, own doc section.
3. **Morte:** his rip will eventually land. The engine named after the
   silent one will then voice the one who never shuts up. No action needed;
   recorded for the irony ledger.
