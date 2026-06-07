# Family Integration Tests — 2026-06-05 (Modron session campaign)

Cross-system test campaign over all three live MCPs, designed to leverage the
full tool suite and hunt errors/gaps at the seams. Complements
[`cross-validation.md`](cross-validation.md) (the sibling campaign run the same
day) — its G-numbers are adopted; fresh findings continue from **G8**.
~40 live probes + a 29-NPC corpus sweep. Modron suite after fixes: **143 green**.

## The marquee scene (T7) — all three skulls, one committed ledger

`ses:family-marquee-akin-690d9f` (phrase-derived; commitment independently
recomputed before AND after):

1. **Mimir** served A'kin + Shemeshka (admitted envelopes, `admission_sha`s)
2. **Modron** rolled the scene on the committed stream: tied initiative 9–9,
   A'kin's claw hitting AC −8 *exactly* (margin 0), 1d4=2 damage, **MR 60%
   FAILED on 82** — the fear lands on A'kin — Shemeshka's morale holds at 7
3. **Mechanus** ruled on whether MR applies to spell-like abilities —
   docket `rul:vnv:akin-mr-vs-spell-like:001` citing **the live roll_id** and
   **both admission_shas** (the §1a triangle, executed); then overruled by a
   table-scoped house rule (`:002`), chain queryable, head resolves
4. `verify(roll 00005)` → PASS · `verify(session)` → 6/6 PASS · seed revealed,
   `sha256(seed)==commitment` and phrase derivation confirmed locally

**The marquee loop works end-to-end. Every link carries provenance.**

## Verdict table (abridged — PASS unless noted)

