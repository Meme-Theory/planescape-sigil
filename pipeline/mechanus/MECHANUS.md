# Mechanus — the Rules Engine MCP (design v1 · core SHIPPED 2026-06-05)

> **Build status:** mechanical core + rulings ledger + MCP server v0 live at
> `pipeline/mechanus/` (stores at `build/mechanus/`, Modron's convention).
> 121 tests + 20-check stdio smoke, all green. Law data page-cited, content-
> addressed (`law_version 0d05d408b20e7314` — changes whenever law data does).
> Store-backed tools parked NOT_POURED until Mimir's handbook.db lands (§9
> steps 1–4). **2026-06-06: the §M planar-law pack landed** (§3a — the
> rule-effect handoff accepted; 199 law ids across 7 families, served live by
> `planar_law`).

> Mechanus is the plane of absolute law: one infinite clockwork, every gear meshed.
> This MCP *invokes* rules (find the governing law, apply it, show the math),
> *arbitrates* them (conflicts get a ruling with a docket, never a shrug), and
> *manifests* them — the same object viewed through any edition's lens.
>
> **The marquee use case (Meme, verbatim):** *"invoke items from the AD&D modules,
> for direct use at a 5E table."* A 2e Uncaged NPC, a Planes of Chaos beast, a
> module's magic sword — asked for in 5e-2024 shape, served with provenance and a
> conversion docket.
>
> Design law (inherited from the lens): **Mimir is the only knowledge store; the gate
> is the only entity write path; every answer carries provenance.** Mechanus adds one
> store of its own — the rulings ledger — and zero entity stores.

Status: design doc, supersedes `RULES-MCP.md` (v0, single-edition framing).
Sister docs: `DIMENSIONS.md` (what entities are), `VALIDATION.md` (how they're admitted),
`ARCHITECTURE.md` (the Mimir↔Mechanus boundary — reconciled; its §"What this changes"
binds this doc too), `REVIEW-5E.md` (5E corpus census — its §A validator pack and §F.2
planar influences are Mechanus jobs). The PlanescaperHandbook MCP is **Mimir**; this is
its sibling. A third sibling — **Modron**, the dice roller — is in design (§1a).

---

## 1. The two skulls — Mimir & Mechanus, and the linkage that matters

| | **Mimir** (content) | **Mechanus** (law) |
|---|---|---|
| owns | `handbook.db` + the admission gate + quarantine + curation | `rulings.db` (rulings, conversion dockets) + the mechanical core |
| surface | curatorial: `propose / validate / adjudicate / coverage / review_queue` | play-time: `view / resolve / arbitrate / convert / delta` + gate-facing `is_lawful` (dice → Modron, §1a) |
| writes | entities & edges, only through the gate | rulings & dockets, only through guarded `record_*` (the `emit_verdict` discipline: syntax-forced, locked, SHA-unique) |
| reads | sources, wikis, scans | `handbook.db` **read-only**, via the shared store lib (no raw SQL coupling) |

**The linkage contract (the part Meme flagged as key):**

1. **One-way read.** Mechanus opens Mimir's store read-only through a shared
   `handbook_store` library both servers import. No MCP-over-MCP hops on the hot path;
   no schema drift, because the lib is the schema.
2. **Propose-back loop.** Mechanus never writes an entity. When it *derives* a new
   manifestation (a 2e item rendered 5e-shaped), it **proposes** it through Mimir's gate
   like any extractor would — `provenance.method = "conversion"`, the conversion docket
   attached as the arbitration record. Checks pass → **auto-ADMIT** (`adjudicator:
   auto` — Meme's ruling, §10: nothing here is sensitive; sticky curation + `supersedes`
   chains make a bad admit cheap to find and fix). Checks fail → quarantine like
   anything else. The gate stays sovereign — what changed is that *passing* no longer
   waits for a human.
3. **Free-witness reciprocity.** Each skull is the other's L3 witness, disjoint brains
   by construction:
   - **Mechanus → Mimir:** the mechanical core *is* VALIDATION.md's "internal
     consistency" channel, mechanized — statblock arithmetic per edition (THAC0 ↔ HD,
     XP ↔ HD/abilities in 2e; CR ↔ AC/HP/DPR bands, save DC ↔ stat+prof in 5e).
     Mechanus's math never saw the extractor's sources, so it's independent.
   - **Mimir → Mechanus:** gate-admitted entities that hold native manifestations in
     *two* editions are Mechanus's **answer key** — calibration pairs for the conversion
     engine (§5). Mimir's FTS/trace also grounds every citation Mechanus emits.
