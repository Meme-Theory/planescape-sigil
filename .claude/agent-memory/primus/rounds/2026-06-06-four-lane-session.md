# Round: the four-lane session (Q6 + Q4 + F4 + F6)

**Date:** 2026-06-06 · **Steward:** Primus · **Trigger:** Meme asked for the
outstanding-task check ("Morte left you some tasks"); at the wake triage he
selected ALL FOUR offered lanes. Order run: F4 → Q4 → Q6/M7 → F6 → mint.

**law_version chain:** `0d05d408b20e7314` → `982b6bb290abc7f0` (M7 pour) →
**`972ff12b18087c03`** (save-matrix pour). Suite 121 → **132** · smoke 20 →
**21** probes, clean · integrity **0 hard / 2 by-design** (historical vnv rows)
· uncage re-pinned + verify **RECONSTITUTED**.

## F4 — precedents FTS5 hyphen crash (code-only)

- Verified still-live FIRST (ledger said the Assize might have fixed it; it
  hadn't — C-lane never touched `precedents`). Bare `MATCH ?` at ledger.py:214.
- Red run reproduced `no such column: like` on `spell-like`; applied Mimir's
  store.py quote-fallback (raw MATCH → `OperationalError` → terms quoted +
  OR-joined); pinned by `test_precedents_hyphenated_topic_quote_fallback`.
- First probe draft lied: asserted `spell-like nonsense-topic == []`, but the
  fallback is OR-joined so the first term still hits. Caught before commit.

## Q4 — M9-M13 adjudication (decision-only, §10 row)

- **M9/M10/M12/M13 ACCEPTED as new families** — `law:belief:` ·
  `law:portal:` · `law:proficiency:` · `law:prime-planar:`; **M11 =
  enrichment** of M1/M2/M4 (Morte's own read, VERIFIED against live data:
  conditions rows carry school/sphere only, so PWH's item-bonus-loss /
  priest-level-loss / True Names charts land as new rows under EXISTING
  families). Pours queued AFTER M7; M12+M13 can share a round.
- Modron dependencies: D11 blocked on M9 *ids* (acceptance ≠ pour); her 8
  pending-M12 NWP cites upgrade at the M12 pour.

## Q6 — the M7 pour (the headline)

- **Witness-first:** ~40 reflow pages read (Elemental Primer 6-21 + every
  chapter's conditions/hazards pages). Page law OBSERVED: printed = reflow − 1
  off the footers, uniform — recorded in `_source.page_convention`, never
  derived.
- **Id-shape ruling (mine per the handoff):** both-and —
  `law:inner-survival:general:<topic>` ×9 (pockets, guides, border-ethereal,
  immunities, no-gravity combat, magic-use, alteration legend, priest
  level-loss, item plus-loss) + `law:inner-survival:<mimir-slug>` ×18 plane
  profiles + hazard sub-ids ×82 (`…:elemental-water:whirlpools`) = **109 ids**.
  Sub-id grain = the XR-3 hazard-node join + Modron D7 ref target.
- **Engine wiring:** PLANAR_LAW_FILES entry + one `_planar_rows` branch;
  `_rule_text` (test + integrity, kept mirrored) extended to sweep
  `conditions` + `per_type` so the shingle misses nothing.
- **Shingle test caught 4 leaks at pour** (pathway-spell list, current ladder,
  2 AC-damage ladders) — all tabular value-runs. Doctrine applied: ladders →
  structured dicts; prose keeps shape + endpoints. 2 sibling ladders (fire
  heat, air storms) restructured prophylactically — they'd passed on OCR luck.
- Deferred honestly: per-plane school-alterations / spell-keys / margin tables
  for the inner 18 = M1/M2-extension round (in `_source.deferred` + §3a + §10).
- Server: off-corpus refusal + `law_info` handoff note de-parked; new smoke
  probe resolves `…:elemental-fire:heat` end-to-end. Integrity pins
  recalibrated 199→308 + family counts + new BOOK_DIR component.

## F6 — the 2e save matrices

- Found in the FG&G cache: warrior p.27 T3.2 ×9 · wizard p.30 T3.9 ×5 ·
  priest p.32 T3.12 ×7 · rogue p.34 T3.13 ×6; rules p.69-70 (1d20-meets-score,
  category priority, modifiers move the DIE, voluntary failure,
  ability-checks-as-saves, creature mapping).
- `save_matrix_2e.json` + `tables.saves_2e(group, level)` /
  `saves_2e_monster(hd)` (L3 library-seam pattern; `law_info` auto-cites).
  p.309 plus-bump SHARED with thac0 via `parse_hd_2e`.
- **The bump bit me too:** my monster pin asserted next-BRACKET (7+3 → 9-10
  row); red run corrected it to next-DIE (7+3→8, stays 7-8) — the exact
  thac0 7+3→13 lesson, now twice-learned, pinned both places.

## Ceremony

- Ride-alongs in-change: MECHANUS.md header (132/21/972ff…/308-across-8 — the
  claim regex needs the phrase CONTIGUOUS; a line-wrap broke it once) + §3a
  family table + M7-poured paragraph + §10 ×3 rows (Q4, Q6, F4+F6) ·
  CLAUDE.md §Mechanus (status + planar paragraph; edited against Modron's
  concurrent changes, their lines untouched) · uncage pin+verify · ledger
  rows (Q6/Q4/F4/F6 → closed tail; XR-3 FULLY UNBLOCKED; D11 re-pointed at
  the M9 pour; new OPEN-to-Mechanus row for the M9-M13 pours) ·
  integration-tests.md F4/F6 close notes.
- **Concurrency note:** Nordom's session ran the same day (PWH acceptance:
  D10/D12/D13 + hope_drain, registry 47, suite 195) and OBSERVED my pour in
  flight — left a deferred-pin rider on the Q6 ledger row; my single `pin`
  captured both engines' new state (RECONSTITUTED). The ledger discipline
  held under live concurrency.
- Pending at close: `/mcp` reconnect (server lru caches hold pre-pour law);
  commit awaits Meme's word — session work UNCOMMITTED.

## Open after this round

- **M9-M13 pour rounds** (M12+M13 can pair; D11 unblocks at M9; M11
  enrichment round needs both-witness reads).
- **M1/M2-extension round**: inner-18 school-alterations + spell keys +
  margin tables (witness windows already mapped in the §M7-UNPARK table).
- **XR-4b** PAitM joint round with Morte; then arbitrate ladder 0–2 →
  conversion v0 (unchanged build order).
- §11 opens for Meme unchanged (resolve scope guard · ruling scope model).
