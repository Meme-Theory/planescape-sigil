# CONVERSION.md — the 2e→5e fusion engine (Mechanus subsystem)

> Owned by the **Mechanus session** (extends MECHANUS.md §5; same etiquette: siblings
> record deltas in their own docs). Status: **DESIGNED 2026-06-05, build pending.**
> Prior-art survey: `build/mechanus/conversion-prior-art.md`.

The marquee goal made mechanical: *invoke items from the AD&D modules, for direct use
at a 5E table.* We forge our own path, but not blindly — three sources did heavy
lifting we build from, each contributing what it's best at:

| source | role in the fusion | poured at |
|---|---|---|
| WotC *Conversions to 5e* v1.0 (2015) | **guiding stone** — doctrine ("feels like, not exact"), the formula floor (p.4), PC-side mappings, treasure/spell policy | `content/official/_free/DnD_Conversions_1.0.pdf` (cite-only) |
| petersgiles 2E→5E gist (2015) | **the field walk** — per-field mapping tables, reference-monster doctrine, action-by-action offense procedure; itself pair-derived (5E MM vs 2E) + descended from WotC's 2e→3e Conversion Manual | `content/fan/web-supplements/conversion-guides/petersgiles-2e-to-5e-gist.md` |
| Methods & Madness O5R (2018) | **the fast rung** — play the 2e stat-line as-is under 5e with bracket adapters; plus honest pair-tables showing where formulas drift | `…/conversion-guides/methodsetmadness-o5r-2018.{html,txt}` |

We are tied to nothing being exact. Where the schools disagree, the disagreement is
**recorded as candidates and adjudicated by calibration pairs** — never silently picked.

---

## 1. Architecture: three rungs, one pipeline

One action-by-action pipeline; three exit rungs of increasing fidelity and cost.
`convert(ref, to_view, profile)` picks the rung. Every output stamps
`conversion_law_version` + `law_version` + profile + per-field provenance.

| rung | profile | what comes out | view-ladder rung (DIMENSIONS) | cost |
|---|---|---|---|---|
| **S — shim** | `card` (O5R) | an **operating card**: the 2e stat-line + bracket adapters (AC 19−, to-hit = HD, max HP/damage, save kit). No 5e statblock materialized. | SCAFFOLD | zero prep, table-speed |
| **Q — quick** | `quick-official` | a minimal 5e block from the official p.4 floor (AC 19− cap 22 · attack HD/2+2 cap +12 · DC 8+HD/2 cap 20) + senses/MR defaults | DERIVED (confidence-capped ≤0.6) | one call |
| **R — restate** | `restate` (default) | a full 5e statblock via stages 0–7, calibrated, docketed, gate-proposable | DERIVED | full pipeline |

The O5R insight that makes rung S honest: it is **not a conversion, it's a view-shim**
— the 2e manifestation stays authoritative and the card carries the adapters. That is
exactly DIMENSIONS' "edition = a view" doctrine applied at zero materialization cost.

CMT doctrine binds all rungs: **map-to-existing first.** If the creature has a
published 5e equivalent, the cheapest lawful conversion is a citation
(`use-existing: SRD Wolf p.393`) — the pipeline short-circuits at stage 1.

## 2. The pipeline (action-by-action)

Every stage emits docket rows: `field → {candidates[], adopted, why, source-cites,
confidence}`. Unmapped residue and deliberate drops are first-class (§5 MECHANUS).

**Stage 0 — intake & normalize.** Admitted 2e envelope (Mimir, with admission_sha) or
raw statblock. Reuse the family's parsers: Modron rollables idioms (`claw/claw/bite`,
` or ` modes, `xN` multipliers, MR %, morale names, class HD `F9`→9d10, monster HD
`12+24`), range-notation decode (`3-12`→3d4 — gist's own rule, already implemented in
rollables), OCR tripwires. HD parse: count + bonus held separately ("5+3": dice=5,
plus=3 — the plus drops from 5e HD per gist, but **feeds the to-hit floor** via the
THAC0 bracket plus-bump we already pinned in `thac0_2e.json`).

