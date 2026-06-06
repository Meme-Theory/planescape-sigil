# Modron — the Dice Engine MCP (design, v1)

> A modron does not gamble. A modron *executes stochastic procedure*.
> Modron is the third system: where Mimir remembers and Mechanus rules,
> Modron **rolls** — every die seeded, every face ledgered, every modifier
> sourced, every result reproducible. Ordered chance. The dice are lawful.
>
> **The marquee use case (Meme, verbatim):** *"not only our dice roller, but
> also our MCP to determine dicerolls from encounters and modules"* — point it
> at an encounter, a module table, a statblock, and it tells you what wants
> rolling, with what dice, under which edition's conventions — then rolls it
> on an auditable stream.
>
> Design law (inherited): **Mimir is the only knowledge store; Mechanus is the
> only judge of law; every answer carries provenance.** Modron adds one store
> of its own — the **roll ledger** — and zero entity stores, zero rulings.

Status: design doc + reference implementation (`pipeline/modron/`).
Sister docs: `ARCHITECTURE.md` (the system split), `MECHANUS.md` (the law),
`DIMENSIONS.md` (what entities are), `VALIDATION.md` (how they're admitted).

---

## 1. The three systems — and where the dice fall

| | **Mimir** (content) | **Mechanus** (law) | **Modron** (chance) |
|---|---|---|---|
| knows | what **is** | what **governs** | what the dice **said** |
| owns | `handbook.db` + gate | `rulings.db` + mechanical core | `rolls.db` (ledger) + the RNG discipline |
| surface | curatorial | rulings/conversion | execution: `roll / roll_check / roll_table / rollables / encounter_rolls / stats / verify` |
| writes | entities, via gate | rulings, via `record_*` | roll records, via guarded append (lockfile + SHA-unique — the `emit_verdict` discipline) |
| reads | sources, wikis, scans | `handbook.db` read-only | `handbook.db` read-only **+** `rulings.db` read-only (when it lands) |

The boundary, sharpened:

| concern | owner | Modron's part |
|---|---|---|
| "A'kin's damage is `1d4/1d4/2d6`" | **Mimir** stores it | parses & executes it |
| "you have advantage; add `+1d4` bless" | **Mechanus** (or the DM) asserts it | composes & executes it, **recording who asserted** |
| "what does this encounter need rolled?" | — | **Modron compiles it** — dice-*syntax* knowledge (finding/parsing dice in data) is Modron's lane; dice-*law* (which modifiers apply) is not |
| "did the d20 come up 17?" | **Modron** — sole authority | seeded stream, per-die audit, ledger row |

Modron **never decides rules**. It accepts a roll *specification* — expression +
modifiers, each modifier tagged with its source — and executes with total
fidelity. When a caller asks a semantic question ("attack roll, 2e, THAC0 7 vs
AC 3"), the *procedure* comes from a **convention pack** (data, per edition),
and the *values* come from the caller, Mimir, or Mechanus — never invented.

## 2. The interface contract

1. **One-way reads, shared-lib seam.** Modron reads `handbook.db` read-only via
   the same shared store lib Mechanus uses (`store.py` — the lib is the schema;
   no MCP-over-MCP on the hot path). Until Mimir pours, the seam also accepts
   the v2 extraction envelopes directly (`build/**/npc/*.json` — live today)
   and inline entities. One file changes when Mimir lands.
2. **Modifiers flow in, with provenance.** Three channels:
   - **inline** — any caller (DM, Mechanus mid-`resolve`, a backend) passes
     `mods: [{id|effect, source:{kind,ref}}]`; applied and ledgered verbatim;
   - **registry** — named modifiers (bless, GWF, Halfling Luck…) shipped as
     data in `data/modifiers/*.json`, each with its own source field;
   - **rulings overlay** — when `rulings.db` exists, scoped house rules that
     alter dice conventions (crit range, max-HP-at-first…) ride in as
     convention overrides; until then, `data/overrides/*.json` is the local
     overlay. Either way: data, never code.
3. **No write path into the siblings.** Modron proposes nothing to the gate and
   records no rulings. Its single store is the append-only roll ledger.
   (If a backend wants a roll *result* persisted as lore — "the slaad rolled
   a natural 20 and the bridge fell" — that's the backend proposing to Mimir,
   citing the `roll_id`.)
4. **Free-witness reciprocity, extended to chance:**
   - **Modron → Mimir:** the *dice-lawfulness check*. Printed average vs
     exact mean (`Hit: 14 (2d8+5)` — mean 14 ✓), printed HP within HD range
     (A'kin 92 ∈ [36,120] for `12d8+24` ✓), dice that fail to parse
     (`2dB+5`) — all transcription-error detectors the gate can run as an L3
     channel for free. Modron's `analysis` never saw the extractor's sources.
   - **Modron → Mechanus:** exact PMFs + the ledger's empirical streams =
     test vectors for DPR/CR estimation when the conversion engine calibrates.
   - **Mechanus → Modron:** convention packs encode per-edition dice law;
     when Mechanus formalizes those rules as entities, packs cite them by ID.
5. **Every roll cites.** A ledger row carries: the expression as asked, the
   expression as executed (post-composition), every die face with its fate
   (kept/dropped/rerolled/exploded), every modifier with its source, the
   context ref (entity/encounter/ruling), seed reference, counter, and a
   content-address SHA. Pull any total's thread and you reach a seed and a page.

## 3. Ordered chance — the RNG discipline

*(This resolves MECHANUS.md §11 Q3 — and `roll` leaves Mechanus's surface; see §9.)*

- **Derivation (engine v1, pinned):** die draws come from
  `sha256(seed ‖ u64be(roll_counter) ‖ u64be(draw_index) ‖ u32be(chunk))` →
  first 8 bytes as a **big-endian** u64 → **rejection-sampled** modulo sides
  (no modulo bias). Uniform by construction, reproducible from
  `(seed, counter)` alone. *(Byte order added 2026-06-06, audit
  F-1-design-docs-01 — the clean-room pin must name it.)*
- **Sessions commit.** `session_open` records `sha256(seed)` — the
  **commitment** — before any die falls. `session_close` SEALS the stream;
  the seed is revealed **on demand** (`reveal=true`, at close or re-called
  later — §12 Q1). Once revealed, anyone can recompute every roll of the night
  and verify no die was fudged. Auditable fairness, cryptographically bound,
  zero table friction.
- **Ephemeral rolls** (no session) get a fresh recorded seed — reproducible
  and ledgered, just not pre-committed.
- **Fiat is honest.** `force` exists (DM's table, DM's god-voice) but writes
  `method: "fiat"` with a reason — a forced value never wears a rolled
  costume. The rogue modron is *labeled*.
- **Replay/verify are first-class tools**, not forensics: `verify(roll_id)`
  re-derives the stream and re-checks the SHA; `verify(session_id)` sweeps the
  whole night.

## 4. The grammar (dice notation is the contract)

Recursive-descent parser → typed AST → evaluator. Regex never touches play.
Canonical **normal form** (what the SHA hashes) round-trips through the parser.

```
expr    := term (('+'|'-') term)*
term    := factor (('*'|'/') factor)*          # '/' = integer, pack rounding
factor  := dice | number | '(' expr ')' | func | '-' factor
dice    := [count] 'd' (sides|'%'|'F') postfix*
postfix := 'kh'N | 'kl'N | 'dh'N | 'dl'N | 'k'N          # keep/drop
         | '!' | '!!' | '!'cmp                            # explode / compound
         | 'r'cmp | 'ro'cmp                               # reroll / reroll-once
         | 'min'N | 'max'N                                # per-die clamp
         | 'cs'cmp | 'cf'cmp                              # success/fail counting
cmp     := ['<'|'>'|'<='|'>='|'='] N      (bare N = exact face)
func    := adv|dis|ea|crit|repeat|floor|ceil|round|abs|min|max '(' … ')'
```

Covers: `3d6+2` · `4d6kh3` (ability) · `2d20kh1` (advantage) · `2d6ro<3`
(Great Weapon Fighting) · `d6!` (exploding) · `1d20min10` (Reliable Talent) ·
`8d6/2` (resistance, pack rounding) · `d%`/`1d100` · `4dF` (Fate) ·
`crit(2d8+5)` (pack-defined crit effect) · `repeat(4d6kh3, 6)` (the array) ·
`10d10cs>=8` (success pools — not D&D, but flexibility is the brief).

**Guardrails (the lawful machine refuses unbounded work):** ≤1000 dice/term,
≤10000 sides, explosion depth ≤100, expression ≤2000 chars, AST depth ≤50.

**Changeability axes** (in order of how often we expect to pull them):
1. new **named modifier** → JSON row, no code (if built from existing effects);
2. new **edition / house variant** → convention-pack JSON drop-in or overlay;
3. new **semantic check kind** → a pack `checks` entry (data);
4. new **effect primitive** → one registered AST-transform function;
5. new **notation** → one postfix/func registration in grammar + evaluator;
6. new **rollable source shape** → one compiler function per dimension
   (the `extract_<type>()` recipe, applied to dice).

## 5. Convention packs — edition is a view, for dice too

The same semantic ask — *attack, save, check, initiative, morale, reaction,
surprise* — resolves through the active view's pack (`data/conventions/<view>.json`):

| | `5e-2014` / `5e-2024` | `2e` |
|---|---|---|
| attack | `1d20+{attack_bonus}` vs AC, ≥; crit nat 20 → `double_dice` | `1d20` vs `THAC0−AC`, ≥; nat 20 hits / nat 1 misses; reports "hits AC ⌊THAC0−roll⌋" |
| save | `1d20+{save_bonus}` vs DC ≥ | `1d20` vs category target ≥ (target supplied — save matrices are **law**, i.e. Mechanus/caller input) |
| ability check | `1d20+{mod}` vs DC ≥ | `1d20` vs ability score **≤** (roll-under) |
| initiative | `1d20+{dex_mod}`, high first | `1d10[+speed]`, **low first** |
| morale | — | `2d10` vs rating ≤ |
| reaction | — | `2d10` banded table (pack data) |
| percent (MR, thief skills, "40% chance") | — / d100 ≤ | `1d100` ≤ pct |
| HP from HD | explicit (`16d10+48`) | `{n}d8+{plus}` for monsters (`12+24` → `12d8+24`) |
| d20 state machine | adv/dis **cancel to flat**, never stack; Elven Accuracy upgrades adv → `3d20kh1` | n/a |
| rounding | down | down |

Packs carry unknown keys untouched (queryable), so a future mechanic can ship
data before code. Overlays deep-merge over packs and are reported by
`conventions()` — a hidden house rule is not a house rule.

**Setting packs (2026-06-06):** the `extends` chain also carries SETTINGS —
`2e-planescape` extends `2e` with plane-scoped check kinds (Limbo casting and
alteration drift, miniflux, Pandemonium wind madness, Styx ingestion, the
Wasting) per the rule-effect handoff (§9). Edition packs stay edition-pure;
overlays stay house-rules-only; printed setting law gets its own view. Its
sibling data lane is the **rollables registry** (`data/rollables/*.json`):
page-cited tables, roll specs, diceless lookups, and encounter specs —
load-validated (source required, coverage checked), served via `roll_table`
(table ids) and `rollables` (any id, or `used_at` discovery).

## 6. The rollables compiler — encounters & modules

`rollables(entity)` walks a Mimir envelope (or v2 build JSON, or inline) and
emits **roll specs with field-level provenance**:

- **2e statblock:** THAC0 → attack spec; `damage "1d4/1d4/2d6 (claw/claw/bite)"`
  → three labeled damage specs; `magic_resistance "60%"` → percent-under;
  `morale "champion (16)"` → morale-vs-16; `level_hd "12+24"` → HP `12d8+24`
  (+ printed-HP-in-range crosscheck); `num_attacks` sanity vs damage count.
- **5e statblock:** action text → `+7 to hit` / `Hit: 14 (2d8+5)` /
  `DC 15 Dexterity saving throw` / `Recharge 5–6`; HP `136 (16d10+48)` with
  printed-average crosscheck; saves/skills/initiative from bonuses.
- **Range inversion:** 2e's `"3-18"` → `3d6` — candidates ranked (no-bonus
  first, common dice first), **alternatives and ambiguity always surfaced**,
  never silently picked.
- **Prose sweep (OCR-lenient):** `Id6 mezzoloths` → `1d6` (the v1b
  normalization map: `I`/`l`→`1`, `O`→`0`, in dice context only), `"40%
  chance of success"` → percent spec — flagged `from_prose`, confidence-tagged,
  `requires_confirmation`. Useful for prep; honest about its grade.
- **`dim:table`:** `{dice, entries[{roll,result}]}` → parse ranges
  (`01-05`, `97-00`, `00`=100), **validate coverage** (gaps/overlaps reported),
  roll, resolve entry, follow `chain` directives depth-guarded.
- **`encounter_rolls`:** the orchestration — check (`1-in-10`) → table →
  number appearing → per-creature HP → surprise (both sides) → distance →
  reaction → initiative; morale specs armed for when triggers fire. Step list
  comes from the pack (2e wandering doctrine vs 5e budget doctrine), caller
  may filter/extend; `plan_only` returns the plan unrolled — the DM sees what
  the night will ask *before* it asks. Executed plans share a `batch_id`.

## 7. Tool surface

**Execute (the hot path):**
| tool | does |
|---|---|
| `roll(expr, view?, session?, mods?, label?, purpose?, context?)` | THE tool — parse, compose modifiers, evaluate on the stream, ledger, return total + per-die audit + applied-mods + `roll_id` |
| `roll_check(kind, view, params, mods?, vs?, session?)` | semantic rolls per the pack: attack/save/check/initiative/morale/reaction/percent — returns outcome (success/margin/crit/"hits AC") |
| `roll_damage(expr, view, crit?, mods?, session?)` | damage under edition law: `crit=true` applies the view's crit effect (5e doubles the DICE, never the modifiers; 2e `none` — noted) + `applies_when: crit` mods |
| `roll_table(table, n?, session?)` | roll on a table (ref/inline), resolve entries, follow chains |
| `rollables(entity, view?)` | compile an entity into roll specs (no dice fall) |
| `encounter_rolls(encounter, steps?, plan_only?, session?)` | §6 orchestration; batch-ledgered |
| `parse_expr(expr)` / `dice_stats(expr, view?)` | AST + normal form + limits; exact PMF (convolution/enumeration) or Monte-Carlo **flagged `estimated`** — never dressed exact |

**Ledger:**
| tool | does |
|---|---|
| `session_open(label, view?, seed_phrase?)` | new session → **commitment** published |
| `session_close(session_id, reveal?)` | seal; seed **withheld** until `reveal=true` (on demand) → the night becomes verifiable |
| `history(session?, purpose?, limit?)` | read the ledger |
| `verify(roll_id \| session_id)` | re-derive + re-hash; PASS/FAIL per row |
| `force(value, expr?, reason, session?)` | DM fiat — ledgered as `fiat`, never disguised |

**Registry (the changeability surface):**
| tool | does |
|---|---|
| `conventions(view?)` | show packs + active overlays (overlays always disclosed) |
| `modifiers(view?, query?)` | search the named-modifier registry |
| `define_modifier(spec)` | guarded write to the local overlay (house dice tech) |
| `usage_stats()` | the lens's counter, kept |

## 8. What Modron refuses to be

- **Not a judge.** It will not decide whether advantage applies, what a save
  target is, or whether a house rule is wise — it executes assertions and
  records the asserter. Law questions go to Mechanus.
- **Not a store.** No entities, no lore, no character sheets, no HP pools.
  The ledger remembers *rolls*, nothing else.
- **Not silent.** No off-ledger dice. Even `force` leaves a row. `stats` that
  estimate say so.
- **Not a counterfeiter.** Fiat never dresses as rolled; estimated never
  dresses as exact; an ambiguous `3-18` inversion ships its alternatives.
- **Not a butterfly.** Same seed, same counter, same faces — forever. Engine
  derivation changes bump `engine_version`; old sessions verify under the
  version that rolled them.

## 9. Deltas to sibling docs

- `MECHANUS.md §1a` (the law side's client requirements) — **all three met**:
  (1) *citable roll IDs* — `rol:<session>:<counter>` / `rol:eph:<sha12>` /
  `rol:fiat:<sha12>`, stable, ledgered, returned with every roll, SHA
  content-addressed for docket cites; (2) *replayable audit* — `verify` /
  `replay` re-derive every face from `(seed, counter)` and re-hash (§3);
  (3) *raw vs composed* — **both, ruled here**: raw dice (`roll("1d20")` —
  "Modron says 17") AND composed conveniences (`roll_check`, the d20 state
  machine, modifier composition) — but composition only *executes assertions*:
  every modifier names its asserter, and what a 17 *means* against AC 19
  stays Mechanus's (outcome math in Modron is pack-data procedure over
  caller-supplied values, never interpretation). Mechanus may use either door.
- `MECHANUS.md §7` — `roll(expr, adv?, seed?)` **migrates out of Mechanus** to
  Modron (as `convert` migrated out of Mimir). Mechanus stays pure law: its
  `resolve()` emits roll *specs*; whoever orchestrates hands them to Modron.
- `MECHANUS.md §11 Q3` (dice seed policy) — **RESOLVED both-and**: every roll
  is seeded & ledgered; sessions add commitment/reveal fairness on top (§3).
- `VALIDATION.md §2.3 L3` — gains a fifth channel candidate: **dice
  lawfulness** (printed-average/HP-range/parse checks, §2.4) — cheap, local,
  disjoint from the extractor.
- `ARCHITECTURE.md` — now describes two of THREE systems. Per sibling etiquette
  (each session reconciles in its OWN doc; the sibling's doc is authoritative
  for its domain and is not edited), the third-system registration lives HERE:
  this document is to Modron what ARCHITECTURE.md's §"Reconciled with
  MECHANUS.md" is to Mechanus. Mimir's session may absorb it at her leisure.
- `build/family/rule-effect-handoff.md` §D (Mimir → Modron, 2026-06-06) —
  **ACCEPTED, with witness-audit amendments; implemented 2026-06-06**
  (suite 144→171; data + two resolution doors, zero new tools — the 17-tool
  surface holds).
  **Q2 answered:** plane-scoped check kinds ride a SETTING pack,
  `data/conventions/2e-planescape.json` with `extends: "2e"` (the same
  mechanism as 5e-2024→5e-2014) — NOT the base `2e` pack (FG&G-anchored
  edition law stays pure) and NOT `data/overrides/` (overlays are disclosed
  house variants; printed setting law is neither). Six setting kinds:
  `limbo_casting` (roll-under Int; nat-20 = fail + surge), `limbo_alteration`
  (1d100 + spell_level − caster_level, banded — the pack `checks` vocabulary
  gained a `sub` key mirroring `add` for this), `limbo_miniflux` (Wis
  roll-under), `wind_madness` (save vs paralyzation, 4-stage track in notes),
  `styx_memory` (save vs spell; success still costs the day),
  `wasting_contraction` (fixed 10%-per-day percent-under). Table / spec /
  lookup / encounter substance lands in a NEW data lane — the **rollables
  registry** (`modron/registry.py` + `data/rollables/*.json`, 34 entries):
  every entry names its source or the load refuses (modifier law, extended);
  official-scan sources are cite-only — paraphrased mechanics + page witness,
  never book prose; tables validate coverage at load; OCR-uncertain figures
  carry `requires_confirmation` (the compiler's idiom). Doors: `find_table`
  serves registry table ids to `roll_table`; the `rollables` tool serves
  entries by id and lists matches by `used_at` (a ref that resolves as a
  Mimir entity keeps priority — registry matches ride along as
  `registry_rollables`). **Mimir can mint `used_at`/`exhibits` pointers at
  these ids** (`tbl:`/`spc:`/`lkp:`/`enc:`/`dmg:` namespaces).
  **Q3 confirmed and standardized:** every §D numeric delta rides a
  modifier-registry row whose `source` is `{kind: mechanus, ref: <law-id>}`;
  until Mechanus mints M1/M2/M5/M7, refs carry the proposed id +
  `(pending … mint; witness: product + page)` — the established
  `(FG&G cite pending pour)` lifecycle, upgraded in place when the ids land.
  Per-item dispositions:
  | item | verdict | what landed / why |
  |---|---|---|
  | D1 Limbo tables | **accepted, reshaped** | TABLE IV → check kind `limbo_alteration` (its roll carries caster arithmetic a bare table can't); TABLEs III + V are DICELESS → registry `lookup`s (served, never rolled — no invented dice); casting/miniflux kinds + guidon/divination/illusion specs ride along (illusion 10% flagged OCR-uncertain) |
  | D2 school deltas | **accepted** | `enhanced-school-save-penalty` (−1), `enhanced-school-protection-bonus` (+1), `spell-key-casting-delay` (+1 init, low-wins penalty); the +1-caster-level bump itself is spell resolution (law/spec), not a blind dice modifier — noted in the rows; WHICH (plane, school) rows apply is M1's table, callers assert |
  | D3 encounter tables | **amended: nothing to pour** | witness audit found NO dice-shaped encounter charts in chaos/conflict/law boxes — chaos TABLE I is an abbreviation key, per-chapter "Other Encounters" are prose lists (Mimir color). The lane is built; charts from later pours drop in as data |
  | D4 portal checks | **accepted, narrowed** | Slags vortex (secret 1d4 type table + 3d6-turn duration + 1d6×10 hurl table) and Hive ooze-portal bundle (save / Dex−2 rescue / 1d4+1 vanish / 1d4 recovery + riders) poured; shifting-portal schedules (cage p8-9) state NO dice — "where stated" resolved to none |
  | D5 Wasting | **accepted, narrowed** | `wasting_contraction` kind (10%/day Oinos); progression is DICELESS (1/day off four stats — notes); hope-drain has no stated dice — prose, Mimir's |
  | D6 madness + wind | **accepted** | `wind_madness` kind (cadence DM-called; hysteria = margin-of-failure minutes) + stage modifiers `wind-madness-frustration` (−1 Wis/Int as +1 roll-under, caller asserts Int/Wis) and `wind-madness-despair` (+1/+1 split-purpose; auto-surprise is an outcome note, not an effect); `styx_memory` rode along (same chapter, dice-stated) |
  | D7 Inner dice | **accepted** | 18 registry entries: pocket hazards (ash/dust/fire/ice/magma/salt/smoke), whirlpool, positive (typed `healing`, 2×-max trap noted) / negative energy, Ice incl. immunity-piercing deep cold, Magma ambient as an AC-banded `lookup` + riders, Scald, Hoarfrost, Salt dehydration — all per-round exprs for `roll_damage`, citing pending M7 |
  | D8 Acheron | **amended: one spec** | free-floating-portal landing 20d6 poured; cube COLLISIONS carry no dice in law-ii p4-5 (1-2 days' warning, crush absolute — prose) |
  | D9 city tables | **split** | Yscoppel's Mounts **declined**: a diceless price/carry lookup is Mimir lore — pouring it here with invented dice would be provenance fraud; Harmonium patrol **accepted** (`enc:` spec, 2-4 → `2d2` w/ `1d3+1` alternative surfaced, levels F1-3, NO invented morale) + mancatcher dice (`1d2` struggle, `1d10` shift-shock + cumulative-1%/point rider) |

## 10. Build order (each step shippable) — v1 SHIPS ALL OF IT

1. **Grammar + engine** — parser/AST/normal-form; seeded stream; per-die audit. ✓
2. **Analysis** — exact PMF (convolution + bounded enumeration), MC fallback. ✓
3. **Convention packs** — 5e-2014, 5e-2024, 2e + overlay loader. ✓
4. **Modifier registry** — core 5e/2e mods as data; AST-transform effects;
   stacking law; provenance-carrying application. ✓
5. **Semantics** — `roll_check` across both editions' check kinds. ✓
6. **Rollables compiler** — 2e/5e statblocks, tables, ranges, prose sweep,
   encounter orchestration; crosschecks. ✓
7. **Ledger** — sessions, commitment/reveal, guarded append, verify, fiat. ✓
8. **Store seam** — build-envelope + future handbook.db read-only. ✓
9. **Server** — MCP stdio, lens skeleton (logging/usage/dispatch). ✓
10. *(later)* `rulings.db` overlay wiring, the moment Mechanus pours it.

## 11. Decisions (this doc keeps its own ledger)

| date | question | ruling | rationale |
|---|---|---|---|
| 2026-06-05 | name | **Modron** | the clockwork natives of Mechanus: lawful executors. Ordered chance. |
| 2026-06-05 | seed policy (MECHANUS §11 Q3) | sessions = committed seeds, revealed at close; ephemeral = recorded seeds; **all** rolls ledgered | auditable fairness without table friction |
| 2026-06-05 | fudging | `force` exists, labeled `fiat`, reason required | DM sovereignty + the honesty principle; no disguises |
| 2026-06-05 | where dice-law lives | convention packs = **data**, per view; values (DCs, save targets) = **inputs** | edition-as-view extended to dice; Mechanus stays the judge |
| 2026-06-05 | rules adjudication in Modron | **never** | three systems, three jobs; the seam stays clean |
| 2026-06-05 | doc home / impl home | doc with its sisters (`pipeline/mimir/`); impl at `pipeline/modron/`; ledger at `build/modron/rolls.db` | docs collect at the spine; `build/` is the derived/mutable home |
| 2026-06-05 | doc home (amended) | MODRON.md now lives at `pipeline/modron/` with the impl (family reorg; the spine keeps cross-cutting docs) | the engine doc travels with the engine |
| 2026-06-05 | reveal cadence (§12 Q1, Meme) | **on demand** — close seals + withholds; `reveal=true` publishes, at close or later | DM-side verifiability is constant; *publication* is the table's choice |
| 2026-06-05 | initiative orchestration (§12 Q2, Meme) | both sides by default; `initiative.sides` omits one | tables that roll their own dice stay sovereign |
| 2026-06-05 | non-d20 packs (§12 Q3, Meme) | refused — d20-family views only | corpus-someday ≠ pack-today; Strahd is already d20 |
| 2026-06-06 | rule-effect handoff §D (Q2): where does setting substance live? | check kinds → a SETTING pack `2e-planescape` riding the `extends` chain; tables/specs/lookups/encounters → the NEW rollables registry (`data/rollables/`, load-validated, source-required); base packs and overlays untouched | edition law stays FG&G-pure; overlays stay house-rule-only; "edition is a view" extends to "setting is a view" with zero new machinery — and the registry mirrors the modifier registry's provenance law (still d20-family, §12 Q3 holds) |
| 2026-06-06 | rule-effect handoff §D (Q3): asserter seam for numeric deltas | CONFIRMED — modifier rows cite Mechanus law ids; pre-mint refs carry `proposed id (pending …; witness: product+page)` and upgrade in place | the `(FG&G cite pending pour)` lifecycle, reused; Modron never invents law, only cites its asserter |
| 2026-06-06 | diceless witnesses (TABLE III/V, Wasting progression, Yscoppel, cube collisions, hope-drain) | lookups SERVED but never rolled; pure lore DECLINED to Mimir; flat progressions ride notes | a rollable without printed dice is provenance fraud — "verified or absent" applies to dice too |
| 2026-06-06 | **the Great Audit (round 2)** — Meme adopted the correction docket in full | docket-first audit of all data/code/ledger/docs: 88 verified findings applied across L1–L5 (`build/modron/review/correction-docket.md`); reaction = FG&G Table 10.7 disposition matrix (`bands_by`); class-HD ladder per FG&G (rogue/wizard cap 10, `ILL`); 1/2 HD = 2d2; analysis cs/cf counts kept NATURALS (engine was right); `verify_session` sweeps unclamped; MC flat creatures compile (`_statblock_of`); all pending FG&G/Mechanus refs minted (M7 stays parked); registry 34→36 (`ice-extreme-cold`, `everymans-madness`); IOOfo = 10% CONFIRMED; `tests/smoke_server.py` minted (18/18, configured spawn); suite 171→185; **L6 deltas FILED to Mimir** (stat-shifted creatures linqua/archedn-lantern/vaath-family, fractional `#AT N/2` rates, morale OCR wounds incl. Kylie `(IS)`=15, hp-roster delta: Parakk now derives, Koe/Omott/Grixitt extractor misses, Ylem needs vision) **and Mechanus** (F4/F6 reaffirmed) — recorded here per sibling etiquette, never applied by this session | verified-or-absent extended to the engine itself: every check, every cite, every die path now carries a witness or a flag — and the audit's tooling (`tools/integrity.py` snapshot law, `tools/review_chunks.py`) stays as the standing re-audit rail |

## 12. Open questions (for Meme)

1. **Reveal cadence** — reveal session seeds at `session_close` (per-night
   verifiability) or only on demand (`verify` stays DM-side)?
   **RESOLVED 2026-06-05 (Meme): on demand.** `session_close` seals and
   WITHHOLDS; `reveal=true` (at close, or re-called on the closed session)
   publishes the seed. `verify` works DM-side regardless. Implemented +
   test-pinned same day (suite 144); supersedes the v1 reveal-at-close default.
2. **Initiative orchestration depth** — should `encounter_rolls` roll *party*
   initiative too (needs party state Modron refuses to store — caller passes
   dex mods inline), or monsters-only by default? v1: rolls whatever sides the
   spec provides, stores none of it.
   **RESOLVED 2026-06-05 (Meme): party AND monsters by default, with omission
   overrides** — spec `initiative.sides: ["monsters"]` drops a side (a table
   rolling its own dice omits `party`); per-side params ride
   `initiative.party/.monsters`. Implemented + pinned same day. Modron still
   stores no party state — mods arrive inline per call.
3. **Pool systems** — `cs`/`cf` success-counting is in the grammar for free;
   do we ever ship convention packs for non-d20 games (the brief said
   *flexible*), or is that scope theater? v1: grammar yes, packs no.
   **RESOLVED 2026-06-05 (Meme): d20-type systems only.** The WoD shelf exists
   user-side but gets no packs ("no vampires for now, unless it's Strahd" —
   and Strahd is already d20). Grammar keeps `cs`/`cf` for free.
4. **`check_stats`** (v1.1 candidate, from the first live `/encounter-plan`,
   2026-06-05) — `dice_stats` answers expression-shaped questions, but the
   table's questions are check-shaped: "hit chance at AC 5?", "reaction-band
   odds at +1?". A `check_stats(kind, params, view)` returning per-outcome /
   per-band probabilities would let encounter artifacts cite tool-exact odds
   instead of designer d20 arithmetic (the rendezvous artifact hand-computed
   both, honestly labeled).
   **REDIRECTED 2026-06-05 (Meme): audit the unified stat chain first.** The
   chain: *what stats* (Mimir — envelope values + provenance: SOLID, G2/G8
   closed) → *what stat system* (Mechanus — which mechanic governs + the
   target-number law: PARTIAL — THAC0 brackets + 5e DC ladders served, **2e
   save matrices unserved**; filed F6 in integration-tests.md) → *how stats*
   (Modron — pack check-kinds + compiler + modifiers: SOLID; the pack `checks`
   vocabulary {attack, save, ability, proficiency, thief_skill, percent,
   morale, reaction, surprise, initiative} is the de-facto family contract for
   "what kind of application is this"). `check_stats` is the odds-piece of
   *how*; queued behind F6.
5. **Multi-creature encounter specs** — the spec carries ONE creature; the
   first live set-piece (friendly-fiend-rendezvous: two named fiends + a guard
   mob) worked around it: batch = the variable opposition, principals fire
   per-event from their compiled specs. Ship `creatures: [...]`, or is the
   workaround the right doctrine? (It may be — principals' dice are
   event-driven, not batch-shaped.)
   **RESOLVED 2026-06-05 (Meme): solve it at the format layer.** Encounters
   assemble by **concatenating entity cards**
   (`.claude/templates/entity-card.md` — identity/Mimir · law/Mechanus ·
   dice/Modron · flags · run-sheet row); the spec stays one-creature (batch =
   variable opposition, principals per-event). No `creatures: [...]` machinery.
