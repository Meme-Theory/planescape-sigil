"""Read-only seam to Mimir (MODRON.md §2.1).

Three doors, tried in order:
  1. inline dict — any caller can pass the entity/table straight in;
  2. file ref — a v2 extraction envelope (build/**/npc/*.json — live today)
     by path, or by bare name globbed under build/ (slug match);
  3. handbook.db — when Mimir pours, this is the ONE file that aligns to her
     store lib ("the lib is the schema"); until then a miss explains itself.

Modron never writes through this seam. There is no write path to write.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
BUILD_DIR = PROJECT_ROOT / "build"
HANDBOOK_DB = BUILD_DIR / "mimir" / "handbook.db"   # Mimir's DEFAULT_DB (poured 2026-06-05)
MIMIR_LIB = PROJECT_ROOT / "pipeline" / "mimir"


class EntityNotFound(KeyError):
    pass


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _load_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_MIMIR_STORE_MOD = None


def _mimir_store():
    """Load Mimir's store lib (pipeline/mimir/store.py) surgically via importlib —
    the lib is the schema (ARCHITECTURE.md), and no sys.path pollution (her dir
    holds server.py/gate.py that must not shadow ours). Cached after first load."""
    global _MIMIR_STORE_MOD
    if _MIMIR_STORE_MOD is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("mimir_store", MIMIR_LIB / "store.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MIMIR_STORE_MOD = mod
    return _MIMIR_STORE_MOD


def _handbook_lookup(ref: str) -> dict | None:
    """Look a ref up in Mimir's handbook.db via HER store lib — no raw-SQL
    coupling, no drift. Read-only. Id first, then unique exact-name FTS hit
    (family cross-validation G2: bare names must reach ADMITTED+CURED data,
    never fall back to stale pre-pour build JSON when the handbook knows them).
    Tolerates lib/DB absence (pre-pour worlds)."""
    if not HANDBOOK_DB.exists():
        return None
    try:
        hb = _mimir_store().HandbookStore(HANDBOOK_DB, readonly=True)
        try:
            hit = hb.get(ref)
            if hit:
                return hit
            # name door: exact (case-insensitive) name match, unique
            rows = hb.search(ref, limit=5)
            exact = [r for r in rows if str(r.get("name", "")).lower() == ref.lower()]
            if len(exact) == 1:
                return hb.get(exact[0]["entity_id"])
            # slug-form name ('a-kin') against slugged entity names
            slugged = [r for r in rows if _slugify(str(r.get("name", ""))) == _slugify(ref)]
            if len(slugged) == 1:
                return hb.get(slugged[0]["entity_id"])
            return None
        finally:
            hb.close()
    except Exception:
        return None  # seam stays soft: fall through to the other doors


def find_entity(ref: dict | str) -> tuple[dict, str]:
    """Resolve an entity ref. Returns (entity_dict, source_descriptor)."""
    if isinstance(ref, dict):
        return ref, "inline"
    ref = str(ref).strip()

    # inline JSON that crossed the MCP wire as a string (V&V catch 2026-06-05)
    if ref.startswith("{"):
        try:
            return json.loads(ref), "inline"
        except json.JSONDecodeError as e:
            raise EntityNotFound(f"ref looks like inline JSON but doesn't parse: {e}")

    # file path (absolute, or project-relative)
    for candidate in (Path(ref), PROJECT_ROOT / ref):
        if candidate.suffix == ".json" and candidate.exists():
            return _load_json_file(candidate), str(candidate)

    # handbook id (when poured)
    hb = _handbook_lookup(ref)
    if hb is not None:
        return hb, f"handbook.db:{ref}"

    # LAST resort: slug glob over raw build envelopes. These are pre-gate
    # extractions — when the handbook exists but didn't know this ref, say so
    # loudly: the data is uncured (or quarantined) by definition (G2/G7).
    slug = _slugify(ref.split(":")[-1])
    if BUILD_DIR.exists():
        hits = [p for p in BUILD_DIR.glob("**/npc/*.json") if p.stem == slug]
        if not hits:
            hits = [p for p in BUILD_DIR.glob("**/npc/*.json") if slug in p.stem]
        if len(hits) == 1:
            src = str(hits[0])
            if HANDBOOK_DB.exists():
                src += "  [WARNING: raw pre-gate extraction — NOT in the admitted " \
                       "handbook (uncured/possibly quarantined); curations do NOT apply]"
            return _load_json_file(hits[0]), src
        if len(hits) > 1:
            raise EntityNotFound(
                f"{ref!r} is ambiguous across build envelopes: "
                f"{[p.stem for p in hits[:8]]} — pass the file path")

    raise EntityNotFound(
        f"can't resolve entity {ref!r}: not a file, not in handbook.db "
        f"({'present' if HANDBOOK_DB.exists() else 'not yet poured'}), "
        f"no build envelope slug-matches. Pass the entity inline, a path under "
        f"build/, or a handbook id once Mimir pours.")


def find_table(ref: dict | str) -> tuple[dict, str]:
    """Resolve a table ref to {dice, entries[...]}. Doors: inline, the Modron
    rollables registry (page-cited setting tables, rule-effect handoff D-lane),
    then find_entity's doors."""
    if isinstance(ref, dict):
        t = ref
        src = "inline"
    else:
        # Modron's own rollables registry FIRST — these ids are ours
        # (tbl:/spc:/lkp:/enc: namespaces), page-cited at load
        from . import registry as _registry
        row = _registry.get(str(ref).strip())
        if row is not None:
            if row.get("kind") != "table":
                raise EntityNotFound(
                    f"rollables-registry:{row['id']} is kind {row.get('kind')!r}, not a "
                    "rollable table — lookups are served (use the rollables tool), never rolled")
            t = dict(row["table"])
            t.setdefault("name", row.get("label"))
            return t, f"rollables-registry:{row['id']}"
        entity, src = find_entity(ref)
        t = entity
    # tolerate envelope nesting (dim:table fields live under 'fields')
    if "entries" not in t and isinstance(t.get("fields"), dict):
        t = t["fields"]
    if "entries" not in t:
        raise EntityNotFound(
            f"{src}: no 'entries' — a table needs {{dice, entries:[{{roll, result}}]}}")
    t.setdefault("dice", "1d100")
    return t, src
