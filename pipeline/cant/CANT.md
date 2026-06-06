# CANT — the transmuter (design doc)

*Mimir remembers, Mechanus rules, Modron rolls, dabus speaks — **cant suggests.***

Plain English in, suggested Sigil street-talk out. The fifth family member:
an MCP whose whole job is STYLE — sentence candidates, a term palette, and
register-tagged exemplars lifted from the corpus the family already trusts.
Built per Meme's direction 2026-06-06: *"make it an MCP; sentence in —
suggested results out; see if python can wrangle it; if not, hook up the API
and have a Haiku bot do the crawling."* Python wrangles it (§4); the Haiku
door exists and stays shut by default (§5).

Impl `pipeline/cant/` · stores `build/cant/` + `pipeline/cant/data/` ·
veneer `.claude/skills/cant/` · registered in `.mcp.json` (py.exe full path,
family law).

## 1. Boundary (lane law)

**cant SUGGESTS — no law, no dice, no canon, no fiat.**

- Every output is a *candidate* or a *palette*, never an assertion. The
  caller's bone-box makes the final call.
- Attestations cite Mimir ids verbatim, but the **authority is Mimir's**;
  cant never writes the handbook, never cures, never promotes.
- No randomness anywhere: rule choices hash deterministically (§4). Chance
  belongs to Modron; a transmuter that diced would be wearing her shoes.
- No rulings: if a table fight breaks out over whether "berk" is in-character,
  that's a Mechanus docket, not a cant tool result.

## 2. Stores & data law

| file | role | write path |
|---|---|---|
| `data/lexicon.json` | curated term lexicon (362 terms: 118 core / 244 ext) | hand-curation ONLY |
| `data/rewrites.json` | EN→cant transformation law (20 templates · 128 subs · 3 seasonings) | hand-curation ONLY |
| `build/cant/cant.json` | compiled: lexicon + corpus attestations + voice_lines + candidates | `harvest.py` ONLY |
| `build/cant/vectors.npz` | semantic sidecar: 362×384 MiniLM def-vectors + meta (model sha, lexicon sha) | `harvest.py` ONLY |
| `tools/minilm/` | MiniLM-L6-v2 ONNX model + tokenizer, sha-pinned in `PROVENANCE.json` (Apache-2.0) | one-time fetch, offline after |
| `pipeline/cant/usage_counter.json` | lens-pattern telemetry | server, atomic replace |

