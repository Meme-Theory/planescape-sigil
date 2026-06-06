# Mimir — Validation Layer (Blocking Admission Gate)

> **Principle: accuracy over speed, every time.** The Handbook contains *only* entities
> that passed the gate. Nothing is written to `handbook.db` except through the gate.
> Failures and uncertainties wait in **quarantine** for adjudication (human or workflow).
> A query against the Handbook is therefore trustworthy *by construction* — never
> "trust but filter," always "verified or absent."

This is the **judge**. It must not share a brain with the defendant (the extractor/arbiter):
its confirming evidence is drawn from sources or senses the extractor never used.

---

## 1. The gate flow

```
extract → arbitrate → PROPOSE(entity|edge)
   │
   ▼  THE GATE  (single write path; deterministic; produces a verdict docket)
   ├─ L1 schema checks      (per-dimension, from the registry)        ─ fail-fast, cheap
   ├─ L2 cross-cutting invariants (dimension-agnostic)               ─ cheap
   ├─ L3 independent verification (vision / held-out witness)         ─ expensive, routed
   └─ decision:
        ALL hard checks pass  AND  independent confirms  AND  conf ≥ θ
            → ADMIT  → write entity + admission_sha to handbook.db
        else
            → QUARANTINE(reason)  → review queue   (NEVER written to handbook.db)
```

The gate is **idempotent and content-addressed**: `admission_sha = sha256(entity_content +
checks_run + witness_used)`. Re-gating an unchanged entity reproduces its verdict; any
re-extraction that changes the entity invalidates its admission and forces a re-gate.

**Derived manifestations (Mechanus conversions) admit on the same terms** — pass the gate +
confidence ≥ θ → ADMIT (Meme, 2026-06-05: *auto-admit*; tighten θ once the answer-key earns
it). No derived-specific hold; the conversion docket rides as their arbitration record.

---

## 2. The three check layers

### L1 — Schema validation (per-dimension)
Declared *beside* each dimension's `fields` schema in `DIMENSIONS.md`. Required fields
present, types correct, enums valid, numerics in range. Examples (Tier 1):

| dim | hard checks (must pass) |
|---|---|
| `npc` | name is not a stat-fragment (no `AC`/`;`/digits-only); descriptor parses; statblock has ≥10/13 fields & numerics in 2e range (AC −10..12, THAC0 0..20) |
| `portal` | `from` AND `to` present; `to` resolves to a real plane/location; key present (or explicit `key:none`) |
| `spell` | `level` ∈ 0..9; `school` ∈ enum; `classes[]` non-empty & resolve |
| `faction` | `philosophy` present; `factol` resolves to an npc; `hq` resolves to a location; `sign` present |
| `plane` | `category` ∈ enum; attaches to a `cosmology` taxon; ≥1 `planar_trait`; ≥1 layer/location edge |
| `deity` | `portfolio[]` non-empty; `alignment` ∈ enum; `realm` resolves; `pantheon` taxon set |
| `location` | `region` resolves; `kind` set; ≥1 incident edge |
| `cant-term` | `term` + `definition` + `register` ∈ enum + `example` present |
| `source` | `code` + `edition` + `year` (the provenance root — everything links here) |

### L2 — Cross-cutting invariants (every entity & edge)
- provenance present, ≥1 source, source has a `sha`; `confidence` present.
- **edge endpoints resolve** to admitted entities (or a known-pending id in this batch).
- **`same_as` is sane**: links the same normalized identity across *different* editions
  (never two different entities; never same edition).
- **garbage detector**: no field carries OCR-failure markers (statblock tokens inside a
  `name`, lone punctuation, control chars, watermark residue).
- `edition` ∈ allowed set; `id` matches the namespaced ID grammar.

### L3 — Independent verification (the point of the whole thing)
A gated entity's **key fields** must be confirmed by a witness from a pool **disjoint from
the arbiter's decision sources**. Three channels, in priority:

1. **Dual-rendering diff** *(free, local — the 5e gift, REVIEW-5E §F.6)* — the same entity
   rendered by two source pipelines (DDB `mon-stat-block` tooltip vs `monster--stat-block`
   page; Morte is dual-attested). Zero cost, fully independent. First choice when it exists.