**Stage 1 — reference resolution (replace or anchor).** Search the 5e corpus
(SRD markdown tree + 5e-database mirrors + handbook once 5e pours) by name/kin.
- Hit, same creature → emit `use-existing` + delta notes. Done (any rung).
- Near-kin → it becomes the **reference monster** (gist doctrine): CR prior, ability
  donor, trait vocabulary. Priority: SRD/MM > poured 5e content > nothing.
- No reference → flag `unanchored` (confidence ceiling drops; model-assist allowed,
  every guess docketed).

**Stage 2 — frame.** Size (gist's exact 2e-feet→5e-category table; 1e S/M/L via its
appendix). Type + tags (2e has none — assigned from description, docketed). Alignment
(direct; official's Basic/4e edge maps; gist's neutral→unaligned-when-instinctive).

**Stage 3 — ability scores.** The thinnest 2e data, the widest candidates:
1. Int from printed score or rating table (Non 1 · Animal 1 · Semi 2–4 · Low 5–7 ·
   Avg 8–10 · Very 11–12 · High 13–14 · Excep 15–16 · Genius 17–18 · Supra 19–20 ·
   Godlike 21+; floor 1).
2. Str via the exceptional ladder (1–18 same · 18/xx→18 · 18/00→19 · 19→20-21 ·
   20→22-23 · 21→23-24 · 22→25-26 · 23→27-28 · 24→29 · 25→30). Official's flat
   "18/xx→18" is the recorded conservative candidate.
3. Description-attested scores as printed.
4. Residuals from the reference monster, tweaked to concept; no reference → fleet
   medians for the CR band, flagged.
Per-score provenance + confidence; clamp 1–30 (official).

**Stage 4 — chassis.**
- **AC** candidates: (a) rebuild — Dex mod + worn armor per 5e armor law, natural
  armor +2 when unarmored 2e AC ≤ 6 (gist); (b) 19 − oldAC cap 22 (official floor;
  O5R derives the same); (c) keep-bracket (rung S only). Adopt (a) when armor is
  legible, else (b); if |a − b| > 2, flag for pair-check. Dragons: known outlier
  class (both sources) — wider tolerance, reference-anchored.
- **HP/HD**: re-die by 5e size (T d4 · S d6 · M d8 · L d10 · H d12 · G d20) + size
  adjustment (+1 die S/M, +2 L/H/G — gist; oozes keep dice); Con bonus × dice;
  printed average = floor-of-mean (Modron crosscheck for free). O5R max-HP is rung-S
  law only. HD *bonus* ("+3") drops from dice, noted in docket.
