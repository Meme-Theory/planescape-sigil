---
name: encounter-run
description: Run a prepared encounter at the table — committed Modron session, doctrine batch, play loop, rulings as dockets, verify-and-seal close (seed reveal on demand), run record. Use when the DM says run/start/play an encounter. Args: "<slug> [night-N] [seed_phrase]"; the artifact must exist under build/encounters/<slug>/.
---

# /encounter-run — the night, on a committed ledger

You are executing `build/encounters/<slug>/encounter.md` and writing its **run
record**. Read first, in order (BLOCKING):

1. **`.claude/rules/encounters.md`** — R1/R5/R6/R8 govern play.
2. **The artifact** — §5 spec, §6 plan, §7 law, §8 triggers, §9 ceremony.
3. **`.claude/templates/encounter-run.md`** — the record's shape.

## Phase 0 — Gate check

- Artifact `status: READY` required. `DRAFT` → stop; either finish
  `/encounter-plan`'s R7 gate or get the DM's explicit override **and write the
  override into the run record header**.
- Resolve every §10 **[bind]** (party-dependent params — e.g. `reaction.cha_mod`)
  with the DM now; bound values go into the run record header. An unresolved
  bind blocks `session_open` (R7).
- `law_info()` vs the artifact's `law_version` — on mismatch, re-validate §7
  against current law before play (R7).
- `conventions(view)` — load the doctrine and check kinds for the artifact's view.

## Phase 1 — Ceremony (commitment BEFORE any die, R5)

1. `session_open(label="<slug>--night-N", view=<artifact view>,
   seed_phrase=<if the table chose one>)`.
2. **Immediately** create `build/encounters/<slug>/runs/<session_id>.md` from
   the template — commitment sha, phrase-or-drawn, where published — *before
   anything rolls*. That ordering IS the fairness protocol.
3. Show the table the commitment.

## Phase 2 — The opening batch

- `encounter_rolls(encounter=<§5 spec>, view=<view>, session_id=<ses>)` — the
  doctrine steps roll as one batch; record `batch_id` and every row (roll_id,
  result) in the record §2.
- Honor `stop_if_no_encounter`. Morale steps arrive **ARMED, not pre-rolled** —
  they wait for §8's fiction triggers.

## Phase 3 — The loop (every die through Modron, R5)

- Attacks/checks/saves: `roll_check(kind=<per conventions(view)>, params={...},
  view, session_id)` — params (THAC0/AC, attack_bonus/DC…) come from the
  artifact's specs and §7 law, not improvisation.
- Damage: `roll_damage(expr, view, crit=<outcome.crit>, session_id)` — crit law
  is the view's, not memory.
- Tables: `roll_table` (inline, path, or entity ref).
- Modifiers: registry names (`modifiers(query)`) or inline **with
  `source{kind,ref}`** — unsourced is refused and that refusal is correct.
  `purpose`/`context` tags on rolls keep `history` legible.
- Morale fires when the fiction says (first blood, leader down — §8):
  `roll_check(kind="morale", ...)`. Reaction bands read from the batch row.
- Every row → record §2 with its roll_id.

## Phase 4 — Rulings at the table (R6)

When a law question arises mid-scene:
1. `precedents(<question terms>)` — same question, same answer. (Until
   Mechanus F4 lands: no hyphens in topics — FTS5 column crash; filed.)
2. New ground → `record_ruling`: docket law (exactly one ADOPTED, `why` on every
   rejection, honest scope — `table:*` for table calls), **citing the live
   roll_ids and the entity id + admission_sha in the quote locs**.
3. Table overrides RAW → `overrule` with scope; chain stays queryable.
4. Docket ids → record §3.

## Phase 5 — Fiat (rare, honest, R5)

Only on the DM's explicit decree: `force(value, reason, expr=<what it stands in
for>, session_id)` → record §4. It ledgers as `method: fiat` forever — never
re-narrate it as a roll. If you're an agent staging this run: **you never call
force** — surface the moment to the DM and wait.

## Phase 6 — The close (R5)

1. `session_close(session_id)` — seals the stream; the seed stays WITHHELD
   (on-demand cadence, MODRON §12 Q1). Record §5: `seed: WITHHELD`.
2. `verify(session_id)` → verdict (N/N PASS, or the exact diff) into §5 —
   verify needs no reveal. Fiat rows report FIAT — that's the labeling
   working, not a failure.
3. Reveal ON DEMAND — when the table asks (or DM policy says): re-call
   `session_close(session_id, reveal=true)`; seed + the
   `sha256(seed) == commitment` PASS/FAIL go into §5 with when/why.
4. Frontmatter `status:` → `CLOSED-VERIFIED` (or `CLOSED-DISPUTED` with the
   diff preserved — never massage it).
5. Artifact frontmatter `status:` → `RUN`.

## Phase 7 — Aftermath (R8)

- Record §6: outcomes, world-delta **proposals** (Mimir review-queue /
  curation candidates — never direct store writes), follow-up threads.
- `history(session_id=...)` to reconcile the record against the ledger before
  calling it closed — every §2 row should match a ledger row.

Hand back: run record path, the §5 verify line, docket ids, and the §6 threads.
