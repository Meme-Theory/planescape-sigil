---
slug: friendly-fiend-rendezvous
title: A Sinister Rendezvous at The Friendly Fiend
view: 2e
status: READY
created: 2026-06-05
designer: modron session · /encounter-plan
law_version: 018b2eed42e9afe7
template_version: 2
---

# A Sinister Rendezvous at The Friendly Fiend

## 1. Premise

A tout sells the party a piece of dark that shouldn't exist: tonight at antipeak,
**Shemeshka the Marauder enters The Friendly Fiend** — the magic shop of her fellow
arcanaloth A'kin — with only her groomer-guards for company. The Cage's chant says
this meeting is impossible: Shemeshka once killed a sod *merely for mentioning her
and A'kin in the same breath* (Uncaged p97, Xideous's footnote 9). Whatever the two
fiends have to say to each other is leverage half of Sigil would bleed for — and a
secret that buries its keepers.

**Win:** witness the meeting (a face, a phrase, an exchanged object) and get out
unmarked. **Partial:** noticed by the guards — the reaction ladder decides whether
that means a shooing, a questioning, or being dragged inside to face two
supra-genius fiends. **Lose:** blades with 7–10 trained assassins in a Lower Ward
side street. **Catastrophic:** the arcanaloths themselves take a personal interest.
The dark beneath it all is the source's own unresolved question — siblings,
cohorts, lovers, or enemies? — and whatever fragment the party overhears should
**deepen that question, never answer it**.

## 2. Sources

| source | lane | license | feeds | cite |
|---|---|---|---|---|
| handbook.db | build/mimir/ | admitted corpus | all three dramatis envelopes | ids in §3 |
| Uncaged: Faces of Sigil | content/official/ | purchased — **POINTER ONLY** | A'kin p9 (shop, statblock, habits) · Shemeshka p96–99 (statblock, guards, footnotes 5–9) | uncaged:p9, uncaged:p97 |
| For Gold & Glory | build/mechanus/fgg-text/ (cache of content/retroclones/) | quotable 2e RAW | guard mechanics (rogue tables) | FG&G p.34, Tables 3.13/3.14 |
| Modron 2e convention pack | pipeline/modron/data/conventions/2e.json | project data | doctrine, checks, crit law | conventions("2e") |
| fandom-planescape wiki | content/wikis/ | CC-BY-SA | surveyed — **nothing carried** | — |

No SRD text is used → no attribution block required. No verbatim `content/official/`
text appears in this artifact — statements above are paraphrase + pointer; the DM
reads the real entries from their own copy at the table.

## 3. Dramatis personae

### A'kin — the host, the wildcard
- id: `npc:uncaged:a-kin` · admission_sha: `a0d539d2953e1e1be5ce4330e7a96d4ba3b8736b55a7ab570389cd71d9f464c8` · conf: 0.92 · loc: `uncaged:p9`
- role: wildcard · disposition: gracious, evasive, *too* friendly; prefers talk, then evasion magic, claws only in self-defense, teleports out as last resort (p9 COMBAT, paraphrase)
- rollables digest (source `handbook.db:npc:uncaged:a-kin`): attack THAC0 7 ×3 ·
  damage 1d4/1d4/2d6 (claw/claw/bite, poison rider on claws) · MR 60% ·
  morale champion(16) · hp 12d8+24 (printed 92, crosscheck **ok**, range [36,120]) ·
  AC −8 · saves: needs target (matrices are law — Mechanus/caller supplies)
- flags — adjudicated:
  - `prose Id6 → 1d6` (gate: mezzoloths), `Id2 → 1d2` (dergholoths), `40%` gate
    success — **CONFIRMED** (standard OCR I/l→1 class; matches the print idiom);
    kept as the §8 escalation specs, `requires_confirmation` honored at the table

### Shemeshka the Marauder — the sinister visitor
- id: `npc:uncaged:shemeshka-the-marauder` · admission_sha: `7833ac620534937f9c32019dc90cc9de55887bf9feefbb2139bbe9ae7d4c692e` · conf: 0.88 · loc: `uncaged:p97`
- role: antagonist (social gravity, not a fair fight) · disposition: attentive and
  encouraging until the guillotine temper turns; deals in leverage, not corpses,
  *especially* where a public scene would expose this meeting (p97, paraphrase)
- rollables digest (source `handbook.db:...shemeshka-the-marauder`): attack THAC0 7 ×3 ·
  damage **mode 1** 1d4/1d4/2d6 (claw/claw/bite, poison rider) · **mode 2** 1d6
  (razorvine whip from the headdress) · MR 60% · morale champion(16) ·
  hp 12d8+24 (printed 98, crosscheck **ok**, range [36,120]) · AC −8 · saves: needs target
