# Rule & effect substance handoff — Mimir → Mechanus / Modron

**Date:** 2026-06-06 · **From:** Mimir session · **Ruling (Meme):** *"Mimir needs to know
who uses what and when, but Mechanus is the coordinator and Modron is what applies the
values to the rolls."*

The lane law, applied to the remaining dimension substance:

| lane | owns | gets from this handoff |
|---|---|---|
| **Mimir** | who / what / where / when — identity nodes + pointer edges | `exhibits` / `keyed_to` / `used_at` edges binding places to law ids and rollable ids; thin identity nodes (a spell's NAME and who casts it where; a table's existence and where it's used) |
| **Mechanus** | what **governs** — page-cited law tables (`mechanus/data/law/*.json`, content-addressed `law_version`) | the planar conditions law below (§M) |
| **Modron** | what the dice **apply** — convention packs, check kinds, rollables, modifiers (sourced!) | the numeric/rollable substance below (§D) |

Every item carries its witness (component + reflow pages, all already distilled under
`build/`). Per sibling etiquette this document only *offers*; Mechanus and Modron accept
or amend **in their own docs**, and Mimir mints pointer edges only after their ids exist.

---

## §M — to MECHANUS (governing law, page-cited)

- **M1 · Per-plane magical-conditions law** (school/sphere alterations, what functions where).
  Witness: every booklet's `MAGICAL CONDITIONS` section — planes-of-law ii pg6-7, iii pg6,
  iv pg6, v pg6, vi pg5; planes-of-chaos pg7 (TABLE II "School Alterations by …" — the *law*
  half; its dice deltas are D2), pg19 (Abyss), pg41 (Arborea), pg70 (Limbo), pg92
  (Pandemonium), pg108 (Ysgard); conflict liber benevolentiae/malevolentiae per-plane
  condition sections. Suggested shape: law table keyed `(plane, school|sphere) → functioning
  rule`, page-cited per row. **Mimir keeps:** `plane —exhibits→ <law-id>` edges.
- **M2 · Spell-key / power-key law** (what unlocks magic, per plane). Witness: `SPELL KEYS` /
  `POWER KEYS` sections — law-ii pg8, law-vi pg6, chaos pg21/42/73/94/110, conflict both
  libers. **Mimir keeps:** named physical keys as item nodes with `keyed_to` edges.
- **M3 · Seals & wards** (portal-blocking law: planar wards, surelock). Witness: law-ii pg7;
  In the Cage p8 names the same law (already witnessed in Mimir's portal pour).
- **M4 · Planar priest law** (sphere access / granted powers by distance-from-power).
  Witness: conditions sections passim in all eight components.
- **M5 · Plane-environment governing rules** — Celestia's purity strictures (law-vi pg4-5),
  Pandemonium's madness law (chaos pg84-92, "Everyman's Madness" pg91), the Gray Waste's
  hope-drain / **the Wasting** (malevolentiae ~pg52-54), Carceri/Gehenna environment law
  (malevolentiae conditions). The *check mechanics* are D5/D6.
- **M6 · New planar spells (mechanics text)** — Cubehopper (law-ii pg8), Shield of the
  Archons (law-vi pg8), Lysander's Kaleidoscope (law-ii pg24); a full sweep will find more.
  Doubles as CONVERSION.md 2e-side corpus. **Mimir keeps:** spell identity nodes
  (name, `castable_by`, `keyed_to` plane) — no mechanics.
- **M7 · Inner Planes survival law** (suffocation, pressure, temperature, elemental
  protection). Witness: planescape-2634-inner-planes — 38 saving-throw pages, suffocation
  pg62/87/123, hazard mentions across 33 pages. Joint future pour (the book itself isn't
  entity-poured yet).
- **M8 · Garnish/legal color with mechanical teeth** from In the Cage (execution law p21,
  Harmonium patrol procedure p19) — *only* the parts that govern play; the rest stays
  Mimir prose.

## §D — to MODRON (applied values: packs, check kinds, rollables, modifiers)

- **D1 · Limbo's tables** — TABLE III Terrain Maintenance (chaos pg68), TABLE IV Alterations
  in Limbo (pg70), TABLE V Spellcasting in Limbo (pg72) → `roll_table` specs + chaos-shaping
  check kinds (Int/Wis-based, per the chapter). **Mimir keeps:** table identity + `used_at`
  plane:limbo.
- **D2 · School-alteration numeric deltas** (failure %, surge dice) → modifier-registry
  entries with `source {kind: mechanus, ref: <M1 law-id>}` — the established asserter seam.
- **D3 · Per-plane encounter tables** (chaos pg7 Table I NPC chart + per-chapter encounter
  charts; both conflict libers) → `encounter_rolls` / rollables.
- **D4 · Random-portal checks** — the Slags vortex "on a roll of 1-3, the vortex acts as a
  portal to the Prime" (In the Cage p115 — Mimir's portal node already carries the witness),
  Hive ooze-portal appearance/duration (p105), shifting-portal schedule dice where stated
  (p8-9) → check kinds in the 2e pack overlay.
- **D5 · Wasting progression + hope-drain rolls** (malevolentiae ~pg52-54) → disease-progression
  check kind; cites M5.
- **D6 · Pandemonium madness checks + wind effects** (chaos pg84-92) → check kind + modifiers;
  cites M5.
- **D7 · Inner Planes damage-per-round + hazard dice** (2634: damage-per-round on 9 pages —
  pg15-17, 54, 71, 74, 87, 105…) → damage specs consumable by `roll_damage`; cites M7.
- **D8 · Acheron cube drift/collision mechanics** where dice-stated (law-ii pg4-5).
- **D9 · Minor city tables** — Yscoppel's Mounts price/carry table (In the Cage p111-114
  region) if wanted as a rollable/lookup; Harmonium patrol response if dice-shaped (p19-20).

## Registry effect (Mimir's side, recorded in DIMENSIONS.md)

- `dim:rule` and `dim:planar-trait` become **pointer dims**: nodes carry name + witness +
  the Mechanus `law_id` once minted; the mechanics live in Mechanus. The `exhibits` edge is
  the join.
- `dim:table` → substance to Modron rollables; Mimir holds identity + `used_at` only.
- `dim:hazard` → split: hazard **existence/where** = Mimir node; governing rule = M7;
  dice = D7.
- `dim:spell` / `dim:psionic` → identity + who/where in Mimir; mechanics = M6 lane.

## Open questions (numbered, per etiquette)

- **Q1 → Mechanus:** accept M1-M8 as law-table families? Propose id scheme
  (`law:planar-conditions:<plane>:<school>`?) so Mimir can mint `exhibits` edges.
- **Q2 → Modron:** D1-D9 as a `2e` pack overlay + rollables drop-in? Confirm whether
  plane-scoped check kinds ride `data/conventions/2e.json` or an overlay pack.
- **Q3 → both:** the D2 seam (Modron modifiers citing Mechanus law ids) is the model for
  every numeric delta in §D — confirm and we standardize.
