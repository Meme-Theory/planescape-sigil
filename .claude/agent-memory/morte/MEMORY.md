# Morte — state of the spine (Mimir engine steward)

## Protocol

- This file auto-loads (first ~200 lines). Honor the header + index; Read a
  full record from `rounds/` only when the work touches it.
- After ANY round: full record to `rounds/<date>-<slug>.md`, ONE index row +
  distilled lesson line(s) here, refresh the state header. Under 200 lines
  always; correct wrong lines IN PLACE.
- Repo docs outrank this file: DIMENSIONS.md's ledger is the law of record.
  Cross-agent asks live in the project memory's `cross-agent-requests.md` —
  check it at session start, verify-before-posing, update on pose/answer/apply.

## State of the spine (refresh every round)

- **Store:** 1,008 entities · 2,199 edges · 92 quarantined (7 adjudicated
  buckets) · FTS 1,008 · integrity 0 hard / 38 documented softs · suite 104.
- **Poured:** 5 books + 4 boxed sets — Uncaged · Factol's Manifesto · In the
  Cage · Planes of Law/Chaos/Conflict · Hellbound · Planewalker's Hbk (2620) ·
  The Inner Planes (2634). 12 source nodes. 29 dims live.
- **Registry:** 29 poured · pointer dims (rule/planar-trait/table/hazard)
  BLOCKED on sibling ids (Q6/M7, D13) · psionic re-parked (wrong-book,
  needs a psionics-bearing source) · 8 CLOSED (ratified).
- **Manifest:** pinned + RECONSTITUTED at the state above (re-pin after every
  pour — curator duty). law_version seam: 0d05d408b20e7314.
- **PWH+Inner audit (2026-06-06): docket PROPOSED, awaiting Meme** —
  `build/mimir/review/audit-pwh-inner/correction-docket.md`: 200/200 reviewed,
  160 clean / 40 flagged, 45 confirmed findings (0 refuted), lanes card 34 /
  module 11 / curations 0; court 1 hold. Apply = card+rule edits, ONE re-pour
  (entities unchanged; edges −1 dwells_in +1 located_in +1 first-printed-in),
  rail, re-pin. review_chunks.py now has 2620/2634 + --books scoped mode.
- **Last commits:** 95482b6 (PWH pour) · c19a10c (equipment round) · d4bb7e4
  (Inner Planes). Commit/push only when Meme authorizes in-session.
- **Next likely rounds:** APPLY the pwh-inner audit docket (on sign-off) ·
  PAitM pour (XR-4b — capture COMPLETE, jointly with Mechanus) · 2600 core box
  (gate-towns 11→16, MS creatures via monstrous.py, dual-source Sigil) ·
  hazard pointer mint (BLOCKED on Q6) · L6/Lane-E/XR-1/XR-2 (see ledger).

## Round index

| date | round | record |
|---|---|---|
| 2026-06-06 | PWH (2620): race 8 · class 11 · spell 57 (+1 head-lost q) · faction 3rd-witness ×15 · psionic re-parked | `rounds/2026-06-06-pwh.md` |
| 2026-06-06 | PWH equipment: item 106→143 (38 cards; planar-wards dual-source merge proved) | `rounds/2026-06-06-pwh-equipment.md` |
| 2026-06-06 | Inner Planes (2634): 18 planes · 44 sites · 4 realms · 17 powers · 1 proxy · M7 unparked (§M7-UNPARK posted, Q6) | `rounds/2026-06-06-inner-planes.md` |
| 2026-06-06 | PWH+Inner AUDIT: 200/200 adversarial review, 45 findings (0 refuted), docket PROPOSED; review_chunks.py scoped mode | `rounds/2026-06-06-audit-pwh-inner.md` |

## Distilled lessons (the playbook's living edge)

- **Anchor windows, never arithmetic:** print offsets DRIFT mid-book (2634:
  +2 → +1). Cards claim PDF windows; attestation lands where it lands.
- **Closed-vocabulary gates kill false heads:** the spell parser's
  school-vocab check made junk heads impossible — prefer a domain vocabulary
  over name-plausibility heuristics.
- **`Level I` ≠ literal I:** OCR renders digit 1 as I/l in rigid heads — map
  it; it hid two priest spells.
- **Ambiguous bindings bind NOTHING:** two-column reflow scrambles
  adjacent-head statlines; the verified-or-absent rule + hand-read curations
  (page witness + semantic why: sphere names, area targets, family templates)
  recovered 12/12 with zero guesses.
- **Per-class print divergence is DISCLOSED, never averaged:**
  `level_by_class` / `stats_by_class` (Protection from Prime W2/P1).
- **Alias by the page's OWN form** (8ARIAUR · BomED BREATII · "Plane of ke" ·
  TE9WER •f s+eRms · a site's named leader when its head is shredded) — the
  Blood Tor law, applied eight+ times today.
- **Re-park, don't invent:** the registry expected psionics from PWH; the
  book has three asides. Corrected the registry note, poured nothing.
- **Merge-aware pours prove the marquee:** same id, both books, one node —
  planar-wards (Grixitt's wields + PWH's mechanics) is the
  invoke-at-the-table join working.
- **Roster-as-fields when stubs would corrupt L1:** 2634's creature index
  (160 entries) rides plane `inhabitants[]`; creature nodes wait for real
  statblocks (MC appendices).
- **New edge rels register in integrity's REL_CATALOG same-session**
  (castable_by · kit_of · native_to · used_by · dwells_in) or the rail flags
  hard.
- **Law substance never pours here:** PWH belief/portal/proficiency law and
  2634 survival law went to the handoff as witnessed M/D offers; statline
  ATTRIBUTES on identity nodes are fine (the creature-statblock precedent).
- **Verify before posing** (the XR-4 lesson): a claim harvested from a
  catalog/status note gets its live record checked first.
- **Doomguard citadel network** text-bound used_by at Sealt/Exhalus/Alluvius/
  Crumbling; Former Flame unbound (no witness) — faction presence is
  edge-worthy when the page says it.
- **Curated card text needs the parser's witness discipline:** the audit's
  worst defects were HAND-WRITTEN fields — hazards_note clauses crossing
  chapter boundaries (the Ice splash quote on energy-negative; an invented
  10d6), glosses importing out-of-book canon (Earthlord/Water Lord), origins
  inferred from use-locus. Cards quote-or-paraphrase ON-PAGE only; hedges
  preserved verbatim; works_on = plane-keyed FUNCTION, never origin.
- **Stat-line continuations are a parser class:** print wraps area_of_effect;
  reflow displaces the tail 0-2 lines (even past Saving Throw) — 6 of 57 PWH
  spells truncated. Rule-first (continuation grammar + self-test), never six
  curations. Sibling class: reversible lives in the BODY ("The reverse of
  this spell, NAME,") when the head tag drops.
- **Audit pattern, proven twice:** scoped chunk dump (exact-reconcile the pour
  records) → wave-throttled reviewers (shared RUBRIC.md) → sonnet refuter
  batches re-reading pages fresh → mechanical preseeds I run myself → docket
  PROPOSED, store untouched. 0% refutation = conservative line-cited finders,
  not lax refuters — check refuters quote line numbers.
- **Harness Grep can no-match strings present in UTF-8 reflow** — reviewers
  fall back to byte-level Python sweeps; put it in the next rubric.
