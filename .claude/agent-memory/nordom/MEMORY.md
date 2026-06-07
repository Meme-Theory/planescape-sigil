# Nordom — state of the engine (Modron engine steward)

## Protocol

- This file auto-loads (first ~200 lines). Honor the header + index; Read a
  full record from `rounds/` only when the work touches it.
- After ANY round: full record to `rounds/<date>-<slug>.md`, ONE index row +
  distilled lesson line(s) here, refresh the state header. Under 200 lines
  always; correct wrong lines IN PLACE.
- Repo docs outrank this file: MODRON.md §11 is the law of record. Cross-agent
  asks live in the project memory's `cross-agent-requests.md` — check it at
  session start, verify-before-posing, update on pose/answer/apply.

## State of the engine (refresh every round)

- **Status:** BUILT + V&V'd + AUDITED + **PWH-ACCEPTED** — round 3 (the PWH
  acceptance) applied 2026-06-06 on Meme's word: Q5 answered IN SCOPE,
  D10/D12/D13 + Lane-E hope-drain landed, D11 alone still blocked
  (MODRON.md §9 §PWH row + §11; VERIFICATION.md round-3 addendum).
- **Gates @ 2026-06-06 (round 3):** suite **195** green · smoke **18/18**
  (configured py.exe spawn, temp ledger) · integrity **0 hard / 0 soft**
  (fleet 93/578 · math 49/49 · replay 50/50 · pending refs **1 = M7**,
  upgrade READY — see Open items) · uncage **RECONSTITUTED** (the deferred-pin
  rider closed same day: Primus's four-lane re-pin captured my two data
  files; verified live before the round-3 commit).
- **Surface:** 17 tools · 4 packs · `2e-planescape` **15 kinds** (+hope_drain
  +8 planar NWPs w/ baked printed modifiers) · 29 modifier rows · **47**
  rollables (+4 D13 item d100s · +3 tiefling d100s · +3 chargen lookups ·
  +planology fortune) · `engine_version 1` · ledger 7 sessions, 52+ rolls,
  sealed (2 fiat rows, reasons on both).
- **Seam stamps:** Mechanus `law_version 972ff12b18087c03` (chain `0d05d408…`
  → `982b6bb2…` → current; her four-lane round 2026-06-06) — data refs cite
  her minted ids (`law:planar-conditions:*`, `law:plane-environment:*`,
  `law:inner-survival:*` now live ×109).
- **Live truth outranks this header:** re-run `tools/integrity.py`; read
  `build/modron/review/integrity-report.json`.
- **Next likely rounds:** the M7 ref-upgrade — **READY NOW** (her Q6 landed:
  109 `law:inner-survival:*` ids live on `972ff12b…`; small round: upgrade
  the 1 pending ref, verify the cited id, re-rail, re-pin) · 8 pending-M12
  NWP cites upgrade when her M9-M13 pour rounds run (D11 mints with M9) ·
  `check_stats` (§12 Q4) — **F6 UNBLOCKED** (save matrices POURED, her
  four-lane round; design the kind against `tables.saves_2e`) ·
  census/dangler re-pins when Mimir mints XR-3 pointers at my 11 new ids ·
  a 5e fleet lane when 5e statblocks pour.

## Round index

| date | round | record |
|---|---|---|
| 2026-06-06 | the Great Audit, round 2: 19-chunk docket-first review → 88 verified findings → docket ADOPTED → L1–L5 applied (suite 171→185, registry 34→36, smoke minted 18/18); L6 FILED to siblings | `rounds/2026-06-06-great-audit-round-2.md` |
| 2026-06-06 | steward mint — this memory primed from the audit round; agent + template per MODRON.md §11 | — |
| 2026-06-06 | PWH acceptance, round 3: Q5 IN-SCOPE + D10 (8 NWP kinds, baked mods) + D12 (tiefling d100s ×3, chargen lookups ×3) + D13 (item d100s ×4) + Lane-E `hope_drain` mint; suite 185→195, registry 36→47, kinds 6→15; uncage pin DEFERRED (Mechanus mid-round); XR-5 record gap filed to Morte | `rounds/2026-06-06-pwh-acceptance.md` |

## Distilled lessons (the playbook's living edge)

- **Composition order is law:** per-die attachments → adds → wraps LAST
  (V&V D1) — resistance/vulnerability halve/double sneak + brutal-crit dice
  too. Every new effect primitive gets a composition test.
