# Mimir V&V Campaign — 2026-06-05 (live wire + source-of-truth)

Comprehensive verification & validation of Mimir — the knowledge spine: the store
(`store.py`), the blocking gate (`gate.py`), the read server (`server.py`), and the
extraction gear-house that feeds them (`pipeline/parse/`). Run against the **live MCP
transport**, the **live `handbook.db`**, and the **source PDF** (`content/official/
Uncaged_ Faces of Sigil (2e)`) — not a mock.

**Verification** asks *did we build it right* (the code honors its contracts).
**Validation** asks *did we build the right thing* (the poured Handbook is true to the
page, and the gate genuinely catches corruption). Both were exercised.

**Three real defects found, fixed, and pinned by regression tests** — the campaign doing
its job. A follow-on pass then **wired the gate's L3 lawfulness channel to Mechanus**
(§P7) and re-poured the live store. Pinned suite: **30 passed** (`pipeline/mimir/tests/` —
`test_store.py` · `test_gate.py` · `test_extract.py`). Gear-house self-tests: **7/7
descriptor · 7/7 title-decode · 5/5 location**. Source fidelity: **29/29 NPC statblocks
attested in the PDF, 0 not-found.**

Run the suite from `pipeline/mimir/`: `py -3.13 -m pytest tests/ -q`.

---

## Verdict table

