# Primus — state of the law engine (Mechanus engine steward)

## Protocol

- This file auto-loads (first ~200 lines). Honor the header + index; Read a
  full record from `rounds/` only when the work touches it.
- After ANY round: full record to `rounds/<date>-<slug>.md`, ONE index row +
  distilled lesson line(s) here, refresh the state header. Under 200 lines
  always; correct wrong lines IN PLACE.
- Repo docs outrank this file: MECHANUS.md §10 is the law of record. Cross-
  agent asks live in the project memory's `cross-agent-requests.md` — check
  it at wake, verify-before-posing, update on pose/answer/apply.

## State of the engine (refresh every round)

- **law_version `972ff12b18087c03`** (chain: `018b2eed42e9afe7` → planar pour
  `a15604342754bf34` → Assize apply `0d05d408b20e7314` → M7 pour
  `982b6bb290abc7f0` → save-matrix pour `972ff12b18087c03`). The 6 ledger
  rulings keep historical stamps BY DESIGN.
- **Suite 132 green** (incl. fleet audit + shingle) · smoke 21/21 ·
  integrity 0 hard / 2 by-design (historical vnv doc-claims) · uncage
  RECONSTITUTED on this stamp (pin captured Modron's PWH files too).
- **Law families:** planar **308 ids / 8 files** (conditions 109 · keys 48 ·
  seals_wards 5 · priest 3 · environment 18 · spells 12 · cage 4 ·
  **inner_survival 109** — 9 general + 18 plane profiles + 82 hazard sub-ids)
  + SRD tables (dc/xp/pb/budget-2024/conditions/attribution) + `thac0_2e`
  (keep-3 17+ RATIFIED) + **`save_matrix_2e`** (F6: FG&G class tables +
  creature mapping; `tables.saves_2e{,_monster}`) + `known_deviations`.
- **Parked (intended):** invoke tools (`view`/`rule_search`/`delta`/
  `convert`/`resolve`…) NOT_POURED until the rule pours land — the error is
  the design.
- **Pending courtesy:** `/mcp` reconnect (server lru caches predate BOTH
  pours). Assize + the four-lane session are UNCOMMITTED as of 2026-06-06 —
  commit on Meme's word only.
- **Open lanes (the work queue):**
  - **M9-M13 pour rounds** (Q4 ANSWERED 2026-06-06: M9/M10/M12/M13 new
    families, M11 = M1/M2/M4 enrichment; id schemes in the §10 row). Modron's
    D11 blocks on the **M9 ids**; her 8 pending-M12 NWP cites upgrade at M12.
    M12+M13 can share a round.
  - **M1/M2-extension round** — inner-18 school-alteration margins + spell
    keys + per-plane conditions (deferred from M7, disclosed in
    `inner_survival.json _source.deferred`; witness windows in §M7-UNPARK).
  - **XR-4b** — PAitM answer-key pour, JOINT round with Morte (capture
    13/13; 5e aspects into Mimir + 2e→5e pairs for conversion calibration).
  - **Build order next:** arbitrate ladder 0–2, then conversion v0
    (CONVERSION.md §5 rungs; calibrate on FG&G↔SRD pairs + the PAitM key).
  - **§11 opens (server-v0 choices, for Meme):** `resolve` scope guard
    (procedure-only vs full adjudication) · ruling scope granularity.
- **Siblings' work (track, don't do):** Mimir — XR-3 hazard mint (FULLY
  UNBLOCKED by my M7 ids + Modron's D13 targets) · REVIEW-5E 14→15-set ·
  XR-5 (handoff §D13 paragraph gap). Modron — pending-M7 ref upgrade (ids
  live now) · D11 (waits on my M9 pour).

## Round index

| date | round | record |
|---|---|---|
| 2026-06-06 | planar law pour (§M accepted → §3a; 199 ids, 7 families; shingle law adopted) — pre-mint, by the session | MECHANUS.md §3a + §10 rows; `rule-effect-handoff.md` §M |
| 2026-06-06 | the Mechanus Assize: 349+1 units audited, 47 findings (38 confirmed/9 refuted), correction docket ratified + APPLIED — pre-mint, by the session | `rounds/2026-06-06-the-assize.md` → `build/mechanus/review/` |
| 2026-06-06 | the four-lane session (first as Primus): F4 fixed+pinned · Q4 adjudicated (M9-M13) · **M7 POURED** (109 ids, 40-page witness read, 4 shingle leaks reworded) · **F6 POURED** (save matrices) · full mint ceremony | `rounds/2026-06-06-four-lane-session.md`; MECHANUS.md §10 ×3 rows |

## Distilled lessons

- **Page conventions per corpus** (the costliest trap): planar witness
  `reflow:[N]` IS `page-{N:04d}.txt` — no offset math ever; SRD cites are
  zero-offset (`p.N` → `pNNNN.txt`); FG&G law cites use the PDF index
  (`p.27` → `p0027.txt`; +10 ONLY converts printed-footer numbers read off
  page images). FG&G prints "THACO" never "THAC0"; bestiary starts p0309.
  2634 (Inner Planes): printed = reflow − 1, READ OFF FOOTERS (uniform;
  the handoff's "drift" note was about pre-reflow windows, not the pages).
- **The Grep tool silently skips `build/`** — bash grep / `rg --no-ignore` /
  absolute Reads; a Grep miss is never evidence of absence.
- **Shingle law:** 10 normalized tokens vs the row's own witnessed reflow =
  leak (hard); 7–9 = near-miss advisory. Reword docket payloads BEFORE
  applying (the Arcadia lesson — the synthesizer predicted the trip).
  **Value-ladder corollary (M7 pour):** tabular dice/score ladders narrated
  in prose reproduce the page's token run — ladders go in STRUCTURED dicts
  (`damage_by_natural_ac` style), prose keeps shape + endpoints only; fix
  siblings that passed on OCR luck while you're there.
- **law_version ride-alongs, same change:** MECHANUS.md header + §10 literal
  · CLAUDE.md §Mechanus · uncage pin+verify · `/mcp` reconnect ask. Code
  never moves law_version; data always does.
- **Hard vs soft is an honesty axis:** thac0 brackets stay SOFT (empirical
  fit ~84%, full pp.309-384 census, outliers in-file, demi-human PC-THACO
  carve-out p.310); plus_bump is next-DIE not next-bracket (7+3→13, FG&G
  p.309) — **it bit AGAIN in the save-matrix pin** (asserted next-bracket,
  red run corrected it); p.309's own text extends the bump to saving throws.
- **Ride-along literals must be CONTIGUOUS:** integrity's doc-claims match
  exact phrases — a line-wrap inside "308 law ids across 8 families" reads
  as a missing claim. Keep the load-bearing phrase on one line.
- **Workflow audits on this rig:** server-side load-shed at full fan-out —
  waves of ~3, sonnet refuters, a dead verifier is NOT a refutation, bank
  partials + surgical re-run of only dead work; `resumeFromRunId` re-bursts
  at full cap (crash recovery only). Journal logs successes only — diagnose
  failures from failure signals, trust Meme's observed agent status.
- **Docket-first held:** 21/22 snapshot shas identical post-workflow (only
  the pre-declared usage-counter advisory moved). The audit caught its own
  scaffolding bugs — refute-first works; keep 2 independent refuters on
  data-changing lanes.
- **Ledger sha law:** `setdefault` defaults land BEFORE `_canonical_sha`
  (kind-before-sha, pinned test); pre-fix rows verify under either
  derivation — stored shas are submission-time content-addresses, never
  rewritten.