- **cs/cf count kept dice's NATURALS; keep/drop ranks by VALUE** — the audit
  proved the ENGINE right and the analysis wrong. Crosscheck both ways before
  "fixing" either.
- **Class HD per the FG&G ladder:** warrior/priest cap 9, rogue/wizard cap
  10, `ILL` is a specialist wizard — Ill 12 once compiled as 12d8 monster
  dice, caught only by the clean-sample false-negative probe. Keep that probe.
- **Entity shape drift = silent spec loss:** MC creatures carry FLAT fields;
  `_statblock_of` aliases them. When Mimir's shapes move, the fleet lane is
  the tripwire — compile ALL statblock-bearers, not samples.
- **verify_session sweeps UNCLAMPED** + counter cross-check — the 500-row
  history cap once hid rolls from verification.
- **Bands can be 2D:** `bands_by` keyed by a param (FG&G Table 10.7 reaction
  = disposition × 2d10, ±999 sentinels at the rails).
- **`ledger._connect()` is RW + executescript** — read-side tooling uses
  `mode=ro` URI connections, always. Never "just peek" through the write path.
- **The census follows Mimir:** her Great-Audit re-pour shifted the fleet
  87→93 with re-slugged ids same-day. Update integrity's pin WITH a dated
  comment, never silently.
- **Workflow audits on this rig:** wave-throttle ~3 · sonnet refuters ·
  `resumeFromRunId` is a PREFIX cache, not a memo · harvest StructuredOutput
  from agent transcripts when agents die · a dead verifier ≠ refutation
  (global memory: `workflow-rate-limit-discipline.md`).
- **Docket-first means PROVABLY read-only:** `snapshot` before,
  `verify-snapshot` after — it also proves no MCP tool fired (any roll/usage
  write would move rolls.db / usage_counter.json).
- **Honest flags get CONFIRMED, never "fixed":** provisional / UNCURED /
  `requires_confirmation` are the system working (IOOfo adjudicated to 10%
  by glyph decomposition, THEN the flag retired with a note).
- **Doc counts move with the suite same-round** (the F-lane honesty), or the
  report says DRIFT.
- **A sentence-shaped table cell gets paraphrased; only bare NAMES are facts**
  — the shingle court convicted 7 of round 3's own strings the moment the
  PWH joined REFLOW_MAP. Run integrity BEFORE calling a pour done.
- **Printed check modifiers BAKE into kinds** (`vs_template "score ± n"`) —
  caller-remembered law is law someone will forget. Two printed uses = two
  kinds, not a param.
- **Never pin the manifest over a sibling's mid-round state** — uncage pin is
  global; an in-flight sibling pour (untracked law file, moved law_version)
  means DEFER with the why recorded and a rider on their ledger row.
- **Verify-before-APPLYING, not just before-posing** — the ledger's "witness
  pages in handoff" for D13 pointed at a paragraph that never existed; the
  book reflow was the real witness. Record gaps get filed (XR-5), not
  papered over.

## Open items (the lane's watchlist)

- **PWH round 3 APPLIED** except **D11 BLOCKED(Mechanus Q4/M9)** — the lone
  survivor; mints when her M9 ids exist. Record gap **XR-5 filed to Morte**
  (handoff has no §D13 paragraph; my pour witnessed from the book reflow).
- **M7 pending ref — upgrade READY:** her Q6 LANDED same day (109 ids,
  `law_version 972ff12b18087c03`; deferred-pin rider SATISFIED — uncage
  verified RECONSTITUTED pre-commit). Next small round: upgrade the ref
  against her live id, re-rail, ledger rows.
- **Meme's running modron server** serves pre-round law until his next `/mcp`
  reconnect (round-3 law proven end-to-end via smoke on the same spawn).
- **Mimir owes** `used_at` reverse edges at the now-47 rollable ids +
  `item:planar-mancatcher`; XR-3 is **FULLY unblocked** (my 11 ids + her
  hazard sub-ids). XR-5 (handoff §D13 record gap) still open to Morte.
- **Mechanus F4 FIXED + F6 POURED** (her four-lane round) — `check_stats`
  (§12 Q4) no longer queued; M9-M13 pour rounds queued on her side (D11 +
  my 8 pending-M12 cites ride them).
