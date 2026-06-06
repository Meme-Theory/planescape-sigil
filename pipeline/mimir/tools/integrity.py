#!/usr/bin/env python
"""integrity.py — mechanical integrity checker over handbook.db (Great Audit, Phase 0).

Deterministic, no agents, read-only. Catches STRUCTURAL violations — things that are
bugs in the pour, not judgment calls for the review workflow: dangling/foreign edges,
catalog drift, empty provenance, confidence out of range, id/type mismatches, FTS
desync, missing per-dimension required fields.

Severity law: `hard` violations exit nonzero (fix BEFORE the review workflow runs);
`soft` ones land in the report for the workflow's attention. Documented-expected
states (the see_also danglers, Prisine's led_by) are whitelisted BY NAME — a new
dangler is a finding, the known two are not.

Output: build/mimir/review/integrity-report.json
Run:    py -3.13 pipeline/mimir/tools/integrity.py
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))                    # pipeline/mimir
sys.path.insert(0, str(HERE.parents[2] / "parse"))          # pipeline/parse
import store as S                                           # noqa: E402
import normalize as N                                       # noqa: E402

OUT = S.ROOT / "build/mimir/review/integrity-report.json"

# The edge catalog — every rel a pour is ALLOWED to mint (DIMENSIONS.md + the pour
# functions in gate.py). A rel outside this list after a re-pour is drift.
REL_CATALOG = {
    "allied_with", "aspect_of", "attested_in", "authored_by", "before", "concerns",
    "connects_to", "defends", "employs", "funds", "gate_to", "has_ward",
    "headquartered_in", "hires", "hub_of", "involves", "layer_of", "led_by",
    "located_in", "member_of", "occurred_at", "opens_from", "opposed_to", "opposes",
    "part_of", "participated_in", "protects", "realm_of", "references", "ruled_by",
    "schemes_around", "seats", "seeks", "serves", "set_in", "spied_on_by", "spies_on",
    "spoken_by", "summoned", "supplies", "wields",
}

# Documented-expected dangling edges (gate.py prints these as expected at pour time):
#  * references → see_also cutters in books not yet poured (Uncaged p-refs)
#  * led_by → npc:uncaged:prisine — an unpromoted companion (promotion = queued session)
def _dangler_expected(rel: str, tgt: str) -> bool:
    if rel == "references":
        return True
    if rel == "led_by" and tgt == "npc:uncaged:prisine":
        return True
    return False

# Dims whose `name` is a proper name (is_name applies). Sayings/dialog are quotes,
# hooks are sentences, portals/adventures are descriptive titles — exempt.
NAME_DIMS = {"npc", "faction", "organization", "deity", "plane", "layer", "realm",
             "gate-town", "settlement", "sect", "creature", "proxy", "source",
             "cosmology", "pathway", "sigil", "event", "location", "fiction"}

# Per-dimension required fields (light floor — the pour guarantees these).
# value = list of alternatives-groups: every group must have >=1 present+truthy key.
DIM_REQUIRED = {
    "portal":   [["sigil_side"], ["far_side"], ["witness"]],
    "realm":    [["power", "note", "parent"]],     # card realms: power|note · gazetteer: parent
    "creature": [["armor_class"], ["hit_dice"]],
    "dialog":   [["register"], ["text"], ["owner"]],
    "saying":   [["text"], ["page"]],
    # layer: plane-card layers always carry parent; cage-gazetteer layers may honestly
    # lack one when the witness names no plane (layer:the-viper-wastes, cage p9 — "in
    # the midst of the Blood War"). Attestation pages suffice mechanically; a missing
    # parent is a REVIEW finding (weak-witness), not a pour bug.
    "layer":    [["parent", "pages"]],
    "hook":     [["premise"], ["grain"]],
    "npc":      [["tier", "descriptor"]],          # full/minor carry descriptor; factols carry tier
    "settlement": [["kind"], ["parent"]],
    "adventure": [["synopsis"]],
}


def check(store: S.HandbookStore) -> dict:
    V: list[dict] = []

    def v(check_name, sev, ref, detail):
        V.append({"check": check_name, "sev": sev, "entity_or_edge": ref, "detail": detail})

    conn = store.conn
    ids = {r["id"]: r["type"] for r in conn.execute("SELECT id, type FROM entities")}

    # ---- edges ----------------------------------------------------------------
    n_edges = 0
    for e in conn.execute("SELECT id, rel, src_type, src_id, tgt_type, tgt_id FROM edges"):
        n_edges += 1
        ref = f"edge#{e['id']} {e['src_id']} -{e['rel']}-> {e['tgt_id']}"
        if e["rel"] not in REL_CATALOG:
            v("edge_rel_in_catalog", "hard", ref, f"rel {e['rel']!r} not in catalog")
        for col, node in (("src_id", e["src_id"]), ("tgt_id", e["tgt_id"])):
            if node not in ids:
                sev = "soft" if _dangler_expected(e["rel"], node) else "hard"
                v("edge_endpoint_exists", sev, ref, f"{col}={node} not admitted"
                  + (" (documented-expected)" if sev == "soft" else ""))
        if e["src_id"] in ids and e["src_type"] and ids[e["src_id"]] != e["src_type"]:
            v("edge_type_match", "hard", ref,
              f"src_type={e['src_type']} but node is {ids[e['src_id']]}")
        if e["tgt_id"] in ids and e["tgt_type"] and ids[e["tgt_id"]] != e["tgt_type"]:
            v("edge_type_match", "hard", ref,
              f"tgt_type={e['tgt_type']} but node is {ids[e['tgt_id']]}")

    # ---- entities ---------------------------------------------------------------
    n_ent = 0
    linked = {r["src_id"] for r in conn.execute("SELECT DISTINCT src_id FROM edges")} \
           | {r["tgt_id"] for r in conn.execute("SELECT DISTINCT tgt_id FROM edges")}
    for r in conn.execute("SELECT id, type, name, content, fields, provenance, confidence FROM entities"):
        n_ent += 1
        eid = r["id"]
        try:
            prov = json.loads(r["provenance"]) if r["provenance"] else {}
        except Exception:
            prov = None
        try:
            fields = json.loads(r["fields"]) if r["fields"] else {}
        except Exception:
            fields = {}
        if prov is None or not (prov or {}).get("value_sources"):
            v("provenance_nonempty", "hard", eid, "provenance.value_sources empty/unparseable")
        c = r["confidence"]
        if c is None or not (0.0 <= c <= 1.0):
            v("confidence_range", "hard", eid, f"confidence={c!r}")
        if not (r["name"] or "").strip():
            v("name_nonempty", "hard", eid, "empty name")
        if not (r["content"] or "").strip():
            v("content_nonempty", "hard", eid, "empty content")
        if eid.split(":", 1)[0] != r["type"]:
            v("id_type_prefix", "hard", eid, f"id prefix != type {r['type']!r}")
        if r["type"] in NAME_DIMS and (r["name"] or "").strip() and not N.is_name(r["name"]):
            v("name_not_fragment", "soft", eid, f"is_name fails: {r['name']!r}")
        if eid not in linked:
            v("orphan_entity", "soft", eid, "zero edges")
        for group in DIM_REQUIRED.get(r["type"], []):
            if not any(fields.get(k) for k in group):
                v("dim_required_fields", "hard", eid,
                  f"none of {group} present in fields")

    # ---- cross-table ---------------------------------------------------------
    fts_n = conn.execute("SELECT COUNT(*) c FROM fts").fetchone()["c"]
    if fts_n != n_ent:
        v("fts_sync", "hard", "fts", f"fts={fts_n} entities={n_ent}")
    fts_ids = {r["entity_id"] for r in conn.execute("SELECT entity_id FROM fts")}
    for missing in set(ids) - fts_ids:
        v("fts_sync", "hard", missing, "admitted but not in FTS")
    for extra in fts_ids - set(ids):
        v("fts_sync", "hard", extra, "in FTS but not admitted")
    for r in conn.execute("SELECT id FROM quarantine WHERE id IN (SELECT id FROM entities)"):
        v("admitted_also_quarantined", "hard", r["id"], "id in BOTH entities and quarantine")

    n_quar = conn.execute("SELECT COUNT(*) c FROM quarantine").fetchone()["c"]
    hard = [x for x in V if x["sev"] == "hard"]
    soft = [x for x in V if x["sev"] == "soft"]
    by_check: dict[str, int] = {}
    for x in V:
        by_check[x["check"]] = by_check.get(x["check"], 0) + 1
    return {
        "violations": V,
        "stats": {"entities": n_ent, "edges": n_edges, "quarantined": n_quar,
                  "fts_rows": fts_n, "hard": len(hard), "soft": len(soft),
                  "by_check": by_check},
    }


def main() -> int:
    store = S.HandbookStore(S.DEFAULT_DB, readonly=True)
    try:
        report = check(store)
    finally:
        store.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    st = report["stats"]
    print(f"integrity: {st['entities']} entities · {st['edges']} edges · "
          f"{st['quarantined']} quarantined · fts {st['fts_rows']}")
    print(f"violations: {st['hard']} hard · {st['soft']} soft · {st['by_check']}")
    for x in report["violations"]:
        if x["sev"] == "hard":
            print(f"  HARD {x['check']:24} {x['entity_or_edge']}: {x['detail']}")
    print(f"report -> {OUT}")
    return 1 if st["hard"] else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
