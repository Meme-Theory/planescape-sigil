# AD&D → 5e conversion: prior art survey — 2026-06-05

**Question:** what conversion tools/schemas already exist before Mechanus builds its
conversion engine (MECHANUS.md §5)? **Method:** targeted web sweep + primary-source
reads; official PDF poured to the corpus and read in full.

## 1. Verdict

1. **Official law exists, is thin, and hasn't moved since 2015.** WotC's
   *Conversions to 5th Edition D&D* v1.0 is 4 pages, "more art than science" by its
   own admission, with exactly ONE hard formula block (quick-conversion, p.4 —
   extracted in §3). The 2024 DMG added **no** conversion guidance (appendices are
   lore + maps). Poured to `content/official/_free/DnD_Conversions_1.0.pdf`
   (sha256 `fe1212b80eafbe38…`, 4pp, "personal use only" license — local-only,
   cite-only, same posture as the purchased corpus).
2. **Community schemas are richer than the official one.** The densest free schema
   is the petersgiles gist (saves-category mapping, HD-by-size, damage step-ups,
   intelligence-rating→score table, speed formula, MR→trait, morale dropped,
   2e-XP→CR estimator) — itself descended from WotC's old 2e→3e Conversion Manual
   and ENWorld lore. Schools disagree on basics (§4): AC `19−` vs `20−`, THAC0
   recalculate-vs-translate-vs-keep.
3. **No one ships machine-readable conversion law.** Tools are thin calculators
   (thaco-converter), closed AI SaaS (LorePanic: OCR+AI, markdown out, no published
   ruleset, no API), or prose guides (CMT, 80+ modules, method embedded per-guide).
   The Foundry 2e systems carry 2e data schemas (thelensrpg's is Unlicense/public
   domain) but no 5e bridge. **Conversion-law-as-data with provenance does not
   exist in the wild — that lane is open and it's ours.**
4. **Answer keys exist for calibration.** PAitM (owned — THE 2e→5e key), Goodman
   Games OAR (licensed 1e→5e with a "Creature Log" per book; purchasable),
   CMT guides (PWYW), and — free and already on disk — **FG&G bestiary ↔ SRD 5.1
   same-name monsters** (wolf, ghoul, lich, ogre…), the same harvest pattern that
   built `thac0_2e.json`.

## 2. Catalog

