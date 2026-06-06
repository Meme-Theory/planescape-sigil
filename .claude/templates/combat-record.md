# Template: combat record

The shape. The requirements live in `.claude/rules/combat-records.md` — read them
before first use. Canonical filled examples:
`.claude/agent-memory/{lemure,abishai}/trials/cbt-*.md`.

Replace `<angle>` fields. Scale the Rounds section to the fight — one swing is
one row; never delete Verification or End state.

---

# Combat Record — <short title>

| field | value |
|---|---|
| id | `cbt:<view>:<encounter-slug>:<NNNN>` |
| date | <YYYY-MM-DD> |
| view | <2e \| 5e-2014 \| 5e-2024> |
| stamps | law_version `<sha16>` · engine_version <n> |
| session | `<session_id>` — commitment `<sha256>` published before any die |

## Combatants

| name | side | ref / source | key values (asserter per value) |
|---|---|---|---|
| <name> | <A/B> | <`type:source:id` + admission `<sha16>` \| <product> p.<N> \| fixture> | <AC/THAC0/HP/morale…> |

lawfulness badges: <name — `is_lawful` verdict, checks run/skipped, law_version;
"all-skip = no witness" if applicable>

## Conventions in force

- pack `<view>` (overlays: <none \| disclosed list from `conventions(view)`>)
- crit law: <5e: double DICE never mods \| 2e: none — nat 20 auto-hits only>
- initiative: <pack line> · house rules: <docket ids \| none>

## Rounds

### Round <n>

| step | actor → target | roll_id | faces | result |
|---|---|---|---|---|
| <attack/save/morale…> | <X → Y> | `<roll_id>` | `<faces>` | <hit/miss/margin/natural> |

- derivation: <2e: THAC0 <t> − total <n> = hits AC <a> vs target AC <a'> \|
  5e: total <n> vs AC <a>>
- riders/conditions applied: <name — law cite> · PENDING: <uncontested save etc.>
- triggers: <morale / concentration — rolled when fired, never pre-rolled>

## Damage & effects ledger

| target | amount/type | roll_id | composition | hp after (asserter) |
|---|---|---|---|---|
| <name> | <n type> | `<roll_id>` | <base / per-die → adds → wraps last> | <n (who tracks)> |

## Rulings

<docket ids + one-line summaries (ADOPTED + rejected-with-why) \| "none needed —
pack-mechanical throughout">

## Law cited

| claim | source | quotable? |
|---|---|---|
| <claim> | <product p.N> | <verbatim ok \| cite-only> |

## Verification

verify(`<session_id>`) → <PASS> (<n>/<n>) · seed revealed · commitment
independently recomputed: <VERIFIED \| not performed> · fiat rows: <n>

## End state

<who stands; HP totals; conditions in force; PENDING checks — resumable from
this block alone>
