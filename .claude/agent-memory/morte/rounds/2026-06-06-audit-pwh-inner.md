# Round: PWH + Inner Planes audit (the post-pour adversarial review)

**Date:** 2026-06-06 · **Store:** UNTOUCHED (1,008 / 2,199 / 92 — all probes readonly)
· **Docket:** `build/mimir/review/audit-pwh-inner/correction-docket.{md,json}` — **PROPOSED, awaiting Meme**

## Why

The Great Audit's docket closed BEFORE the PWH and Inner Planes pours landed —
both books had gate-time attestation but no adversarial page-witness round.
Meme asked for the audit; this round extends the Great-Audit discipline to the
two newest pours.

## Machinery (landed in-repo this session)

- `tools/review_chunks.py` EXTENDED: BOOK_REFLOW + resolve() branches for
  2620/2634 (race/class/spell; item-PWH; plane/deity/realm/location/proxy-inner;
  pwh-spell quarantine), scope-aware primary_book, and a `--books`/`--out`
  SCOPED mode (separate output dir — never clobbers the Great-Audit chunks;
  scoped coverage assert + per-dim print). Unscoped path byte-compatible.
- Both pour lanes store `pages` as REFLOW FILE numbers (anchor-window law), so
  the new branches are offset-free.

## The round

1. Baseline rail GREEN before review: suite 104 · integrity 0 hard / 38 soft ·
   uncage RECONSTITUTED (audited a known state).
2. Scoped dump: **200 entities, 12 chunks, 0 page-misses**; per-dim counts
   reconciled the round records EXACTLY first try (class 11 · deity 17 · item 38
   · location 44 · plane 18 · proxy 1 · race 8 · realm 4 · source 2 · spell 57);
   quarantine bucket = exactly the 1 head-lost spell.
3. Review: 12 general-purpose agents, 3 waves of 4 (the rate-limit lesson),
   shared RUBRIC.md (Great-Audit findings schema + verified-or-absent + OCR
   tolerance + merge law). 200/200 reviewed.
4. Verification: 8 sonnet refuters re-read every cited page fresh —
   **44/44 confirmed, 0 refuted**, all fixes judged faithful. Plus my own
   deterministic checks (audit_mech_checks.py): faction 3rd-witness 15/15 ·
   first-printed-in 8/8 · castable_by↔classes 57/57 · REL_CATALOG complete ·
   planar-wards + 5 merged planes NO-CLOBBER · 1 mechanical preseed
   (wastequake's HELLBOUND tag + absent edge, both machine-verified).
5. Docket: **45 findings · 160 clean / 40 flagged · lanes: card 34,
   module-curation 11, curations.json 0** · court: 1 hold (correctly held;
   promotion aid recorded: likely a *crown of …* sibling, p130 print).

## The systematic classes found (rules-first on adoption)

- **Area-of-effect continuation truncation (6 spells):** print stat-line wraps;
  reflow displaces the tail 0-2 lines (even past Saving Throw); parser kept
  line one. → ONE continuation-grammar rule in pwh.py + self-test (6 recover,
  51 byte-identical). despair · dictate · elemental-breach · howl ·
  sphere-of-survival · wastequake.
- **Reversible body-paragraph (gate family, 2 spells):** head tag print/OCR-
  dropped; body says "The reverse of this spell, NAME,". → body-sweep rule.
  close-gate (open gate) · major-gate-ward (break major gate ward).
- **Creature-index column interleave (1 page, 9 entries):** p127's two-column
  reflow fed 9 Earth-list entries into Air's inhabitants. Refuter clinched via
  archomental symmetry (Sunnis+Ogremoch in the block = Earth pair). →
  INDEX_CURATIONS table in inner.py (column-reconstruction parsing judged too
  risky for one page).
- **Card-text drift in hand-curated fields:** hazards_note clauses that
  paraphrased ACROSS chapter boundaries (the Ice splash quote landing on
  energy-negative; border-region law stated as core law; an invented 10d6) and
  glosses importing out-of-book canon (Earthlord, Water Lord). The lesson:
  CURATED text needs the same witness discipline as parsed text — quote-or-
  paraphrase ON-PAGE only, hedges preserved verbatim.
- **Origin-by-inference on items:** cards asserted origin where the page gives
  use-locus ("used primarily in the Abyss" ≠ made there); siblings hedge when
  the page hedges. works_on = plane-keyed FUNCTION only.

## Cross-lane safety

§M7-UNPARK checked: it is a PAGE-ANCHOR table (Primus reads reflow directly) —
none of the hazards_note defects propagate; its energy-negative row already
anchors p66 (the page the card window missed). No handoff correction needed.
No new cross-agent asks posed.

## Honest tallies

- 0% refutation rate — reviewer pool was conservative (line-cited findings,
  low-confidence honesty on weak-witness calls); refuters did independent
  page-level work (column reconstructions, sibling-phrasing comparisons), not
  rubber stamps.
- One reviewer hit the harness-Grep-vs-UTF-8 anomaly (no-match on present
  strings) and fell back to byte-level sweeps — carry into the next rubric.
- Store untouched; docket-first law held: nothing applied without sign-off.
- Post-apply expectation recorded: entity count UNCHANGED; edge delta exactly
  −1 dwells_in · +1 located_in · +1 first-printed-in.

## Agent ids (for SendMessage continuation if needed)

reviewers: c1 a273f01391c04d7fa · c2 a4b9aa23fd5d914ac · c3 a380513e1ebcde3a1 ·
c4 afe89b8b51e87b490 · c5 a61ebeb170489c1b3 · c6 adbb404dde569ce09 ·
c7 aebe50cdf9b87bd58 · c8 a248f38df9ae18bc5 · c9 ab71e259ce7ce01e0 ·
c10 a8c9e1d5731b01019 · c11 a4ae90b8762edcdc9 · c12 aced6494af69de9ce
refuters: ac006b535dbb0793b · a734fcdd15311c513 · a71d4d3dc49b3d34d ·
a5dc960f2dc4f9575 · a110c1d19942432c1 · a4f8cd02fef9d5228 ·
a27ed90a56e532132 · aaf526fdf41db657c
