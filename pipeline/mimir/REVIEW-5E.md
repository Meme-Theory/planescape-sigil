# 5E Review — PAitM corpus vs the Dimension Registry

Sister-session answer to `DIMENSIONS.md` §"5E cross-check checklist". Every claim below
is grounded in the ingested 5e corpus, citable via provenance anchors of the form
`paitm/<book>/<page>#<Anchor>` (these are literal `<!-- src:… -->` comments in
`build/planescape-adventures-in-the-multiverse/*/book.md`).

**Corpus reviewed:** all 13 PAitM pages (≈138k words; sato/mpp/tofw), 55 statblocks
(54 mpp + Morte in tofw), 48 hand-saved tooltip pages (`_compendium-captures/`),
2,568 typed entity refs (`entities.json` per component), 10 DM/player map pairs.

---

## A. 5e statblock sub-schema — CONFIRMED. Field census from 54 mpp statblocks:

| field | observed | note |
|---|---|---|
| Armor Class / Hit Points / Speed | 54/54 | AC *ascending*; speed lists modes incl. `(hover)` |
| ability table STR..CHA | 54/54 | score + mod, e.g. `19 (+4)` |
| Senses / Languages / Challenge | 54/54 | **Challenge line carries XP *and* Proficiency Bonus inline**: `Challenge 9 (5,000 XP) Proficiency Bonus +4` — parse both from one line |
| Skills | 48 | |
| Saving Throws | 42 | |
| Damage Resistances / Immunities / Vulnerabilities | 23 / 15 / 1 | vulnerability attested (Morte: Bludgeoning — `monsters/3883553-morte` capture) |
| Condition Immunities | 22 | 2014 closed condition set |
| section headers | Actions 54 · Bonus Actions 20 · Reactions 14 · Lair Actions 3 · **Legendary Actions 0** | Lair without Legendary exists (Planar Incarnate, time dragons) — don't make validators require the pair |
| Habitat / Treasure | **0** | those are 2024/MM'25 conventions — their absence is edition evidence (→ §E) |

Extractor cue: in the D&D Beyond sources HTML these section headers are
`p.monster--action-header` (NOT headings); `book.md` now renders them as `#### Actions`
etc. Tooltip-page captures use different markup (`mon-stat-block__*`, `ability-block`)
— same data, independent rendering (→ §F.6).

**Validator pack (L1, edition-keyed `5e-2014`), all derivable-checkable:**
- AC int 5–25 ascending; abilities 1–30 with `mod == (score-10)//2` cross-check
- `CR ∈ {0, 1/8, 1/4, 1/2, 1..30}`; `PB == ceil(CR/4)+1` (min +2); XP from the CR table
- HP `avg ≈ mean(dice expr) ±1`; speeds multiples of 5
- passive Perception `== 10 + WIS mod (+ PB if Perception in Skills)`
- conditions ∈ the 2014 14-set; senses ∈ {blindsight, darkvision, tremorsense, truesight} (+ passive)
- saving-throw / skill bonuses `== ability mod + PB` (or 2×PB expertise) — flags OCR-class typos for free

## B. Candidate new dimensions — verdicts

- **`background` — CONFIRM as dimension.** Corpus: exactly 2 (`…/character-options#GateWarden`,
  `#PlanarPhilosopher`) but the shape is structural: named `Feature:` block, "Building a X
  Character", suggested-characteristics d6 tables (dim:table refs). Critical nuance: the
  registry's "faction-as-background" is *one background with a faction choice inside it* —
  `#FactionsofSigil` sits INSIDE Planar Philosopher. Model as edge
  `background→affiliated_with(faction)`, not 16 backgrounds. SRD 5.2.1 adds more → multi-source dim.
- **`feat` — CONFIRM as dimension, with a prereq EDGE.** 7 in corpus
  (`#ScionoftheOuterPlanes` + Agent of Order, Baleful Scion, Cohort of Chaos, Outlands
  Envoy, Planar Wanderer, Righteous Heritor). PAitM builds a literal feat *tree*: the six
  are gated on Scion of the Outer Planes → fields `{prereq, repeatable, benefits[]}` and
  edge `requires`(feat→feat). The `with-metadata` heading class in the HTML marks these
  entries — cheap extraction cue.
- **`subclass` — DO NOT build yet.** Zero subclasses in PAitM. Keep as a field on `class`;
  the registration recipe makes later promotion free. Don't pre-build off speculation.

## C. Field additions — CONFIRMED, with exact observed shapes

