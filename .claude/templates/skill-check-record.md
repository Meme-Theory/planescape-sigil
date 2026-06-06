# Template: skill-check record

The shape. The requirements live in `.claude/rules/skill-check-records.md` — read
them before first use; a record that breaks a MUST there is an anecdote, not a
record. Canonical filled examples:
`.claude/agent-memory/{lemure,abishai}/trials/skc-*.md`.

Replace `<angle>` fields. Delete rows that genuinely don't apply (e.g. `state`
in 2e — no advantage machinery); never delete the Verification section.

---

# Skill Check — <short title>

| field | value |
|---|---|
| id | `skc:<view>:<slug>:<NNNN>` |
| date | <YYYY-MM-DD> |
| view | <2e \| 5e-2014 \| 5e-2024> |
| stamps | law_version `<sha16>` · engine_version <n> |
| actor | <name> — <`type:source:id`, admission `<sha16>` \| fixture (asserter: <who>)> |
| check | `<pack kind>` — <ability / skill / proficiency name> |
| target | <n> — asserter: <who/what>; law: <product> p.<N> |
| state | <flat \| advantage \| disadvantage> |

## Modifiers

| name | value | source {kind: ref} |
|---|---|---|
| <name or "none"> | <±n> | <core\|mimir\|mechanus\|table\|fiat: ref> |

## Dice

session `<session_id>` — commitment `<sha256>` published before any die fell

| purpose | roll_id | faces | total | sha |
|---|---|---|---|---|
| <check> | `<roll_id>` | `<faces>` | <n> | `<sha16>` |

## Outcome

**<SUCCESS \| FAILURE>** — natural <n>, total <n> vs target <n>, margin <±n>
(pack `<view>` success_op `<op>`; <margin semantics, e.g. roll-under: margin =
target − total>)

## Law

- "<verbatim quote>" — <FG&G \| SRD 5.1 \| SRD 5.2.1> p.<N> <(+ attribution
  shipped, if SRD quoted into a shared artifact)>
- <paraphrase only> — <official product> p.<N> (cite-only source)

## Verdict & notes

<the adjudication: RAW stated apart from interpretation; rejected readings
preserved with why; open questions numbered>

## Verification

verify(`<session_id>`) → <PASS> (<n>/<n> recomputed) · seed revealed ·
commitment independently recomputed: <VERIFIED \| not performed> · fiat rows: <n>
