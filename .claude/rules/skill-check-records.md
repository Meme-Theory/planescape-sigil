# Rules: skill-check records (REQUIREMENTS)

Skills direct. Templates format. **Rules require.** A record that violates a MUST
below is not a record — it's an anecdote. The shape lives in
`.claude/templates/skill-check-record.md`; canonical examples in
`.claude/agent-memory/{lemure,abishai}/trials/skc-*.md`.

Scope: any ability / skill / proficiency / save-style check adjudicated by an
agent or at the table, any view (`2e`, `5e-2014`, `5e-2024`).

## Identity & stamps

1. MUST carry id `skc:<view>:<slug>:<NNNN>` — NNNN monotonic within the recording
   agent's memory; never reused, never backfilled.
2. MUST carry an absolute date, the view, and stamps: Mechanus `law_version` and
   Modron `engine_version` whenever any law table or roll is cited.
3. The check kind MUST be a convention-pack kind for the view (see
   `conventions(view)`), and the record states the pack's success semantics —
   e.g. 2e roll-under: success is total ≤ target, margin reads target − total.

## Dice

4. Every die face MUST come from Modron: roll_id, faces, total, sha. A number
   without a roll_id is fiction — never write one.
5. DM overrides go through `force`, and the record says `method: fiat` plus the
   reason. A fiat row wearing a rolled costume is a bug in Modron's law and a lie
   in ours.
6. When a session is used, record session_id + seed commitment; the verification
   block (rule 13) becomes mandatory.

## Values & asserters

7. The target (DC / score / percentage) MUST name its asserter AND its law
   source: a `dc_suggest` cite (5e), a statblock value (entity ref), or a printed
   page. "DC 15 because it felt right" is fiat — label it fiat.
8. Every modifier MUST carry a source `{kind: core|mimir|mechanus|table|fiat,
   ref}`. Modron refuses unsourced inline mods at roll time; this format refuses
   them at record time.
9. Actor facts served by Mimir MUST carry the admission_sha. Non-poured stand-ins
   are labeled `fixture` with an honest asserter — a fixture posing as an
   admitted entity is provenance fraud.

## Law

10. Verbatim quotes ONLY from quotable sources: FG&G (2e RAW) and SRD 5.1/5.2.1
    (CC-BY-4.0 — quoted SRD text ships with attribution; Mechanus `attribution`
    serves the block). `content/official/` (purchased PDFs, incl. PAitM) is
    CITE-ONLY in anything that ships: product + page, paraphrase. A local
    record may reproduce an official excerpt ONLY through a local store that
    already holds it (a Mimir envelope, a docket raw_quote), citing the
    admission_sha / docket id — never pasted from the scan itself.
11. RAW and interpretation MUST be separated; readings you rejected are preserved
    with why — docket law applies to records too.
12. A skipped check is NO WITNESS, never a pass (the G6 lesson). If everything
    contemplated turned out inapplicable, the record says so explicitly.

## Verification

13. Sessions: record the close reveal, the `verify(session_id)` verdict, and
    whether the commitment was independently recomputed. Sessionless rolls: note
    the ephemeral-seed reproducibility instead.
14. If the check spawned an official ruling, record the Mechanus docket id. The
    docket cites roll_ids; it never contains dice.
