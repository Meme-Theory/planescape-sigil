# Modron — the dice engine MCP

> Mimir remembers. Mechanus rules. **Modron rolls.**

Design doc (with its sisters): [`pipeline/mimir/MODRON.md`](../mimir/MODRON.md).
Registered in the project `.mcp.json` as `modron` (stdio, `python server.py`).

## Layout

```
pipeline/modron/
  server.py            — MCP stdio server (17 tools)
  modron/
    grammar.py         — dice-notation parser → AST → normal form (the contract)
    engine.py          — seeded auditable stream + evaluator (per-die fates)
    analysis.py        — exact PMFs (fractions) / flagged Monte Carlo; the
                         printed-average crosscheck (gate witness)
    conventions.py     — convention-pack loader (+ overlays, always disclosed)
    modifiers.py       — named-modifier registry; effects = AST transforms;
                         stacking law; provenance required
    semantics.py       — attack/save/check/morale/reaction/… per the view
    rollables.py       — find the dice hiding in data: statblocks, tables,
                         ranges, prose (OCR-lenient), encounter plans
    ledger.py          — rolls.db: sessions (commit → on-demand reveal),
                         SHA-unique rows, verify/replay, honest fiat
    store.py           — read-only Mimir seam (build/**.json today,
                         handbook.db when poured)
  data/
    conventions/       — 2e.json, 5e-2014.json, 5e-2024.json (edition = a view);
                         2e-planescape.json (SETTING pack, extends 2e — the
                         rule-effect handoff's plane-scoped check kinds)
    modifiers/         — core-5e.json, core-2e.json; planescape-2e.json
                         (school deltas + madness stages, mechanus-seam refs)
    rollables/         — the rollables REGISTRY: page-cited tables / roll specs /
                         diceless lookups / encounter specs (planescape-2e.json);
                         source-required, coverage-validated at load
    overrides/         — local overlays (house dice tech; disclosed)
  tests/               — pytest suite
```

Ledger lives at `build/modron/rolls.db` (override: env `MODRON_LEDGER`).

## The contract, in one breath

Modron executes roll *specifications* with total fidelity and total audit —
expression + modifiers, every modifier naming its asserter (core / mimir /
mechanus / table / fiat). It decides no law (Mechanus), stores no lore (Mimir),
tracks no character state (the table). Sessions commit `sha256(seed)` before
the first die; close seals, and the seed reveals **on demand** — once revealed,
every face of the night recomputes. `force` exists and is labeled `fiat`, forever.

## Quick taste

```
roll        {"expr": "4d6kh3", "label": "STR"}
roll_check  {"kind": "attack", "view": "2e", "params": {"thac0": 7, "ac": 3}}
roll_damage {"expr": "2d6+4", "view": "5e-2014", "crit": true,
             "mods": ["great-weapon-fighting", {"id": "sneak-attack", "params": {"n": 3}}]}
rollables   {"entity": "a-kin"}        ← compiles the real Uncaged envelope
rollables   {"entity": "plane:salt"}   ← lists the registry's page-cited hazards there
roll_table  {"table": "tbl:2e:sigil:slags-vortex-type"}   ← secret-1d4 vortex split
roll_check  {"kind": "wasting_contraction", "view": "2e-planescape"}
encounter_rolls {"encounter": {"creature_ref": "a-kin", "number_appearing": "1d3"},
                 "view": "2e", "plan_only": true}
dice_stats  {"expr": "adv(1d20+7)"}    ← exact, or honestly estimated
```

## Tests

```bash
cd pipeline/modron && python -m pytest tests/ -q
```
