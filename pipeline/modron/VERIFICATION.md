# Modron V&V Campaign — 2026-06-05 (live wire)

Comprehensive verification & validation of the running `modron` MCP server,
executed over the actual stdio transport (not the test harness). 43 live
checks across six phases (the verdict table is the count of record). **Three
real defects found, fixed, and pinned by regression tests** — which is the
campaign doing its job.

Suite after campaign: 140 passed (143 post-fixes; 171 after the rule-effect
handoff; **185 after audit round 2; 195 after the PWH acceptance round — see
below**). Ledger evidence:
`build/modron/rolls.db` (sessions `ses:vnv-campaign-e50023`,
`ses:friendly-fiend-shakedown-f41bfe`). Fixtures: `build/modron/vnv/`.
*(Header counts corrected 2026-06-06 per audit F-2-verification-claims.)*

## Verdict table

| # | Check | Expected | Observed | Verdict |
|---|---|---|---|---|
| **P0 — protocol & registry** |||||
| 0.1 | `conventions()` lists views | 2e, 5e-2014, 5e-2024 | exact | PASS |
| 0.2 | full 2e pack disclosure | procedures + `_overlays` visible | full, overlays `[]` disclosed | PASS |
| 0.3 | provisional data self-declares | reaction bands flagged | `provisional: true` + confirm-vs-FG&G note | PASS |
| 0.4 | registry search by view | 5e mods only, sources shown | 17 rows, all sourced; elven-accuracy self-flags non-SRD | PASS |
| 0.5 | `parse_expr` normal form | stable, groups listed | `adv(1d20+7)+2d6!!+4d6dl1` round-trips | PASS |
| **P1 — math conformance (independent ground truth)** |||||
| 1.1 | 2d6 pmf | triangle, P(7)=6/36 | exact (0.166667) | PASS |
| 1.2 | 4d6kh3 mean | 12.244598765… | 12.244598765432098, method exact | PASS |
| 1.3 | adv(1d20) | μ=13.825, P(20)=39/400 | 13.825, 0.0975 | PASS |
| 1.4 | GWF 2d6ro<3 mean | 25/3 = 8.3333 | 8.3333… | PASS |
| 1.5 | 1d6! mean | 4.2, honesty flag | 4.2, method `exact-truncated` + note | PASS |
| 1.6 | crit(2d8+5) under 5e law | μ=23 (4d8+5) | 23.0 | PASS |
| 1.7 | 30d20kh3 | MC, flagged estimated | `monte-carlo`, 100k samples, "estimated" note | PASS |
| **P2 — fairness protocol (the core claim)** |||||
| 2.1 | commitment from phrase, pre-computed LOCALLY before server saw it | `e5002326…b151f68` | server returned identical commitment | **PASS — derivation = spec** |
| 2.2 | 7-roll battery on committed stream | counters sequence under parallel calls | 00001–00006 + fiat, no gaps | PASS |
| 2.3 | mid-flight `verify(session)` | PASS, seed hidden | PASS, `seed_revealed: false` | PASS |
| 2.4 | close → reveal | sha256(seed)==commitment | verified locally | PASS |
| 2.5 | **clean-room recompute**: independent reimplementation from MODRON.md §3 text only, replaying `rolls.db` | every face matches | **21/21 faces across 6 rolls ALL MATCH**; fiat row excluded by label | **PASS — gold standard** |
| 2.6 | phrase derivation documented | seed==sha256("modron:seed:"+phrase) | verified locally | PASS |
| **P3 — edition semantics, live** |||||
| 3.1 | adv+dis+bless | cancel to flat, all mods recorded | `1d20+1d4+7`, cancel note | PASS |
| 3.2 | the full rogue stack (adv+EA+halfling+reliable+guidance) | upgrade→3d20, reroll+clamp on all three | `3d20kh1ro1min10+1d4+8`; two clamped 10s dropped, 14 kept | PASS |
| 3.3 | barbarian crit stack (GWF+brutal+vuln) | brutal die inside the ×2 wrap | pre-fix: `…*2+1d12` escaped; **post-reconnect rerun: `(2d12ro<=2+4d6ro<=2+4+1d12)*2`** | **FAIL → FIXED → RERUN PASS** (D1) |
| 3.4 | death save | vs fixed 10, nat-1 flagged | fumble + law note surfaced | PASS |
| 3.5 | 2e THAC0 w/ mods | target=thac0−ac, hits_ac derived | 13+2=15 vs 9, hits AC −8 | PASS |
| 3.6 | 2e roll-under (ability/proficiency/thief/morale) | ≤ semantics, target math | proficiency target 14−3=11, margins signed right | PASS |
| 3.7 | 2e initiative | low-wins declared | `order: asc` + note | PASS |
| 3.8 | recharge 5–6 | d6 vs threshold | 2 vs 5 → fail | PASS |
| **P4 — real data integration** |||||
| 4.1 | `rollables("a-kin")` bare-name | resolves build envelope | 12 specs, HP crosscheck ok | PASS |
| 4.2 | `rollables("black-marian")` | second real envelope compiles | THAC0 18, morale steady(16→12), OCR `ld6+2`→`1d6+2` prose find | PASS |
| 4.3 | doctored 5e block (avg 30 vs 4d8+8; 19 vs 1d6+1) | MISMATCH flags | both surfaced in `lawfulness_flags` | PASS |
| 4.4 | inline JSON over the wire | accepted | pre-fix: arrived as string, rejected; **rerun: `source: inline`, both MISMATCH flags fire; inline table rolled a natural 100 → `97-00` entry resolved (the `00`→100 edge, confirmed live)** | **FAIL → FIXED → RERUN PASS** (D2) |
| 4.5 | gappy table ×5 | gap [91,96] reported BEFORE rolling; entries resolve | exact; warning attached | PASS |
| 4.6 | encounter from creature-ref, default doctrine | plan with default wandering check | pre-fix: **KeyError 'expr'**; **rerun: plan emits check/hp(12d8+24)/surprise/reaction/initiative×2/morale-armed(16); executed run rolled 2 vs `<=1` → honest stop, batch ledgered** | **FAIL → FIXED → RERUN PASS** (D3) |
| **P5 — honesty & refusals** |||||
| 5.1 | inline mod, no source | refuse, name the law | "every modifier names its asserter" | PASS |
| 5.2 | 5e bless on 2e | refuse, name the views | exact | PASS |
| 5.3 | unknown check kind | refuse with menu | full kind menu listed | PASS |
| 5.4 | adv state without view | refuse, ask for view | exact | PASS |
| 5.5 | save without dc | roll, report natural, NO invented verdict | "no success verdict" note | PASS |
| 5.6 | `4d6d1` | refuse with dl1/dh1 guidance + caret | exact, caret at pos 3 | PASS |
| 5.7 | `1001d6` | guardrail refusal | exact | PASS |
| 5.8 | roll on closed session | refuse | "session … is closed" | PASS |
| 5.9 | `define_modifier` bad op | refuse, list known ops | exact | PASS |
| 5.10 | house mod roundtrip | define → disclosed overlay → applies live | `spire-proximity` → `1d20-2+1`, both mods recorded | PASS |
| 5.11 | fiat ledger filter | `history(purpose=fiat)` | 2 rows, both `method: fiat` | PASS |

