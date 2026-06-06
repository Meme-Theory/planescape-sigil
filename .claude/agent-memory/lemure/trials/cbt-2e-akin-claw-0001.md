# Combat Record — A'kin's claw vs an AC 5 intruder (the executed triangle)

| field | value |
|---|---|
| id | `cbt:2e:akin-claw:0001` |
| date | 2026-06-05 |
| view | 2e |
| stamps | law_version `018b2eed42e9afe7` · engine_version 1 |
| session | `triangle-cross-validation-014128` — commitment `014128ef…` published before any die (full hex recorded in `build/family/cross-validation.md` §2) |

## Combatants

| name | side | ref / source | key values (asserter per value) |
|---|---|---|---|
| A'kin, the Friendly Fiend | A | `npc:uncaged:a-kin`, admission `e3a9694cbb0e56e3` (Uncaged p.9 — official, cite-only) | THAC0 7 · claws 1d4/1d4/2d6 · poison rider (all: admitted envelope) |
| intruder | B | fixture (asserter: trial) | AC 5 — value chosen for the exercise, honestly labeled |

lawfulness badges: A'kin served pre-G1 fix passed 2/skipped 3 (vacuous-lawful
demo — the finding that BECAME gap G1); post-fix adapter runs all 5 checks.
No-witness discipline applies to the original badge.

## Conventions in force

- pack `2e` (overlays: none)
- crit law: **none** — nat 20 auto-hits, no damage effect (RAW 2e)
- initiative: not rolled — single contested swing · house rules: none

## Rounds

### Round 1

| step | actor → target | roll_id | faces | result |
|---|---|---|---|---|
| claw attack | A'kin → intruder | `rol:triangle-cross-validation-014128:00001` | nat **20** | AUTO-HIT per FG&G |
| claw damage | A'kin → intruder | `rol:triangle-cross-validation-014128:00002` | 1d4 → 4 | 4 damage |

- derivation: THAC0 7 − total 20 = hits AC **−13** vs target AC 5 — hit on the
  math AND by the nat-20 auto rule; both shown, the auto rule governs
- riders applied: poison claw — cumulative permanent −1 on the foe's attack
  rolls unless bless / neutralize poison / slow poison (quote held by docket
  `raw_quotes`, sha `bdc3ca3b4b95fbbd`, loc: admitted envelope
  `npc:uncaged:a-kin` + admission `e3a9694cbb0e56e3` + uncaged:p9 — reproduced
  via the store, not pasted from the scan)

## Damage & effects ledger

| target | amount/type | roll_id | composition | hp after (asserter) |
|---|---|---|---|---|
| intruder | 4 (claw) | `…00002` | base only | unknown − 4 (fixture has no hp total) |

## Rulings

`rul:vnv:triangle:akin-claw:001` (scope `table:vnv`, confidence 0.95) —
**ADOPTED**: nat 20 auto-hits per FG&G; 4 claw damage; poison rider applies.
**REJECTED**: "treat nat 20 as critical double damage" — *why*: RAW 2e has no
critical damage effect; Modron's convention-pack note credited as the law
source. A crit house rule would be its own docket.

## Law cited

| claim | source | quotable? |
|---|---|---|
| attack roll & THAC0 procedure | FG&G ch.8 p.65 | verbatim ok |
| nat 20 auto-hit, no crit effect | FG&G ch.8 + 2e pack `crit_effect: none` | verbatim ok |
| monster THAC0 brackets | `data/law/thac0_2e.json` (80-pair FG&G harvest) | code-true law |
| poison rider | Uncaged p.9 via admitted envelope | **cite-only source** — reproduced via docket/envelope only |

## Verification

verify(`triangle session`) → PASS (2/2) · seed revealed · commitment
independently recomputed: VERIFIED (recorded in
`build/family/cross-validation.md` §2) · fiat rows: 0

## End state

Intruder: hit once, 4 damage taken (no hp total — fixture), **poison rider in
force**: cumulative permanent −1 to-hit until bless / neutralize poison / slow
poison. A'kin: untouched, smiling, wrapping your purchase. PENDING: none.