- flags — adjudicated:
  - `damage.1.3` normalized_from `2d6 way past a guard to see She-` (column-bleed) —
    **CONFIRMED 2d6 bite**: matches A'kin's identical arcanaloth line; wound already
    filed to Mimir's review loop (integration-tests.md, corpus findings)
  - morale label carries bleed (`cham- bladeling … pion (16)`) — **CONFIRMED 16**;
    parser recovered the rating; same filed wound
  - `statblock.name` ate the descriptor — cosmetic, no dice impact, same filed wound
  - prose `ld4+6 → 1d4+6` (her guard complement) — **CONFIRMED** (l→1 OCR class;
    promoted to the §5 `number_appearing`)

### The groomer-guards — the actual opposition (inline; from admitted prose)
- source: Shemeshka's envelope, `sections.SOURCE` (`uncaged:p97`): guarded at all
  times by **1d4+6 5th-level tiefling thieves** — wispy hangers-on who are each a
  trained, eager assassin (p97, paraphrase)
- mechanics (FG&G p.34 — quotable lane): **THAC0 18** (Table 3.14, L5) ·
  **hp 5d6 each** (rogue HD d6) · saves PPDM 12 / RSW 12 / PP 11 / Breath 15 /
  Spell 13 (Table 3.13, L5–8) · AC & weapons: DM kit (leathers + knives suggested;
  open question Q2) · morale **13 (elite)** — designer assessment from the prose
  ("trained and eager assassins" who nonetheless "seldom last more than a few
  months"); confirm or adjust (open question Q2)
- thief skills (MS/HS %) are point-allocated in 2e, not fixed by level — DM-set at
  the table if the guards stalk anyone (open question Q2)
- sub-note — **Colcook**: the mirror-bearer, most-loyal of the guards, and (per the
  framing text) Xideous's leak inside Shemeshka's house (p97, footnote 5 + body).
  Prose figure, not an admitted entity; usable as the hook's seller or as the berk
  who panics first.

## 4. Stage

**The Friendly Fiend** — id: `location:sigil:the-friendly-fiend` · admission_sha:
`27172f177814751fed2339438de11368d4be385d913b0c7eab4bf5e6b91c5439` · conf: 0.9 ·
kind: site, **Lower Ward** (seeded from A'kin's entry; detail pointers → uncaged:p9).

Mechanically live features (paraphrase, p9):
- **One public room**, tall; one street door. Hundreds of wall bins of minor
  trinkets (cover — but a knocked bin is noise); a central glass case with the
  pricey stock (noise hazard, and the thing guards instinctively flank).
- **Windowless upstairs quarters** — rumored lower-planar portal (A'kin's bolt-hole
  and the fiends' discreet exit; the party can't use it without a key they don't have).
- **Antipeak street**: Lower Ward foot traffic thinned to shadows and smoke; the
  guards have clear sightlines — approaching unseen is the surprise contest (§5).
- Two arcanaloths inside, each *can't be surprised on the Lower Planes* — but Sigil
  is not the Lower Planes (§7 Q-A1, anticipated ruling).

## 5. Encounter spec

The batch covers **the guards** — the variable, rollable opposition. The two
arcanaloths ride the play loop from their §3 specs (their dice fire per-event:
MR, fear saves, claws — not as batch steps). `steps` override drops `check`/
`table` (the tout fixed the *when* — a set-piece skips the wandering check, per
the pack's own doctrine note) and `distance` (engagement is doorway/interior —
conversational range, predetermined by the fiction).

```json
{
  "steps": ["number", "hp", "surprise", "reaction", "initiative", "morale"],
  "number_appearing": "1d4+6",
  "creature": {"hp_expr": "5d6", "morale": 13},
  "reaction": {"cha_mod": 0}
}
```

- `number_appearing` 1d4+6 — Shemeshka's printed complement (§3 flag, confirmed)
- `hp_expr` "5d6" explicit — class-leveled thieves roll **d6**, not monster d8
  (FG&G p.34; this is the G9 lesson: class HD ≠ monster HD)
- `reaction.cha_mod` 0 — placeholder; set from the approaching PC at the table (Q1)

## 6. Dice plan — validated `plan_only` output (2026-06-05, view 2e)

```json
[
  {"step": "number",     "expr": "1d4+6",  "label": "number appearing (1d4+6)"},
  {"step": "hp",         "expr": "5d6",    "per_creature": true, "label": "hit points per creature (5d6)"},
  {"step": "surprise",   "check": {"kind": "surprise", "params": {}}, "sides": ["party", "monsters"], "label": "surprise (each side)"},
  {"step": "reaction",   "check": {"kind": "reaction", "params": {"cha_mod": 0}}, "label": "reaction roll"},
  {"step": "initiative", "side": "party",    "check": {"kind": "initiative", "params": {}}},
  {"step": "initiative", "side": "monsters", "check": {"kind": "initiative", "params": {}}},
  {"step": "morale",     "check": {"kind": "morale", "params": {"morale": 13}}, "armed": true, "label": "morale (when triggered — not pre-rolled)"}
]
```

Odds the DM should know cold (`(exact)` = dice_stats-backed; unmarked rows are
flat d20 / band-sum arithmetic, designer-computed — see MODRON.md §12 Q4):
- **Guard count** 1d4+6: 7–10, uniform 25% each, mean 8.5 *(exact)*
- **Guard hp** 5d6: mean 17.5, range [5,30] — a mid-level party CAN drop one per round
- **Surprise** (each side): ≤3 on 1d10 → **30%**
- **Reaction** 2d10 at cha_mod 0: friendly 6% · indifferent 15% · cautious 24% ·
  threatening 40% · hostile 15% — **55% lands threatening-or-worse**; these are
  paranoid assassins at a secret meeting. Every +1 of effective charisma/approach
  shifts the whole ladder one pip friendlier — talk beats sneak here.
- **Guard blades** THAC0 18: 40% vs AC 5 · 15% vs AC 0
- **Arcanaloth claws** THAC0 7: **95% vs AC 5** · 70% vs AC 0; full round
  1d4+1d4+2d6 *(exact)*: mean 12, p95 17, max 20 — plus the cumulative −1 poison
  rider per claw. Two of them act ×3 each. **This is the "do not fight" math.**
- **Gate** (each fiend, 1/day): 40% success → 1d6 mezzoloths or 1d2 dergholoths —
  the catastrophic escalation, and an event so public neither fiend wants it.

## 7. Law

| question | source | answer | cite |
|---|---|---|---|
| DCs for 2e tasks? | `dc_suggest(view=2e)` | **refused, correctly**: "no DC ladder for view '2e' — 2e tasks are roll-under ability checks (Modron's pack handles the dice)" | tool refusal, verbatim |
| MR vs spell-like abilities (fiend-on-fiend) | `precedents("magic resistance")` | head of chain: **innate spell-likes of fellow fiends bypass MR** at this table (conf 0.7, scope table:vnv) | `rul:vnv:akin-mr-vs-spell-like:002` (supersedes :001) |
| MR vs *mortal* casters | same chain, by its scope | ruling covers fiend-vs-fiend only → PC spells at the fiends still face MR 60% | scope reading; record fresh if contested (Q-A2) |
| Guard THAC0 / HD | FG&G | L5 thief: THAC0 18, 5 HD (d6) | FG&G p.34 Table 3.14 |
| Guard saves | FG&G | L5–8 rogue: 12/12/11/15/13 (PPDM/RSW/PP/Breath/Spell) | FG&G p.34 Table 3.13 |
| Crits | 2e pack | `crit_effect: none` — nat 20 auto-hits, no bonus damage (RAW 2e) | conventions("2e"), FG&G-sourced |
| Encounter budget | 2e | no XP-budget law exists in 2e — difficulty rides reaction/morale doctrine | pack doctrine; law_info |
| Reaction bands | 2e pack | 2d10 banding marked **provisional:true** (common DMG rendering, pending FG&G pour) — disclosed | conventions("2e") |
| House rules in scope | `house_rules()` | one: committed-loot-rolls (scope table:vnv, view 5e-2014) — **not binding** on this 2e encounter; its commitment ceremony is adopted here by design anyway | `rul:vnv:house:committed-loot-rolls:001` |

**Anticipated rulings** (draft only — record at play, citing live roll_ids):
- **Q-A1**: A'kin/Shemeshka "can't be surprised *on the Lower Planes*" (uncaged:p9/p97)
  — Sigil is not a Lower Plane. Likely answer: **they CAN be surprised here**; the
  immunity reads as plane-scoped RAW. Expect the table to weigh supra-genius (19)
  Int as a soft argument the other way.
- **Q-A2**: if a PC casts at either fiend, does the table:vnv MR carve-out apply?
  Likely answer: no — `:002` is scoped to *fellow fiends'* innate abilities; PC
  spellcraft faces MR 60% as RAW.

## 8. Contingencies

- **Morale (guards, ARMED, vs 13):** fire on — first guard dropped · a fiend
  visibly angered (the famous temper, p97) · half the complement down. On a break:
  they scatter into the Ward, and *someone* reports to Shemeshka — the campaign
  consequence outlives the scene. **The arcanaloths take no practical morale tests**
  (champion 16, and they don't flee — they conclude.)
- **Reaction branches** (2d10 + approach):
  - *friendly (2–4)*: the guards take the party for expected couriers — waved
    toward the door, straight into the meeting. The social deep end.
  - *indifferent (5–7)*: "Shop's closed, berk." A second approach is a new roll, one band worse.
  - *cautious (8–10)*: questioned, names taken. Colcook memorizes faces — the party
    is now *in the web* whatever happens next.
  - *threatening (11–15)*: seized for questioning — dragged inside, before both
    fiends. Catastrophe by another door (run it as theater, not combat).
  - *hostile (16+)*: knives, quietly, in the side street. No questions.
- **Escalation:** fear (each fiend, 1/day — vs mortals MR is moot; guards save vs
  spell at 13) · gate at 40% (§6) — but a yugoloth gate in the Lower Ward is a
  city-wide event; **neither fiend wants this**. Their true escalation is patience:
  let the party leave, then own them by what the web learns.
- **De-escalation:** A'kin's whole shtick is the open door — the gift at the
  threshold, the tea, the chat (p9). He may simply **invite the caught party in**,
  to Shemeshka's silent fury — the best scene in the design; let it happen.
- **The weird thing:** if the party tries to *buy* their way in (it's a shop), it
  works better than stealth: A'kin never turns a customer away, and Shemeshka must
  sit there pretending to browse. Reward the lateral move.

## 9. Ceremony

- Run direction: `.claude/skills/encounter-run` · requirements: `.claude/rules/encounters.md`.
- `session_open(label="friendly-fiend-rendezvous--night-N", view="2e",
  seed_phrase=<table's choice>)` → run record at
  `build/encounters/friendly-fiend-rendezvous/runs/<session_id>.md` **before any die** (R5).
- Opening batch = §5 spec with `session_id` (drop `plan_only`); record `batch_id`.
- The loop: guard blades vs PC AC (`roll_check` attack, THAC0 18); fiend dice only
  per-event from §3 specs; reaction re-rolls only on a genuinely new approach.
- Anticipated rulings Q-A1/Q-A2 → `precedents` first, then `record_ruling` citing
  the live roll_ids + entity ids/admission_shas (R6). Note: **hyphenate nothing**
  in `precedents` topics until Mechanus F4 lands (FTS5 hyphen crash, filed).
- RAW argument prep: the `lemure` agent (2e lawyer, `.claude/agents/`) can brief
  Q-A1/Q-A2 with page witnesses before the night.
- Close: `session_close` seals (seed **withheld** — reveal on demand via
  `reveal=true`, MODRON §12 Q1) → `verify(session_id)` → record §5 → statuses.

**Run sheet** (mid-scene reference — provenance and flags live in §3):

| combatant | # | AC | hp | THAC0 | atk | damage | MR | morale | saves |
|---|---|---|---|---|---|---|---|---|---|
| groomer-guard (T5 tiefling) | 1d4+6 | DM kit (Q2) | 5d6 each | 18 | 1 | by kit (1d6 knife suggested) | — | **13** ARMED | 12/12/11/15/13 |
| A'kin | 1 | −8 | 92 (12d8+24) | 7 | 3 | 1d4/1d4/2d6, claws poison (cum. −1) | 60% | 16 | needs target |
| Shemeshka | 1 | −8 | 98 (12d8+24) | 7 | 3 | claw/claw/bite **or** 1d6 razorvine | 60% | 16 | needs target |

Per-event: fear 1/day each (save vs spell — guards save on 13) · gate 1/day at
40% → 1d6 mezzoloths / 1d2 dergholoths · surprise ≤3 on 1d10, each side ·
reaction 2d10 + approach · initiative 1d10, low wins, both sides.

## 10. Validation (R7 gate)

- [x] R1 — artifact at `build/encounters/friendly-fiend-rendezvous/encounter.md`, template-derived
- [x] R2 — single view `2e`; no cross-view borrowings (§7 confirms)
- [x] R3 — all three entities cited id + admission_sha + loc as served; guards are
      inline **from admitted prose** with the flag adjudicated; UNCURED: none
- [x] R4 — no verbatim official text (paraphrase + pointers); FG&G rows from the
      quotable lane; no SRD text → no attribution block owed
- [x] R5 — every rollables flag adjudicated in §3 (5 across both fiends; wounds
      already filed to the review loop)
- [x] R6 — targets sourced (FG&G p.34; dc_suggest refusal recorded); precedents
      checked (`:002` chain head cited)
- [x] R7 — §5 passed `plan_only` (output §6); no rollable tables in this design
- [x] Open questions enumerated & classed:
      1. **[bind] Party context** — size/levels and the approaching PC's reaction
         adjustment (replaces `cha_mod: 0` in §5; resolve before `session_open`).
      2. **[bind] Guard kit & morale** — AC/weapons for the tieflings; confirm or
         adjust morale 13 (elite); MS/HS percentages if stalking happens.
      3. **[DM color] The fragment** — what half-truth do the fiends let slip?
         (Design intent: deepens the siblings/cohorts/lovers/enemies question,
         never answers it.)
      4. **[DM color] Timing** — which session/night? (Sets the run label.)
