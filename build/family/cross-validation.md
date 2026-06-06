# Three-Skull Cross-Validation — seam audit, 2026-06-05

**Scope:** tool-to-tool validation across Mimir/Mechanus/Modron over the live MCP
connections, immediately after Mimir's first pour (Uncaged: 52 entities, 229 edges,
0 quarantined). **Question asked:** do the *contracted* seams actually carry load, and
where are the gaps? **Verdict: the family meshes — every seam either works or fails
exactly where its own design doc predicted.** Two gaps fixed in-session (Mechanus
lane), four assigned (one each: Modron ×2, Mimir+Mechanus joint, Mechanus design),
six skills identified for the table loop.

---

## 1. Connect-point map (what's contracted, what's carried)

| # | seam | mechanism | live status |
|---|---|---|---|
| C1 | siblings → Mimir store | `store.py` read-only (`HandbookStore(DEFAULT_DB, readonly=True)`) — the lib IS the schema | **VERIFIED** from Mechanus context: `get`/`search`/`neighbors` serve admitted+cured envelopes; write attempt refused at the SQLite layer (`attempt to write a readonly database`) |
| C2 | Mimir gate → Mechanus `is_lawful` (L3) | contracted in ARCHITECTURE §3 | **PLACEHOLDER** — gate.py's own docstring: "implemented locally as a placeholder until those siblings are importable." They are importable now → G3 |
| C3 | Mimir gate → Modron dice-lawfulness (L3) | MODRON §2.4 | **PLACEHOLDER** — same line of gate.py → G3 |
| C4 | Modron `rollables` ← entity source | "build/ envelopes live today; handbook.db when poured" (MODRON §2.1) | **WORKS, WRONG LAYER** — handbook ids resolve to pre-pour v2 build JSON → G2 (his anticipated one-file flip) |
| C5 | Mechanus dockets → Modron `roll_id`s | docket law `rolls[]` | **VERIFIED** (triangle: 2 roll_ids cited, `verify(session)` PASS) |
| C6 | Mechanus dockets → Mimir entities | free-text `raw_quotes.loc` carrying id + admission_sha | **WORKS AS CONVENTION**, unstructured → G4 |
| C7 | edition strings | `2e` / `5e-2014` / `5e-2024` everywhere; `srd` = license axis, not edition (her CLAUDE.md pin) | **AGREE** across all three |
| C8 | Mimir `curated` → Mechanus waivers | `entity.curated.lawful_waivers` | **SHAPE-COMPATIBLE**, unexercised (no 2e waivers yet); contract stands |
| C9 | Modron rulings-overlay ← `rulings.db` | MODRON §2.3 "when it lands" | **UNWIRED — it landed.** House-rules that alter dice conventions should now flow → assigned with G2 |
| C10 | Mechanus invoke tools ← handbook.db | parked NOT_POURED | **UNPARKABLE NOW** — C1 proves the path; next Mechanus build step |

## 2. The triangle, executed (every system in its lane)

```
Mimir  : get_entity npc:uncaged:a-kin → THAC0 7, claws 1d4/1d4/2d6, admission e3a9694c…
Modron : session_open (commitment 014128ef… published BEFORE any die)
         roll_check attack {thac0:7, ac:5} → NAT 20, auto-hit per FG&G,
            note: "RAW 2e has no critical damage effect"   ← law-correct restraint
         roll 1d4 claw → 4
Mechanus: record_ruling rul:vnv:triangle:akin-claw:001
            • cites BOTH roll_ids  • quotes the poison rider verbatim with
              loc = entity id + admission_sha + uncaged:p9
            • rejected candidate ("nat-20 double damage") preserved with why,
              crediting Modron's pack note as the law source
Modron : verify(session) → PASS (2/2 re-derived) → session_close → seed revealed
us     : sha256(seed) == commitment → VERIFIED independently
```

Provenance threads end-to-end: pull the docket's thread and you reach a die face, an
admission sha, and a page. The boundary held under temptation — Modron *flagged* the
crit question without judging it; Mechanus judged it citing Modron's pack note as law.

## 3. Gaps (numbered, owned, dispositioned)