| # | Check | Expected | Observed | Verdict |
|---|---|---|---|---|
| **P0 — store contract (`store.py`)** |||||
| 0.1 | readonly write-guard | `admit`/`quarantine`/`add_edge` all raise | `PermissionError` on all three | PASS |
| 0.2 | `admit` envelope guard | missing `type`/`id` → `ValueError` | both raise | PASS |
| 0.3 | **edge dedup, role=NULL** | identical NULL-role edge collapses | pre-fix **2 rows**; post-fix **1 row** | **FAIL → FIXED → PASS** (D1) |
| 0.4 | edge role significance | distinct roles stay distinct edges | PRIMARY dedups, DERIVED kept (2 rows) | PASS |
| 0.5 | `admission_sha` idempotence | deterministic + content-sensitive | re-gate reproduces; field change invalidates | PASS |
| 0.6 | curation preservation | prior `curated` carried unless overridden | carried `{fields.x:1}`; explicit `2` overrides | PASS |
| 0.7 | FTS resync on re-admit | stale content not matched after update | `arcanaloth`→∅ after re-admit; `deva` hits | PASS |
| 0.8 | quarantine isolation | held entity never enters `entities` | absent from entities; counted in quarantine | PASS |
| 0.9 | `require_resolve` | refuse edge to unadmitted endpoint | ghost endpoint → `False`; real → `True` | PASS |
| **P1 — the gate is a real judge (`gate.py`)** |||||
| 1.1 | lawful monster | ADMIT + member_of/references edges + docket | admitted, both edges synthesized, docket `auto` | PASS |
| 1.2 | L1 monster below floor | <10/13 fields → schema-fail | 5/13 → QUARANTINE schema-fail | PASS |
| 1.3 | L1 humanoid floor | char_class → floor 7, admits at 7/13 | 7-field humanoid ADMITs | PASS |
| 1.4 | L1 name-fragment | `AC 5; MV 12` name → schema-fail | QUARANTINE schema-fail | PASS |
| 1.5 | L2 missing confidence | `confidence=None` → invariant-fail | QUARANTINE invariant-fail | PASS |
| 1.6 | L2 provenance backstop | empty provenance → hard fail | check fires `fail` (envelope guarantees upstream) | PASS |
| 1.7 | L3 AC out of range | AC 99 → conflict | QUARANTINE conflict | PASS |
| 1.8 | L3 THAC0 out of range | THAC0 50 → conflict | QUARANTINE conflict | PASS |
| 1.9 | L3 hp ∉ HD range | HD 2 / hp 500 → conflict | QUARANTINE conflict | PASS |
| 1.10 | L3 hp check skipped for humanoids | class HP not d8-bounded → no false fail | ADMIT (check correctly inert) | PASS |
| 1.11 | L3 damage not dice | `by weapon type` → conflict | QUARANTINE conflict | PASS |
| 1.12 | θ floor | conf 0.69 → low-confidence | QUARANTINE low-confidence | PASS |
| 1.13 | θ at floor | conf 0.70 → ADMIT | ADMIT | PASS |
| 1.14 | curation overrides θ | conf 0.40 + curated → ADMIT, adjudicator human-vision | ADMIT, docket `human-vision`, override recorded | PASS |
| 1.15 | id-collision | second same-id held, never clobbers | `[ADMIT, id-collision]`, first survives | PASS |
| **P2 — determinism (re-pour)** |||||
| 2.1 | two independent pours | identical counts + per-entity `admission_sha` | counts identical; **29/29 npc shas identical** | PASS |
| 2.2 | fresh pour vs live DB | shas reproduce the shipped Handbook | **29/29 match live `handbook.db`** | PASS |
| **P3 — graph integrity (live DB)** |||||
| 3.1 | dangling edges | all explainable, none to admitted nodes | 49 danglers, **all `references`**, 0 unexpected, 0 dangling sources | PASS |
| 3.2 | closed relations resolve | member_of/located_in/part_of/attested_in both-ends | 12/31/9/29 edges, **all resolve** | PASS |
| 3.3 | attestation completeness | every npc → `source:uncaged` | 29/29 | PASS |
| 3.4 | faction membership | every member_of target a real faction | 11/11 | PASS |
| 3.5 | orphans | no admitted node islanded | **0 orphans** | PASS |
| 3.6 | dangler analysis | danglers are out-of-book cutters, not broken links | 20 out-of-book + 1 companion + **1 slug-dup**; 0 resolvable-to-admitted | PASS (1 finding) |
| **P4 — live MCP wire (`server.py`, real stdio)** |||||
| 4.1 | `coverage` | matches direct DB | 52 entities (29/11/11/1), 229 edges, 0 quarantined — exact | PASS |
| 4.2 | `search_handbook("arcanaloth")` | FTS ranks true arcanaloths first | A'kin, Shemeshka first; 6 hits | PASS |
| 4.3 | `get_entity("A'kin")` | full node by name | complete statblock + provenance `uncaged:p9` | PASS |
| 4.4 | `trace_entity(Shemeshka)` | full edge neighbourhood | 11 outbound / 6 inbound, grouped by rel | PASS |
| 4.5 | `query_graph(lady-s-ward, located_in, in)` | the ward's residents | Autochon, Black Marian, Tarholt, Zadara | PASS |
| 4.6 | `list_entities(faction)` | enumerate dimension | 11 factions, all conf 1.0 | PASS |
| 4.7 | `review_queue` | quarantine state | empty — nothing held | PASS |
| **P5 — source fidelity (vs the Uncaged PDF)** |||||
| 5.1 | A'kin spot-check | DB ≡ page | `AC -8; hp 92; THAC0 7; MR 60%` exact | PASS |
| 5.2 | Cirily + curation | hp lawful under curated HD 7+10 | `AC -3; hp 44; THAC0 13`; hp 44 ∈ [17,66] — `740`→`7+10` validated | PASS |
| 5.3 | **bulk triple attestation** | every DB `(AC,hp,THAC0)` present verbatim in source | **27/29 full triples + 2 AC/hp; 0 NOT-FOUND** | PASS |
| 5.4 | THAC0 gaps (Zadara, Seamus) | source omission OR extraction miss? | **extraction miss** — `THACO S`→5, `THACO IS`→15 OCR-dropped | **FAIL → FIXED → PASS** (D2) |
| **P6 — gear-house (`normalize.py`)** |||||
| 6.1 | descriptor parser | positional, race from 2nd slot | 7/7 machine | PASS |
| 6.2 | garbled-title decoder | fuzzy-match to clean pool | 7/7 machine | PASS |
| 6.3 | Sigil location parser | ward + site | 5/5 machine | PASS |
| **P7 — the Mechanus seam (L3 lawfulness delegated, 2026-06-05)** |||||
| 7.1 | import as library | `mechanus.lawful.is_lawful`, no MCP-over-MCP | imported + guarded fallback | PASS |
| 7.2 | coercion contract | withhold HD (statblock+descriptor) for class humanoids & non-bracket HD | Tarholt (76 hp/9 HD) & The Us (`1 each`) skip HD checks; 10 clean-HD monsters genuinely run them | PASS |
| 7.2a | sibling-contract drift | her mid-session descriptor-HD fix caught by the suite | `test_l3_hp_check_skipped_for_humanoids` flipped red → coercion strips both → green | **CAUGHT → FIXED** |
| 7.3 | all 29 stay lawful | 0 hard fails through the coerced seam | 0 hard; 2 soft (`thac0_vs_hd`: Tripicus, Zadara — author-intent) | PASS |
| 7.4 | hard fail → conflict | impossible monster hp quarantines via `law:hp_in_hd_range` | QUARANTINE conflict, Mechanus-sourced | PASS |
| 7.5 | docket stamping | every NPC docket carries `law_version` | 29/29 stamped (`018b2eed…`); A'kin shows 5 `law:*` passes | PASS |
| 7.6 | graceful degradation | Mechanus absent → local fallback, no crash | monkeypatched None → local hp check still gates | PASS |
| 7.7 | live re-pour | seam + D1 schema + D2 data land together | 29/29 admit, 0 quarantine, served live via MCP | PASS |

