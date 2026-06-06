# Combat Record — Wolf (Pack Tactics) vs Guard, one exchange

| field | value |
|---|---|
| id | `cbt:5e-2014:wolf-bite:0001` |
| date | 2026-06-05 |
| view | 5e-2014 |
| stamps | law_version `018b2eed42e9afe7` · engine_version 1 |
| session | `ses:agent-primer-abishai-6da8d5` — commitment `6da8d5550edb678ba4d7f0a1b7e374557d002b3a58efad2ea881f0ae318d4045` published before any die |

## Combatants

| name | side | ref / source | key values (asserter per value) |
|---|---|---|---|
| Wolf | A | SRD 5.1 p.393 (print) + `5e-database/src/2014/en/5e-SRD-Monsters.json` (machine mirror) | AC 13 natural · HP 11 (2d8+2) · Bite +4, 2d4+2 piercing + DC 11 Str prone rider · Pack Tactics |
| Guard | B | SRD 5.1 p.399 (print) + same mirror | AC 16 (chain shirt + shield) · HP 11 (2d8+2) |

lawfulness badges: Wolf — `is_lawful` → **lawful: true**, 9 checks passed / 3
skipped (saves/conditions/senses empty — skipped, not passed: no witness),
law_version `018b2eed42e9afe7`. Guard — not badged this trial (single-target
exercise; noted, not silently omitted).

## Conventions in force

- pack `5e-2014` (overlays: none disclosed by `conventions`)
- crit law: **double_dice** — dice doubled, never modifiers
- initiative: not rolled — single-exchange trial · house rules: none

## Rounds

### Round 1

| step | actor → target | roll_id | faces | result |
|---|---|---|---|---|
| Bite (advantage) | Wolf → Guard | `rol:agent-primer-abishai-6da8d5:00001` | `2d20kh1[18, (7 dropped)]` | total 22 vs AC 16 — **HIT**, margin 6, natural 18 |
| Bite damage | Wolf → Guard | `rol:agent-primer-abishai-6da8d5:00002` | `2d4[3, 3]+2` | **8 piercing** |

- derivation: 18 (kept die) + 4 = 22 vs AC 16; advantage = `2d20kh1` per pack;
  natural read from the KEPT die — 18, so crit law not triggered (noted, since
  a 20 would have doubled the 2d4 to 4d4 and never the +2)
- advantage source: Pack Tactics — "The wolf has advantage on an attack roll
  against a creature if at least one of the wolf's allies is within 5 ft. of
  the creature and the ally isn't incapacitated." (SRD 5.1 p.393, CC-BY-4.0;
  attribution ships if this record ever leaves the project)
- riders: **PENDING** — Bite's prone rider (DC 11 Str save, SRD 5.1 p.393) was
  not contested in this trial; recorded pending, never dropped

## Damage & effects ledger

| target | amount/type | roll_id | composition | hp after (asserter) |
|---|---|---|---|---|
| Guard | 8 piercing | `…00002` | base only (no adds, no wraps) | 11 → **3** (this record, from SRD p.399 print HP) |

## Rulings

none needed — pack-mechanical throughout.

## Law cited

| claim | source | quotable? |
|---|---|---|
| attack total vs AC | SRD 5.1 p.94 (Making an Attack) | verbatim ok (+attribution on ship) |
| advantage machinery | SRD 5.1 pp.76–77 | verbatim ok (+attribution on ship) |
| crit doubles dice only | SRD 5.1 pp.96–97 + pack `crit_effect: double_dice` | verbatim ok |
| Pack Tactics / Bite / AC / HP | SRD 5.1 pp.393, 399 | verbatim ok |

## Verification

verify(`ses:agent-primer-abishai-6da8d5`) → PASS (3/3 recomputed,
session-wide) · seed revealed `206ca7a5…09ae` · commitment independently
recomputed: VERIFIED (sha256(seed) == commitment, checked outside Modron) ·
fiat rows: 0

## End state

Guard: 3/11 HP, standing, **PENDING DC 11 Str save vs prone** (resolve before
any round 2). Wolf: untouched, 11/11. Conditions in force: none yet.