- **Tiers:** `core` = corroborated across the published-glossary line (PWHB
  TSR 2620 / PSCS TSR 2600 / PS:T) via ≥2 independent archives; `ext` =
  fan-canonical (chiefly mimir.net's dictionary). The engine's density ladder
  respects the split: light/street lean core, heavy reaches the ext tail.
- **Match policy** (`word` | `phrase` | `none`) guards attestation honesty:
  common-English collisions (case, music, box, blood…) never auto-attest.
  A false attestation is provenance fraud, not free flavor.
- **License lanes:** definitions are original paraphrases; published
  glossaries are CITE-ONLY products (no verbatim text lives in the lexicon);
  fan archives are credited by URL + fetch date in `_meta.sources`.
  Curation drops are logged in `_meta.curation_notes` (5e-era faction renames,
  City-of-Glass dialect, planardm's Takers≠Athar error — corrected).
- **The growth loop (the marquee):** pour a book into Mimir → `py -3.13
  pipeline/cant/harvest.py` → richer attestations + voice_lines + new
  `candidates` (unknown hyphen-compounds seen in dialog). Promotion of a
  candidate into the lexicon is a CURATION act — a human (or a session under
  one) edits `lexicon.json` with a source. Never automatic.
- Harvest reads `handbook.db` READ-ONLY via Mimir's own store lib (importlib
  seam, same as Modron's `_mimir_store()`); admitted entities only —
  quarantine stays quarantined.

## 3. Tool surface (5)

| tool | in | out |
|---|---|---|
| `transmute` | text, density (light/street/heavy), attitude (friendly/neutral/hostile), register (main/amused/stern/grave), method (rule/model) | 3 deterministic candidates (one per density, requested first) + applied-rule trace + suggestion palette (lexicon-dressed, attestation counts, corpus example) + register-biased corpus exemplars + store freshness note |
| `voiceover` | text, voice OR npc (Mimir id → speakers.toml cast), density, attitude, register, method | the cant line + `speakable` (the exact dabus `speak` payload, `[register]`-tagged, alias-routed) + casting verdict + transmute trace; uncast npc ⇒ speakable withheld with the why (D11) |
| `decode` | text | inline-glossed text + hits (term, def, tier, `loose` flag on common-English collisions) |
| `suggest_terms` | query, cat?, tier?, limit | ranked reverse-dictionary (prefix-stemmed matching; attestation breaks ties, never qualifies) |
| `examples` | register?, term?, speaker?, limit | voice_lines from the dialog dimension, filtered |
| `cant_info` | — | engine version, lexicon/rewrites counts, store state (COMPILED / **STALE** / LEXICON-ONLY), model-door state, usage |

Refusals are structured and correct: empty text, unknown density/attitude/
register/method, model door without a key. Don't "fix" them.

## 4. Engine law (the Python wrangler)

Pass order: **templates** (whole-intent recasts: greetings, threats, curses,
tell-me-about…) → **substitutions** (span swaps with `\N` backrefs) →
**seasoning** (damn→sodding @street, very→stinking @heavy) → **address law**
→ capitalization repair.

- **Determinism:** every choice = `crc32(input | rule_id | density) % n`.
  Same ask, same answer, byte-identical. `hash()` is salted and BANNED.
- **Density ladder:** light sees `out[0]` (plainest), street the first two,
  heavy the whole list (ornate tail). Rules may sleep below `min_density`
  ("never → when the Lady speaks" wakes only at heavy).
- **Single-address law:** one address term per line — the FIRST `{addr}`
  fills (street+), every other placeholder strips; auto-inject only on
  2nd-person sentences that have no address yet. (V&V D1.)
- **Register** is the dialog dimension's axis (`main/amused/stern/grave`,
  from speech verbs — dialog.py) and biases corpus-exemplar selection;
  it does not yet gate rule choices (§9 Q3).
- All three data files reload on mtime change (`_Fresh`) — **data edits land
  on the next call, no reconnect**. Code changes still need `/mcp` reconnect
  (family law).

### 4b. The semantic lane (D9 — built 2026-06-06 on Meme's word)

Paraphrase recall the regexes can't reach: "that gemstone" surfaces `sparkle`
though no rule fires; "bribe" finds `garnish` at cosine 0.585.

- **Encoder:** MiniLM-L6-v2 via **onnxruntime CPU**, `intra_op = inter_op = 1`
  (byte-determinism over speed; ~10-20 ms a sentence). Masked mean-pool, L2
  norm. Model sha verified against `PROVENANCE.json` at boot — a wrong sha
  shuts the lane with the reason, never serves silently-wrong vectors.
- **Vectors at harvest, queries at call:** `harvest.py` embeds every
  `term: def` into `vectors.npz`; the sidecar carries the **lexicon's file
  sha** and the **model's sha**. The engine refuses vectors cut from a
  different lexicon (stale ranking = silent lie) or a different model
  (ranking-drift law) — both `why`s name the fix.
- **Where it serves:** `suggest_terms` blends cosine into ranking
  (`match: {lexical, semantic}` both shown; semantic-only entries need
  cosine ≥ 0.35); `transmute` gains a `concepts` channel — meaning-near terms
  the surface pass missed, surface-matched/palette terms excluded.
- **PRECISION LAW: suggestions only.** Nothing semantic ever fires a rewrite —
  rule candidates are byte-identical with the lane on or off (pinned by
  test). A wrong suggestion wastes a glance; a wrong rewrite ships a lie.
- **Calibration (live, 2026-06-06):** θ_include 0.35 / θ_floor 0.30 — "they
  arrested him" → scragged 0.355 (passes), vague "took him away" tops at 0.31
  and weather-talk at 0.33 (both silenced). Single-word polysemy ("payoff")
  under-reaches by design — sentences carry the context the encoder needs.
- **Ops:** boots eagerly in the server BEFORE stdio parks (dabus D8 — C-ext
  DLL loads deadlock after); lazily for CLI/pytest. `CANT_SEMANTIC=off` is
  the hatch. Lane absent/unprovisioned ⇒ everything else serves, status says
  why (same honesty as the Haiku door).

## 5. The model door (the Haiku bot)

`transmute(method="model")`:

- **Shut by default.** Opens only when `CANT_API_KEY` or `ANTHROPIC_API_KEY`
  is set; model `CANT_MODEL` (default `claude-haiku-4-5-20251001`).
- The prompt is built FROM the rule output (palette + corpus exemplars), so
  the model dresses what the data already witnessed — it cannot invent
  unsourced cant without disobeying its own brief.
- Rule candidates ALWAYS ride along as the reproducible witness; the response
  declares `method` honestly, and model output is labeled non-deterministic.
- No key / network failure ⇒ structured refusal + the rule fallback stands.
  This is the family's first cloud seam — kept opt-in for exactly that
  reason (D6).

## 6. Wire law

- Warnings suppressed before imports; **file logging only**
  (`cant_mcp.log`) — stderr breaks MCP stdio.
- **No held handles:** every data file opens-and-closes per (re)load; the
  server NEVER touches `handbook.db` (harvest is the only reader, offline).
  Mimir's re-pours can never hit a `WinError 32` because of cant.
- Smoke-test through the EXACT configured spawn
  (`py -3.13 pipeline/cant/smoke_server.py` reads `.mcp.json`).

## 7. V&V

**Full live-wire ceremony: `pipeline/cant/VERIFICATION.md`** (2026-06-06) —
4 layers, all PASS, 0 engine defects: offline foundations, 15 live probe
families through the session MCP (incl. cross-MCP provenance re-fetched from
live Mimir and byte-determinism on the wire), freshness drills (two NATURAL
stale-detect/recover cycles — real pours landed mid-ceremony; vectors-absence
degrade/recover proving the no-held-handle law; rewrites live-reload with
zero reconnects), robustness (4.8 ms/transmute, adversarial metachars).

- `py -3.13 -m pytest tests/ -q` — **43 passed** (gears law, transmute
  contract, determinism, decode, suggest, data-law audits — incl. the
  ceremony-added backref-vs-groups and sidecar-integrity guards — semantic
  refusal laws via fake sidecars + 5 live-model pins, and the D11 handoff
  pack: fake-voices-dir casting law ×9 + live grace-pack pin; live pins
  auto-skip on unprovisioned machines).
- `py -3.13 pipeline/cant/smoke_server.py` — **18/18** live stdio probes
  (semantic + voiceover blocks adaptive: provisioned ⇒ full contract;
  absent ⇒ the why must be present).
- **Live chain demo (2026-06-06):** engine `voiceover` → dabus MCP `speak`
  fired with the speakable VERBATIM → `rnd:8e7fe9149700`, Grace amused,
  5.08 s WAV. The handoff also CAUGHT engine defect D12 while staging
  (address stutter) — fixed, version-bumped, pinned.
- `py -3.13 pipeline/cant/cant/embed.py` — encoder self-test (shape, norm,
  ranking sanity, byte-determinism).
- Defects caught live, fixed, pinned:
  - **D1** double-address pileup ("cutter… cutter") → single-address law + pin.
  - **D2** `suggest_terms` leaked zero-relevance terms (attested bonus
    qualified instead of tie-breaking) + missed morphology (kill≠killed) →
    base-then-bonus scoring, prefix-stem matching + pin.
  - **D3** degenerate prose snippet over-trimmed to emptiness → raw-window
    fallback + pin.
  - **D4** decode missed bare "chant" (phrase policy too strict for the
    READER direction) → loose headword door, `?`-flagged + pins in both
    layers.
  - (data-law catch) rewrites linked `celestial` before the lexicon held it —
    the audit test refused; entry added (core, PWHB-corroborated).

## 8. Decisions ledger

| date | decision | rationale |
|---|---|---|
| 2026-06-06 | D1: MCP, not skill-with-data | Meme's direction; "sentence in — suggested results out" is a tool contract, and the family lens (logging, counters, refusals) fits it |
| 2026-06-06 | D2: rule engine deterministic via crc32; no RNG | chance is Modron's lane; reproducible suggestions are auditable suggestions |
| 2026-06-06 | D3: transformation law as data (rewrites.json), live-reloaded | the family's law-is-data pattern; a new idiom is a JSON drop-in, no code, no reconnect |
| 2026-06-06 | D4: lexicon tiered core/ext with per-term match policy | published-corroborated vocabulary defaults; attestation honesty over recall |
| 2026-06-06 | D5: candidates channel for unknown compounds; promotion = hand-curation | mirrors curations.json — "verified or absent", never auto-parsed guesses |
| 2026-06-06 | D6: model door opt-in by env key; rule witness always rides | first cloud seam in an all-local family — explicit, declared, refusable |
| 2026-06-06 | D7: usage counter best-effort atomic, no lockfile | telemetry, not provenance; the mutable stores that need the O_EXCL lens (handbook/rulings/rolls/renders) live elsewhere |
| 2026-06-06 | D8: decode gets a loose door (none-policy + phrase headwords), `?`-flagged | the reader direction wants recall; the flag keeps it honest (D4) |
| 2026-06-06 | D9: semantic lane BUILT — MiniLM ONNX, vectors-at-harvest, suggestions-only, double-sha staleness law (lexicon sha + model sha), θ 0.35/0.30 live-calibrated | Meme's word on §9 Q5; onnxruntime over torch (weight class), determinism preserved (single-thread ORT), rewrites stay regex-auditable |
| 2026-06-06 | D10: model files at `tools/minilm/` sha-pinned, fetched once, offline after | dabus HF-offline doctrine; integrity refusal beats silent wrongness |
| 2026-06-06 | D11: dabus handoff = `voiceover` emitting the exact `speak` payload; casting read from dabus's speakers.toml READ-ONLY; uncast refuses; caller fires the render | "direct" within the law — data seams and caller-chaining, never MCP-over-MCP, never editing the sibling |
| 2026-06-06 | D12: ENGINE_VERSION 1→2 — post-substitution vocatives strip `{addr}` placeholders (the "Lady's grace, cutter — cutter!" collision) | caught STAGING the first voiceover; composition law changed ⇒ version bump, never silent |

## 9. Open questions (addressed to Meme)

1. **Candidate promotion cadence** — sweep `build/cant/cant.json::candidates`
   after every pour, or batch per book? (Today: 1 candidate, `milk-white`,
   correctly rejected — OCR flotsam.)
2. **dabus seam** — ANSWERED + BUILT (Meme's word, 2026-06-06; D11). The
   `voiceover` tool: transmute → cast the voice from dabus's OWN
   `speakers.toml` (read-only data seam — the Modron-reads-handbook pattern;
   uncast npcs refuse, cant never guesses a voice) → register mapped onto the
   pack's axis (shared {main,grave,amused,stern} by construction — both sides
   inherit the dialog dimension's axis; pack `[register_aliases]` routed;
   absent register falls back to `[main]` with a note) → the EXACT dabus
   `speak` payload under `speakable`. The CALLER fires it — no MCP-over-MCP,
   dabus untouched. Proven live: `rnd:8e7fe9149700` (Grace, amused, 5.08 s)
   rendered from a speakable verbatim. Deterministic transmute +
   content-addressed renders ⇒ same English ⇒ same WAV. Multi-voice
   `dialogue` handoff (scene-shaped) stays open as Q6.
3. **NPC-persona transmute** — `voice: "npc:uncaged:a-kin"` biasing rule
   choices toward that NPC's attested terms/register (the data is already in
   voice_lines). Queued; wants a per-NPC term-frequency table in the compiled
   store.
4. **Register-gated rules** — should `stern` suppress `amused`-flavored
   templates (e.g. "swob me bob")? Today register only biases exemplars.
5. **Semantic layer** — ANSWERED + BUILT (Meme's word, 2026-06-06; see §4b
   and D9/D10). The embedding lane shipped: MiniLM via onnxruntime,
   suggestions-only, double-sha staleness law. REJECTED for cause and staying
   rejected: AllenNLP SRL (archived upstream, duplicates the caller-LLM's
   polish pass), AMR (formal graphs are overkill for style; brittle on table
   speech), NLI zero-shot (400MB+ for what intent-exemplar cosine does at
   1/10 weight), spaCy vectors (context-free, weaker than MiniLM here).
   STILL OPEN remnant: spaCy POS-gating of ambiguous substitutions, IF table
   play surfaces false swaps the match policy doesn't already fence.

## 10. Sibling deltas

None yet. (Reconcile-in-own-doc law: if Mimir's dialog schema or store lib
API moves, the delta lands HERE with a date, and harvest.py follows.)