| artifact | kind | what it gives | license posture | steal? |
|---|---|---|---|---|
| [WotC *Conversions to 5e* v1.0 (2015)](https://media.wizards.com/2015/downloads/dnd/DnD_Conversions_1.0.pdf) | official law | quick-conversion formulas (p.4), PC mapping doctrine, treasure constraints | free download, personal-use-only; **poured** `content/official/_free/` | formulas → `convert` law table, page-cited |
| [petersgiles gist: 2E→5E guidelines](https://gist.github.com/petersgiles/ae202f22b007749f3a40c3ac52e70b55) | community schema | saves mapping, HD-by-size, damage step-up, Int-rating table, speed, MR→trait, XP→CR | public gist | the saves/ability tables, as *candidates* checked against pairs |
| [Methods & Madness O5R (2018)](http://methodsetmadness.blogspot.com/2018/07/o5r-converting-tsr-d-monsters-to-5e-d.html) | contrarian method | run 2e stat-line AS-IS: bonus-to-hit = HD, max HP, save DC = bonus+10 | blog | the third conversion *profile* (preserve, don't restate) |
| [thaco-converter (GitHub)](https://github.com/DontBlink93/thaco-converter) | tool | `20 − THAC0` / `20 − AC` calculator | OSS | nothing (formula conflicts with official 19−; both rows go in the table) |
| [LorePanic converter](https://lorepanic.com/blog/dnd-converter) | AI SaaS | OCR→auto-detect edition→5e markdown; flags ambiguities | closed, free tier | proof of demand; zero provenance — the anti-pattern we refuse |
| [Classic Modules Today](http://classicmodulestoday.com/modules-conversion-list/) | guide series | 80+ module conversion guides; map-to-existing-5e-monster doctrine | DMs Guild PWYW (site cert expired) | the map-to-existing-first doctrine (= Mimir nearest-match before statblock synthesis) |
| [Goodman Games OAR diary](https://goodman-games.com/blog/2020/06/02/designers-diary-the-process-of-converting-a-classic-adventure-into-an-original-adventure-reincarnated/) | licensed practice | "Creature Log" (every converted stat + its source), minimal-text-alteration doctrine | commercial (diary bot-walled, 403) | the Creature Log IS a docket ledger — we already have one |
| [Blog of Holding business-card series](https://www.blogofholding.com/?p=7338) ([2024 MM](https://www.blogofholding.com/?p=8469)) | regression analysis | 5e stat-by-CR curves fitted from the actual MMs, 2014 + 2024 | blog | cross-check for OUR fleet-derived curves |
| [thelensrpg/dnd2e-foundry](https://github.com/thelensrpg/dnd2e-foundry) | 2e data schema | Foundry actor schema w/ THAC0+saves (`template.json`) | **Unlicense** (public domain), WIP | schema comparison only — Mimir's envelope already richer |
| [5etools homebrew repo](https://wiki.5e.tools/index.php/Homebrew_Repository) | community JSON | 5e-side homebrew JSON schema + scattered TSR-era conversions | community | already mirrored at `content/fan/5etools-homebrew` |
| WotC 2e→3e Conversion Manual (1999) | ancestral official | the lineage the community tables descend from | old free official | provenance footnote only |

## 3. The official law, extracted (cite: Conversions v1.0, PDF pp.)

**Quick conversion of 1e/2e monsters (p.4) — the only formulas WotC ever shipped:**
- AC = **19 − old AC**, cap 22
- attack modifier = **HD/2 + 2**, cap +12 ("ignore THAC0" is implicit — THAC0 never appears)
- save DC = **8 + HD/2**, cap 20
- creature's own checks/saves: **HD/2 + 2** when it "should be good at it", else 0 or a penalty
- groups of **≥7 monsters**: evaluate for reduction (esp. parties < 5th)

**Careful conversion (pp.3–4):** rebuild with 5e pieces, keep the HD count, clamp
abilities 3–30, then set CR via the DMG's *Monster Statistics by Challenge Rating*
table and adjust. **License snag:** that table — and the trap tables the doc leans
on — is 2014 DMG ch.9 material, **absent from SRD 5.1/5.2.1** (same family as the
refused 2014 encounter budgets). The official careful path routes through tables we
cannot hold. **Counter-move:** rederive stat-by-CR targets by regression over the
334-monster SRD 5.1 fleet we already audit with `is_lawful` (+ SRD 5.2.1 set for
2024 targets), cross-checked against Blog of Holding's published fits. Licensed,
content-addressed, ours.

**PC side (pp.1–3):** levels convert 1:1 (cap 20; 4e × ⅔); 2e kits / secondary
skills / best NWPs → **backgrounds**; exceptional STR 18/xx → 18; infravision →
darkvision (same range); resistances lose numeric values; racial micro-modifiers
(<±4) dissolve into advantage/disadvantage or nothing; spells: nearest existing
match first, DMG creation second; magic items: swap for existing, bonus cap +3
(+4 legendary); treasure re-rolled on 5e hoard tables rather than translated.

## 4. Community consensus & conflicts (candidate rows for the law table)

| mapping | official (2015, p.4) | petersgiles gist | thaco-converter | O5R |
|---|---|---|---|---|
| AC | 19 − AC, cap 22 | 19 − AC (dragons; Russ Morrissey) | 20 − AC | as-written (bracketed) |
| attack | HD/2 + 2, cap +12 | recalc: ability mod + PB | 20 − THAC0 | = HD |
| save targets | DC 8 + HD/2 | DC 8 + PB + ability | — | DC = bonus + 10 |
| save categories | — | **PPDM→Con · RSW→Wis/Dex · PP→Con/Wis · Breath→Con/Dex · Spell→Wis** | — | best two saves get the bonus |
| HP | (careful path: keep HD count) | HD-by-size dice + Con/die, +1–2 dice by size | — | maximum possible HP |
| damage | — | step-up table (1d6→1d8 or 2d6 …), size escalators | — | always max damage |
| speed | — | ≤12: ÷3 ×10; >12: ×2 (imperfect — Move 12 → 40, but 5e human = 30; calibrate, don't trust) | — | bracket value as-written |
| Int ratings | — | Semi 2–4 · Low 5–7 · Avg 8–10 · Very 11–12 · High 13–14 · Excep 15–16 · Genius 17–18 | — | — |
| morale | silent | **dropped** | — | **kept** |
| MR % | — | becomes a trait | — | as-written |
| XP→CR | — | 2e-XP estimator table | — | unchanged |

The disagreements are the finding: every mapping above is a **candidates list for a
docket**, not settled law. Adopt-with-why per row, calibrated against real pairs.

## 5. What Mechanus's conversion engine v0 takes from this

1. **Conversion law as data** — `mechanus/data/law/convert/2e-to-5e.json` (+ a
   `2014-to-2024.json` sibling): one row per mapping, each row carrying
   `candidates[]` with source cites (official p.4 / gist / O5R / derived-from-pairs)
   and one ADOPTED value — docket discipline inside the law table itself.
   Content-addressed into `law_version` like everything else.
2. **Profiles, not one truth** — the survey shows three legitimate philosophies:
   `quick-official` (p.4 verbatim), `restate` (full 5e rebuild, calibrated), and
   `o5r-preserve` (stat-line faithful). `convert` takes a profile parameter; every
   output stamps profile + law_version + per-field provenance.
3. **Calibration corpus, in trust order** — (a) FG&G bestiary ↔ SRD 5.1 same-name
   pairs (free, on disk, harvest pattern proven); (b) PAitM (owned answer key,
   cite-only) once poured; (c) SRD 5.1 ↔ 5.2.1 pairs for the 2014→2024 axis;
   (d) OAR Creature Logs if ever purchased — spot-checks only.
4. **5e-side targets are rederived, not borrowed** — fleet regression over the SRD
   corpus replaces the unlicensed DMG stat-by-CR table; Blog of Holding's fits are
   the published cross-check.
5. **Map-to-existing-first** (CMT doctrine) — before synthesizing a converted
   statblock, search the 5e corpus for the creature's published equivalent; a
   conversion docket that says "use SRD Wolf, p.393" beats a generated block.
6. **What stays out of formulas** — spells, items, class features: the official
   doc itself punts to nearest-match-plus-judgment. That's the arbitration ladder
   + `delta`/`view` lane, recorded as dockets, never auto-math.

— *Mechanus session, against live web sources; official PDF read in full from the
poured copy. Sources inline above.*