4. **Provenance flows through.** Every Mechanus answer cites Mimir entity IDs (which
   carry their own provenance); every conversion docket names the conversion-rule
   entities that fired, by ID. Pull any answer's thread and you reach a page and a sha.

## 1a. Modron — the third sibling (dice; design in flight, his doc governs his lane)

The most lawful beings in the multiverse, made custodians of its randomness — the joke
is load-bearing: **lawful randomness is auditable randomness.** Rolling moves out of
Mechanus entirely; Mechanus is a *client*. What the law side requires of Modron —
requirements, not design; his internals are his:

1. **Citable roll IDs.** Any ruling or conversion docket that involved randomness
   references the roll by a stable ID in Modron's ledger — the docket discipline
   (§5, §6) extends to dice or it's theater.
2. **Replayable audit.** A docket replay must be able to re-verify its rolls (seed,
   content-address, ledger lookup — his choice; old §11 Q3 is his inheritance).
3. **Raw vs composed** — does Modron expose advantage/disadvantage/rerolls natively,
   or serve raw dice that Mechanus composes under law? His call; Mechanus adapts.
   Either way *interpretation* stays here: Modron says "17", Mechanus says what a 17
   means against AC 19.

---

## 2. Identity & the edition view (the data model)

Meme's requirement: objects aren't merely *tagged* by edition — **edition is a view
over the same data.** The model that delivers this without touching the envelope:

- **Identity** — the edition-less thing: *the vrock*, *Fireball*, *initiative*,
  *A'kin*. A thin first-class node: `{type, identity_id, name, aliases[]}`.
  Synthesized from `same_as` clusters (DIMENSIONS.md edge catalog — already there);
  materialized as **real, gate-admitted rows in handbook.db** (decided, §10) — Mimir
  owns identity like any entity, and cross-edition curation has a durable home.
- **Manifestation** — what DIMENSIONS.md already defines: an edition-tagged entity
  with the standard envelope, gate-admitted, provenance-bearing. **No envelope change.**
  Each links to its identity via an `aspect_of` edge (new rel string = data, not schema).
- **View** — a *pure function*, never a mutation:
  `view(identity, edition, conversion_law_version) → manifestation`. Same inputs, same
  output; derived results are content-addressed (`sha(source manifestations + rules
  version)`) exactly like the gate's `admission_sha`. Deterministic by construction.

```
identity:creature:vrock
 ├─ aspect @ 2e        ← Planes of Chaos MC (scan, user-purchased, local)
 ├─ aspect @ 5e-2014   ← SRD 5.1 (CC-BY-4.0)
 └─ aspect @ 5e-2024   ← SRD 5.2.1 (CC-BY-4.0)        ← a free calibration row, too

identity:npc:akin
 └─ aspect @ 2e        ← Uncaged p.10 (gate-admitted already)
      → view(akin, 5e-2014) has no native aspect → conversion ladder (§5)
```

**View resolution ladder:**
```
view(X, E):
  1. NATIVE     — an admitted manifestation in E exists → serve it
  2. ADMITTED   — a previously derived manifestation passed the gate → serve (docket attached)
  3. DERIVED    — run the conversion engine live → serve flagged DERIVED + confidence
                  + docket; propose to Mimir's gate in the background (auto-admits on
                  pass, §10 → promotes to ADMITTED for every later invoke)
  4. SCAFFOLD   — not enough to convert → serve the nearest native aspect + the mapping
                  skeleton: which fields translate, which are gaps, what a human must rule
```
A derived answer is **never** dressed as a native one. The flag, the confidence, and
the docket ride along or the answer doesn't ship.

**The unifying trick:** *rules are entities too* (dim:rule), so the law itself is
identity-clustered — `identity:rule:initiative` has 2e, 5e-2014, 5e-2024 aspects.
`delta(topic)` is just a diff of two manifestations of one identity. Cross-edition
rule questions, statblock conversion, and the 2e→5e uplift all run on the same three
primitives: identity, aspect, view.