---

## Defects found & fixed (each pinned by a regression test)

| id | defect | root cause | fix | pinned by |
|---|---|---|---|---|
| **D1** | identical NULL-role edges duplicate; `add_edge`'s `INSERT OR IGNORE` silently fails to dedup | SQL treats every `NULL` as DISTINCT, and `role` is NULL for the majority of edges (references/located_in/attested_in/part_of); the table-level `UNIQUE(...role)` never fires for them | replaced the constraint with an expression unique index `coalesce(role,'')` so NULL and '' fold to one key (`store.py`) | `test_edge_dedup_null_role` |
| **D2** | THAC0 OCR'd as letter-lookalikes drops to None; the value is recoverable but lost (Zadara `THACO S`=5, Seamus `THACO IS`=15) | the THAC0 capture demanded a literal `\d+`; the numeric-OCR gear (`norm_num`, which already maps S→5, IS→15) was never applied to the field | capture the lookalike token, repair via `norm_num`, range-guard to lawful 2e THAC0 1..20 (`regions.parse_statblock`) | `test_thac0_letter_lookalikes_repaired` |
| **D3** | the read server leaks a SQLite connection per call (`_store()` never closed) → on Windows the open handle keeps `handbook.db` locked and **blocks the gate's re-pour** (`WinError 32`, reproduced live) | each tool handler opened its own store and never closed it | open once per call in the dispatcher, close in `finally`; handlers take the store as a parameter (`server.py`) | manifested live (re-pour `unlink` PermissionError reproduced); fixed by-construction — handlers hold no store of their own |

