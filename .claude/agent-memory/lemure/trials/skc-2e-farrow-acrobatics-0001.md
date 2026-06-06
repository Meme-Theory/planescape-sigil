# Skill Check — Farrow tumbles the Great Bazaar stall-rail

| field | value |
|---|---|
| id | `skc:2e:farrow-acrobatics:0001` |
| date | 2026-06-05 |
| view | 2e |
| stamps | law_version `018b2eed42e9afe7` · engine_version 1 |
| actor | Farrow — fixture (asserter: table; sample rogue, Dex 14 — no handbook entity, honestly labeled) |
| check | `proficiency` — Acrobatics (non-combat skill) |
| target | 14 — asserter: fixture Dex 14; check_mod +0 per law: FG&G p.46 |

## Modifiers

| name | value | source {kind: ref} |
|---|---|---|
| none — pack applied check_mod +0 to the target | — | — |

## Dice

session `ses:agent-primer-lemure-e50970` — commitment
`e50970f443f46c604d49a7539c7e2b387bd47a50f715a96e369a5ee9ec80064d` published
before any die fell (seed_phrase ceremony used)

| purpose | roll_id | faces | total | sha |
|---|---|---|---|---|
| proficiency check | `rol:agent-primer-lemure-e50970:00001` | `1d20[17]=17` | 17 | `6356c107959e4b6c` |

## Outcome

**FAILURE** — natural 17, total 17 vs target 14, margin −3
(pack `2e` success_op `<=`; roll-under semantics: margin = target − total, so
success would have been 14 or less — Farrow eats the cobbles)

## Law

- "Acrobatics (Rogue, Dexterity, +0, 1 skill point)" — FG&G p.46 (quotable RAW;
  entry format is `Name (class, ability, check mod, points)`)
- pack note: "nonweapon proficiency: roll-under ability, check modifier adjusts
  the target" — `pipeline/modron/data/conventions/2e.json`

## Verdict & notes

Pack-mechanical; no ruling needed. RAW: FG&G ch.6 non-combat skills are
roll-under-ability with the entry's check mod adjusting the TARGET (not the
roll). Interpretation, labeled: the p.46 encumbrance restriction ("cannot use
this skill if more than lightly encumbered") was considered and found
inapplicable — Farrow carried nothing. A considered-but-inapplicable
restriction is recorded, not silently dropped (no-witness discipline).

## Verification

verify(`ses:agent-primer-lemure-e50970`) → PASS (1/1 recomputed) · seed
revealed `80f9b4d6…5225` · commitment independently recomputed: VERIFIED
(sha256(seed) == commitment, checked outside Modron) · fiat rows: 0