---

## 3. Editions & law libraries (what RAW *is*, per edition)

Edition registry (extends DIMENSIONS.md §edition; open set, new editions = data):

| edition | RAW law library | structured witness | posture |
|---|---|---|---|
| `5e-2024` | SRD 5.2.1 PDF (364pp, born-digital, sha `8974902d…`) | 5e-bits `src/2024` (v5.9.0) | CC-BY-4.0; attribution emitted with every quote |
| `5e-2014` | SRD 5.1 PDF + extracted markdown | 5e-bits `src/2014` (complete, incl. Spells/Rules/Levels) | CC-BY-4.0 |
| `2e` | **For Gold & Glory** (retroclone = the freely-licensed 2e RAW text — decided, §10) | our v2 region-model extractions of the scans | FG&G free; official scans user-purchased, local-only |
| `1e` *(later)* | OSRIC | — | free retroclone |
| `3e/3.5e (d20)` *(maybe)* | d20 SRD 3.5 | — | OGL; PSCS 3.0/3.5 already in `content/fan` |
| `4e` *(maybe)* | — none; GSL never allowed SRD-style text | PSCS 4e draft (fan) | user-purchased/fan local-only; weakest case |

Known structured-witness gaps that shape the build: 5e-bits `2024/` still lacks
**Spells, Rules, Rule-Sections, Levels** (verified against `2014/`) → for those, the
5.2.1 PDF is the only machine source (single-witness + vision channel until upstream
lands them; `merge_curated` keeps our fixes when it does). 2024-only sets (`Species`,
`Subspecies`, `Weapon-Mastery-Properties`, `Poisons`) confirm DIMENSIONS.md checklist
items B & E from the source's own ontology.

Licensing nuance worth pinning: SRD 5.2.1 p.202 carries XP Budget / Encounter
Difficulty (verified in the PDF) → 2024 encounter math is CC-clean. SRD 5.1 never had
encounter-building → 2014 budgets are PAitM-local or an honest refusal naming why.

## 3a. Planar law — the rule-effect handoff §M, accepted (2026-06-06)

Mimir's handoff (`build/family/rule-effect-handoff.md`) offered the boxes'
remaining *rule substance* to this lane: **Mimir keeps who/what/where, Mechanus
keeps what governs, Modron applies the values.** Accepted and poured as seven
law-table families at `mechanus/data/law/` — every row a **page-cited
PARAPHRASE** of the user-purchased scans (cite-only lane; enforced in code by
`tests/test_planar_law.py::test_no_verbatim_leak` — no 10-token run of any rule
may appear verbatim in its witnessed reflow page; 25 drafts were caught and
reworded by that test before landing). Witnesses are
`{component, reflow[, printed]}` — the filename-addressable pages under
`build/<book>/<component>/reflow/`.

