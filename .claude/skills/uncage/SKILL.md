---
name: uncage
description: Reconstitute the rig on a fresh machine and PROVE the end state — same books in, same Cage out. Drives pipeline/uncage.py (status/run/verify) against the pinned manifest; Mimir's handbook, Mechanus's law caches, and Modron's packs land verified. Use when handing the repo to another DM, bootstrapping a new machine, checking end-state drift after a re-pour, or re-pinning the manifest after a new book pours. Args: "[status|run|verify|pin]" or nothing (the skill triages).
---

# /uncage — same books in, same Cage out

The repo ships code, law-as-data, curations, and records — never the licensed
corpus nor the stores derived from it. This skill walks a machine from
fresh-clone to **verified** end state. The engine is `pipeline/uncage.py`; the
oath is `pipeline/uncage-manifest.json` (the curator's pinned fingerprints:
entity-id sets per dimension, edge digests, quarantine by reason, law_version,
engine_version, source shas). Skills direct, code executes — never eyeball
counts yourself when `verify` can swear to them.

## Phase 0 — which side of the portal

- **Recipient** (new DM / new machine): phases 1–5.
- **Curator** (this rig, after a new pour, adjudication, or law change):
  phase 6 only.

If no args, run `py -3.13 pipeline/uncage.py status` first and let its
next-hint decide.

## Phase 1 — prerequisites (recipient)

1. Python 3.13 via the **py launcher**, then
   `py -3.13 -m pip install -r pipeline/requirements.txt`.
2. Localize `.mcp.json`: the `command` paths embed the curator's username —
   point them at THIS machine's `py.exe` (full path; bare `python` is the
   WindowsApps stub and dies before the handshake, CLAUDE.md "MCP
   registration"). The `dabus` entry needs the whole voice stack
   (`tools/README.md`) — park it (remove the entry) unless you're rebuilding
   that too; mimir/mechanus/modron/cant don't need it.

## Phase 2 — acquire the books (recipient)

- Buy-list with links: `content/official/CATALOG.md`. The required seven:
  Uncaged (2624) · The Factol's Manifesto (2611) · In the Cage (2609) ·
  Planes of Law (2607) · Planes of Chaos (2603) · Planes of Conflict (2615) ·
  Hellbound (2621).
- Drop each PDF at the **exact pinned path** — `status` prints every missing
  path with its expected sha and page count. Filenames are load-bearing: psx
  slugs and the parse modules' reflow paths derive from them. Rename to match;
  never rename the pin.
- Free corpus (Mechanus's quotable law): FG&G + SRD 5.1 + SRD 5.2.1 at the
  paths `status` shows — sources and licenses in `content/README.md`.
- The wiki witness corpus ships in-repo (CC-BY-SA) — nothing to fetch.

## Phase 3 — run the chain (recipient)

```bash
py -3.13 pipeline/uncage.py status   # triage — repeat until no MISSING-PDF
py -3.13 pipeline/uncage.py run      # inventory -> pilot per book -> npc parse
                                     # -> 26-dimension gate pour -> law caches
```

- `run` is idempotent (re-runs skip finished stages; `--force` re-extracts).
- The pour rebuilds `build/mimir/handbook.db` from zero and re-applies
  `curations.json` — fix-a-berk-once survives by design.
- **WinError 32** at the gate = an MCP server holds the old handbook.db; `/mcp`
  reconnect releases it (Windows file-lock gotcha), then re-run.

## Phase 4 — verify (the point of all this)

```bash
py -3.13 pipeline/uncage.py verify
```

| verdict | meaning | move |
|---|---|---|
| `RECONSTITUTED` | byte-same sources reproduced the pinned end state; integrity 0 hard | play |
| `DRIFT-EXPLAINED` | a source sha differs (different scan/printing) — counts advisory | read the per-dimension diff; real gaps become **gate curations** (`build/mimir/curations.json`), same channel as ours — never hand-edit the store |
| `DRIFTED` | sources match but stores differ | a bug or local edits — diff `build/uncage/verify-report.json`, re-run `run`, escalate to the curator if it holds |

Refusals that are CORRECT, not broken: 5e-2014 encounter budgets (license),
invoke tools NOT_POURED until conversion lands, unsourced modifiers refused.

## Phase 5 — bring the family up (recipient)

1. `/mcp` reconnect → mimir/mechanus/modron/cant handshake.
2. Smokes through the *configured* spawn: `pipeline/mechanus/tests/smoke_server.py`,
   `pipeline/cant/smoke_server.py`; suites per CLAUDE.md Commands.
3. Modron's ledger starts EMPTY on purpose — chance is history, not state.
   Mechanus likewise: our six dockets ride as citable reference in
   `build/mechanus/rulings-export.json`; a new table's rulings enter only
   through `record_ruling`.

## Phase 6 — re-pin (curator only)

After any new pour, adjudication wave, or law-data change:

```bash
py -3.13 pipeline/uncage.py pin      # manifest + rulings export from live state
```

Commit `pipeline/uncage-manifest.json`, `build/mechanus/rulings-export.json`,
and `build/mimir/curations.json` together — the manifest must never lag the
stores it swears to. A `verify` straight after `pin` MUST read RECONSTITUTED;
anything else is a driver bug, not drift.
