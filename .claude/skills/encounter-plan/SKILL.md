---
name: encounter-plan
description: Design a Planescape encounter into a validated artifact under build/encounters/ — recon via Mimir, color from content/, law from Mechanus, dice plan from Modron. Use when the DM asks to design, plan, prep, build, or stage an encounter. Args: a premise, or "<location|faction|npc> [view] [slug]".
---

# /encounter-plan — design the scene, forge the artifact

You are building the **encounter artifact**: the single document that runs the
night. Skills direct (this file), rules require, templates format. Read both
before writing anything:

1. **`.claude/rules/encounters.md`** — R1–R8 bind every step below (BLOCKING read).
2. **`.claude/templates/encounter.md`** — the artifact's exact shape.

Output: `build/encounters/<slug>/encounter.md`, status `DRAFT` until the R7 gate
passes, then `READY`.

## Phase 0 — Intake

Pin down with the DM (ask only what the prompt doesn't give):
- **Premise** — or at least a location / faction / NPC to build around.
- **View** — exactly one of `2e | 5e-2014 | 5e-2024` (R2).
- **Party context** — size/level if a 5e budget will matter; tone (talk-heavy
  vs blades-out) shapes §8.
- **Slug** — kebab-case; it names the directory.

Stamp `law_version` from `mechanus law_info` into the frontmatter.

## Phase 1 — Recon (Mimir first: "search the Handbook before you generate")

- `search_handbook` the premise terms; `list_entities` by type to see the lanes.
- `get_entity` every candidate — record **id, `admission_sha`, confidence, and
  the page loc from `provenance.value_sources`** exactly as served (R3).
- `trace_entity` the leads — the edge neighbourhood IS the plot web (who knows
  whom, who owes whom, attested_in what).
- `query_graph` for faction/location webs when casting a side.
- A miss in the handbook is information: either recast from what's admitted, or
  go to content/ knowing the entity arrives UNCITED-BY-ENVELOPE (Phase 2 rules).

## Phase 2 — Deepen (content/ — lanes decide quotability, R4)

Map first: `content/INDEX.md`, `content/official/CATALOG.md`.

| lane | use | quote? |
|---|---|---|
| `content/official/` | the real text — read for design | **pointer cites only** (product, page) — never paste |
| `content/srd/` | 5e RAW | verbatim OK **with** Mechanus `attribution` block |
| `content/retroclones/` (FG&G) | 2e RAW | verbatim OK (the quotable 2e) |
| `content/wikis/`, `content/fan/` | color, chant, cross-refs | per each wiki's license — note it in §2 |
| `build/mechanus/{fgg,srd51,srd52}-text/` | page-cited law caches (filename = page) | per the underlying lane — **prefer these over re-mining PDFs** for §3/§7 mechanic witnesses |
| `build/<book-slug>/` | raw extraction | **UNCURED** (R3) — flag it, prefer the handbook |

Grep tips for this corpus: PDF-extracted text carries ligatures (`ﬁ`) and
`\xa0`/`\t\r` soup — search loose (`-i`, fragments), normalize before matching.
Every fact you carry forward gets its (product, page) or (wiki, url) — an
uncited fact doesn't ship (R3).

## Phase 3 — Law (Mechanus)

- `dc_suggest` for every anticipated check; RAW page cites for fixed targets → §7.
  (View 2e: expect the documented refusal — no DC ladder exists in 2e; record it
  once and source targets as roll-under/percentile per the pack.)
- Budget: `encounter_budget` is **5e-2024 only** — the 5e-2014 refusal is
  correct, don't work around it (R4). A 5e-2014 table loans the 2024 budget
  with a note; 2e difficulty rides reaction + morale doctrine, no XP law.
- `precedents` for every ruling the scene is likely to raise (MR vs spell-like,
  cover, surprise…); cite docket ids in §7. Draft *anticipated* rulings with
  their likely answer + RAW witness — record nothing yet; dockets are play-time.
- `house_rules` for the table's scope — disclose anything that bends this scene.
- Quoting SRD text into the artifact? Ship the `attribution` block in §2/§7.

## Phase 4 — Dice (Modron)

- `rollables(entity=<handbook id>)` per dramatis member. Into §3: the digest
  (attack/damage/MR/morale/hp) and **every flag** —
  `lawfulness_flags`, `requires_confirmation`, `suspect`, UNCURED-source.
  Adjudicate each: confirmed / cure at Mimir's gate / struck (R5). A MISMATCH
  crosscheck is a transcription smell — file it toward the review loop, don't
  silently "fix" the number.
- Emit each dramatis member as an **entity card**
  (`.claude/templates/entity-card.md`) — §3 is a concatenation of cards, and
  the §9 run sheet assembles from their run-sheet rows. Cards pin
  `admission_sha`, so a re-pour can't shift them silently.
- `conventions(view)` — the doctrine dictates which §5 spec keys exist.
- Compose §5: the exact `encounter_rolls` object. Omitting a key drops its step
  EXCEPT `check` — the pack's check_default arms regardless; set-pieces drop it
  with an explicit `steps: [...]` override. One creature per spec: batch the
  variable opposition, principals fire per-event from §3. Say why beside the spec.
- `encounter_rolls(encounter=<§5>, view=<view>, plan_only=true)` → paste the
  plan into §6 (R7).
- `dice_stats` the swingy lines → §6 odds: hit chance at party ACs, expected
  swing, the roll that can drop a PC. Keep exact-vs-monte-carlo labels as given.

## Phase 5 — Write & gate

- Write the artifact from the template into `build/encounters/<slug>/encounter.md`
  — every section filled, "none" over deleted headings.
- §8 contingencies: fiction triggers for ARMED morale, reaction-band branches,
  the weird-thing branch.
- Walk §10 against the rules. All boxes checked → flip `status: READY`; an
  unchecked box keeps `DRAFT`. Open questions don't block READY unless classed
  **[design hole]** — class every one ([design hole] | [bind] | [DM color],
  R7), numbered, addressed to the DM.

Hand back: artifact path, status, the §6 odds digest, and the open questions.
Running it is `/encounter-run` — don't open a session from this skill.
