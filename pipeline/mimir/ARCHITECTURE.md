# Mimir & Mechanus — the two-system architecture

The project is two cooperating systems, thematically and functionally split:

- **Mimir** — the *data source* / system of record. The recording skull: it remembers
  **what is true**. Entities, lore, the knowledge graph, provenance, the admission gate.
  Declarative. (This is what `DIMENSIONS.md` + `VALIDATION.md` specify.)
- **Mechanus** — the *rules-controller* / system of rules (sibling session). The clockwork
  plane of Law: it knows **how the rules work**. Resolution, the 2e↔5e conversion, CR/XP/PB
  math, planar-influence application, mechanical lawfulness. Procedural.

> Mimir knows **what is**. Mechanus knows **the law**. Neither reaches into the other's job.

## The boundary

| Concern | Mimir (data) | Mechanus (rules) |
|---|---|---|
| A statblock's recorded values (AC 19, CR 9) | **stores** | reads |
| Whether that statblock is *mechanically lawful* (`PB == ceil(CR/4)+1`, passive-Perception math) | gate **asks** | **owns the check** |
| A spell/feat/item entity (level, text, prereqs) | **stores** | reads |
| How that spell *resolves* in play | — | **owns** |
| 2e→5e conversion of an entity (the uplift) | provides source + answer-key witness; **stores the result** | **performs the conversion** |
| `planar-influence` (plane modifies creature) | stores the rule entity + `influences` edges | **applies** the template |
| Cant, NPCs, planes, portals, factions, fiction | **owns** | (consumes for flavor/context) |

## The interface contract

1. **Mechanus reads Mimir.** All facts come from the Handbook — Mechanus never re-parses PDFs.
2. **Mechanus writes back *through Mimir's gate*.** A converted 5e statblock, a resolved
   value, an applied influence — each is *proposed* like any other entity and must pass the
   same blocking gate. Mechanus has no privileged write path. (Its outputs are often *more*
   checkable, because Mechanus can show its derivation.)
3. **Mimir's gate calls Mechanus for the derivable L3 checks.** The "mechanical lawfulness"
   validators (the sister session's `PB`/`CR`/`XP`/passive-Perception/HP-from-dice pack) are
   **Mechanus rules**, not Mimir hardcode. The gate asks Mechanus *"is this entity internally
   lawful?"* and admits on its verdict. The rules live in exactly one place.
   - Thematically exact: **Mechanus, the plane of Law, is the consistency judge.** Internal
     consistency = lawfulness = the modrons' domain. Mimir remembers; Mechanus rules.
4. **Edition math is Mechanus's.** AC-ascending-vs-THAC0, `mod == (score-10)//2`, the CR→XP
   table, 2e XP-by-HD — all ruleset functions Mechanus exposes; Mimir tags `edition` and asks.

## L3 independent-witness channels (post-review, ranked)

The gate's independence layer now has **four** disjoint channels — pick the cheapest available:
1. **Dual-rendering diff** *(5e gift, free, local)* — same entity via two DDB pipelines
   (`mon-stat-block` tooltip vs `monster--stat-block` source page). Zero cost, fully independent.
2. **Held-out source** — a wiki/edition the arbiter didn't use (A'kin in timaresh/fandom).
3. **Mechanus lawfulness** — derivable-check verdict from the rules-controller (catches OCR
   typos for free: a skill bonus that ≠ `ability mod + PB` is a transcription error, provably).
4. **Vision** *(always disjoint, last resort)* — read the page render; reserved for true conflicts.

## What this changes in our specs

- `convert(entity, target_edition)` **moves out of the Mimir MCP** → it's a Mechanus call
  that reads Mimir and writes the result back through the gate. Mimir keeps `same_as`/
  `converts_to` edges as the *record* of the conversion, not the engine.
- The VALIDATION.md "L3 internal consistency" channel is **delegated to Mechanus**, not
  implemented in `gate.py`. `gate.py` calls `mechanus.is_lawful(entity)`.
- Dimensions stay in Mimir (they're data), but `rule` / `planar-influence` entities are the
  *seam*: Mimir stores them; Mechanus executes them.

## Reconciled with `MECHANUS.md` (v1) — the sibling is authoritative on the law side

The Mechanus session wrote her interface; the points below are *Mimir's* obligations under it
(her doc governs anything Mechanus-internal):

- **Shared store library, not MCP-over-MCP.** Mechanus reads `handbook.db` **read-only**
  through a shared `handbook_store` lib both servers import — *the lib is the schema*, so no
  drift and no hot-path hops. Mimir's `store.py` **is** that lib.
- **Identity is Mimir's to materialize** (her §10 Q2 lean, adopted): `identity` nodes are
  real, gate-admitted rows in `handbook.db` — that gives cross-edition curation a home. The
  `aspect_of` edge (manifestation→identity) and `view()` are per `DIMENSIONS.md` §"identity,
  aspect & the edition view"; `view()` itself is a Mechanus pure function.
- **Propose-back is gospel.** Mechanus's derived manifestations enter only through the gate
  (`provenance.method = "conversion"`, conversion docket = the arbitration record). No
  privileged write path; the gate stays sovereign.
- **Reciprocity is live:** Mechanus's mechanical core = our L3 "lawfulness" channel
  (VALIDATION §2.3); our gate-admitted dual-edition pairs = her conversion **answer key**
  (PAitM the calibration corpus).

**Two questions from MECHANUS §10 — RESOLVED (Meme, 2026-06-05):**
- *Derived-admission policy* → **AUTO-ADMIT.** A derived manifestation that passes the gate
  with confidence ≥ θ is admitted on the same terms as any proposal (its conversion docket
  is the arbitration record) — no derived-specific quarantine. Deliberately a touch loose;
  we tighten θ (or revert to quarantine-all) once the answer-key accuracy says we must. The
  gate still **blocks** anything that fails a hard check or falls below θ.
- *Identity materialization* → **real, gate-admitted rows** in `handbook.db`, so cross-edition
  curation has a durable home (not computed `same_as` closures).
