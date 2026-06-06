# abishai — trial memory (5th Edition rules lawyer)

## Protocol

- This file auto-loads (first ~200 lines). Honor the index; Read a full record
  from `trials/` only when the matter at hand touches it.
- After ANY trial: write the full record to `trials/<id>.md` shaped by
  `.claude/templates/{skill-check,combat}-record.md` and bound by
  `.claude/rules/{skill-check,combat}-records.md` (the MUSTs), then add ONE
  index row and (when it taught something) ONE distilled precedent line here.
- ids are monotonic per kind+slug: `skc:<view>:<slug>:NNNN`,
  `cbt:<view>:<slug>:NNNN` — and the view is ALWAYS declared (2014 ≠ 2024).
- Keep this file under 200 lines: records live in `trials/`, never inline.
  Correct a wrong precedent IN PLACE and note the correction.
- Mechanus dockets outrank these notes: precedents here are pointers, the
  ledger is the law. Disagreement = fix this file.

## Index

| id | date | kind | subject | outcome | record |
|---|---|---|---|---|---|
| `cbt:5e-2014:wolf-bite:0001` | 2026-06-05 | combat, single exchange | Wolf (Pack Tactics adv) vs Guard AC 16 | hit 22 vs 16, 8 piercing, prone-save PENDING | `trials/cbt-5e-2014-wolf-bite-0001.md` |
| `skc:5e-2014:lich-arcana:0001` | 2026-06-05 | ability check | Lich Arcana +18 (witnessed waiver) vs DC 15 | SUCCESS by 22 (nat 19) | `trials/skc-5e-2014-lich-arcana-0001.md` |

## Distilled precedents

- **Advantage is `2d20kh1` and the natural reads from the KEPT die** (18 kept,
  7 dropped → no crit); states cancel to flat, never stack (pack 5e-2014;
  SRD 5.1 pp.76–77).
- **Crit law doubles DICE, never modifiers** (2d4+2 → 4d4+2 on a 20) — noted
  even when not triggered, so the record teaches (SRD 5.1 pp.96–97).
- **DCs come from the ladder, never freehand**: `dc_suggest(medium)` → 15,
  page-cited (SRD 5.1 p.77), law_version stamped. A freehand DC is fiat and
  gets labeled fiat.
- **Witnessed waivers use the print AS PRINTED**: lich Arcana +18 over the
  derived +12, because the page witness exists (`known_deviations.json`);
  the same file's upstream 5e-bits bugs are NOT waivers — they stay flagged.
- **Uncontested riders go PENDING** (wolf's DC 11 Str prone save) — recorded,
  never dropped; the end-state block must make the fight resumable.
- **Badge skips are no witness**: Wolf badged lawful 9-pass/3-skip — the three
  skips (saves/conditions/senses empty) are *unwitnessed*, not passed (G6).

## Standing cautions

- 5e-2014 encounter budgets are REFUSED by license (SRD 5.1 has no budget
  math); `encounter_budget` serves 2024 only (SRD 5.2.1 p.202) — the refusal
  is the tool working.
- Sage Advice is never RAW here — not ingested, not freely licensed; label any
  user-supplied designer ruling as interpretation.
- SRD quotes that leave the project ship the attribution block
  (`mechanus.attribution`).
- 2024 questions start at the Rules Glossary (SRD 5.2.1 pp.176–191) — defined
  terms ARE the law.
- `precedents` FTS chokes on hyphenated terms (F4) — strip hyphens or quote.
