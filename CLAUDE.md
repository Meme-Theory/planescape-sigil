# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Planescape DM project: a legitimately-sourced content corpus → extraction/arbitration
pipelines → a family of three MCP servers (Mimir = knowledge, Mechanus = rules,
Modron = dice) → edition-conversion and eventual play at the table. The marquee goal:
*invoke items from the AD&D modules, for direct use at a 5E table.*

The architectural model is Meme's production physics-research rig
(`C:\sandbox\Ainulindale Exflation\tools`) — SQLite/FTS5 store, guarded write paths,
provenance on everything. Read `pipeline/mimir/ARCHITECTURE.md` first; it defines the
system boundaries.

## Session topology & etiquette (read before editing anything)

Each MCP is designed and built by **its own named session**. The rules, set by
ARCHITECTURE.md and honored since:

- **Reconcile in your OWN doc.** The sibling's doc is authoritative for its domain.
  Never edit a sibling's design doc or implementation — record deltas/acceptances in
  your own doc (see MODRON.md §9 and MECHANUS.md §10 for the pattern).
- Family-level design docs (ARCHITECTURE/DIMENSIONS/VALIDATION/CONVERSION/REVIEW-5E)
  live at `pipeline/mimir/` (the spine); each engine's own doc lives with its impl
  (`pipeline/mechanus/MECHANUS.md`, `pipeline/modron/MODRON.md`); mutable stores
  (DBs, logs, counters) live at `build/<name>/`.
- Decisions get recorded in each doc's own decisions ledger (§10/§11 style tables) with
  dates and rationale. Open questions are numbered and addressed to Meme.
- Shared infra (`.mcp.json`, this file, `build/` layout) is fair game for any session;
  fixing it is not "editing the sibling's doc."