| id | owner | finding | disposition |
|---|---|---|---|
| **G1** | Mechanus | Served 2e envelopes carry **string numerics** (`"ac":"-8"`) and `level_hd` in `descriptor`, not statblock → adapter skipped THAC0/HP/AC checks → **vacuous lawful** (demonstrated live: A'kin passed 2, skipped 3) | **FIXED + PINNED** this session (`_int_coerce`, descriptor fallback; served-shape test runs all 5 checks). Live server picks it up on next `/mcp` reconnect |
| **G2** | **Modron** | `rollables` resolves handbook ids to the **extraction layer** → misses gate-time curations. Demonstrated: Cirily compiles **`740d8` hp** from raw OCR while the admitted envelope holds the vision-cured `7+10` (his own crosscheck flagged `unknown` — the smell detector works; the source is still wrong) | Flip the store seam to `handbook.db` via C1 (`store.py` readonly) — exactly the "one file changes when Mimir lands" his §2.1 promised. It landed |
| **G3** | **Mimir** (+Mechanus assist) | Gate L3 duplicates law locally as admitted placeholder; **drift already visible** — her flat `thac0_range 1..20` vs the FG&G bracket law (no plus-bump, no fractional rows) | Import the siblings: `mechanus.lawful.is_lawful` (use `applicable` — see G6) + Modron's printed-average/parse checks; delete the local duplicates. "The rules live in exactly one place" is her own architecture doc |
| **G4** | Mechanus (design) | Dockets cite entities as free-text `raw_quotes.loc` — works, but precedents-by-entity isn't queryable | Add structured `entity_refs: [{id, admission_sha}]` to docket law (validated like `rolls[]`); index it. Small ledger schema addition, my lane |
| **G5** | Mechanus | `known_waivers()` keys on 5e-bits index/name; handbook ids (`npc:uncaged:*`) won't hit when 5e pours | Harmonize key normalization at 5e pour time (strip `type:source:` prefix before lookup) |
| **G6** | Mechanus | All-checks-skipped returned `lawful:true` — silence read as confirmation | **FIXED + PINNED**: verdicts now carry `applicable` + `checks_run`; a gate must treat `applicable:false` as *no witness*, never as pass |
| **G7** | Modron (+Mimir assist) | Even post-G2-flip, `rollables` has no quarantine-awareness — it would happily compile a quarantined entity | Serve admission status through `store.py` (Mimir: tiny accessor) and have rollables flag/refuse non-admitted entities |

## 4. Skills identified (thin orchestrations over existing tools)

Candidates for `.claude/skills/` — each is the triangle (or a slice) packaged for play.
All become materially better after G2/G3 land:

1. **`/statblock <name> [view]`** — Mimir `get_entity` → Mechanus `is_lawful` badge →
   Modron `rollables` → one table-ready card with provenance. (Read-only triangle.)
2. **`/attack <npc> vs <ac>`** — rollables spec → `roll_check` on the active session →
   outcome + cites; offers the damage follow-up from the same spec set.
3. **`/ruling <question>`** — Mechanus `precedents` first (same-question-same-answer),
   else walk the ladder, `record_ruling` with `rolls[]`/`entity_refs[]`; renders RAW
   quote apart from interpretation, losers included.
4. **`/session open|close [label]`** — Modron ceremony wrapper; close auto-verifies the
   night and posts commitment/reveal pair for the table.
5. **`/encounter <location|faction>`** — Mimir search/graph for context → Modron
   `encounter_rolls plan_only` → DM reviews the plan → execute batch on session.
6. **`/pour-status`** — Mimir `coverage` + `review_queue` digest; the curation
   worklist as a morning report.

## 5. Family observations (working as designed)

- **Provenance composes across stores**: `law_version` (dockets) + `engine_version`
  (rolls) + `admission_sha` (entities) interlock — any answer reconstructs.
- **Boundary discipline held under live fire**: Modron surfaced the crit question as a
  *pack note*, refused to adjudicate it; Mechanus adjudicated citing the note. No system
  reached into another's lane during the whole exercise.
- **Edition-as-view agreement is real**: same strings, same semantics, three codebases.
- **The lens pattern is uniform**: all three stores audit the same way (locks, SHA
  dedup, guarded writes) — a fourth sibling would know exactly how to behave.

— *executed by the Mechanus session against live mimir/mechanus/modron MCP connections;
reproducible from the transcript, the ledgers, and the suites (Mechanus 109 green incl.
G1/G6 pins).*
