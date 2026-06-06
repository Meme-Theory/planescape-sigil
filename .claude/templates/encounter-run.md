---
slug:                # parent encounter (build/encounters/<slug>/)
session_id:          # ses:... from session_open
label:               # e.g. friendly-fiend-heist--night-1
view:                # inherited from the artifact (R2)
opened:              # timestamp from session_open
closed:              # timestamp from session_close — filled at close
status: OPEN         # OPEN | CLOSED-VERIFIED | CLOSED-DISPUTED
template_version: 1
---

# Run: <label>

<!-- One run, one record (R1). Format = this template; requirements =
     .claude/rules/encounters.md; direction = .claude/skills/encounter-run.
     §1 is written BEFORE any die falls — that ordering IS the fairness
     protocol. Empty sections say "none"; absence must be legible. -->

## 1. Commitment — written before any roll (R5)

- commitment `sha256(seed)`: `...`
- seed_phrase: <table-chosen phrase | none — drawn>
- published: <where/when the table saw it — chat, table screen, this file>

## 2. The rolls

<!-- Chronological. The opening batch from encounter_rolls first (one batch_id),
     then the play loop. Every row carries its roll_id — that's the citation
     currency. Morale rows note the fiction trigger that fired them (§8 of the
     artifact). -->

- batch_id: `...`

| # | step / intent | roll_id | expr / kind | result | note |
|---|---|---|---|---|---|

## 3. Rulings

<!-- Docket per ruling (R6): precedents consulted first; record_ruling cites
     roll_ids + entity id + admission_sha in the quote locs. If the director
     agent staged this run, rulings appear here as PROPOSED docket JSON for the
     DM to record — mark them recorded (docket id) before close. -->

| docket | question | outcome | cites |
|---|---|---|---|

## 4. Fiat ledger

<!-- Every force() call: ledgered method:fiat, reason required (R5). Empty is
     the goal; honest is the law. -->

| roll_id | stood in for | value | reason |
|---|---|---|---|

## 5. Close & verify (R5)

- `verify(session_id)`: <N/N PASS | the exact diff>
- seed: WITHHELD (on-demand cadence, MODRON §12 Q1) | revealed `<hex>`
- if revealed — `sha256(seed) == commitment`: PASS | FAIL · when/why: <the
  table asked | DM policy | dispute>
- status set: CLOSED-VERIFIED | CLOSED-DISPUTED <!-- mirror into frontmatter -->

## 6. Aftermath (R8)

- outcomes: <who lived, what changed hands, what the party now knows or owes>
- world-delta proposals filed: <review-queue items / curation candidates — never direct store writes>
- follow-ups: <threads opened, debts incurred, the next encounter's seed>