Doc map, in read order: `ARCHITECTURE.md` (boundaries) → `DIMENSIONS.md` (entity
registry + identity/aspect/view model) → `VALIDATION.md` (the admission gate) →
`MECHANUS.md` (rules engine) → `CONVERSION.md` (the 2e→5e fusion engine: three rungs,
action-by-action pipeline, conversion law as data) → `MODRON.md` (dice engine) →
`REVIEW-5E.md` (5E corpus census; the §A validator pack is Mechanus's spec).

## Layout & data law

- **`content/` is immutable.** Pipelines only read it; everything derived lands in
  `build/`. Holds only legitimately-free material (CC/OGL SRDs, retroclones, fan
  archives, wiki exports) — EXCEPT `content/official/`, which is Meme's purchased PDFs:
  **local-only, never redistributed, never quoted into published artifacts.**
- **Licensing is enforced in code, not vibes:** SRD 5.1/5.2.1 are CC-BY-4.0 (verbatim
  attribution blocks ship with quoted law — `attribution` tool); For Gold & Glory is
  the *quotable* 2e RAW (decided, MECHANUS.md §10); Sage Advice is NOT ingested (not
  freely licensed); 5e-2014 encounter math is **refused** (SRD 5.1 never contained it).
  When a tool refuses on license grounds, that refusal is correct behavior — don't
  "fix" it.
- **The page is the unit of provenance.** Every extracted value traces to
  `(product, page, sha)`; every law table cites its page; every docket cites its
  sources. An answer without a citation doesn't ship.
- `D&D Beyond/` (root) is a browser-save inbox; `python pipeline/extract/dndbeyond.py
  ingest` sweeps it into the PAitM build (user-purchased, local-only, the 2e→5e
  conversion answer key).

## Commands

```bash
# Mechanus (rules engine) — from pipeline/mechanus/
python -m pytest tests/ -q                 # full suite (incl. 334-monster fleet audit)
python -m pytest tests/test_lawful.py -q   # one module; -k name for one test
python tests/smoke_server.py               # end-to-end MCP stdio smoke (20 checks)

# Modron (dice engine) — from pipeline/modron/
python -m pytest tests/ -q

# dabus (voice engine) — from pipeline/dabus/
py -3.13 -m pytest tests/ -q               # unit pack (no model needed)
py -3.13 smoke_server.py                   # live stdio smoke (loads model, renders)

# Sourcebook pipeline — from repo root (see pipeline/README.md)
python pipeline/extract/psx.py status      # corpus triage table
python pipeline/extract/psx.py pilot --slug <slug>   # full single-book run

# Reconstitution — fresh machine, same books, verified end state (/uncage skill)
py -3.13 pipeline/uncage.py status         # sources/stages triage vs pinned manifest
py -3.13 pipeline/uncage.py run            # extract → pour → caches (idempotent)
py -3.13 pipeline/uncage.py verify         # live stores vs pipeline/uncage-manifest.json
py -3.13 pipeline/uncage.py pin            # CURATOR: re-pin after every pour/adjudication
```

**MCP registration (`.mcp.json`):** servers MUST use the py launcher by full path
(`C:\\Users\\Meme\\AppData\\Local\\Programs\\Python\\Launcher\\py.exe`, args
`["-3.13", "pipeline/<name>/server.py"]`, cwd repo root). Bare `python` resolves to
the WindowsApps Store stub and dies before the handshake (`-32000`). Smoke-test
servers through the *exact* configured spawn, never via `sys.executable`.
Code changes to a running server need an `/mcp` reconnect to take effect.
**Exception (DABUS.md D1):** dabus serves from the f5-venv interpreter by full
path (`tools\\f5-venv\\Scripts\\python.exe`) — the F5 model lives in-process;
same spirit (full-path real interpreter), amended letter.

## The MCP family

| | Mimir (knowledge) | Mechanus (law) | Modron (chance) | dabus (voice) | cant (style) |
|---|---|---|---|---|---|
| knows | what **is** | what **governs** | what the dice **said** | what was **said aloud** | how a Cager would **say it** |
| owns | `handbook.db` + admission gate | `rulings.db` + mechanical core | `rolls.db` + RNG discipline | `renders.db` + voice packs | lexicon + rewrites (data) + compiled attestations |
| status | store/gate/server **BUILT + V&V'd**; **3 books + 4 boxed sets** poured across **26 dimensions** (824 entities, 1,820 edges) | core BUILT + V&V'd | BUILT + V&V'd | **BUILT + smoked** (unit 25/25 · live stdio 14/14 incl. a handbook line end-to-end) | **BUILT + V&V'd** (33 tests · 16/16 stdio · live-wire ceremony, `pipeline/cant/VERIFICATION.md`) |

Write discipline is structural everywhere: entities enter only through Mimir's gate;
rulings only through `record_ruling`/`overrule`; rolls only through the guarded append;
renders only through the content-addressed ledger (identical asks serve the cached WAV).
The stores use the lens pattern: O_EXCL lockfile, content-address SHA dedup,
file logging (never stderr — it breaks MCP stdio), usage counters.

## cant (style)

Design `pipeline/cant/CANT.md` · impl `pipeline/cant/` · data
`pipeline/cant/data/{lexicon,rewrites}.json` (hand-curated; law-as-data) ·
compiled store `build/cant/cant.json` (NEVER hand-edited). English in →
suggested Sigil cant out: `transmute` (3 deterministic candidates
light/street/heavy + term palette + register-tagged corpus exemplars),
`decode`, `suggest_terms`, `examples`, `cant_info`. **Lane law: cant
SUGGESTS — no law, no dice, no canon, no fiat; rule choices are crc32-hashed
(chance belongs to Modron).** The growth loop: after each book pours into
Mimir, `py -3.13 pipeline/cant/harvest.py` re-attests the lexicon against the
dialog dimension + prose and queues unknown compounds for hand-promotion
(`cant_info` reports STALE when the handbook outdates the compile). The Haiku
door (`transmute method=model`) opens only on CANT_API_KEY/ANTHROPIC_API_KEY;
rule output always rides as the reproducible witness. **Semantic lane (D9):**
MiniLM-L6-v2 ONNX at `tools/minilm/` (sha-pinned, offline) — harvest cuts
`build/cant/vectors.npz`, `suggest_terms` blends cosine, `transmute` gains
`concepts` (paraphrase recall: "gemstone"→sparkle with no rule fired);
**suggestions only, never rewrites**; double-sha staleness law (wrong
lexicon/model sha ⇒ lane shut with the why); `CANT_SEMANTIC=off` hatch.
**dabus handoff (D11):** `voiceover` — transmute + cast (npc id via dabus's
`speakers.toml`, read-only; uncast REFUSES) + `[register]` tag (shared axis,
alias-routed) → the exact dabus `speak` payload under `speakable`; the CALLER
fires it (no MCP-over-MCP; proven live, `rnd:8e7fe9149700`). Deterministic
transmute + content-addressed renders ⇒ same English ⇒ same WAV.
Table veneer: `/cant` skill (engine first; polishing allowed; invented terms
= provenance fraud; `--speak` chains voiceover→dabus verbatim).

```bash
# cant (transmuter) — from pipeline/cant/
py -3.13 -m pytest tests/ -q               # 43 tests (live pins auto-skip)
py -3.13 smoke_server.py                   # 18-probe stdio smoke (configured spawn)
py -3.13 harvest.py                        # re-attest + re-vector after a pour
```

## dabus (voice)

Design `pipeline/dabus/DABUS.md` · impl `pipeline/dabus/` · store `build/dabus/`
· voice stack + packs `tools/` (README there is the venv/patch map). The marquee:
**Jennifer Hale's Fall-from-Grace and Sheena Easton's Annah at the table** —
zero-shot F5-TTS on the 9070 XT (rocmsdk Windows torch). Voice packs =
`tools/voices/<voice>.toml` (the F5 CLI's own multi-voice shape; registers =
same speaker, different reference clips — the emotion dial). Tools: `speak`
(register tags inline, content-addressed cache — "smart provision"),
`speak_dialog` (the Mimir seam: dialog/npc id → cast via
`tools/voices/speakers.toml` → render named by the dialog id, the stable
join-key; store lib readonly, open-close per call, no MCP-over-MCP), `dialogue`
(multi-voice scenes, stitched), `onboard_voice` (rip folder → transcripts →
pitch survey → ranked refs), `list_voices`/`voice_info`/`find_renders`/
`render_info`/`stack_status`/`unload_model`. **Ref doctrine:** F5 anchors a
render's opening to the ref clip's TAIL register — pick settled tails
(`_refs.md` ranks them). **Wire law (DABUS.md D8):** heavy imports preload at
boot (C-extension DLL loads deadlock once the stdio reader parks), the fd
guard never touches fd 0, HF stays offline. **Lane law:** every render is
local-only (PST rips + living actors + CC-BY-NC checkpoints); renders never
ship in published artifacts. dabus performs — no law, no dice, no fiat.

## Rules-lawyer agents & record law (`.claude/`)

Two subagents argue the law at the table (defined in `.claude/agents/`; file-authored
agents load at session start — restart or use `/agents` after edits):

- **`lemure`** (AD&D-lawyer / FG&G-lawyer) — 2e only; quotable RAW = FG&G.
- **`abishai`** (5th-lawyer / SRD-lawyer) — 5e-2014 + 5e-2024; SRD quotes ship
  attribution; 2014 encounter budgets stay refused.

Both return docket-shaped verdicts, never invent die faces, and keep persistent
memory at `.claude/agent-memory/<name>/` (`MEMORY.md` index + full trials in
`trials/`, primed with live verified sessions). **Record law:** `.claude/rules/`
are the requirements, `.claude/templates/` the formats — skills direct, templates
format, rules require. Their grep-able page-cited law caches live at
`build/mechanus/{fgg,srd51,srd52}-text/` (filename = citation page; re-pour with
`py -3.13 pipeline/mechanus/tools/build_text_cache.py`).

**Agent mint-shapes** live at `.claude/agent-templates/` — `dm.md` (campaign-bound
director; ancestor = `encounter-director`), `mvp.md` (NPC → agent promotion; the
bar + ceremony are in its header), `rules-lawyer.md` (the lemure/abishai pattern
for a new view's lawyer). Mint = copy below the header comment to
`.claude/agents/<name>.md`, fill every `<angle>`, seed agent-memory, reload via
`/agents`. Lane law holds at mint time: no minted agent gets `force` or
`record_ruling` — fiat and dockets stay the DM's voice.

## Mimir

Design `pipeline/mimir/{ARCHITECTURE,DIMENSIONS,VALIDATION}.md` · impl `pipeline/mimir/`
(`store.py` / `gate.py` / `server.py`) + `pipeline/parse/` (extractor + the `normalize.py`
gear-house) · store `build/mimir/handbook.db` · adjudications `build/mimir/curations.json`
· V&V report `pipeline/mimir/VERIFICATION.md` (30 pinned + 7-tool live wire; 3 defects caught,
fixed, pinned — edge-dedup, THAC0-OCR, server conn-leak — and the Mechanus L3 seam wired).

**Status: BUILT — 3 books + 4 boxed sets (Uncaged · The Factol's Manifesto · In the Cage ·
Planes of Law/Chaos/Conflict · Hellbound) poured across 26 dimensions (824 entities · 1,820
edges · 89 queued for review in six honest buckets).** Registry: 26 poured · 4 handoff-pending
(rule/planar-trait/table/hazard → Mechanus/Modron ids) · 4 book-pending (spell/race/class/psionic
→ Planewalker's Hbk) · 8 proposed-closed (DIMENSIONS ledger). The books' WHOLE contents:
- **npc 71** — Uncaged's 58 (roster-driven split: the contents page is the authoritative entry boundary
  at an auto-calibrated offset — recovered all 41 roster entries vs the 29 font-detection dropped — plus a
  **minor tier** for the appendix's descriptor-only cutters) + **13 factols** promoted from the Manifesto.
- **item 110 · dialog 100 · location 90 · hook 85 · npc 71 · layer 58 · realm 48 · deity 46 ·
  portal 33 · plane 25 · faction 17 · gate-town 12 · source 9 · organization 3 · cosmology 2 ·
  pathway 2 · event 2 · fiction 2 · sigil 1.** Locations are REAL (establishment nodes from both
  Sigil books); **items are the 110 magic items the cast carries** (`wields` edges — the marquee
  "invoke at the table").
- **3rd book (In the Cage, 2609) = the geography vector (`parse/cage.py` + `pour_cage`):** six ward
  tours by roster law — 21 establishments MERGED into Uncaged nodes (dual-source), 30 new (incl. 8
  minor-tier pubs), 10 shredded heads quarantined BY NAME (`cage-head-lost`, v1b re-OCR path). The
  **portal sweep** (TRIGGER×DEST, clause-paired, negation-guarded, θ=0.55) poured witnessed portals
  (`opens_from`/`connects_to`; `PORTAL_CURATIONS` re-binds witnessed reflow scrambles) and the
  **Places dims poured attested-only from the curated gazetteer**. The review queue was then
  **adjudicated to empty** (`PORTAL_ADJUDICATIONS`: 6 promoted incl. city-level class-portals with
  `src_class` disclosed, 5 rejected with recorded whys) — **33 portals stand.** The cage prose also
  fed the hook tagger (+36 seeds).
- **Planes boxes (Law 2607 / Chaos 2603 / Conflict 2615) = the planar skeleton (`parse/planes.py` +
  `pour_planes`):** curated PLANE_CARDS **text-validated against each box's own reflow** — 16
  Great-Ring planes enriched (layers in box order + gate_town + layer_note), **56/56 layer claims
  attested (0 refused)**, +7 gate-towns backfilled (12 of 16 stand). Identity merge: Pelion ⊃
  layer:amun-thys (one node, both books' names).
- **Realms round (`REALM_CARDS` + `pour_realms`): 48 realms + 46 powers.** Double-witnessed law —
  realm name AND power name must both attest (the Law/Conflict books' literal `POWER.` stat lines
  are the anchor; the Chaos Travelogue heads realms by name); power=None needs its note (Stillsong's
  mystery, the Spawning Stone's slaad lords). Deity stubs typed honestly (power / pantheon-group /
  abyssal-lord-quasi-power), `realm_of` + `located_in`(layer-or-plane) edges. 1 designed refusal
  (Blood Tor, header shredded → quarantine `realm-unattested`). Per-plane alignment/traits still
  deferred — page witnesses or nothing.
- **Seven-dim round (`parse/boxset.py` + `parse/monstrous.py`):** proxy 4 (named bindings only,
  powers minted) · sect 6 + settlement 11 (cards, attested) · saying 31 (pull-quote sweep, θ=0.6,
  prose/letter-space guards) · adventure 31 (SYNOPSIS cards w/ levels/factions) · **creature 16 +
  9 quarantined by name** (MC parser: three reflow formats + type-signature correction; the
  reusable engine for every MC book) · timeline +4 (Hellbound's phrase-witnessed Blood War
  chronology, `before` chain ⊂ event:the-blood-war).
- **Cross-book merge (2nd book = The Factol's Manifesto, 2611):** the Uncaged statblock/roster extractor
  finds NOTHING here (0 statblocks); its value is 15 hand-transcribed faction cards MERGED into the
  Uncaged faction nodes (dual-source provenance — philosophy/factol/HQ/allies/enemies), factols promoted
  to npc, HQs resolved against existing Sigil locations (`pour_manifesto`, `FACTION_DATA`).
- **Hooks are now MECHANICALLY TAGGED, not just hand-curated:** `hook 49` = 5 curated plot arcs
  (`grain:plot`) + **44 auto-tagged seeds** (`grain:seed`) from `parse/hooks.py` (TRIGGER×ANCHOR×PROXIMITY,
  4 flavors, confidence+θ=0.55, list-density cap, prose-vs-field regimes). The cross-book **pivots** are
  graph-walkable nodes with aliases — `trace_entity("The Lady of Pain")` shows Uncaged + Manifesto hooks
  in one neighbourhood; seeds nest `part_of` the curated arcs. (DIMENSIONS.md §7 + decisions ledger.)
- **All three cross-book pivots FOLD into home dims (deity · sigil · event poured):** **`deity:aoskar`**
  ⊃ subject:aoskar (the corpus's lone attested power; fills out w/ On Hallowed Ground); **`sigil:the-lady-of-pain`**
  ⊃ the Lady (sui-generis ruler — `location:sigil` is `ruled_by` her, `seats` 17 factions, holds 6 wards);
  **`event:the-blood-war`** ⊃ the Blood War. The plothook tagger re-anchored every hook on the new nodes
  automatically (`PIVOT_TYPES`). **Capstone: `event:the-great-upheaval`** (~630y ago — the Lady slew Aoskar,
  forbade worship, chartered the factions) ties three dims: deity:aoskar + sigil:the-lady-of-pain
  `participated_in`, `occurred_at` the Shattered Temple. The `subject` staging lane is now empty, open for
  the next book's MacGuffin.
- **NPC dialog is bound + register-tagged (the voice vector):** `dialog 100` = each character's spoken
  lines (`parse/dialog.py`) bound via `spoken_by`, with the **register read from the speech verb**
  (snarled→stern · chuckled→amused · whispered→grave — the `tools/voices/grace.toml` axis) so a line is
  render-ready. `trace_entity(npc)` walks an NPC's whole voice; the F5-TTS stack (`tools/`, out-of-band)
  consumes it. OCR column-bleed guarded; pathological-OCR entries go to review.
  against the column-reflowed page and poured with a page witness** (the `ORGS`/`PLOTS`/
  `ESTABLISHMENTS`/`XREF_SOURCES`/`FACTION_DATA`/`SUBJECTS` tables in `gate.py`) — "verified or absent,"
  never auto-parsed guesses. The name→node resolver (`_node_resolver`) maps the book's name variants to ids.
- **Witnessed schema-waiver** (`gate.py`): a curation may downgrade a named hard-check with a page
  witness — e.g. Patch the razorvine (a stationary plant lacks MR/morale; 8/13 fields is complete).
  Mirrors Mechanus's `lawful_waivers`. **Re-pour = `book.py` (extract) → `gate.py` (gate + pour).**

Live MCP read tools: `search_handbook`, `get_entity`, `trace_entity` (the soul tool —
an entity's whole edge neighbourhood), `query_graph`, `list_entities`, `coverage`,
`review_queue`.

- **`store.py` IS the shared schema-library** — Mechanus & Modron import it read-only
  (`HandbookStore(DEFAULT_DB, readonly=True)`); the lib is the schema, no MCP-over-MCP,
  no drift. Envelope `entity(type,id,name,edition,fields,content,provenance,confidence,
  curated,source_sha)` + generic `edge(rel,src,tgt,role,…)` + uniform FTS5 + `quarantine`
  + `dockets`. Open fields + generic edges ⇒ a new dimension never migrates the store.
- **The gate (`gate.py`) is the ONLY entity write path** (VALIDATION.md): `admit()` /
  `quarantine()` each REQUIRE a verdict docket — nothing enters undocumented. L1 schema
  (per-dimension; **type-aware floor** — class-based humanoids lack SA/MR, don't score
  them as monsters), L2 invariants (provenance/confidence/garbage; **id-collisions are
  surfaced as quarantine, never silently clobbered**), L3 independent: lawfulness is
  **delegated to Mechanus `is_lawful`** — WIRED as a library import, no MCP-over-MCP
  (VALIDATION §8); she owns the rules-math (hard→`conflict`, soft→recorded smell, every
  docket stamped `law_version`), Mimir keeps only coarse OCR-garbage bounds + damage-as-dice;
  plus held-out wiki (Modron dice-lawfulness · vision still pending). Auto-admit if
  hard checks pass AND conf ≥ θ(0.70); a human-vision adjudication overrides the θ floor.
  **Re-pour = `python pipeline/parse/book.py` (extract) → `python pipeline/mimir/gate.py`
  (gate + pour factions/locations/source).**
- **Curation survives every rebuild.** `curations.json` = vision/human rulings (dot-path
  `set` + adjudication provenance), re-applied at gate time → fix a berk once. Cirily's
  `level_hd 7+10` (OCR ate the `+`, a *dropped char*) is the canonical case — the only
  thing that needs vision is the genuinely irrecoverable; everything systematic is a rule.
- **`normalize.py` is the gear-house** (self-tested in `__main__` — run it):
  `normalize_dice_ocr` (Id4/ldV/ldlO→1d4/1d4/1d10, guarded by real-die-size),
  `dehyphenate`, `is_name` (prose-vs-name guard), `parse_descriptor` (positional 2e
  `PLANE/[sex]RACE/CLASS|HD/FACTION/ALIGN` — race from the 2nd slot, never the plane),
  `decode_title` (`fARRew`→Farrow by fuzzy-match vs the clean cross-ref name pool),
  `parse_location` (Sigil ward + site). **Strengthen a rule here with a self-test before
  reaching for a per-item curation;** tailored case-handlers live beside the general rule.
- **Multi-NPC entries** (`book.py`): an entry is a subject + a filtered retinue. Primary
  statblock = first **LAWFUL** block (non-decoy + dice parse) — not max-field (crowned
  companions) nor first (grabbed prose decoys). Name = clean statblock name > title-decode
  > cross-ref consensus. Companions are structured sub-records; **promoting them to
  first-class npc nodes (`companion_of` edges) is a queued session.**
- **Adding a dimension:** register the type + `extract_<type>()` + field schema +
  validators + edge-synthesis (DIMENSIONS.md recipe), then a `pour_<type>()` in `gate.py`
  (pattern: `pour_factions`/`pour_locations`). Envelope/FTS/graph/MCP-tools unchanged.
- **Edition = a view** (DIMENSIONS.md): identity nodes + per-edition aspects + `view()`
  (a Mechanus pure function); `srd` is a *license* axis, not a ruleset — keep it out of
  `edition`.

## Mechanus

Design `pipeline/mechanus/MECHANUS.md` · impl `pipeline/mechanus/mechanus/` · stores
`build/mechanus/` · V&V report `build/mechanus/vnv-report.md` (47/47 live probes).

- **Live tools:** `is_lawful` (the gate's L3 consistency channel — REVIEW-5E §A pack
  for 5e-2014/5e-2024 + 2e THAC0/HP brackets from an 80-pair FG&G harvest),
  `dc_suggest`, `encounter_budget` (2024 only, by license), `attribution`,
  `planar_law` (the §M planar-law pack — see below), and the
  rulings ledger (`record_ruling`/`overrule`/`precedents`/`house_rules`/`ruling_chain`).
  Invoke tools (`view`/`rule_search`/`delta`/`convert`/`resolve`/…) are **parked
  NOT_POURED** until Mimir's store lands — that error is intended.
- **Planar law poured (2026-06-06, MECHANUS.md §3a):** the rule-effect handoff §M
  accepted — 7 page-cited law families (199 ids) distilled from the three Planes
  boxes + In the Cage: per-plane magical conditions (all 16 Great Ring planes),
  spell/power keys, seals & wards, planar-priest frame, plane-environment law
  (wind-madness, the Wasting, hope-drain…), planar spells, Cage law. Ids reuse
  Mimir's plane slugs (`law:planar-conditions:the-abyss` ⟷ `plane:the-abyss`) for
  her `exhibits` edges; Modron deltas cite them as `{kind: mechanus, ref}` (the D2
  seam). Rows are PARAPHRASE — official scans stay cite-only, enforced by a
  shingle test against the witnessed reflow pages. M7 (Inner Planes survival)
  parked for the joint 2634 pour.
- **Law is data:** `mechanus/data/law/*.json`, every table page-cited, the set
  content-addressed as `law_version` (stamped into every docket and answer). Changing
  law data changes `law_version`; code changes don't.
- **Witnessed-waiver policy:** print-attested non-derivable values (lich Arcana +18
  et al., `known_deviations.json`) get waivers carrying a page witness; a waiver
  without a witness is ignored. Upstream transcription bugs (5e-bits halved-XP,
  dropped Skills rows) must STAY flagged — that's the check working, not a bug to fix.
- **Docket law** (enforced at write): exactly one ADOPTED candidate, `why` on every
  rejection, scope ∈ global|campaign:*|table:*, confidence ∈ [0,1], `rolls[]` cites
  Modron roll_ids (dockets cite dice, never contain them).
- **Adding a lawfulness check:** extend `_checks_5e`/`_checks_2e` in `lawful.py`,
  choose hard (blocks) vs soft (reports) honestly, add the corruption probe to
  `tests/test_lawful.py`, and re-run the fleet audit — if real SRD monsters start
  failing, adjudicate against the PDF print before assuming the check is right.
- **Next:** arbitrate ladder 0–2 (mechanical), then conversion engine v0 calibrated
  on SRD dual-edition pairs + the PAitM answer key (post-pour).

## Modron

Design `pipeline/modron/MODRON.md` · impl `pipeline/modron/modron/` · ledger
`build/modron/rolls.db` (env `MODRON_LEDGER` overrides) · V&V report
`pipeline/modron/VERIFICATION.md` (~54 live probes; 3 defects caught, fixed, pinned)
· family campaign `build/family/integration-tests.md` (G2/G7-half/G8–G12 closed).

- **Tool surface (17):** execute — `roll` (full notation: `kh/kl/dh/dl`, `!`/`!!`,
  `r`/`ro`, `min/max`, `cs/cf`, `d%`, `dF`, `adv/dis/ea/crit/repeat`), `roll_check`
  (semantic kinds per view: THAC0, roll-under, morale, reaction bands, death_save,
  recharge…), `roll_damage` (crit law per view), `roll_table`, `rollables`,
  `encounter_rolls`, `parse_expr`, `dice_stats` · ledger — `session_open/close`,
  `history`, `verify`, `force` · registry — `conventions`, `modifiers`,
  `define_modifier`, `usage_stats`.
- **Session ceremony:** `session_open` publishes `sha256(seed)` BEFORE any die falls
  (optional table-chosen `seed_phrase`); rolls draw from `(seed, counter)`;
  `session_close` SEALS — the seed stays **withheld**, revealed **on demand**
  (`reveal=true` at close or re-called later; §12 Q1 ruling 2026-06-05) → once
  revealed the whole night recomputes (`verify(session_id)` needs no reveal,
  or clean-room from `rolls.db` — derivation pinned as `engine_version 1` in
  MODRON.md §3; never change it without a version bump). Sessionless rolls carry an
  open ephemeral seed. `force` is the only override and is ledgered `method: fiat`
  with a required reason — a fiat row wearing a rolled costume is a bug, full stop.
- **Edition = data:** convention packs at `data/conventions/<view>.json` (`extends`
  chains, e.g. 5e-2024 → 5e-2014); house variants overlay at
  `data/overrides/<view>.json` and are ALWAYS disclosed in `conventions()` output.
  New edition or house crit range = JSON drop-in, no code. New check kind = a pack
  `checks` entry (templates use `roll`, params, `add`/`sub`, `success_op`,
  `vs`/`vs_template`, `derived`, `bands`). **Setting = a view too (handoff §D,
  2026-06-06):** `2e-planescape` extends `2e` with plane-scoped kinds
  (limbo_casting/alteration/miniflux, wind_madness, styx_memory,
  wasting_contraction) — base packs stay edition-pure, overlays stay house-only.
- **Rollables registry** (`data/rollables/*.json` + `modron/registry.py`, the
  rule-effect handoff's §D lane): page-cited tables / roll specs / diceless
  lookups / encounter specs from the corpus (34 Planescape entries — Slags
  vortex, Hive ooze portals, Inner-Planes hazard dice, Acheron landing,
  Harmonium patrol). Source-required at load (unsourced = refused), tables
  coverage-validated, official scans cite-only (paraphrase + page witness),
  OCR-doubt flagged `requires_confirmation`. Served via `roll_table` (table
  ids) and `rollables` (id or `used_at` discovery — a resolving Mimir entity
  wins the name; registry matches ride along). Mimir mints `used_at` pointers
  at these ids; D2-style numeric deltas ride `data/modifiers/planescape-2e.json`
  with `source {kind: mechanus, ref: <law-id> (pending mint; witness page)}`.
- **Modifiers:** registry at `data/modifiers/core-{5e,2e}.json` + local overlay via
  `define_modifier` (effects validated; bad ops refused). Inline mods REQUIRE a
  `source {kind: core|mimir|mechanus|table|fiat, ref}` — unsourced is refused, the
  ledger records every asserter. Composition order (V&V catch D1, 5e RAW): per-die
  attachments → **adds → wraps last** (resistance/vulnerability apply after all other
  modifiers, so brutal-crit/sneak dice halve/double too). Stacking: `named` collapses
  (skips listed), `untyped` stacks.
- **Rollables compiler** (`modron/rollables.py`): resolves refs **handbook-first**
  (Mimir's store lib loaded via importlib — admitted+cured data by id or exact
  name; raw `build/` JSON only as a flagged-UNCURED last resort) and unwraps
  Mimir envelopes (`fields` nesting). 2e statblocks (THAC0, damage strings incl.
  ` or ` modes + `x4` multipliers, MR%, morale `champion (16)`, monster HD
  `12+24`→`12d8+24`, **class HD** `F9`→`9d10`+Con-allowance — class-leveled
  cutters never roll d8s), 5e action text (`+7 to hit`, `Hit: 14 (2d8+5)`, DC
  saves, `Recharge 5-6`), range inversion (`3-18`→`3d6`, alternatives surfaced),
  OCR-lenient prose sweep (`Id6`→`1d6`, flagged `requires_confirmation`),
  implausible-HD tripwire (>40 ⇒ suspect — the `7+10`→`740` OCR-fusion class).
  Printed-average/HP-range crosschecks emit `lawfulness_flags` — a MISMATCH is a
  transcription smell (the gate's free L3 witness), not something to silently
  correct; HP-not-derivable yields a visible info spec, never silence. Tables
  validate coverage before rolling (gaps/overlaps reported; `00`=100 on percentile).
- **Boundary:** Modron judges NO law — it executes specs and records asserters.
  Values (DCs, save targets, AC) are inputs from caller/Mimir/Mechanus; Mechanus
  dockets cite Modron `roll_id`s (her §1a contract — met, see MODRON.md §9).
- **Wire lesson (V&V D2):** MCP transport may deliver inline JSON objects as
  *strings*; the store seam (`store.find_entity`/`find_table`) json-loads
  `{`-prefixed strings. Keep that door when extending entity refs.
- **Adding notation/effects:** new postfix or function → `grammar.py` registry +
  evaluator arm + a round-trip test; new effect primitive → one entry in
  `modifiers._EFFECT_OPS` + an AST transform + a composition test. Run the suite
  from `pipeline/modron/` (171 tests); smoke through the *configured* py.exe spawn.

## Table loop (.claude/ — shared infra, any session may fix)

**Skills are direction, rules are requirements, templates are formats.**
- `/encounter-plan` (design → artifact) and `/encounter-run` (committed-session
  play) at `.claude/skills/`; the `encounter-director` agent (`.claude/agents/`)
  designs and dry-runs but **never** calls `force`/`record_ruling` — fiat and
  dockets are the DM's voice in the main conversation.
- Binding law: `.claude/rules/encounters.md` (R1 artifact · R2 one-view ·
  R3 provenance · R4 license · R5 dice · R6 law-lane · R7 validation gate ·
  R8 aftermath). Formats: `.claude/templates/encounter{,-run}.md` +
  `entity-card.md`, the concatenable dramatis unit — encounters assemble by
  card concatenation (MODRON §12 Q5 ruling).
- Artifacts: `build/encounters/<slug>/encounter.md` + `runs/<session_id>.md`.
  `READY` requires the R7 gate (spec passes `plan_only`, every rollables flag
  adjudicated, checklist green). Lineage: cross-validation.md §4 candidate #5.
- `/uncage` — reconstitute + verify the rig on a fresh machine (hand-off to
  another DM who owns the books). Drives `pipeline/uncage.py` against
  `pipeline/uncage-manifest.json` (pinned end-state fingerprints: id sets,
  edge digests, law_version, source shas). The wiki witness corpus ships
  in-repo (CC-BY-SA) so gate confidence reconstitutes deterministically.
  **Curator duty: `pin` + commit the manifest after every pour** — a manifest
  that lags its stores is an oath sworn to a dead state.

## Windows gotchas (these cost redos — check before shelling out)

- Bare `python` in spawn configs → WindowsApps Store stub → silent death (see MCP
  registration above).
- Native `jq.exe` emits CRLF — `tr -d '\r'` anything feeding APIs.
- `/tmp` doesn't resolve for native exes under this Git Bash — use project paths
  (`content/_meta/tmp/`).
- Always `encoding="utf-8"` in Python file IO. PDF text extraction yields ligatures
  (`ﬁ`) and `\t\r \xa0` whitespace soup — normalize before matching; four "missing"
  SRD statblocks were present all along behind this.
- A running stdio read-server with an open SQLite connection **locks the DB file** on
  Windows: the gate's re-pour (`db.unlink()`) then dies with `WinError 32` (file in use).
  Release it with a `/mcp` reconnect before re-pouring. Read servers must open-once /
  close-once per call so they hold no handle between calls (Mimir V&V D3) — a per-call
  connection that's never closed leaks handles AND blocks every future re-pour.
