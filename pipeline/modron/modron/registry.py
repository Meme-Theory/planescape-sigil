"""The rollables registry: Modron-owned, page-cited rollable substance as data.

The rule-effect handoff (build/family/rule-effect-handoff.md, 2026-06-06) split
the lanes: Mimir keeps identity + used_at pointers; Mechanus keeps governing
law; Modron keeps what the dice APPLY. This registry is the data home for that
third lane — tables, pre-compiled roll specs, diceless lookups, and encounter
specs harvested from the corpus, each carrying its witness.

Entry shapes (data/rollables/*.json — a list of entries):
    {id, label, kind, used_at: [...], source: {product, page|pages, ...},
     notes?, requires_confirmation?} + ONE payload by kind:
  kind "table"     -> table: {dice, entries:[{roll, result, ...}]}  (roll_table-able)
  kind "spec"      -> spec: a rollables-compiler-shaped roll spec
                      ({purpose, expr?|check?, label?, ...}) — feed expr/check to
                      roll / roll_damage / roll_check
  kind "lookup"    -> rows: [{key, ...}] — diceless reference data bound to a
                      mechanic (served, NEVER rolled; no invented dice)
  kind "encounter" -> encounter: an encounter_rolls spec

Law carried over from the modifier registry: every entry NAMES its source —
an unsourced entry fails at load. Official-scan sources are cite-only:
entries hold paraphrased mechanical substance (dice, numbers, terse outcome
labels) with page witnesses, never book prose. Table entries validate
coverage at load (gaps/overlaps refuse loudly, the validate_table law).
"""

from __future__ import annotations

import json
from pathlib import Path

from .grammar import DiceSyntaxError, parse

PACKAGE_DIR = Path(__file__).resolve().parent.parent
ROLLABLES_DIR = PACKAGE_DIR / "data" / "rollables"

_KINDS = ("table", "spec", "lookup", "encounter")
_PAYLOAD_KEY = {"table": "table", "spec": "spec", "lookup": "rows",
                "encounter": "encounter"}


class RegistryError(ValueError):
    pass


def _validate_entry(entry: dict, file: str) -> None:
    eid = entry.get("id")
    if not eid:
        raise RegistryError(f"{file}: registry entry without id: {entry!r}")
    kind = entry.get("kind")
    if kind not in _KINDS:
        raise RegistryError(f"{file}: {eid}: unknown kind {kind!r} (known: {_KINDS})")
    if not entry.get("source"):
        raise RegistryError(
            f"{file}: {eid}: no source — every rollable names its witness "
            "(source: {product, page, ...}); an unsourced entry is refused")
    payload = _PAYLOAD_KEY[kind]
    if payload not in entry:
        raise RegistryError(f"{file}: {eid}: kind {kind!r} needs a {payload!r} payload")
    if kind == "table":
        # coverage validates at load — a gappy table refuses loudly, not at the table
        from .rollables import validate_table
        report = validate_table(entry["table"])
        if report["verdict"] != "ok":
            raise RegistryError(
                f"{file}: {eid}: table coverage issues {report['gaps']=} "
                f"{report['overlaps']=} {report['unparsed']=}")
    if kind == "spec":
        expr = entry["spec"].get("expr")
        if expr:
            try:
                parse(str(expr))
            except DiceSyntaxError as e:
                raise RegistryError(f"{file}: {eid}: spec expr {expr!r} doesn't parse: {e}")
        if not expr and not entry["spec"].get("check"):
            raise RegistryError(f"{file}: {eid}: a spec needs an expr or a check")


def _load_registry() -> dict[str, dict]:
    reg: dict[str, dict] = {}
    if ROLLABLES_DIR.exists():
        for path in sorted(ROLLABLES_DIR.glob("*.json")):
            with open(path, "r", encoding="utf-8") as f:
                rows = json.load(f)
            for row in rows:
                _validate_entry(row, path.name)
                row.setdefault("_file", path.name)
                if row["id"] in reg:
                    raise RegistryError(f"{path.name}: duplicate rollable id {row['id']!r}")
                reg[row["id"]] = row
    return reg


def registry() -> dict[str, dict]:
    return _load_registry()


def get(rid: str) -> dict | None:
    return _load_registry().get(rid)


def search(query: str = "", used_at: str | None = None,
           kind: str | None = None) -> list[dict]:
    """Substring search over id/label/notes/used_at; optional kind/used_at filters."""
    q = (query or "").lower()
    ua = (used_at or "").lower()
    out = []
    for row in _load_registry().values():
        if kind and row.get("kind") != kind:
            continue
        row_used = [str(u).lower() for u in (row.get("used_at") or [])]
        if ua and not any(ua in u for u in row_used):
            continue
        hay = " ".join([row["id"], row.get("label", ""), str(row.get("notes", "")),
                        " ".join(row_used)]).lower()
        if q and q not in hay:
            continue
        out.append(row)
    return sorted(out, key=lambda r: r["id"])