2. **Held-out witness** *(secondary)* — a source/edition the arbiter did **not** use
   (A'kin in timaresh/fandom). The gate records the partition.
3. **Mechanus lawfulness** *(delegated — not `gate.py`'s code)* — the derivable mechanical
   checks live in the **Mechanus** rules engine. The gate calls `mechanus.is_lawful(entity)`;
   per-edition arithmetic (`PB == ceil(CR/4)+1`, passive-Perception `== 10 + WIS(+PB)`,
   XP-from-CR, 2e `THAC0 ↔ HD`, `mod == (score−10)//2`) flags OCR/transcription typos
   *provably*. Internal consistency = lawfulness = the plane of Law's job, by design.
4. **Vision** *(always disjoint, last resort)* — read the page render; reserved for true conflicts.

**Routing (accuracy-over-speed, but not wastefully):** L1+L2 run first and fail fast.
L3 runs only on entities that cleared L1+L2. Vision is the default L3 for every Tier-1
entity; cheaper channels (held-out, consistency) gate the long tail and pre-screen before
spending a vision read. Disagreement at L3 → `QUARANTINE(conflict)`, never silent admit.

---

## 3. The verdict docket (auditable, like the lens's `emit_verdict`)

```jsonc
{
  "entity_id": "npc:uncaged:akin",
  "decision": "ADMIT",                       // ADMIT | QUARANTINE
  "checks": [ {"layer":"L1","name":"statblock_fields","sev":"hard","result":"pass","detail":"13/13"},
              {"layer":"L2","name":"edges_resolve","sev":"hard","result":"pass"},
              {"layer":"L3","name":"vision_confirm","sev":"hard","result":"pass",
               "witness":"vision:uncaged:p10","fields":["ac","hp","thac0"],"agreement":1.0} ],
  "independent": {"channel":"vision","disjoint_from":["official-ocr"],"agreement":1.0},
  "confidence_final": 0.97,
  "adjudicator": "auto",                     // auto | human:Meme | workflow:<id>
  "admission_sha": "…", "ts": "<stamped post-run>"
}
```
Every admission and every quarantine writes a docket. The docket is the answer to "why is
this in the Handbook?" — and the audit trail an independent reviewer checks.

---

## 4. Quarantine & the review loop

Quarantine is a **separate store** (`handbook_quarantine.db`), partitioned by reason so
review effort routes cleanly:

| bucket | meaning | typical fix |
|---|---|---|
| `schema-fail` | missing/malformed required field | re-parse, vision re-OCR the region |
| `invariant-fail` | dangling edge, bad `same_as`, garbage field | fix reference / split entity |
| `conflict` | L3 witness disagrees with extracted value | adjudicate which is right |
| `low-confidence` | passed checks but `conf < θ` | confirm or upgrade evidence |

**Two adjudication modes (both first-class):**
- **Solo** — the gate emits a **review card** per item: the page render + the proposed
  value + the conflicting witness + the failing check. You rule; your ruling writes to the
  entity's `curated` layer and re-submits to the gate.
- **Workflow** — a quarantine-processing workflow fans out one agent per item (or batch):
  vision-read the page, repair the field, re-propose. Agents can ADMIT only by passing the
  same gate — they cannot bypass it.

**Curation is sticky.** Every human/workflow ruling lands in the `curated` layer, which is
transplanted across every future rebuild (the lens's `merge_curated_from_existing`). You
fix a thing once; re-extraction never re-breaks it. Curated values still pass the gate —
but a human override is itself a recorded, SHA'd witness.

---

## 5. How validators are declared (extensible with the dimensions)

A validator is a registry entry, not bespoke gate code:
```python
register_validator("npc", checks=[
    schema("statblock", min_fields=10, ranges=AD2E_RANGES, hard=True),
    name_not_fragment(hard=True),
    edges_resolve(["member_of","located_in"], hard=True),
    independent_vision(fields=["ac","hp","thac0"], hard=True),
    consistency_2e_thac0(sev="soft"),     # soft → low-confidence, not reject
])
```
Adding a dimension ships its validators in the same plugin (step 3 of the registration
recipe). `hard` checks block; `soft` checks lower confidence and may route to
`low-confidence` review. The gate composes whatever the registry declares — it has no
per-dimension logic of its own.

---

## 6. MCP surface (the gate, exposed)

- `propose(entity|edge)` → runs the gate, returns the docket (ADMIT writes; QUARANTINE holds).
- `validate(entity_id?)` → re-run the gate on demand; report dockets.
- `coverage(type?)` → admitted vs quarantined counts, by dimension and reason bucket.
- `review_queue(bucket?, limit)` → pull review cards for solo or workflow adjudication.
- `adjudicate(entity_id, ruling)` → write a curation + re-gate (the only human-in-the-loop write).

`propose`/`adjudicate` are the **sole write paths**; there is no direct DB write. This is
what makes "blocking" structural rather than aspirational.

---

## 7. First test subject

Re-gate the 29 Uncaged NPCs we already extracted. Predicted outcome (accuracy honestly
surfaced): A'kin and the clean statblocks ADMIT on vision-confirm; the 3 review-pile
statblocks (Shemeshka page-split, the fensir twins, Sly Nye) and the descriptor-cruft
cases (`PS (BragO`, `Px [Arawnl`) QUARANTINE to `conflict`/`schema-fail` — which is the
gate doing its job, not failing. The count that ADMITs clean is our real fidelity number,
not the self-graded one.
```

---

## 8. The Mechanus seam — L3 lawfulness, WIRED  *(2026-06-05)*

§2 always specified L3's consistency channel as **Mechanus `is_lawful`**; `gate.py` ran a
local placeholder "until the sibling is importable." She is now BUILT + V&V'd, so the gate
delegates. Recorded here in **Mimir's own doc** (sibling etiquette — her `lawful.py` is
authoritative for her domain; I consume it, never edit it).

**How (no MCP-over-MCP).** `gate.py` imports `mechanus.lawful.is_lawful` as a **library** —
the same seam `store.py` is for the siblings. The import is guarded: if Mechanus can't be
imported, or raises, the gate degrades to a local hp-in-HD check and **never** lets a sibling
fault block an admission.

**The division of labor (who owns what verdict):**
- **Mechanus owns LAWFULNESS** — the derivable rules-math (2e: `hp_in_hd_range` hard;
  `thac0_vs_hd` bracket, `ac_2e_range`, `morale`, `magic_resistance` soft; the full 5e
  PB/CR/XP/save/skill/passive-perception suite when 5e entities arrive). Her **hard** fails →
  the gate's `conflict` quarantine; her **soft** fails are recorded in the docket, non-blocking
  (a "lawfulness smell," e.g. Tripicus's author-intent THAC0). Every NPC docket is stamped
  with her `law_version`.
- **Mimir keeps only its extraction-QA duty, not rules-of-the-game** — coarse **garbage
  bounds** on AC (−10..12) and THAC0 (1..20) that catch OCR junk like `99`/`50` (looser than
  the lawful range, so Mechanus still gets to flag genuine deviation softly), and
  **damage-reads-as-dice** (Modron's grammar). These stay hard and local.

**The coercion contract (`_coerce_2e`, Mimir-side).** Mechanus *met the seam from her side*:
her `_adapt_2e` now coerces printed-string numerics itself (`_int_coerce`) and reads `level_hd`
from **either** the statblock **or the descriptor** (her gap-G1 envelope fix, 2026-06-05). So
the gate hands her the envelope almost as-is — Mimir's only remaining job is to **withhold Hit
Dice** where its own scope skips the d8-monster-HD math: it strips `level_hd` from **both** the
statblock and the descriptor copy when the NPC has a `char_class` **or** its HD isn't a clean
bracket (`\d+(\+\d+)?`). That rule is load-bearing — a class humanoid's hp isn't d8-bounded
(Tarholt, 76 hp on 9 HD) and a `"1 each"` pack HD isn't a bracket (The Us) — so withholding
makes her `hp_in_hd_range`/`thac0_vs_hd` skip exactly the NPCs Mimir's local check skipped.
Clean monster HD is left intact for her to judge (10 of the 29 now genuinely run the HD math).

> **Reconciliation note (sibling-contract drift, caught by V&V).** The seam's first cut
> withheld HD from the *statblock only* — correct against her then-current adapter. Mid-session
> she added the descriptor fallback, which would have false-`conflict`ed every class humanoid
> (Tarholt et al.). `tests/test_gate.py::test_l3_hp_check_skipped_for_humanoids` caught it on the
> next run; the coercion now strips both. *Open question to Mechanus (her doc is authoritative):
> should `is_lawful` itself decline `hp_in_hd_range`/`thac0_vs_hd` when a 2e entity carries a
> `char_class`? Class hp/THAC0 follow class tables, not the monster d8/bracket — today Mimir
> guards that boundary at the call site.*

**Validated.** All 29 Uncaged NPCs stay lawful (0 hard fails) through the coerced seam; one
soft smell surfaced (Tripicus `thac0_vs_hd`) that the local placeholder never produced. A live
re-pour ADMITs 29/29, 0 quarantined, every NPC docket stamped `law_version`. Pinned by
`tests/test_gate.py::test_l3_delegates_to_mechanus_with_law_version`,
`::test_l3_hp_in_hd_range_comes_from_mechanus`, and `::test_l3_falls_back_when_mechanus_absent`
(graceful degradation). Full account in `VERIFICATION.md`.