## Defects found & fixed (each pinned by a regression test)

| id | defect | root cause | fix | pinned by |
|---|---|---|---|---|
| **D1** | added dice (brutal critical) escaped vulnerability's ×2 wrap | `compose()` applied total-wraps before additive terms; 5e RAW applies resistance/vulnerability **after** all other modifiers | phase order swapped: adds → wraps (`modifiers.py`) | `test_wraps_apply_after_adds_5e_raw` |
| **D2** | inline JSON entities/tables/encounters rejected over MCP | transport delivers inline objects as **strings**; store seam only accepted dicts | JSON-string door in `store.find_entity` + encounter handler | `test_inline_json_as_string_over_the_wire` |
| **D3** | creature-ref encounters with default doctrine crash (`KeyError 'expr'`) | pack `check_default` uses the pack idiom `roll`; `encounter_plan` read `expr` only | accept both keys (`rollables.py`) | same test (default-doctrine path) |

> **Post-fix wire confirmation complete (2026-06-05, after `/mcp` reconnect):**
> 3.3, 4.4, and 4.6 all rerun PASS on the live server — composed expression,
> inline-string acceptance, and default-doctrine encounter (plan + executed)
> observed exactly as asserted. Suite: 140 green.

## Boundaries observed (documented behavior, not defects)

- **GWF scope** `damage` = all non-d20 dice — it rerolls sneak-attack dice too.
  RAW says weapon dice only; a finer scope (`first_group`) is a future data
  primitive. Interpretation stays with the asserter (MODRON.md §1).
- **sneak-attack as a modifier doesn't double under `crit=true`** — adds compose
  after the crit transform. The registry note says so and says what to do
  (put the dice in the base expr). Honest, documented, deliberate.
- **Black Marian's alignment-split damage** (`1d6+1 to nonevil, 5d4 to evil`) —
  only the first expression compiles; the 5d4 variant rides in `raw`. Multi-clause
  damage is a v1.1 compiler nicety.
- **Prose percent sweep** needs "chance"/"in lair" context — "75% of the time"
  is skipped. Tightness chosen over false positives; widen with evidence.
- **Clean-room recompute boundary**: replay covered plain/keep/repeat rolls
  (21 faces). Reroll/explode chains share the same draw stream (unit-tested)
  but weren't in the live battery.

## What was proven, in one breath

The notation is a real grammar with guardrails; the math is exact where it
claims exact and flagged where it estimates; the editions are data and behave
per their packs; modifiers compose lawfully and name their asserters; the
compiler reads the real corpus and flags transcription smells; refusals are
specific and instructive; and the fairness protocol survives the strongest
test we can mount — **a commitment computed before the server ever saw the
phrase, and every ledgered face reproduced by an independent implementation
written from the published derivation alone.** The dice are lawful.

---

# Round 2 — the Great Audit (2026-06-06)