> **D1 latent, not yet manifest:** the live DB had **0 duplicate edges** at audit time
> (the cast's see_also lists happen not to repeat a target). The fix matters for what's
> next — companion-promotion and a second book *will* synthesize colliding edges. Fixed
> before it bit.
>
> **D2/D3 landed in code + extraction; live DB re-pour pending one `/mcp` reconnect.**
> `book.py` re-extraction now writes Zadara THAC0 5 / Seamus THAC0 15 into the node JSONs,
> and a full re-gate into a temp DB confirms both ADMIT with L3 `thac0_range` **pass**
> (29/29, 0 quarantine, D1 index present). The *live* `handbook.db` can't be re-poured
> until the running (pre-fix) server releases its handle — a `/mcp` reconnect respawns it
> with the D3 fix, after which `py -3.13 pipeline/mimir/gate.py` absorbs both improvements.
> Until then the live DB serves the prior-validated data (correct except those two THAC0s).

---

## Boundaries observed (documented behavior, not defects)

- **L3 lawfulness is now Mechanus's (RESOLVED, §P7).** `gate.py` delegates the derivable
  rules-math to `mechanus.lawful.is_lawful` (imported as a library, guarded), keeping only
  coarse OCR-garbage bounds + damage-as-dice as Mimir's own. Severity is now hers: hard fails
  → `conflict`, soft fails → recorded smells. The lawfulness law lives in her page-cited
  tables, stamped into every docket as `law_version`. See `VALIDATION.md §8` for the seam
  record and the coercion contract. *Remaining sibling seam: Modron dice-lawfulness as an
  additional L3 channel (damage-string → rollable validation) — not yet wired.*
- **`held_out_wiki` is a substring membership test** (soft, non-blocking). A short name
  ("Fell") can match prose ("fell") and spuriously "confirm." It never blocks admission;
  it only adds a soft confirmation. Tighten to a tokenized/anchored match when it earns it.
- **Cross-ref slug variants** (`dj-hek-nlarr`==`djhek-nlarr`, `grixitt`/`the-grixitt`):
  see_also targets are slugged from raw page text and not normalized against an alias pool,
  so a cutter spelled two ways yields two dangling ids. Harmless today (both dangle), but
  the **companion/cross-book promotion session** should run a reference-resolution pass.
- **Companions are not first-class nodes yet** (deferred, by ruling). ~20 of the 49
  danglers are genuine out-of-book cutters (Rule-of-Three, Kylie, Patch…); the rest are
  retinue members awaiting promotion. P3.6 confirmed **none** resolve to an already-admitted
  entity — the deferral hides no broken links.
- **identity / `aspect_of` / `view()`** (DIMENSIONS §identity) are designed but unpoured —
  a single-edition (2e) corpus has no cross-edition cluster to synthesize yet (two 2e books now,
  but no 2e↔5e pair). `edition` is a real field; the view machinery is Mechanus's and waits.

---

## Plothook + subject dimensions — cross-book V&V (2026-06-05, 2nd build · 2nd book)

The 2nd book (The Factol's Manifesto, 2611) merged into the Uncaged graph, and `hook` grew a
**mechanically-tagged** `grain:seed` tier (`parse/hooks.py`) beside the hand-curated arcs. The assay
(`tools/hook_probe.py`) drove the design adversarially — each failure mode it surfaced is now a guard
with a regression test:

| failure mode (the assay caught it) | guard | pinned by |
|---|---|---|
| list-density fan-out ("Zadara schemes around [12 names]" = a relationship LIST already in `PLOT_EDGES`) | drop a trigger sentence resolving >3 distinct anchors | `test_hooks::test_list_density…` |
| struct-field re-tag (Manifesto `Enemies:` = already `opposed_to` edges) | `STRUCT_LINE` routes card fields out; field-books restricted to `subject` anchors | `test_gate::test_manifesto_restricted…` |
| alias double-count (Aoskar + "god of portals" → two hits) | collapse to one per entity id | `test_hooks::test_prose_goal_hook…` |
| polysemy (rival-as-compare, reward-as-adjective) | ×0.5 penalty + lexicon guards | `test_hooks::test_ambiguous_trigger…` |
| setting-scale anchor (Sigil/the Cage match everything) | specificity ×0.4 → below θ | `test_hooks::test_setting_scale_anchor…` |
| oblique cross-book reference ("god of portals", no name) | `subject` nodes carry pivot-specific aliases | `test_hooks::test_oblique_alias_resolves…` |

**Cross-book bridge proven on the live wire:** `trace_entity("The Lady of Pain")` returns ONE
`subject` neighbourhood holding both books — `opposes` ← Shemeshka (Uncaged) **and** Sign-of-One
(Manifesto); `hires` ← Djhek'nlarr (Uncaged); `seeks` ← Fated (Manifesto — the Darkwood coup). The
subject node *is* the bridge; no special cross-book edge exists. **Central finding:** the tagging
method must match the book's shape — prose-embedded (Uncaged → 41 seeds, exact NPC subjects) vs
field-structured (Manifesto → 3 seeds, subject-anchored only, because the faction geography is already
poured as fields+edges). 48 tests green (34 prior + 9 `test_hooks` + 5 `test_gate`); the marquee plots
(Aoskar resurrection, Darkwood coup, Blood War double-dealing) trace end-to-end.

---

## In the Cage + Places dimensions — 3rd book V&V (2026-06-06)

The 3rd book (In the Cage, 2609 — grade-C scan, the hostile display face) poured the city's
geography: 51 establishments (21 dual-source merges, 30 new incl. 8 minor pubs), **27 witnessed
portals**, and the first **Places** nodes (plane 24 · gate-town 5 · layer 4 · pathway 2 ·
cosmology 2 · realm 1 — attested-only from the curated gazetteer). The assay (`tools/cage_probe.py`)
drove it adversarially; each failure mode is a guard with a regression test (`tests/test_cage.py`, 18 probes):

| failure mode (the probe caught it) | guard | pinned by |
|---|---|---|
| smallcaps carnage (T→`+`, O→`©/0/9/e`, M→`ITI/III/ffl/m`, LL→`tt`, &→`8t`) | heading-only OCR decoder + fuzzy roster match | `test_decode_smallcaps_carnage` |
| heads lost to the scan (10 of 61) | named `EXPECTED_ABSENT` table → quarantine `cage-head-lost`, never a guess | `test_expected_absent_is_quarantined…` |
| lost entry lets neighbors absorb its pages | UNFOUND rows still emit page-end fallback boundaries | `test_fallback_boundary_caps…` |
| duplicate head fragments (Bones of the Night ×2) | near-tie earliest-position wins | (probe; covered by segment coverage) |
| catchall pubs inside the Wayfarer's span | `segment_minors` + `trim_entries` — the minor owns its text | (probe; minors all found) |
| "not to the gate-towns of the Outlands" pours a fake portal | clause-scoped negation guard | `test_negation_guard_holds_the_wayfarer` |
| one sentence, two portals ("…appear in the Golden Bariaur, and the Ditch…") | clause-paired nearest-src binding | `test_clause_pairing_binds_nearest_src` |
| layer AND its plane in one clause (Amun-Thys in… Arborea) | layer-suppresses-parent dedup | `test_layer_suppresses_parent…` |
| reflow scrambles a paragraph into the next entry (Jeremo's Ysgard door → Prison) | `PORTAL_CURATIONS` witnessed re-bind | `test_portal_curation_rebinds_the_jester` |
| watermark variants ("Ryan Berry (Order #…)") leak into witnesses | generalized furniture pattern | `test_watermark_variants_are_furniture` |
| index-page adjacency mints portals ("Tea Street Transit → Abyss p127") | the Index never sweeps | (pour law) |
| gazetteer overreach | a Places node ships ONLY with page witnesses — bytopia + 11 gate-towns stay absent | `test_places_are_attested_only` |

**Live-wire verify:** `coverage` reads 19 dims / 553 admitted / 84 quarantined / 1,327 edges;
portal nodes trace with both edges (`opens_from` + `connects_to`); the cured Jester portal exists and
the Prison phantom does not. Marquee finds the sweep surfaced by itself: the nic'Epona's three
gem-portals (one sentence, three bindings), the Bottle & Jug arch-cluster (×5 inner-planes doors),
the Hive's wandering Limbo shack, the one-way ooze puddles. **77 tests green.**

### Round 2 (same day): review adjudication + the Planes boxes

**Portal review queue → EMPTY by adjudication** (`PORTAL_ADJUDICATIONS`, applied at pour): 6
promoted — the human override of θ (the Gymnasium's turquoise arch at 0.50), a comma-list rescue
(the Mortuary nexus), and four **city-level class-portals** (`opens_from` location:sigil,
`fields.src_class` disclosed: butcher shops/public baths/foundries/hidden air-supply) — and 5
rejected with recorded whys under `portal-rejected` (illustrative shifting-pattern examples ×3, a
crime-category hypothetical, the defunct rumor-grade Baator arch). 33 portals stand.

**Planes boxes (Law 2607 / Chaos 2603 / Conflict 2615):** curated `PLANE_CARDS` text-validated by
`attest_card` against each box's own reflow — **56/56 layer claims attested, 0 refused**; 16 planes
enriched dual/triple-source; +7 gate-towns (12/16 stand; Fortitude/Ecstasy/Curst/Glorium honestly
absent — their witness is the unpoured Player's Primer). Spelling law followed the print: **Cania**
(not Caina), Olympus/Ossa/**Pelion** (Greek names), **"the Plain of Infinite Portals"** (Pazunia is
post-2e and never appears). Identity merge pinned: Pelion ⊃ `layer:amun-thys` — renamed, aliased,
SAME id, so the Ditch portal still connects. Live wire: `plane:baator` carries 9 `layer_of` inbound
+ Ribcage `gate_to` + the Ditch portal `connects_to` — Sigil → door → plane → layer in one walk.
Realms + alignments deferred (ledger): the "realm of X" sweep yields OCR fragments. **87 tests green;
store 624 entities / 1,490 edges.**

### Round 3 (same day): the realms round

The deferral resolved properly: the Law/Conflict books carry literal **`POWER.` stat lines** (the
mechanical anchor the prose sweep lacked) and the Chaos Travelogue heads each realm with its display
name. `REALM_CARDS` (48, curated from those sections) pour under the **double-witness law**: realm
name AND power name must both attest in the component, or the card declares power=None with a note.
Results: **47 realms + 45 deity stubs poured; 1 designed refusal** (Blood Tor — its name survives
only as the shredded header `BL OOIJ ToR`; quarantined `realm-unattested` for v1b). Names follow
the text, not canon memory: **Cavern of Azuth** (the box's prose, twice), **The Slime Pits**
(Shedaklah OCR-shredded → alias). Deity `kind` typed honestly: power / pantheon-group (the Titans,
the Vanir) / abyssal lord (quasi-power) for Graz'zt, Demogorgon, Zuggtmoy, Kostchtchie, Pazrael.
Live wire: `deity:odin` ← `realm_of` ← Asgard; `layer:ysgard` hosts its seven realms (Asgard,
Alfheim, Himinborg, Jotunheim, Gates of the Moon, Merratet, Vanaheim) exactly as the Travelogue
maps them. **92 tests green; store 716 entities / 1,674 edges.**

### Round 4 (same day): the seven-dim round — the registry completes

proxy 4 (named `proxy of` bindings only — 25 unnamed mentions correctly refused; the Sphinx
serves Ra AND Osiris, both minted) · sect 6 + settlement 11 (curated cards, text-attested —
Zoronor `located_in` layer:ocanthus) · saying 31 ≥θ / 11 queued (attribution-dash blocks; the
prose-attribution and letter-spaced-soup guards each pinned; Factol Hashkar's "LAWS CAN BE
LEARNED" surfaced) · adventure 31 (SYNOPSIS-carded with levels/PCs/factions fields) ·
**creature 16 clean + 9 quarantined BY NAME** (`mc-parse`) — the MC parser survived three reflow
formats (inline labels, label/value alternation with WRAPPED labels, split-column run-zip) plus
a type-signature correction pass; two parser traps caught and pinned: the wrap-join eating
`'High (13-14)' + 'TREASURE:'`, and label fragments leaking into names · timeline 4
(phrase-witnessed Blood War chronology: the baernaloths stagger forth → yugoloths spawned →
the Disappearance → the Ships of Chaos; `before` chain + `part_of` the Blood War).
**102 tests green; store 824 entities / 1,820 edges / 26 dimensions; quarantine 89 across six
honest buckets.** The registry: 26 poured · 4 handoff-pending (rule/planar-trait/table/hazard)
· 4 book-pending (spell/race/class/psionic — PWH) · 8 proposed-closed. The mass spot-check
workflow has its target.

---

## What was proven, in one breath

The store enforces its laws structurally — gate-only writes, a content-address that
reproduces a verdict and invalidates on change, curation that survives rebuild, FTS that
stays in sync, and (now) edge dedup that actually dedups. The gate is a real judge: a
lawful block sails through, and every doctored field — short statblock, fragment name,
missing confidence, impossible AC/THAC0/hp, non-dice damage, sub-θ confidence — lands in
the correct quarantine bucket, while a human-vision adjudication is the one thing that
overrides the θ floor. The graph closes (every closed relation resolves, zero orphans) and
its danglers are honestly out-of-book, not broken links. Over the live MCP wire all seven
tools answer, and `coverage` matches the disk to the row. And against the source PDF, **27
of 29 statblock triples are attested verbatim and the other two were not source omissions
but an OCR miss the campaign caught and repaired** — the gate proves *consistency*; only the
page proves *truth*, and the Handbook agrees with the page. Mimir remembers what is, and
can show its work.

---

## Round 5 — the Great Audit apply pass (2026-06-06)

**Scope:** Meme adopted the Great Audit correction docket wholesale ("Misbinds are
expected - Implement the correction docket; good audit") — 314 confirmed findings +
35 quarantine-court promotes, applied as data/lane edits + ONE re-pour, per
`build/mimir/review/PLAN.md` Phase 3.

**The audit itself (Phases 0-2, docket-first):** all 824 entities page-witness
reviewed across 47 chunks (3 workflows, incl. a server-load-shed salvage with
wave-throttled retry); every finding adversarially verified (2 refuters, refute-first;
24 refuted findings preserved); 89 quarantined items judged by a six-bucket court;
`handbook.db` sha byte-identical until sign-off (`db-sha-prework.txt`). Tools now
permanent: `tools/integrity.py` (mechanical checker), `tools/review_chunks.py`
(work-list dumper), `tools/assemble_docket.py`.

**What the apply pass changed (verified post-pour):**
- **Witnessed entry recoveries** — `cage.ENTRY_CURATIONS` (14 anchor-resolved spans;
  anchors, never line numbers; a failed anchor re-queues the entry). All 10
  `cage-head-lost` names POUR (location 90 → 97); Speckled Rat minted as a minor and
  merged into its Uncaged node; `EXPECTED_ABSENT` queue drains to ZERO.
- **The misbind family died at the root** — re-split scopes re-anchor the hook tagger:
  `black-sails` no longer `seeks` Aoskar (Bones of the Night does); the Prison no
  longer wears the Palace of the Jester's kriegstanz; the DM-mechanics seeds (vortex
  d4, mount impairments) either reject by `HOOK_ADJUDICATIONS` (stable keys
  book×object×flavor×page — seed ids renumber) or ceased to exist when the side-table
  left the scope.
- **Portals**: the Ditch over-mint rejected (4 plane-dest dups of one "respectively"
  clause), `ditch--plague-mort` minted via the p49 spelling alias, the Great Ring
  locative dup rejected, two off-by-page witnesses corrected → **29 stand**.
- **Creatures**: `monstrous.CREATURE_CURATIONS` (22 entries keyed book×page×RAW name —
  renames re-slug ids): Kytedn→Kyton, Sj.Asrath→Slasrath, Bj.Ade J.I Ng→Bladeling…;
  6 court recoveries ADMIT (16 → 22; 3 confirm-rejects stay queued); Conflict
  creatures' `attested_in` re-bound to their own box (MC_BOOK, not _box_source).
- **Dialog**: 28 misattributed lines (anonymous narrators, the mimir's voice, column
  splices) quarantined `dialog-rejected` by `DIALOG_ADJUDICATIONS`; 1 rebind; 14
  court promotes admitted via the new vision-over-θ consult in `pour_dialog`
  (content-addressed ids; the apply pass caught + pinned an owner-clobber defect in
  the first rebind implementation — D-R5-1).
- **Cards**: 18 fixes — Goldfire (not the Glass Tarn) and Windwrath (not CenterSpire)
  renamed per witnesses; Noctos' Domain REMOVED (the moon is a layer epithet);
  Blood Tor attests via whitespace-tolerant `_name_rx` (48 realm cards → 47 cards
  poured 47/47, 0 refused); Unseelie Court fixed to Phlegethon; Vorkehan is the
  Mercykillers'; Bleak Cabal home = Pandemonium; the Other Place ad is Harys
  Hatchis's; `gate_town` fields now verified-or-absent (6 backfills stand).
- **Items**: 7 extraction-debris drops + 4 de-fusion renames (`ITEM_CURATIONS`,
  extraction-time so ids re-slug clean); Saure's and Shemeshka's SPECIAL EQUIPMENT
  sections restored verbatim from their pages (110 → 106 items, all real).
- **curations.json**: 3 → 130 entries, every one stamped with its docket adjudication;
  the `_admit_seed` hook now applies curations across EVERY dimension (universal
  lane-3 rail, pinned by 2 gate tests).

**End state:** 814 entities · 1,817 edges · 91 quarantined in six HONEST buckets
(dialog-rejected 28 · hook-rejected 5 · low-confidence-dialog 16 · low-confidence-hook
29 · mc-parse 3 · portal-rejected 10 — every row carries its adjudicated why).
Suite **104 green** · parse self-tests green · `integrity.py` **0 hard** (38 softs =
documented danglers + name-style reports) · re-dumped chunks cover 814/814 with 0 page
misses · cant harvest re-attested (85 terms, 0 unknown compounds) · live MCP traces
walk the corrected graph (Bones of the Night's re-anchored hooks; Windwrath →
Shurrock → Tefnut). Post-apply sha: `db-sha-postapply.txt`.

**Defects caught during apply (fixed + pinned):**
- **D-R5-1** `pour_dialog` rebind clobbered the node's `oid`, drifting the
  content-addressed ids of every later utterance in that entry (2 court promotes
  missed; 2 lines mis-bound to Ylem). Fixed with a per-utterance `owner_id`;
  14/14 promotes verified admitted.
- **D-R5-2** `pour_cage` merge path crashed on a curated hint whose target wasn't
  poured (test fixtures); merge now requires the node to EXIST, else fresh-mint.
- **D-R5-3** `_box_source` lacked the MC components and defaulted Conflict creatures
  to `source:planes-of-law` — sources now derive from `MC_BOOK`.

### Round 5 addendum — Modron's cross-audit wounds (same day)

Modron's own audit (build/modron/review/correction-docket.md, the G-* gaps) handed
back 18 field wounds in Mimir's lane. Every locator PAGE-VERIFIED here before
writing; three resolved by TRUE VISION reads against the page scans
(`pages/page-NNNN.jpg`, the Cirily precedent):

- **Qaida** `ML elite (14)` — the reflow's `Q4JJ` was the OCR-eaten parenthetical;
  the page image reads it plainly.
- **Ylem** `M5` (mage 5) — the print carries a SPELLS line the reflow shredded
  (1st: alarm/color spray/feather fall/phantasmal force; 2nd: blindness/web;
  3rd: haste); spells through 3rd + THAC0 19 + hp 18 ∈ 5d4 settle Modron's
  "genuinely ambiguous" slot.
- **archon-lantern** `hit_dice 1` — the column-zip ate the lantern's HD cell (stored
  6 was the hound's); its surviving THAC0 20 IS the 2e 1-HD bracket.

Reflow-witnessed cures: morale for Kylie `champion (15)` / Sly Nye `steady (12)` /
Adamok `elite (13)`; the 2e fractional attack rates restored (Autochon `5/2`,
Djhek'nlarr `3/2`, Tarholt `3/2`, Jemorille `2 (beams) or 1`, Adamok `2 or 1`);
Gabberslug `1d4/1d4/2d4`; **Alluvius's printed `HD 9d4+23` poured verbatim**
(witnessed-waiver class — Modron can now compile the book's own dice); descriptor
slots recovered (Omott `linqua/HD 2`, Grixitt `T1`, Setus `B1`, Sister Cade `C1`,
Tcha `F11`, Brot `F1` — the l↔1 class-code family). Koe was already cured by the
bulk pass. curations.json → 147; 58/58 npc admit (24 disclosed vision
adjudications); 18/18 post-pour value checks pass; suite 104; integrity 0 hard.

**Queued for the next EXTRACTION round (rules beat curations for systematics, but
re-extraction churns the npc JSONs and is its own validation session):**
normalize/book.py arms for (a) class-code l→1 (`^[BCDFMPRTW]l+$`, guarded off
`Wil`/`Ill`), (b) C-for-( descriptor paren (Koe/Omott/Ly'kritch class), (c) morale
tail forms (`Ml `→`ML `, `M.L`→`ML`, `C12)`→`(12)`), (d) `#AT n/2` fractional-rate
capture. Modron's docket carries the per-case witnesses.
