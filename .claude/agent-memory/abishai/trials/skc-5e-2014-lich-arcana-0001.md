# Skill Check — Lich identifies a planar sigil (Arcana, the waiver star)

| field | value |
|---|---|
| id | `skc:5e-2014:lich-arcana:0001` |
| date | 2026-06-05 |
| view | 5e-2014 |
| stamps | law_version `018b2eed42e9afe7` · engine_version 1 |
| actor | Lich — SRD 5.1 p.325 (print; no handbook entity — 5e pour pending, source honestly the SRD itself) |
| check | `check` — Intelligence (Arcana) |
| target | DC 15 — asserter: `mechanus.dc_suggest(medium)`; law: SRD 5.1 p.77 "Typical Difficulty Classes" (CC-BY-4.0) |
| state | flat |

## Modifiers

| name | value | source {kind: ref} |
|---|---|---|
| Arcana | +18 | core: SRD 5.1 Lich p.325 — **witnessed waiver** (`known_deviations.json`): derivation says Int +5 + PB +7 = +12; the print attests +18; print wins WITH the page witness |

## Dice

session `ses:agent-primer-abishai-6da8d5` — commitment
`6da8d5550edb678ba4d7f0a1b7e374557d002b3a58efad2ea881f0ae318d4045` published
before any die fell

| purpose | roll_id | faces | total | sha |
|---|---|---|---|---|
| ability check | `rol:agent-primer-abishai-6da8d5:00003` | `1d20[19]+18` | 37 | `62c961a6c7a40635` |

## Outcome

**SUCCESS** — natural 19, total 37 vs DC 15, margin +22
(pack `5e-2014` success_op `>=`)

## Law

- DC from the ladder, never freehand: `dc_suggest` returned task "Medium",
  DC 15, source "SRD 5.1 p.77 'Typical Difficulty Classes' (CC-BY-4.0)",
  law_version `018b2eed42e9afe7`
- the +18: non-derivable but print-attested — used AS PRINTED with the waiver
  cite. An underived bonus WITHOUT a page witness is refused, not waived
  ("a waiver without a witness is a blindfold").

## Verdict & notes

Pack-mechanical; no ruling needed. Teaching points this trial exists for:
(1) targets name their asserter — here the asserter is a Mechanus tool with a
page-cited law source; (2) modifiers name their source — here core RAW whose
*deviation from derivation* is itself documented law (`known_deviations.json`,
attested_deviations); (3) the same file's `upstream_5e_bits_bugs` rows are NOT
waivers — transcription bugs stay flagged. Rejected reading, preserved: "house-
correct the lich to +12 because the math says so" — rejected *why*: the SRD
print is RAW and the deviation is witnessed; derivation does not outrank an
attested print.

## Verification

verify(`ses:agent-primer-abishai-6da8d5`) → PASS (3/3 recomputed,
session-wide) · seed revealed `206ca7a5…09ae` · commitment independently
recomputed: VERIFIED · fiat rows: 0