Docket-first mass review of everything Modron is: ~100 data rows vs their
witnesses (FG&G/SRD text caches quotable; official-scan reflow cite-only),
the whole ledger replayed, an independent PMF enumerator vs `analysis`, the
87-entity fleet compiled, four docs vs the code. Record:
`build/modron/review/` (PLAN.md · integrity-report.json · chunks/ ·
correction-docket.md · run-summary.md · workflow-results.json).

**Shape:** mechanical integrity pass (0 hard) → 18 review chunks →
refute-first adversarial verify (2 independent refuters per data-changing
finding) → two resolution courts (Mechanus law ids; FG&G cites), each
double-refuted → deterministic merge. **101 findings → 93 deduped →
88 VERIFIED · 5 refuted · 0 under-verified; courts 22/22.** Store snapshot
byte-identical across the audit (nothing mutated until adoption).

**Adopted and applied (correction-docket, all lanes):**
- **L1 packs** — 2e ability/proficiency gain FG&G's nat-1/nat-20 auto rules;
  **reaction is now FG&G Table 10.7's 2D disposition matrix** (`bands_by`,
  default column disclosed; flat provisional bands condemned); initiative
  drops weapon-speed adds (FG&G: ties only); every 2e kind carries its
  fgg-text cite; 5e kinds carry SRD page cites; 1/2 HD = 2d2 (printed 283);
  2e-planescape law refs upgraded to minted Mechanus ids (+ miniflux and
  styx-memory refs added).
- **L2 modifiers** — all six core-2e "(FG&G cite pending)" refs resolved to
  quoted pages; all five planescape mechanus refs upgraded to minted law ids.
- **L3 rollables** — IOOfo adjudicated **10% CONFIRMED** (flag retired);
  magma chart restored to the print's **seven** natural-AC bands; Scald
  relabeled to Smoke (its actual chapter); ice extreme-cold tier minted;
  slags trio book page corrected 115→118 + paraphrase reworded;
  acheron witness widened p4-5; `lkp:2e:pandemonium:everymans-madness`
  minted (56 quirk names). Registry 34 → **36**.
- **L4 code** (each pinned): MC flat-creature adapter (`_statblock_of` — 16
  creatures now compile fully; fleet 440→502 specs); class-HD ladder per
  FG&G (rogues/wizards cap 10; `ILL` specialist; multiclass and unparseable
  class codes flag loudly, never silent); **analysis cs/cf now counts kept
  NATURALS via a joint (natural, value) distribution** (engine was right,
  analysis was wrong); `verify_session` sweeps ALL rolls (the old
  `history(limit=500)` cap could PASS a long night unchecked) + counter
  cross-check; bare `roll()` discloses split-purpose double-fire; morale
  band-names emit visible flagged specs; 0-level accepts both glyphs;
  `parse_hd` takes explicit printed dice; prose sweep guards the
  ability-array false-positive class; `_validate_effects` fills placeholders
  with a lawful die size.
- **L5 docs** — §3 derivation names byte order; §7 table now lists all 17
  tools; README pointer fixed; these header counts corrected.
- **L6 filed to siblings** — 20 findings recorded for Mimir (stat-shifted
  creatures, fractional attack rates, morale OCR wounds, the hp-roster
  delta: Parakk derives) and Mechanus (F4/F6 reaffirmed). Not applied here.

**Gates after apply:** suite **185 passed** (171 + 14 audit regressions) ·
integrity **0 hard · 0 soft** · math fixtures **49/49** (the enumerator and
`analysis` now agree everywhere) · ledger replay **50/50** · pending refs
**1** (the M7-parked ash-pocket note — held by law until TSR 2634 pours) ·
**`tests/smoke_server.py` minted: 18/18 through the exact configured py.exe
spawn** (Modron was the last sibling without a stdio smoke). The dice are
still lawful — and now the books they cite are, too.

## Round 3 addendum — the PWH acceptance round (2026-06-06, same day)

Handoff §PWH (Q5 + D10/D12/D13) + the Lane-E hope-drain remnant, accepted and
implemented (MODRON.md §9 carries dispositions; §11 the ruling). What changed:
`hope_drain` + 8 planar-NWP check kinds (printed modifiers baked via
`vs_template`); registry 36→47 (4 D13 item d100s · 3 tiefling chargen d100s ·
3 racial lookups · planology fortune); integrity gained the PWH
`REFLOW_MAP` row — new-entry witness pages now RESOLVE and ride the shingle
court (which convicted 7 of this round's own strings; re-worded to 0 the same
run: the cite-only law works on its author).

**Gates after the round:** suite **195 passed** (185 + 10 acceptance pins) ·
smoke **18/18** (re-run after data changes) · integrity **0 hard · 0 soft**
(47 rollables · 15 setting kinds · census pins moved WITH dated comments) ·
pending refs **1** (M7 — Mechanus's Q6 pour observed IN FLIGHT, uncommitted;
upgrade imminent) · **uncage pin DEFERRED, deliberately**: the manifest is not
re-pinned over a sibling's mid-round law state; Mechanus's post-pour pin
captures this round's two data files. D11 stays BLOCKED(Q4/M9), untouched.