| family (id prefix) | file | rows | substance |
|---|---|---|---|
| `law:planar-conditions` | `planar_conditions.json` | 109 | **M1** — per-plane magical conditions for all 16 Great Ring planes (school-by-school prose law + 3 box-general rows; school grain addressable as `…:<plane>:<school>`) |
| `law:planar-keys` | `planar_keys.json` | 48 | **M2** — spell-key and power-key law per plane (`…:<plane>:spell` / `:power`) |
| `law:seals-wards` | `planar_seals_wards.json` | 5 | **M3** — portal-blocking doctrine (Sigil portal law, planar wards, surelock, gate ward/seal) |
| `law:planar-priest` | `planar_priest.json` | 3 | **M4** — the priest frame: off-home-plane penalty, power-key restoration, attested sphere grants |
| `law:plane-environment` | `planar_environment.json` | 18 | **M5** — environment law with teeth (Celestia purity ladder, Pandemonium wind-madness, the Waste's hope-drain + wasting sickness, Gehenna falls, Elysium undead-burn, Limbo miniflux, the Styx…) |
| `law:planar-spell` | `planar_spells.json` | 12 | **M6** — planar spell mechanics (cubehopper, shield of the archons, Lysander's pair, the archon crowns, gate ward/seal, value); doubles as CONVERSION.md 2e-side corpus |
| `law:cage` | `cage_law.json` | 4 | **M8** — Sigil's teeth: plane-shift ban, Harmonium patrols, execution law, garnish rates |

**M7 (Inner Planes survival law) is accepted-but-PARKED** — the handoff itself
marks it a joint future pour (2634 isn't entity-poured); id family
`law:inner-survival:<topic>` is reserved, no file ships until the pour.

- **Id scheme (handoff Q1, answered):** `law:<family-tail>:<plane-or-topic>
  [:<school|spell|power|rule>]`. Plane slugs are **Mimir's own** (`limbo`,
  `the-abyss`, `the-gray-waste`…), so `plane:<slug> —exhibits→
  law:planar-conditions:<slug>` is a suffix-match join; Sigil rides as `sigil`.
  Both grains are mintable: plane rows for coarse edges, school/rule sub-ids
  for fine ones.
- **Serving:** new live tool `planar_law` (by `law_id`, by `plane`, by
  `family`; no args = index) — every answer stamped with `law_version` + the
  cite-only license line. Off-corpus planes (Outlands, Inner) refuse honestly
  and name the M7 parking.
- **The D2 seam (handoff Q3, confirmed from this side):** Modron modifier/check
  rows cite these ids as `source {kind: "mechanus", ref: "<law_id>"}`;
  `planar_law(law_id)` is the resolver that makes such a ref verifiable. Dice
  deltas, check kinds, and rollable tables stay HIS (handoff §D) — rows here
  are deliberately prose-law, not roll specs, and several point at their D-lane
  counterparts by number (D1, D5, D6, D9).
- OCR honesty: rows whose witness text is ambiguous carry an `ocr_note`
  (Arcadia's illusion −2, bladestorm's 1d8/level, crown of radiance's eaten
  radius, the scrambled TABLE II cell matrix) — verify against the print
  before a high-stakes ruling, per the witnessed-waiver spirit.

---

## 4. PAitM — the answer key

`build/planescape-adventures-in-the-multiverse/` (~138k words, 2.6k typed refs,
user-purchased, local-only) is the **calibration corpus**: WotC's own 2e→5e
conversions of *exactly our setting*. Every identity with both a 2e aspect (from the
box scans) and a PAitM 5e aspect is a scored test row for the conversion engine —
dabus, factions-as-backgrounds, planar effects, the Sigil cast. Plus the SRD-only
pairs (vrock, balor, marilith…) that are CC-clean end-to-end.

Calibration loop: run the conversion ladder on the 2e aspect *as if the 5e didn't
exist* → diff against the official 5e aspect → score per field class (AC/HP/CR/saves/
traits/actions) → tune the conversion law → re-run. The engine's accuracy number is
*measured against WotC's own choices*, not self-graded. (VALIDATION.md's honesty
principle, applied to conversion.)

---

## 5. The conversion engine (conversion law is data, not code)

- **Conversion rules are entities** — `dim:rule, category=conversion`, each with
  provenance (the free WotC *Conversions to 5th Edition D&D* guide is a legitimate
  encodable source; community CR-estimation heuristics enter *flagged* as such),
  versioned as a set (`conversion_law_version` — part of every view's content address).
- **The 2e→5e ladder (first target):** descending AC → ascending; THAC0 → attack
  bonus; HD → HP dice + CR band estimate (calibrated, §4); 5-category saves → 6-ability
  saves; MR % → Magic Resistance trait; morale → drop (recorded as a *deliberate* drop,
  not a silent one); SA/SD prose → traits/actions (model-assisted, always docketed);
  XP → recomputed from final CR, never carried.
- **Every derivation emits a docket** (sibling of the ruling docket): rules fired (by
  ID), field-by-field mapping, candidates rejected + why (loser preservation), unmapped
  residue, confidence. The docket *is* the arbitration record the gate sees on
  propose-back — and under the auto-admit ruling (§10) it is the *entire* defense file,
  so it must be complete: a conversion without a full docket doesn't propose.
- **Drops and gaps are first-class.** What 2e had that 5e can't hold (morale, weapon
  speed) and what 5e wants that 2e never said (proficiency, senses ranges) are listed
  in the docket — the DM sees the seams, because the seams are where rulings live.
- **Prior art surveyed 2026-06-05** — `build/mechanus/conversion-prior-art.md`. The
  official 2015 guide (poured: `content/official/_free/DnD_Conversions_1.0.pdf`,
  personal-use license → cite-only) carries ONE formula block (p.4: AC = 19−old, cap
  22 · attack = HD/2+2, cap +12 · save DC = 8+HD/2, cap 20); its careful path leans
  on DMG ch.9 stat-by-CR tables that are in NO SRD → 5e-side targets are re-derived
  by regression over the SRD fleets instead (Blog of Holding fits as cross-check).
  Community schemas conflict on basics (19− vs 20−; recalculate vs translate vs
  O5R-preserve) → conversion-law rows carry `candidates[]` with cites and one ADOPTED
  value; `convert` exposes **profiles** (`quick-official` | `restate` |
  `o5r-preserve`). Nobody ships machine-readable conversion law — the lane is open.
  CMT doctrine adopted: map to an existing 5e equivalent BEFORE synthesizing a block.
  Free calibration pairs identified: FG&G bestiary ↔ SRD 5.1 same-name monsters.
- **Fusion design 2026-06-05 → `CONVERSION.md`** (sibling doc, this directory — the
  full spec; this section stays the summary). Three rungs over ONE action-by-action
  pipeline: `card` (O5R view-shim, SCAFFOLD rung, zero materialization) →
  `quick-official` (p.4 floor formulas, confidence-capped) → `restate` (default:
  stages 0–7, gist field-walk, calibrated, gate-proposable). Conversion law lives at
  `data/law/convert/*.json` (16 tables, candidates[]-with-adopted, source-cited,
  content-addressed as `conversion_law_version`). Fit on FG&G↔SRD pairs; test on
  PAitM held-out. Derived blocks get NO waivers — internally lawful or honestly
  `unconvertible`.

---

## 6. The arbitration ladder (rules questions, per edition)

`arbitrate(question, context, view)` runs top-down, returns a ruling docket:

```
0. table house-rule        (rulings.db, scope-matched — curated law, wins outright)
1. RAW, the view's library (verbatim quote + section/page cite + attribution)
2. errata / supersedes     (within-edition corrections we legitimately hold)
3. cross-edition clarifier (another aspect of the same rule-identity disambiguates —
                            ADVISORY, never silently substituted)
4. interpretation          (RAI built from adjacent rules; labeled; adjacents cited)
```

- **RAW/RAI separation is typographic law** — the quote renders apart from the
  reasoning, always.
- **Precedent is sticky like curation**: dockets survive rebuilds, are scoped
  (`campaign` | `table` | `global`), and `precedents(topic)` replays them. Overruling
  writes a new docket that `supersedes` the old — chain preserved, like everything else
  in this project.
- Sage Advice & friends: **not ingested** (not freely licensed). The ladder's step 3
  does much of that work from sources we actually hold.

```jsonc
// ruling docket (rulings.db)
{
  "ruling_id": "rul:tofw:grapple-while-invisible:001",
  "question": "Does Invisible impose disadv. on the grapple escape check?",
  "view": "5e-2014", "scope": "campaign:tofw",
  "ladder_path": ["house:none", "raw:srd5.1:grappled+invisible", "interp"],
  "raw_quotes": [ {"text": "…", "loc": "SRD5.1 §Appendix PH-A", "sha": "…"} ],
  "candidates": [ {"position": "yes — attack-roll-only reading", "fate": "rejected", "why": "escape is a check, not an attack"},
                  {"position": "no — checks unaffected", "fate": "ADOPTED"} ],
  "confidence": 0.9, "adjudicator": "auto",        // auto | human:Meme
  "supersedes": null, "sha": "…", "ts": "<stamped post-run>"
}
```

---

## 7. Tool surface (sketch — `view=` is the universal lens parameter)

**Invoke (read, fast):**
| tool | does |
|---|---|
| `view(identity_or_name, view)` | THE tool — resolve any identity to its manifestation in an edition, via the §2 ladder. `statblock`, `spell`, `item`, `condition` are typed conveniences over it |
| `rule_search(query, view?)` | FTS over the view's law library → ranked hits + cites |
| `rule_quote(rule_id)` | verbatim RAW + provenance + CC-BY attribution line |
| `resolve(action, context, view)` | governing rules → ordered procedure, each step cited; marks exactly where DM discretion enters |
| `delta(identity, from_view, to_view)` | diff two aspects of one identity (rule, spell, creature — same machinery) |
| `apply_influence(creature, plane, view)` | applies a Mimir-stored `planar-influence` template (REVIEW-5E §F.2) → influenced variant; a template-view on the same primitives — dockets and proposes back like any derivation |
| `dc_suggest(difficulty?, view)` / `encounter_budget(party[], difficulty, view)` | mechanical core; budget math per §3 licensing reality |
| `planar_law(law_id? \| plane? \| family?)` | the §3a planar-law pack — per-plane conditions/keys/seals/priest/environment/spell/Cage rows, page-cited paraphrase, law_version-stamped; the resolver behind Mimir `exhibits` edges and Modron `{kind: mechanus, ref}` sources |
| `is_lawful(entity)` | **gate-facing** (ARCHITECTURE.md §3): the REVIEW-5E §A derivable pack per edition — `PB == ceil(CR/4)+1`, mods, passive Perception, HP-from-dice, skill = mod+PB… Mimir's L3 consistency channel, served from one place |
| *dice* | **Modron's** (§1a) — Mechanus consumes roll IDs, never rolls |
| `precedents(topic, scope?)` / `house_rules(scope?)` | ledger reads |
| `ruling_chain(ruling_id)` | a ruling's full `supersedes` chain, oldest first, plus the head docket — ledger read |
| `law_info()` | `law_version` (content-address of every law table) + per-table source citations + known deviations |
| `usage_stats()` | tool-call counts for this server |
| `attribution()` | the CC-BY-4.0 block any published artifact must carry |

**Arbitrate & convert (the slow path):**
| tool | does |
|---|---|
| `arbitrate(question, context, view)` | §6 ladder → docket; does **not** write — **not yet served** (§9 step 8 'next': neither live nor parked on the server) |
| `convert(entity_id, to_view)` | §5 engine explicitly → full docket + derived manifestation; queues the gate propose-back |
| `record_ruling(docket)` / `overrule(ruling_id, new_docket)` | the only ledger writes — guarded, locked, SHA-unique (scope is a docket field) |
| `answer_key(type?)` | calibration pairs + current conversion accuracy by field class (the engine grades itself in public) |

Server skeleton mirrors `knowledge-mcp/server.py` (list_tools/call_tool dispatch,
usage counter, lock discipline on the one writable store).

---

## 8. What Mechanus refuses to be

- **Not a character manager.** No sheets, no HP tracking — state belongs to the
  table/VTT layer. Mechanus answers law.
- **Not a homebrew generator.** It cites, converts, and arbitrates existing law;
  generation is the backends' job (they may consult it).
- **Not a counterfeiter.** A derived manifestation never ships without its DERIVED
  flag, confidence, and docket. No edition-blending without a delta flag. No native
  costume on converted goods.
- **Not silently helpful.** No answer without citation; no math from sources we don't
  hold rights to.

---

## 9. Build order (each step shippable)

1. **Pour the 5E law** — load 5e-bits JSON (both rulesets) → gate proposals; 5.2.1
   page-anchored text extraction (born-digital, embedded layer is grade-A — reuse the
   `<!-- pg -->` anchor format, no OCR pass) wired as the L3 held-out witness.
2. **2024 gap fill** — Spells + Rules glossary extracted from the 5.2.1 PDF directly
   (the sets 5e-bits lacks); single-witness + vision channel.
3. **Pour the 2e law** — For Gold & Glory through the pipeline → `edition=2e` rule/
   spell/creature manifestations. (The scans' module entities are already Mimir's lane.)
4. **Identity clustering** — synthesize identity nodes from `same_as` across the
   poured editions; name-match first pass, human adjudication through Mimir's existing
   review loop. Unlocks `view()` NATIVE + `delta()`.
5. **Mechanical core** — ✅ **SHIPPED** (`pipeline/mechanus/mechanus/`): the REVIEW-5E
   §A pack (`is_lawful` — PB/CR/XP, mods, passive Perception, HP-from-dice,
   save/skill=mod+PB, condition/sense enums), 2e THAC0-vs-HD (FG&G brackets,
   80-pair empirical harvest) + HP-in-HD-range, DC ladder, 2024 budgets. Law data
   page-cited JSON, content-addressed. **Fleet-audited against all 334 SRD 5.1
   monsters:** 326 lawful; 3 print-attested deviations (lich/night-hag/priest →
   witnessed waivers, `known_deviations.json`); 5 upstream 5e-bits bugs caught
   (dropped Skills rows, mis-keyed passives); 4 halved-XP rows soft-flagged.
   Dice are Modron's lane (§1a) — not in this core.
6. **Server v0** — ✅ **SHIPPED** (mechanical + ledger surface): is_lawful,
   dc_suggest, encounter_budget, attribution (verbatim legal-page blocks),
   record_ruling/overrule/precedents/house_rules/ruling_chain, law_info.
   Invoke tools (view/search/quote/delta/resolve/convert/apply_influence/
   answer_key) are listed but parked — honest NOT_POURED until steps 1–4.
7. **Conversion engine v0** — encode the WotC conversion guide as conversion-rule
   entities; calibrate on SRD vrock-class pairs + PAitM answer key; ship `convert` +
   DERIVED-tier `view` + gate propose-back.
8. **Rulings ledger + arbitrate** — ledger ✅ **SHIPPED** (`build/mechanus/rulings.db`:
   schema-forced dockets — exactly one ADOPTED candidate, why on every rejection,
   rolls cite Modron roll_ids; lockfile + content-address SHA dedup; supersedes
   chains; FTS precedents). `arbitrate` ladder 0–2 then 3–4: **next**.
9. **d20 / 4e** *(maybe, later)* — new edition registry rows + law libraries; the
   identity/aspect/view model needs zero changes (that's the point of it).

---

## 10. Decisions (rulings to date — this doc keeps its own ledger)

| date | question | ruling | rationale / consequence |
|---|---|---|---|
| 2026-06-05 | name | **Mechanus**; the Handbook MCP is **Mimir** | the two skulls, §1 |
| 2026-06-05 | edition scope | multi-edition from day one: 5E + AD&D; d20/4e maybe later | edition = a *view* over the same data, §2 |
| 2026-06-05 | derived-admission policy | **auto-ADMIT on gate-pass** — no human review gate on conversions | Meme: "it's not like we have sensitive data; we can fix and readdress." Gate checks (L1/L2/consistency) still run; failures still quarantine; docket mandatory (§5) so any admit is auditable; `supersedes` chains make fixes cheap. Human review is *available* (review sweeps, overrule), just not *blocking*. |
| 2026-06-05 | identity materialization | **real, gate-admitted rows** in handbook.db, owned by Mimir | cross-edition curation gets a durable home, §2 |
| 2026-06-05 | FG&G as 2e RAW | **yes** — the retroclone is the quotable 2e law library | the licensing posture that makes a publishable Mechanus possible, §3 |
| 2026-06-05 | dice ownership | **Modron** — third sibling MCP, design in flight | Mechanus is a client: dockets cite Modron roll IDs; requirements (not design) in §1a. Implementation ("cooking") starts once Modron's design lands. |
| 2026-06-05 | Modron's §9 deltas | **accepted in full** | `roll` left this surface; §11 Q3 resolved both-and (his §3); `resolve()` emits Modron-ready roll specs; ledger `rolls[]` validates roll_id strings. His v1 satisfied every §1a requirement. |
| 2026-06-05 | impl home | `pipeline/mechanus/` + mutable stores at `build/mechanus/` | Modron's doc-home/impl-home convention (his §11), adopted |
| 2026-06-05 | print-deviation policy | **witnessed waivers** | fleet audit vs all 334 SRD 5.1 monsters: non-derivable but print-attested values (lich Arcana +18 p.325, night-hag skills p.319, priest Religion +4 p.401) get curated waivers — RAW is authoritative even when the math isn't. A waiver without a page witness is ignored ("a blindfold"). Upstream transcription bugs stay flagged — that's the check working. |
| 2026-06-05 | conversion prior art | surveyed; **profiles model adopted** (`quick-official` / `restate` / `o5r-preserve`), 5e-side stat-by-CR targets re-derived from the SRD fleet, map-to-existing-first (CMT doctrine) | `build/mechanus/conversion-prior-art.md`. Official 2015 PDF poured to `content/official/_free/` (sha `fe1212b80eafbe38…`, personal-use-only → cite-only). DMG ch.9 stat-by-CR tables absent from every SRD — same refusal family as 2014 budgets; regression over our audited fleet replaces them. Free calibration pairs: FG&G bestiary ↔ SRD 5.1 same-name monsters. |
| 2026-06-06 | rule-effect handoff §M (M1–M8) | **accepted; poured as §3a** — 7 law families, 199 ids, `planar_law` live; **M7 parked** (joint pour with 2634's entity pour, id family reserved) | Mimir's lane ruling honored: identity/pointers stay hers, governing law lands here, dice deltas stay Modron's (§D). Q1 answered: id scheme reuses Mimir's plane slugs so `exhibits` edges suffix-join; school/key sub-ids give fine grain. `law_version` moved `018b2eed42e9afe7` → `a15604342754bf34`. |
| 2026-06-06 | cite-only enforcement for official-scan law | **paraphrase law is now machine-checked** — `test_no_verbatim_leak` shingles every row (10 tokens, normalized) against its own witnessed reflow pages | "licensing enforced in code, not vibes" extended to authored law tables; 25 draft rows were caught and reworded before landing. Mechanical facts (names, dice, numbers) survive normalization as short runs; prose copying cannot. |
| 2026-06-06 | the D2 modifier seam (handoff Q3) | **confirmed, Mechanus side** — Modron rows cite `source {kind: mechanus, ref: <law_id>}`; `planar_law(law_id)` resolves any such ref | the asserter chain is verifiable end-to-end: a school-alteration delta in Modron names the M1 row it implements; her acceptance of D1–D9 belongs in MODRON.md (her doc, her lane). |
| 2026-06-06 | the Mechanus Assize (workflow audit) + correction docket APPLIED | **349 units + 1 bonus audited** (every law row witness-verified against its pages; code-as-law vs RAW; 6 dockets; seams; docs) — 47 findings, 38 confirmed/9 refuted, all refute-verified by full live panels. Lanes A–D applied 2026-06-06: `law_version` moved `a15604342754bf34` → `0d05d408b20e7314` (thac0 plus-bump rule text now matches FG&G p.309 next-DIE law; fit disclosure completed ~84%; Stygia year-loss tooth; Arcadia second intent-failure; surelock de-ranked; Well of Worlds = TSR 2604; witness corrections ×7; ledger.py kind-before-sha + pinned test = 121). Meme ratified keep-3 for the 17+ bracket (Table 3.3 L18→3; C.3 ceiling + specimens disclosed in `_source.note_17plus`). Lane E (11 sibling re-binds) handed off at `build/family/mechanus-audit-lane-e.md` — never applied cross-lane. | `build/mechanus/review/` holds the full record: correction-docket.{md,json}, run-summary.md (350-row coverage), integrity-report.json, PLAN.md. Audit law adopted: known-intentional.json (the don't-flag list) + tools/integrity.py as the standing post-pour gate. Old rulings keep their historical stamps — the stamp is the point. |
| 2026-06-05 | conversion fusion design | **`CONVERSION.md` adopted** (Meme: official guide as guiding stone; build from the gist + O5R heavy lifting; "we aren't tied to anything being exact") | Three rungs over one action-by-action pipeline (card / quick-official / restate); 16 convert/ law tables, candidates[]-with-adopted, `conversion_law_version` axis; fit-on-FG&G-pairs / test-on-PAitM; derived blocks get no waivers; THAC0 never translated (verified at intake, rebuilt from PB+ability). Sources poured: gist + O5R → `content/fan/web-supplements/conversion-guides/` (SOURCES.md provenance). Build order in CONVERSION.md §5; un-parks `convert` at step 7. |

## 11. Open questions (for Meme)

1. **`resolve` scope guard**: stop at procedure + citations (DM stays the judge), or
   fully adjudicate outcomes given complete game state? (v0 lean: procedure only.)
2. **Ruling scope model**: is `campaign` granularity enough, or per-table/per-group
   namespaces in `rulings.db` from day one?
3. ~~Dice seed policy~~ → **migrated to Modron** (§1a.2): seed/replay strategy is his
   design; Mechanus only requires citable, replayable roll IDs.

None of these block build-order steps 1–5 (§9) — they're server-v0-stage choices.
