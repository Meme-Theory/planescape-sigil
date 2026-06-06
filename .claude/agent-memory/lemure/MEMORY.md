# lemure — trial memory (AD&D 2e rules lawyer)

## Protocol

- This file auto-loads (first ~200 lines). Honor the index; Read a full record
  from `trials/` only when the matter at hand touches it.
- After ANY trial: write the full record to `trials/<id>.md` shaped by
  `.claude/templates/{skill-check,combat}-record.md` and bound by
  `.claude/rules/{skill-check,combat}-records.md` (the MUSTs), then add ONE
  index row and (when it taught something) ONE distilled precedent line here.
- ids are monotonic per kind+slug: `skc:2e:<slug>:NNNN`, `cbt:2e:<slug>:NNNN`.
  Never reuse, never backfill.
- Keep this file under 200 lines: records live in `trials/`, never inline.
  Correct a wrong precedent IN PLACE and note the correction — never stack a
  contradiction on top of it.
- Mechanus dockets outrank these notes: a precedent here is a pointer, the
  ledger is the law. When they disagree, the ledger wins and this file gets
  fixed.

## Index

| id | date | kind | subject | outcome | record |
|---|---|---|---|---|---|
| `skc:2e:farrow-acrobatics:0001` | 2026-06-05 | proficiency (roll-under) | Acrobatics, Dex 14, FG&G p.46 | FAILURE by 3 (nat 17) | `trials/skc-2e-farrow-acrobatics-0001.md` |
| `cbt:2e:akin-claw:0001` | 2026-06-05 | combat, single exchange | A'kin claw vs AC 5 — nat 20, poison rider | hit, 4 dmg, rider in force | `trials/cbt-2e-akin-claw-0001.md` |

## Distilled precedents

- **Roll-under margins read target − total**: nat 17 vs Dex 14 = fail by 3;
  check_mod adjusts the TARGET, not the roll (2e pack; FG&G ch.6 entry format
  `Name (class, ability, mod, points)` — FG&G p.46).
- **RAW 2e has no critical damage effect** — nat 20 auto-hits, nothing more;
  a crit house rule is its own docket (`rul:vnv:triangle:akin-claw:001`, the
  rejected candidate with why).
- **THAC0 derivation is always shown**: hits AC = THAC0 − total (A'kin: 7 − 20
  = AC −13); the bracket law + plus-bump lives in `data/law/thac0_2e.json`.
- **Riders ride through stores**: official text (Uncaged p.9 poison) enters a
  record only via the admitted envelope / docket quote with admission_sha —
  never pasted from the scan.
- **Considered-but-inapplicable restrictions get recorded** (Farrow's
  encumbrance check): no witness ≠ doesn't exist.

## Standing cautions

- A 2e statblock served by Mimir carries STRING numerics and descriptor-resident
  `level_hd` — pre-coercion adapters returned vacuous lawful (gap G1, fixed +
  pinned; live server picks it up on `/mcp` reconnect).
- `precedents` FTS chokes on hyphenated terms (F4) — strip hyphens or quote.
- 2e has NO DC ladder; a "2e DC" request is a category error — offer roll-under.
