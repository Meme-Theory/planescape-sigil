# Rules: combat records (REQUIREMENTS)

Skills direct. Templates format. **Rules require.** The shape lives in
`.claude/templates/combat-record.md`; canonical examples in
`.claude/agent-memory/{lemure,abishai}/trials/cbt-*.md`.

Scope: any combat — one swing or a whole melee — adjudicated by an agent or at
the table, any view (`2e`, `5e-2014`, `5e-2024`).

## Identity & stamps

1. MUST carry id `cbt:<view>:<encounter-slug>:<NNNN>` (monotonic per recording
   agent), an absolute date, the view, `law_version`, `engine_version`.
2. Conventions in force are disclosed up front: the pack and any overlays
   (`conventions(view)` discloses house variants), crit law, initiative law, and
   the docket ids of any house rules that apply.

## Combatants

3. Every cited value (AC, THAC0, HP, saves, morale, MR) names its source: Mimir
   entity ref + admission_sha, a printed page, or a labeled fixture. UNCURED
   build-layer values keep their UNCURED flag — rollables' warning is reproduced,
   never laundered.
4. A lawfulness badge (`is_lawful`) is RECOMMENDED per combatant. An
   `applicable: false` or all-skip verdict is no witness — record it as such,
   never as a pass.

## Rounds & dice

5. Initiative, attacks, damage, saves, morale: every die from Modron with
   roll_id + faces. Fiat only via `force`, labeled with its reason.
6. Every attack shows its derivation per pack: 2e `hits AC = THAC0 − total`
   (descending AC); 5e `total vs AC`. Naturals are recorded; nat-20/nat-1
   handling per pack — 2e auto-hit/miss with NO damage effect, 5e crit doubles
   the DICE and never the modifiers.
7. Damage with modifiers records composition order: per-die attachments → adds →
   wraps LAST (resistance/vulnerability after everything — Modron V&V D1). Each
   wrap names its source.
8. Riders and conditions apply only with a law cite; condition names come from
   the view's closed set (`conditions.json`). Unresolved riders (an uncontested
   save, an unanswered morale trigger) are recorded PENDING, never dropped.
9. 2e morale: record the trigger, roll 2d10 ≤ morale when it fires — never
   pre-roll. 5e concentration: DC = max(10, ⌊damage/2⌋), each instance its own
   save.
10. HP accounting: running totals per combatant, each total's asserter named;
    temp HP and healing the same.

## Rulings & law

11. Anything beyond pack-mechanical adjudication becomes a Mechanus docket
    (`record_ruling`): exactly one ADOPTED, why on every rejection, scope honest,
    `rolls[]` citing the roll_ids. Docket ids land in the record.
12. Quoting law: FG&G / SRDs verbatim-with-page (SRD quotes ship attribution);
    official scans cite-only — same law as skill-check rule 10.

## Verification

13. Committed sessions for anything that matters: commitment recorded at open,
    reveal + `verify(session_id)` at close, independent recomputation noted,
    fiat rows enumerated.
14. The record ends with the field state — who stands, HP totals, conditions in
    force, PENDING checks — so a follow-up session can resume from the record
    alone.
