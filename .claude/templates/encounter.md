---
slug:                # kebab-case; names the dir build/encounters/<slug>/
title:
view:                # 2e | 5e-2014 | 5e-2024 — exactly one (R2)
status: DRAFT        # DRAFT | READY | RUN (= played ≥once; re-runs fine) — READY only past the R7 gate
created:             # YYYY-MM-DD
designer:            # session or agent name
law_version:         # mechanus law_info at design time — the run skill re-checks it (R7)
template_version: 3
---

# <Title>

<!-- Format = this template. Requirements = .claude/rules/encounters.md (R1–R8).
     Direction = .claude/skills/encounter-plan. Fill every section; write "none"
     rather than deleting a heading — absence must be legible. -->

## 1. Premise

<!-- 3–6 sentences: the hook, what's at stake, why HERE, why NOW. Win / lose /
     walk-away shapes — in the Cage an encounter ends in talk as often as blood.
     Name the dark of it: what the players can learn that nobody's selling. -->

## 2. Sources

<!-- Every source feeding this encounter; the lane decides quotability (R4). -->

| source | lane | license | feeds | cite |
|---|---|---|---|---|
| handbook.db | build/mimir/ | admitted corpus | dramatis envelopes | ids in §3 |
<!-- | Uncaged: Faces of Sigil | content/official/ | purchased — POINTER ONLY | A'kin, the shop | uncaged:p9 | -->
<!-- | For Gold & Glory | content/retroclones/ | quotable 2e RAW | morale/THAC0 law | FG&G p.NN | -->
<!-- | timaresh | content/wikis/ | CC-BY-SA (note it) | ward color | url | -->

## 3. Dramatis personae

<!-- One block per creature/NPC, everything from the SERVED envelope (R3).
     digest = the rollables keys that matter at the table. flags = every
     lawfulness_flag / requires_confirmation / suspect / UNCURED, each with its
     adjudication (confirmed | cured at gate | struck) — R5.
     INLINE combatants (a retinue named only inside an admitted envelope's
     prose) are sanctioned: cite the parent envelope + field path + the prose
     flag's adjudication, and witness every derived mechanic from a quotable
     law lane (e.g. FG&G page tables). Provenance flows through the parent.
     CARDS (§12 Q5): each block IS an entity card — generate via
     .claude/templates/entity-card.md, one per dramatis member, and
     concatenate; cards sourced through Mimir + Mechanus snap together, and
     the §9 run sheet assembles from their run-sheet rows. -->

### <Name> — <one-line role in this scene>
- id: `npc:...` · admission_sha: `...` · conf: `0.NN` · loc: `<product>:p<NN>`
- role: antagonist | wildcard | prize | bystander · disposition: <reaction posture / what turns it>
- rollables digest: <e.g. attack THAC0 7 ×3, damage 1d4/1d4/2d6 claw/claw/bite, MR 60%, morale champion(16), hp 12d8+24 (crosscheck ok)>
- flags: <each flag + adjudication, or "none">

## 4. Stage

<!-- Location entity (id + admission_sha if admitted; else cite pages). Then ONLY
     the features that matter mechanically: exits, light, cover, crowd, portals
     and their keys, who's watching. Sigil note: the Lady and the dabus are not
     encounter pieces — if the design tempts them onstage, rethink in §8. -->

## 5. Encounter spec

<!-- The exact object encounter_rolls eats — keys per the view's doctrine
     (conventions(view) shows it). 2e wandering: check → table → number → hp →
     surprise → distance → reaction → initiative (+ morale ARMED). 5e: number →
     hp → initiative. creature_ref takes a handbook id; inline creature takes
     {hd | hp_expr, morale, ...} — class-leveled foes need explicit hp_expr
     (T5 → "5d6", never monster d8s).
     DROPPING STEPS: omitting a key drops its step EXCEPT `check`, which falls
     back to the pack's check_default — a set-piece must drop it with an
     explicit `steps: [...]` override (procedure steps — surprise/initiative/
     morale — arm from doctrine, not from keys). Note WHY beside the spec.
     ONE SPEC, ONE CREATURE: the batch carries the VARIABLE opposition; named
     principals stay in §3 and their dice fire per-event in the play loop.
     RUN-TIME BINDS: party-dependent params (e.g. reaction.cha_mod) get a
     placeholder here + a [bind] entry in §10 — resolved before session_open. -->

```json
{
  "check": {"expr": "1d10", "encounter_on": "<=1"},
  "number_appearing": "2d4",
  "creature_ref": "npc:...",
  "distance": "10d10",
  "reaction": {"cha_mod": 0}
}
```

## 6. Dice plan

<!-- Record the VALIDATED plan_only output (compact reformat is fine — the run
     re-executes the spec, not this transcript; keep step order, exprs, kinds,
     params, and ARMED markers). Below it, the odds the DM should know cold:
     dice_stats the expressions and keep its exact/monte-carlo labels as given;
     flat d20 thresholds and band sums may be designer arithmetic — declare
     which is which in one line. -->

## 7. Law

<!-- DCs with dc_suggest results or RAW page cites (R6). Budget: 5e-2024 XP
     p.202 only; for a 5e-2014 table, note the 2024-budget loan; 2e has no
     budget law — reaction + morale doctrine carries difficulty. Precedents
     consulted (docket ids) and anticipated rulings with the likely answer and
     its RAW witness. Cross-view borrowings declared here (R2). -->

| question | source | answer | cite |
|---|---|---|---|

## 8. Contingencies

<!-- Morale specs arrive ARMED, not pre-rolled — write the fiction triggers that
     fire them (first blood? leader downed? half the band?). Reaction-band
     branches (hostile/wary/neutral/friendly — what each looks like HERE).
     Escape routes, escalation and de-escalation, and the "players do the weird
     thing" branch. -->

## 9. Ceremony

<!-- How this runs at the table: session label `<slug>--night-N`, seed_phrase if
     the table chooses one (ceremony beats entropy), which §5 steps execute as
     the opening batch, what lands in the run record and when. END WITH A RUN
     SHEET: one compact table, one row per combatant kind (# / AC / hp /
     THAC0-or-bonus / attacks / damage / MR / morale / saves) + a per-event line
     (fear, gate, surprise, reaction, initiative) — mid-scene reference must not
     require scrolling §3. Direction: .claude/skills/encounter-run. Run record:
     build/encounters/<slug>/runs/. -->

## 10. Validation (R7 gate — every box, or status stays DRAFT)

- [ ] R1 — artifact at `build/encounters/<slug>/encounter.md`, this template
- [ ] R2 — single view in frontmatter; borrowings declared in §7
- [ ] R3 — every §3 entity: id + admission_sha as served + page loc; UNCURED acknowledged or absent
- [ ] R4 — verbatim text only from quotable lanes; official/ is pointers only; SRD quotes carry attribution
- [ ] R5 — every rollables flag in §3 adjudicated
- [ ] R6 — DCs sourced; precedents checked (§7)
- [ ] R7 — §5 passed plan_only (output in §6); tables validated
- [ ] Open questions enumerated & classed: <numbered; each tagged
      **[design hole]** (blocks READY) | **[bind]** (resolve before
      session_open) | **[DM color]** (never blocks) — or "none">
