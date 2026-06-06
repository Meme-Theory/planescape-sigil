---
description: Binding requirements for designing and running encounters (the artifact law)
paths:
  - build/encounters/**
  - .claude/skills/encounter-plan/**
  - .claude/skills/encounter-run/**
  - .claude/templates/encounter*
---

# Encounter Law — requirements, not suggestions

Skills direct (`.claude/skills/encounter-plan`, `encounter-run`), templates format
(`.claude/templates/encounter.md`, `encounter-run.md`); **this file binds**. A
violation is a defect even if the encounter "worked." Cite rules by number.

## R1 — Artifact law
- No table play without an artifact: `build/encounters/<slug>/encounter.md`,
  derived from the template, frontmatter `status: READY`.
- Each run gets its own record: `build/encounters/<slug>/runs/<session_id>.md`
  from the run template. One run, one record, never overwritten.
- Encounter artifacts live under `build/encounters/` ONLY. `content/` is
  immutable — nothing is ever written there. Handbook/rulings/rolls writes go
  through their owners' guarded paths (gate, `record_ruling`, Modron ledger) —
  never by editing store files.

## R2 — One view
- Exactly one edition view per encounter: `2e` | `5e-2014` | `5e-2024`
  (frontmatter `view:`). `srd` is a license axis, NOT an edition.
- Cross-view borrowing (a 2e cutter at a 5e table) is declared in §7 Law with
  the conversion noted — never silent.

## R3 — Provenance
- Every dramatis entity cites handbook id + `admission_sha` **exactly as served**
  by `mimir get_entity`, plus its page loc from `provenance.value_sources`
  (e.g. `uncaged:p9`).
- Raw `build/<book>/` extraction refs are last resort, marked `UNCURED` in §3,
  and require an explicit DM-acknowledgment line. Quarantined entities are
  refused — cure them at Mimir's gate; don't smuggle them in.
- Every fact taken from `content/` carries (product, page) or (wiki, url).
  An uncited fact doesn't ship.

## R4 — License
- Verbatim text in artifacts ONLY from quotable lanes: SRD 5.1/5.2.1
  (CC-BY-4.0 — ship the Mechanus `attribution` block alongside), For Gold &
  Glory (the quotable 2e RAW), fan/wiki per the license noted in §2.
- `content/official/` (purchased PDFs): cite by (product, page) pointer ONLY —
  never paste its text into an artifact. The DM reads from their own copy.
- 5e-2014 encounter math is REFUSED by license (SRD 5.1 never contained it).
  That refusal is correct behavior: use the 5e-2024 budget (XP p.202) with a
  note, or 2e reaction/morale doctrine. Don't work around the refusal.

## R5 — Dice
- Every roll for the encounter goes through Modron. No die falls before
  `session_open`; the commitment goes into the run record §1 FIRST.
- The run ends with `session_close` + `verify(session_id)`; the verdict lands
  in the run record §5. The seed is revealed **on demand** (MODRON §12 Q1 —
  `session_close(reveal=true)`, at close or re-called later): when revealed,
  seed + sha-check join §5; until then §5 says `WITHHELD`. A record without
  close+verify is still OPEN, not done.
- Modifiers carry sources: registry names, or inline with
  `source{kind: core|mimir|mechanus|table|fiat, ref}`. Unsourced is refused —
  that refusal is correct.
- Fiat happens only through `force(value, reason)`; it is ledgered
  `method: fiat` forever and listed in the run record §4. A fiat wearing a
  rolled costume is a defect, full stop.
- Every `lawfulness_flags` / `requires_confirmation` / `suspect` raised by
  `rollables` is surfaced in §3 and adjudicated (confirmed, cured at the gate,
  or struck) before `status: READY`. Silencing a flag is a defect.

## R6 — Law lane
- DCs and targets come from `mechanus dc_suggest` or page-cited RAW — not vibes.
- Check `precedents` before ruling fresh. Rulings during play go through
  `record_ruling` (docket law: exactly one ADOPTED, `why` on rejections,
  honest scope), citing Modron `roll_id`s and entity id + admission_sha in the
  quote locs.
- Skulls stay in lane: Modron judges no law, Mimir asserts no law, rulings live
  only in Mechanus's ledger.

## R7 — Validation gates (design AND run)
- §5 spec passes `encounter_rolls(..., plan_only=true)`; the validated plan is
  recorded in §6 (compact reformat fine) and reviewed by the DM.
- Any rollable table validates (coverage gaps/overlaps adjudicated, not ignored).
- §10 checklist fully checked. Any open box keeps `status: DRAFT`.
- Open questions are classed, and the class decides the gate: **[design hole]**
  blocks READY · **[bind]** (party-dependent params, e.g. `reaction.cha_mod`)
  must be resolved into the run record header before `session_open` ·
  **[DM color]** never blocks.
- At run time, before `session_open`: every [bind] resolved, and the artifact's
  `law_version` compared against live `law_info()` — on mismatch, re-validate
  §7 before play. The stamp exists to be checked, not worn.

## R8 — Aftermath
- World-state changes from play are PROPOSALS: file them to Mimir's review loop
  (review queue / curation candidates) — never direct store writes (R1).
- The run record links every docket id, fiat row, and follow-up before the
  session is called closed.
