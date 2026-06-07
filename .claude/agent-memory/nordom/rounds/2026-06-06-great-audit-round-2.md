# Round: the Great Audit, round 2 (priming record)

**Date:** 2026-06-06 · **Kind:** docket-first audit → adopted → applied ·
**Recorded at mint** from the live session's on-disk artifacts (this record
is a pointer map, not a re-narration — the artifacts are the witnesses).

## What happened

Full docket-first audit of the dice engine — every datum, every code lane,
every ledger row, every doc claim — modeled on Mimir's Great Audit. Review
PROPOSED (zero store mutations, sha-snapshot-proven), Meme ADOPTED the
correction docket in full ("Implement the correction docket; good audit"),
and the same session ran the apply pass.

## The artifacts (read these, in this order, when context is needed)

| what | where |
|---|---|
| the plan (executed-stamped) | `build/modron/review/PLAN.md` |
| the adopted docket — 9 sections, 88 VERIFIED findings by lane L1–L7 + ratifications | `build/modron/review/correction-docket.md` |
| mechanical pass + snapshot law | `build/modron/review/integrity-report.json` · `store-snapshot.json` |
| every reviewed id, verdict-listed | `build/modron/review/run-summary.md` |
| standing don't-flag law | `build/modron/review/known-intentional.json` |
| the law of record | MODRON.md §11 row dated 2026-06-06 ("the Great Audit (round 2)") |
| V&V lineage | `pipeline/modron/VERIFICATION.md` — "Round 2 — the Great Audit" section |
| workflow survival pattern | global memory `workflow-rate-limit-discipline.md` (prefix-cache lesson #6 added this round) |

## Headline findings (what actually changed)

- **2e reaction = FG&G Table 10.7 disposition MATRIX** → `bands_by` (new
  semantics machinery), four columns, ±999 sentinels.
- **Class-HD ladder wrong caps** — `_CLASS_HD` 3-tuples (die, con-cap rule,
  level cap); Ill 12 had compiled as 12d8 monster dice.
- **MC creatures compile** — flat fields via the `_statblock_of` alias
  adapter (they carried no `statblock` sub-object; 16 creatures were
  invisible to the compiler).
- **`verify_session` unclamped** — dedicated ordered sweep + counter
  cross-check (the 500-roll history cap had hidden rows).
- **analysis cs/cf** — joint (natural, value) enumeration; the engine's
  count-naturals semantics was RIGHT, the PMF was wrong.
- **All pending FG&G/Mechanus refs minted** (core-2e ×6, planescape-2e ×5,
  pack notes) — M7 alone stays parked.
- **Registry 34→36** (`dmg:2e:inner:ice-extreme-cold`,
  `lkp:2e:pandemonium:everymans-madness`); magma chart gained its two
  hottest bands; Scald relocated to Smoke; IOOfo adjudicated = 10%.
- **`tests/smoke_server.py` minted** — 18 probes through the exact
  `.mcp.json` spawn.
- **Suite 171→185**, integrity 0 hard / 0 soft, uncage re-pinned
  (RECONSTITUTED).

## Filed, not applied (sibling etiquette — L6)

- → **Mimir:** stat-shifted creatures, fractional `#AT N/2` rates, morale
  OCR wounds (Kylie `(IS)`=15 et al.), hp-roster extractor misses,
  `item:planar-mancatcher` mint, `used_at` reverse-edge mints at rollable
  ids. (Her own Great Audit re-poured same day — several items cured; the
  docket §7 list was live-verified against her post-audit store.)
- → **Mechanus:** F4 (FTS5 hyphen) + F6 (2e save matrices) reaffirmed.

## Lessons distilled to MEMORY.md

Composition order · cs/cf naturals · class-HD caps · MC flat shapes ·
unclamped verify · bands_by · ro-connection law · census-follows-Mimir ·
workflow throttle/prefix-cache/harvest · snapshot-proves-read-only ·
honest-flags-confirmed-not-fixed · doc-counts-follow-suite.