- **Speed**: piecewise formula (≤12: ÷3×10; >12: ×2, round to 10 — gist) as the
  candidate **with its known anomaly recorded** (Move 12 human → 40 vs 5e's 30); a
  pair-fit lookup overrides the formula once harvested. Movement-type glyphs (Fl Sw
  Br Cl Wb; 1e `/ // () * @`) map to 5e speeds; Wb → Web Walker trait.
- **Senses**: infravision/ultravision → darkvision (range carried); non-visual sight
  → blindsight/tremorsense; innate true seeing → truesight; passive Perception =
  10 + final Perception bonus (is_lawful will check our own work).

**Stage 5 — offense, per action.** Each 2e attack mode / Special Attack / description
power becomes its own docket row:
- **to-hit** candidates: (a) PB + max(Str,Dex) mod — natural attacks treated finesse
  (gist, from MM pairs); (b) HD/2+2 cap +12 (official floor); (c) HD (O5R, rung S).
  Adopt (a); if |a − b| > 2, pair-check flag. THAC0 itself is **never translated**
  (the official guide pointedly ignores it) — but our `thac0_2e.json` brackets verify
  the 2e side parsed right before we leave it behind.
- **damage**: weapon attacks → 5e weapon dice + size escalation (L +1 die, H +2,
  G +2-3); natural attacks → step-up table (1d4→1d6/2d4 · 1d6→1d8/2d6 · 1d8→1d10/2d8
  · 1d10→1d12/2d10 · 1d12→2d8/2d12; multi-die: step the die by the die count, e.g.
  2d4→2d6; min die d4; "strongest attack" may step die AND add one — once only);
  + Str (melee) / Dex (ranged) folded; average recomputed floor-of-mean. A
  `keep-dice` option preserves TSR feel (recorded as profile variant, default off).
- **riders**: save-bearing effects get DC = 8 + PB + ability (gist/5e law) with the
  official 8+HD/2 as sanity floor; the 2e save *category* maps the ability —
  **PPDM→Con · RSW→Wis(Dex) · PP→Con(Wis) · Breath→Con(Dex) · Spell→Wis** —
  alternates legal, docketed. Condition names land in the view's closed set
  (`conditions.json`). Energy drain → Life Drain (named-mechanic map). Limited-use →
  **Recharge 5–6** for most; X/day for once-a-fight nukes (gist policy).
- **multiattack**: 2e routines (claw/claw/bite) synthesize a Multiattack action.
  Gist observes the 5e cap-2 norm (3 = dragon exception) — **open question Q1**:
  keep 2e attack count or compress; v0 default keep-count ≤3, docketed either way.
- **reactions**: triggered abilities split out as Reactions.

**Stage 6 — defenses & traits.**
- Special Defenses → vulnerabilities / resistances / immunities with 5e phrasing law:
  "+N or better weapon to hit" → *bludgeoning, piercing, and slashing from nonmagical
  weapons* (+ material carve-outs: *…that aren't silvered/adamantine*); undead innate
  kit (poison damage + poisoned condition); incorporeal template (acid/cold/fire/
  lightning/thunder resist + nonmagical b/p/s; poison immune; grappled/paralyzed/
  petrified/poisoned/prone/restrained immune).
- **MR %** → Magic Resistance trait (advantage on saves vs spells); the printed %
  preserved in provenance, never silently discarded.
- Spell-like power lists → **Spellcasting** (CL = printed caster level, else HD);
  concept-critical powers → **Innate Spellcasting** (ability Wis/Cha) or bespoke
  traits/actions. Spells map nearest-SRD-equivalent first (official doctrine);
  no equivalent → arbitration lane, not auto-math.
- Traits: nearest MM-vocabulary trait first; else adapt; else carry original text
  (gist's fallback), flagged `untranslated-prose`.

**Stage 7 — meta, self-audit, gate.**
- **CR**: candidates = reference-monster CR · gist 2e-XP estimator (CR0=7xp · ⅛=15-35
  · ¼=65-120 · ½=175-270 · 1=420 · 2=650 · 3=975-1400 · 4=2000 · 5=3-4k · 6=5-6k ·
  7=7k · 8=8k · +1000/CR; separate 1e table, +5000/CR past 23) · **our fleet-derived
  stat-by-CR targets** (the licensed replacement for DMG ch.9 — regression over the
  334 SRD 5.1 monsters we already audit, Blog-of-Holding fits as published
  cross-check). Adopt by defensive-CR/offensive-CR averaging against the targets;
  iterate once if PB shifts.
- **PB** from CR (`pb_by_cr.json`); **XP recomputed** from final CR, never carried
  (MECHANUS §5, standing).
- **Skills**: hard-to-surprise → Perception proficiency; ambusher → Stealth;
  "signature skill" expertise (double PB) is **curation-only in v0** (Q2).
- **Morale**: dropped as a 5e field, **recorded as a deliberate drop** with the value
  preserved in provenance (MECHANUS §5); `port_morale: true` honors the gist's
  concept-critical exception — it rides as a trait note, flagged house.
- **Languages** mapped to the 5e list, else carried.
- **Self-audit**: the converted block runs `is_lawful` (REVIEW-5E §A pack) and must
  pass with **zero hard fails and zero waivers** — waivers require print witnesses
  and a derived block has none. An unlawful conversion is a bug in the law tables or
  an honest `unconvertible` verdict — never shipped quietly.
- **Docket + propose-back**: the conversion docket (rules fired by ID, per-field
  candidates/adopted/why, drops, residue, confidence) is the entire defense file
  under auto-ADMIT (MECHANUS §10) — no docket, no propose.

## 3. Conversion law as data

`pipeline/mechanus/mechanus/data/law/convert/` — every table page/section-cited to
its source (official PDF p.N · gist §heading · o5r · pairs-derived), every row a
candidates-with-adopted record. `conversion_law_version` = content-address over
`convert/` (a separate axis from `law_version`, both stamped on every output — a
data change re-versions every view, per MECHANUS §5).

| file | carries | primary sources |
|---|---|---|
| `profiles.json` | rung definitions S/Q/R + confidence ceilings | this doc |
| `ac.json` | rebuild law, natural-armor heuristic, 19− floor cap 22, dragon-outlier flag | gist §AC · official p.4 · o5r |
| `hd_hp.json` | size→die, +1/+2 dice, ooze/dragon exceptions, floor-of-mean, max-HP (rung S) | gist §HD · o5r |
| `speed.json` | piecewise formula + anomaly note + pair-lookup override + glyph map + Wb trait | gist §Speed/§1E |
| `abilities.json` | Int ratings · Str ladder · reference-fill policy · clamps | gist §Abilities · official pp.2,4 |
| `attack.json` | finesse doctrine, HD/2+2 floor cap 12, HD (rung S), divergence tolerance | gist §Actions · official p.4 · o5r |
| `damage.json` | step-up + multi-die + min-d4 + strongest-attack + size escalators + keep-dice variant + range-notation decode | gist §Damage · MMII tip |
| `saves.json` | category→ability map + DC 8+PB+ability + 8+HD/2 floor + O5R class-save kit (F→Str/Con, M→Wis/Int, T→Dex/Int; full bonus best-two, half rest, rung S) | gist §Saves · official p.4 · o5r |
| `defenses.json` | resistance/immunity phrasing law, undead/incorporeal templates, MR→trait | gist §V/R/I |
| `senses.json` | infravision→darkvision etc., passive Perception law | gist §Senses |
| `spellcasting.json` | spell-likes→(Innate) Spellcasting, CL=printed‖HD, nearest-spell doctrine, psionics→Innate (flagged) | gist §Traits/§1E · official pp.2,4 |
| `actions_policy.json` | multiattack count policy (Q1), recharge policy, reaction split, energy-drain map | gist §Actions/§Recharge |
| `cr_xp.json` | 2e-XP→CR + 1e-XP→CR estimators (priors only) | gist App.1/App.2 |
| `cr_targets.json` | **fleet-regression stat-by-CR curves** (AC/HP/atk/DC/dmg per CR, 5e-2014 + 5e-2024 fits) | derived from SRD corpora; BoH cross-check |
| `frame.json` | size map, alignment edges, type/tag policy | gist §Size · official p.2 |
| `pc_side.json` | kits/NWP→backgrounds, exceptional Str, level 1:1 cap 20, infravision, treasure constraints — DM-facing notes, not auto-math | official pp.1–3 |

## 4. Calibration & acceptance (the answer keys)

**Fit on free pairs, test on the bought key.**

1. **Pair harvest** (`tools/harvest_pairs.py` → `build/mechanus/pairs/2e-5e.json`):
   FG&G Appendix C (pp.310–370) ↔ SRD 5.1 same-name monsters — wolf, ghoul, ogre,
   goblin, lich, vampire, purple worm… expected ~40–80 pairs (the THAC0 harvest
   pattern, proven at 80 pairs).
2. **Table fitting**: each convert/*.json adopted value checked against the pairs
   (does 19− or rebuild fit AC better? does the speed formula or a lookup win? how
   often does finesse to-hit land within ±1 of print?). Fit report →
   `build/mechanus/pairs/fit-report.md`; outliers (dragons!) get class flags, not
   silent exceptions. O5R's own goblin/ogre/red-dragon table is the smoke test.
3. **cr_targets regression**: defensive (AC,HP) and offensive (atk,DC,avg dmg) curves
   vs CR over the 334-monster fleet; 5e-2024 fit from the SRD 5.2.1 set; publish
   alongside Blog-of-Holding's numbers with deltas.
4. **Held-out gold**: PAitM pairs (post-pour) are **test-only** — the engine never
   fits on them; disagreement is a finding (maybe ours, maybe WotC's conversion
   choices — both worth a docket). OAR Creature Logs if ever purchased: spot-checks.
5. **Acceptance gate for v0** (all must hold):
   - convert(FG&G wolf) vs SRD Wolf: every numeric field within tolerance
     (AC ±1, to-hit ±1, HP ±20%, CR exact-or-adjacent), zero is_lawful hard fails;
   - same for ghoul (riders: paralysis save), ogre (weapon damage path), lich
     (class-levels + spellcasting path), red dragon (outlier class — tolerances
     doubled, flags expected and REQUIRED to surface);
   - every emitted field traceable: docket names rule-IDs and source cites;
   - rung S card for A'kin renders with zero errors from the admitted envelope;
   - re-run = byte-identical (content-addressed law, no hidden randomness).

## 5. Tool surface & build order

`convert` un-parks (MECHANUS §7) as:
`convert(ref | statblock, to_view='5e-2014', profile='restate' | 'quick-official' |
'card', options{keep_dice, port_morale, multiattack_policy, reference_hint})` →
`{result: statblock | card | use-existing, docket}`. Siblings: `delta` reads the
same docket; `answer_key` serves pairs; Modron's rollables can compile either the
2e envelope (rung S card) or the converted 5e block (rungs Q/R) — same dice, both
views, which is the whole point.

Build order (each step its own session-sized brick):
1. `convert/` law tables poured from the three sources, page-cited (no code).
2. Pair harvest + fit report; adopted values adjudicated against pairs (dockets).
3. `cr_targets.json` fleet regression (+ BoH cross-check note).
4. Stages 0–4 (frame/abilities/chassis) + docket emitter; wolf passes chassis.
5. Stages 5–6 (offense action-by-action, defenses/traits); ghoul + ogre pass.
6. Stage 7 (CR/PB/XP/self-audit/propose-back); lich passes; acceptance gate run.
7. Rungs S + Q (cheap once R exists: S is law-table rendering, Q is the floor
   formulas); A'kin card; `convert` un-parked on the server.
8. PAitM held-out validation, post-pour → fit-report v2 + law-table revisions
   (supersedes chains, the ledger remembers).

## 6. Refusals & honesty (inherited, applied)

- Tables absent from every SRD (DMG ch.9 stat-by-CR, 2014 budgets) are **never
  transcribed** — they are re-derived from licensed corpora or refused.
- Derived blocks get **no waivers** — waivers need print witnesses; conversions have
  none. Internally lawful or honestly `unconvertible`.
- Official scans (incl. PAitM) stay cite-only; their values appear only as held-out
  test verdicts (pass/fail + docket), never as quoted tables.
- Model-assisted steps (type/tags, trait prose, unanchored abilities) are **always
  docketed as model-assisted** with confidence — a guess wearing a formula's costume
  is the conversion engine's version of a fiat row in a rolled costume.

## 7. Open questions (for Meme)

1. **Multiattack policy (Q1)**: default keep 2e attack count (≤3) or compress to the
   5e cap-2 norm? v0 leans keep-count; pairs + PAitM will referee.
2. **Signature-skill expertise (Q2)**: auto-grant double-PB on strong description
   cues (doppelganger Deception pattern), or curation-only? v0 leans curation-only.
3. **Damage feel (Q3)**: `restate` defaults to the gist step-up (5e-normal damage) —
   want `keep_dice` (TSR-feel, lighter hits) exposed as a table-level house default
   instead of per-call?

## 8. Decisions ledger (this doc's own)

| date | question | ruling | rationale |
|---|---|---|---|
| 2026-06-05 | fusion shape | **three rungs over one pipeline** (card/quick/restate) | O5R is a view-shim not a conversion; official p.4 is a floor not a method; the gist is the method. Profiles = exit points, not forks |
| 2026-06-05 | source roles | official = doctrine+floor · gist = field walk · O5R = rung S | each at its strength; conflicts live as candidates[], pairs adjudicate |
| 2026-06-05 | THAC0 | never translated; verified at intake (thac0_2e.json), rebuilt from PB+ability | official ignores it pointedly; gist recalculates; our brackets keep the 2e side honest |
| 2026-06-05 | 5e-side targets | fleet regression, not DMG transcription | license law; we already audit the corpus the curves come from |
| 2026-06-05 | derived-block waivers | **none, ever** | waivers need print witnesses; conversions have none |
| 2026-06-05 | sources poured | gist + O5R into `content/fan/web-supplements/conversion-guides/` w/ SOURCES.md | web rots (CMT cert dead, Goodman bot-walled); law tables cite local copies |