- **spell** (`…/character-options#GateSeal`, `#WarpSense` — only 2 in PAitM; 5e spell
  volume comes from the SRDs, the wiki's 617 is 2e-skewed): level+school line
  `*2nd-Level Divination*` (ritual appends `(ritual)`), `**Casting Time:**`, `**Range:**`,
  `**Components:** V, S, M (a razorvine leaf)` — keep material text, `**Duration:**
  Concentration, up to 1 minute` → `concentration` is a *prefix of duration*, not a flag
  field in source. `at_higher_levels` attested in SRD shapes.
- **item** (`#Mimir`, `#PortalCompass`, `#SensoryStone`): type line
  `*Wondrous Item, Rare (Requires Attunement)*` → `{kind, rarity, attunement, attunement_req}`.
  Note the mascot is officially a magic item. Portal Compass exercises the
  `unlocks`/`keyed_to` portal edges for real.
- **condition** — promote ✓; 9 distinct condition tooltip refs in entities.json; closed set.

## D. Rule-not-dimension — confirmed, plus one borderline

- **Glitch/incarnation mechanic** (tofw `beginning-of-the-end#GlitchCharacters`): bespoke
  campaign rule — PC death manifests a "probable incarnation". No DMG charms/supernatural
  gifts anywhere in TOFW (0 hits). → `rule` + d-tables. Confirmed NOT a dimension.
- **Milestone advancement**: explicit per-chapter grants ("Each character gains a level on
  escaping" — `the-mosaic-mimir`). → `adventure.acts[].advancement`, no new dim.
- **BORDERLINE — party-state trackers.** The Mimir Restoration Tracker
  (`the-mosaic-mimir#MimirRestorationTracker`) is a *progress machine*: per-gate-town
  report graded accurate/skewed/missing, conclusion branches on the tally; materialized as
  **handout 4.1** (an image artifact we hold). 5e-era WotC repeats this shape (renown,
  piety). Recommendation: `rule.kind=progression` first; promote to `dim:tracker` only if
  it recurs across sources. But DO add `handout` to `dim:map.kind` now — handouts are real,
  player-facing, and we hold them.

## E. Edition enum — PAitM is `5e-2014`. CONFIRMED.

Evidence: statblock format (Challenge+PB inline; no Habitat/Treasure; 2014 condition set;
Lair-without-Legendary patterning), backgrounds/feats as the only character chassis (no
species/race text at all — PAitM ships zero playable races; bariaur is a monster:
`bestiary-a-to-z#BariaurWanderer`). Keep `5e-2024` distinct for SRD 5.2.1. One sharpening:
`srd` in the edition enum is a *license axis*, not a rules axis — SRD 5.1 ≅ 5e-2014,
SRD 5.2.1 ≅ 5e-2024. Consider `edition` (ruleset) × `license` (already on dim:source) and
drop `srd` from the edition enum to avoid double-counting the same ruleset.

## F. NOT on your list (the question you actually asked)

1. **Faction-keyed creature archetypes.** 16 of the 54 mpp statblocks are faction agents
   (`bestiary-a-to-z#FactionAgents`: Athar Null … Transcendent Order Instinct). The
   registry synthesizes `member_of` only from `npc.descriptor.faction` — **add the same
   edge rule to `creature`** (`affiliated_with`/`member_of`(faction)). This is the 5e
   box's primary faction mechanization; without the edge, faction queries miss it.
2. **Planar influences — the plane↔creature mechanical bridge.**
   `multiversal-menagerie#PlanarInfluences`: plane-keyed modification templates for
   creatures ("influenced by X gain Y"). `planar-trait` covers plane-side properties, but
   nothing models *plane modifies creature*. Add `rule.kind=planar-influence` + edge
   `influences`(plane→rule→creature) — exactly the kind of crunch the 2e→5e uplift wants
   to diff (2e had per-plane survival rules in the same conceptual slot).
3. **Mimir-notes as first-class fiction.** 76+ in-world attributed quotes
   (`aside:text--mimir-notes` ×51 sato/mpp + ×25 tofw, `aside:text--morte-notes` ×20,
   epigraphs ×28) with speakers ("–Standard mimir introduction", "–Xixi, planar guide").
   Add `mimir-note` (and `read-aloud`) to `dim:fiction.form`; `authored_by` edges to
   in-world speakers. Extraction is nearly free — every instance is already tagged in
   book.md with its aside class and section anchor. **The Handbook MCP *is* a mimir; this
   dimension is its voice bank.** The 101 `text--quote-box` read-alouds in TOFW are the
   play-aid sibling (form=read-aloud, tied to area keys).
4. **Area keys ↔ map markers.** TOFW keys encounters to numbered map areas (Map 1.1
   Mortuary Basement …). `dim:location.fields += map_ref{map, marker}`;
   `dim:map.fields += {player_version: file-pair, grid, scale}` and a `variant_of` edge
   between DM/player versions — we hold 10 such pairs with identical basenames
   (`…-player.jpg`). Also `dim:map.kind += handout` (§D).
5. **Encounter/CR support tables** (`#StatBlocksbyChallengeRating`, `#PlanarEncounters`,
   `#EncountersinSigil`, `#SigilCalamities`, `#FactionMissions`, gate-town tables with
   slide rules in `the-outlands#GateTowns`): all fit existing `dim:table`/`dim:hook` —
   attestation noted, no schema change. Gate-town `slide_risk` ✓ confirmed live in 5e.
6. **Free L3 witness for the gate.** VALIDATION.md wants independent confirmation "drawn
   from sources or senses the extractor never used." The 48 tooltip captures are the same
   entities in a *different DDB rendering pipeline* (`mon-stat-block`/`ability-block` vs
   sources-page `monster--stat-block`) — e.g. Morte is attested in both
   `tofw/schemes-in-sigil` and `monsters/3883553-morte`. Diffing the two renderings is a
   cheap, fully-local independent witness for every dual-attested statblock.

## Priority notes

`background`, `feat` → Tier 2 (small counts in PAitM but structural for 5e play);
faction-agent edge rule (§F.1) → Tier 1 alongside `faction` (it's how 5e factions bite);
mimir-note fiction (§F.3) → Tier 2, high leverage for the language backend.

---

*On the wager: dimension already lands at least triple here — the registry's dimensions,
the planes they catalog (dim:plane, a dimension of dimensions), and the map pairs whose
physical dimensions we now track. The fourth — the mimir-notes giving the Handbook-mimir
its voice across all of them — we leave for the Lady to adjudicate.*