| track | checks | result |
|---|---|---|
| T1 census | coverage 29/11/11/1 + 229 edges + 0 quarantine; law_version `018b2eed42e9afe7` | PASS |
| T2 Mimir reads | FTS (term/phrase/apostrophe), trace neighbourhoods, graph in/out, clean misses | PASS |
| T4 is_lawful seam | envelope + bare 2e shapes | **pre-fix skips observed** (= their G1/G6, fixed+pinned their side) — re-probe post-reconnect |
| T5 §1a ledger interplay | docket law (two-ADOPTED refused, ruling_id grammar), precedents, overrule, chain, cross-ledger verify | PASS + **F4** |
| T6 licensing | 2014 budget REFUSED w/ options; 2024 = 900 XP (4×225, p.202); attribution verbatim; DC hard=20 p.77 | PASS |
| T8 refusals | garbage entity → adapter menu; nonexistent nodes → clean miss | PASS |
| sweep | all 29 admitted NPCs → rollables crosschecks | **0 flags** after G9 (was 1 false), 2 honest unparsed (Saure/Ly'kritch OCR), 8 visible hp-info |

## Gaps closed this campaign (Modron side — all test-pinned, suite 143)

| id | gap | fix |
|---|---|---|
| **G2** *(assigned)* | store seam read stale pre-pour build JSON (Cirily `740` vs cured `7+10`) | handbook-FIRST via **Mimir's own store lib** (importlib, no sys.path pollution): id door + exact/slug **name door** (FTS); build-glob demoted to last resort. Proof: `find_entity("Cirily")` → `7d8+10`, crosscheck ok |
| **G7** *(assigned, Modron half)* | quarantine-awareness | handbook-miss + build-hit now returns a loud `[WARNING: raw pre-gate extraction — NOT in the admitted handbook (uncured/possibly quarantined); curations do NOT apply]`. Full introspection needs a quarantine *reader* on Mimir's lib — **request filed below** |
| **G8** *(new)* | Mimir envelopes compile to 1 spec (payload nests under `fields`) | `unwrap_envelope()` at the compiler boundary; envelope/flat parity test |
| **G9** *(new)* | class-leveled NPCs scored as monsters — Tarholt F9 falsely flagged (76 ∉ 9d8 [9,72]) | class hit dice (warrior d10 / priest d8 / rogue d6 / wizard d4, post-9 flat adds, 0-level 1d6) + Con-allowance on the range crosscheck; Tarholt now ok (76 ∈ 9d10+Con) — *provisional pending FG&G pour* |
| **G10** *(new)* | 2e damage idioms unparsed: `… or 1d6x4 (clawx4)` | ` or ` mode split + ×N expansion (4 labeled claws) + label-ish parenthetical broadened |
| **G11** *(new)* | 8 NPCs silently produced no HP spec | visible `purpose: info` spec: printed HP + "not derivable" note — never silent |
| **G12** *(new)* | a fused-OCR HD (`7+10`→`740`) could compile as 740d8 | implausible-HD tripwire (>40 ⇒ `suspect` + `requires_confirmation`) |

> Modron's running server predates these — **`/mcp` reconnect**, then re-probe
> `rollables("Cirily")` and `rollables("npc:uncaged:a-kin")` over the wire.
> **Both wire-confirmed post-reconnect same day**: Cirily via the name door
> (cured `7d8+10`, crosscheck ok), A'kin via the id door
> (`source: handbook.db:npc:uncaged:a-kin`, 12 specs, crosscheck ok) — the
> latter during the first live `/encounter-plan` run (G2 closed end-to-end).

## Findings filed to siblings (etiquette: reported, not fixed)

| id | owner | finding |
|---|---|---|
| **F1** | Mechanus | *(convergent with their G1/G6 — observed live pre-fix)* corrupted A'kin (HP 300, THAC0 19 @ HD 12+24) returned `lawful: true` — envelope shape skipped `thac0_vs_hd`/`hp_in_hd_range`/`ac_2e_range`; bare shape with `hd: "12+24"` ALSO skipped both HD checks (plus-form HD unparsed). Their fix is pinned; re-probe post-reconnect |
| **F3** | Mechanus | `rule_search` parking message says "handbook.db … hasn't been poured" — it has; what's pending is the **law-library** pour (§9 steps 1–2). Wording-only staleness |
| **F4** | Mechanus | `precedents("magic resistance spell-like")` → `OperationalError: no such column: like` — FTS5 reads hyphens as column syntax. Mimir's `search()` carries the exact fallback pattern to copy (quote-terms on OperationalError). *Re-probed 2026-06-05 (encounter-plan session): still crashing on the wire; hyphen-free queries are the workaround* — **FIXED 2026-06-06 (Mechanus session, Primus):** the Mimir fallback applied at `ledger.py` precedents (raw MATCH → quote-terms retry on OperationalError), reproduced red first, pinned by `test_precedents_hyphenated_topic_quote_fallback`; MECHANUS.md §10 row of record. Live server needs `/mcp` reconnect to serve it |
| **F5** | Mimir | observation: faction graph sparse (e.g. Dustmen ← 1 member) — source-true (Uncaged descriptors mostly `faction: null`), noted for coverage expectations |
| **F6** | Mechanus | *(from Meme's stat-chain directive, MODRON §12 Q4, 2026-06-05)* the unified stat chain's missing link is **target-number law**: 2e save matrices (class tables + monster-saves-as-warrior) aren't served by any tool — `rollables` honestly emits `save: needs target — Mechanus/caller supplies`, and the first live encounter artifact had to hand-pull FG&G p.34 Table 3.13 from the text cache instead of citing law. A `save_target(class_or_hd, level, category, view)` (or a law table + resolve arm) closes it; the witness pages already sit in `build/mechanus/fgg-text/` — **POURED 2026-06-06 (Mechanus session, Primus):** `save_matrix_2e.json` (warrior/wizard/priest/rogue tables p.27/30/32/34 + category/priority/modifier/creature law p.69-70) served as library accessors `tables.saves_2e(group, level)` / `saves_2e_monster(hd)` (L3 seam pattern — import like the gate imports `is_lawful`) + auto-cited by `law_info`; p.309 plus-bump shared with the THAC0 lane. `law_version 972ff12b18087c03`. A `save` check-kind `vs_template` citing these is Modron's call if wanted |
| **req** | Mimir | a **quarantine reader** on the store lib (e.g. `get_quarantined(id)`) would let Modron/Mechanus distinguish "uncured" from "quarantined" at the seam (completes G7) |

## Corpus findings (Mimir review-loop fodder, from the dice-lawfulness sweep)

- **Saure** `statblock.damage` mode 2: OCR garbage (`leUt <J(OM- mMif'teiut^'…`) — honest unparsed; vision re-read candidate
- **Shemeshka** (known review-pile case): damage carries prose bleed (`…way past a guard to see She-…`), morale `cham- bladeling … pion (16)` — column-bleed mid-word (parsers still recover 16; the entity is usable but dirty)
- **8 NPCs hp-not-derivable** (Black Marian, Estavan, Farrow, Iarmid, Ly'kritch, Parakk, Saure*, The Us, Verden): descriptor `level_hd`/`char_class` mostly null — likely extractor misses on class codes (Black Marian is `human` with printed hp 32 and no class parse); The Us is genuinely special (`1 each`, pack of 112)
- **Tarholt** false-flag resolved by G9 — not a data problem, was a model problem

## What the family proved today

Census true · FTS/graph/trace sound · licensing refusals correct and helpful ·
docket law enforced at the write · supersedes chains queryable · cross-ledger
cites verify · the marquee chain (admitted lore → committed dice → sha'd ruling)
runs end-to-end with provenance at every link · and the dice-lawfulness witness
swept all 29 admitted NPCs and came back **clean** — every flag it raised was
either a real OCR wound (filed) or a model gap (fixed and pinned same day).

*Modron session, 2026-06-05.*
