#!/usr/bin/env python
"""handbook_store — Mimir's single store and the schema-as-library.

This is THE shared seam (ARCHITECTURE.md): Mimir writes through it, Mechanus and
Modron import it **read-only**. The library *is* the schema — no MCP-over-MCP, no
drift. When this lands, the siblings flip their seam from reading `build/**/npc/*.json`
to reading `handbook.db` here (MODRON.md §2 / MECHANUS.md §1).

Design law enforced here:
  * **Gate-only writes.** The only entity write surface is `admit()` / `quarantine()`,
    and each *requires a verdict docket* — nothing enters undocumented. `store.py`
    holds no admission policy (that's `gate.py`); it holds the contract that you
    cannot write an entity without a decision attached.
  * **Fixed envelope, open fields, uniform FTS, generic edges** (DIMENSIONS.md §0).
  * **Curation survives rebuild** — `admit()` transplants any prior `curated` block
    for an id unless the incoming entity overrides it (the lens's merge_curated).
  * **Identity is a real, gate-admitted row** (Ryan's ruling); `aspect_of` edges link
    manifestations to it; `view()` (a Mechanus function) reads these.

Reads are safe for siblings to call concurrently; open with `readonly=True`.
"""
from __future__ import annotations
import json, sqlite3, hashlib, re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                 # C:/sandbox/Planescape
DEFAULT_DB = ROOT / "build" / "mimir" / "handbook.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS entities (
  id            TEXT PRIMARY KEY,     -- namespaced: npc:uncaged:akin | identity:npc:akin
  type          TEXT NOT NULL,        -- dimension id, or 'identity' / 'taxon'
  name          TEXT,
  edition       TEXT,                 -- ruleset axis; NULL for edition-less identity nodes
  fields        TEXT,                 -- JSON, open per-dimension schema
  content       TEXT,                 -- flat projection for FTS
  provenance    TEXT,                 -- JSON arbitration record (sources, method, agreement)
  confidence    REAL,
  curated       TEXT,                 -- JSON human/agent edits; preserved across rebuilds
  source_sha    TEXT,
  admission_sha TEXT,                 -- content-address of the admitting verdict
  admitted_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_entities_type    ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_edition ON entities(edition);

CREATE TABLE IF NOT EXISTS edges (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  rel        TEXT NOT NULL,           -- member_of | aspect_of | leads_to | references | ...
  src_type   TEXT, src_id TEXT NOT NULL,
  tgt_type   TEXT, tgt_id TEXT NOT NULL,
  role       TEXT,                    -- taxonomy membership role (PRIMARY/DERIVED/…), else NULL
  edition    TEXT,
  provenance TEXT,
  confidence REAL
);
-- Edge dedup. A bare UNIQUE(rel,src_id,tgt_id,role) does NOT work: SQL treats every NULL as
-- DISTINCT, and role is NULL for the majority of edges (references/located_in/attested_in/
-- part_of), so identical edges would silently duplicate. The expression index folds NULL and
-- '' to one key, so INSERT OR IGNORE truly dedups regardless of role.  (V&V D1, 2026-06-05)
CREATE UNIQUE INDEX IF NOT EXISTS idx_edges_unique ON edges(rel, src_id, tgt_id, coalesce(role, ''));
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id);
CREATE INDEX IF NOT EXISTS idx_edges_tgt ON edges(tgt_id);
CREATE INDEX IF NOT EXISTS idx_edges_rel ON edges(rel);

CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
  entity_id, type, name, content, edition, tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS quarantine (
  id      TEXT PRIMARY KEY,
  type    TEXT, name TEXT, edition TEXT,
  entity  TEXT,                       -- full JSON envelope as proposed
  reason  TEXT,                       -- schema-fail | invariant-fail | conflict | low-confidence
  docket  TEXT,
  held_at TEXT
);

CREATE TABLE IF NOT EXISTS dockets (
  admission_sha TEXT PRIMARY KEY,
  entity_id     TEXT,
  decision      TEXT,                 -- ADMIT | QUARANTINE
  docket        TEXT,
  ts            TEXT
);
"""

ENVELOPE_KEYS = ("type", "id", "name", "edition", "fields", "content",
                 "provenance", "confidence", "curated", "source_sha")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slug(s: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", (s or "").lower())).strip("-")


def admission_sha(entity: dict, docket: dict) -> str:
    """Content-address of an admission: entity content + the checks that admitted it.
    Re-gating an unchanged entity reproduces this; any change invalidates it."""
    payload = json.dumps({
        "id": entity.get("id"), "fields": entity.get("fields"),
        "content": entity.get("content"),
        "checks": docket.get("checks"), "independent": docket.get("independent"),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HandbookStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB, readonly: bool = False):
        self.db_path = Path(db_path)
        self.readonly = readonly
        if readonly:
            uri = f"file:{self.db_path.as_posix()}?mode=ro"
            self.conn = sqlite3.connect(uri, uri=True)
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.executescript(SCHEMA)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.conn.close()

    # ---- gate-only writes (require a docket) -------------------------------
    def _guard(self):
        if self.readonly:
            raise PermissionError("store opened read-only — writes go through Mimir's gate only")

    def admit(self, entity: dict, docket: dict) -> str:
        """Write an admitted entity. CALLED ONLY BY THE GATE (gate.py) after a passing
        verdict. Carries forward prior curation; syncs FTS; records the docket."""
        self._guard()
        for k in ("type", "id"):
            if not entity.get(k):
                raise ValueError(f"entity missing required envelope key: {k}")
        e = {k: entity.get(k) for k in ENVELOPE_KEYS}
        # curation preservation: inherit prior curated unless this proposal overrides
        prior = self.conn.execute("SELECT curated FROM entities WHERE id=?", (e["id"],)).fetchone()
        carried = json.loads(prior["curated"]) if prior and prior["curated"] else {}
        carried.update(e.get("curated") or {})
        e["curated"] = carried
        sha = admission_sha(entity, docket)
        self.conn.execute("""
            INSERT INTO entities(id,type,name,edition,fields,content,provenance,confidence,
                                 curated,source_sha,admission_sha,admitted_at)
            VALUES(:id,:type,:name,:edition,:fields,:content,:provenance,:confidence,
                   :curated,:source_sha,:sha,:ts)
            ON CONFLICT(id) DO UPDATE SET
              type=:type,name=:name,edition=:edition,fields=:fields,content=:content,
              provenance=:provenance,confidence=:confidence,curated=:curated,
              source_sha=:source_sha,admission_sha=:sha,admitted_at=:ts
        """, {**e,
              "fields": json.dumps(e.get("fields"), ensure_ascii=False),
              "provenance": json.dumps(e.get("provenance"), ensure_ascii=False),
              "curated": json.dumps(e["curated"], ensure_ascii=False),
              "sha": sha, "ts": _now()})
        # FTS resync + drop from quarantine if it was held
        self.conn.execute("DELETE FROM fts WHERE entity_id=?", (e["id"],))
        self.conn.execute("INSERT INTO fts(entity_id,type,name,content,edition) VALUES(?,?,?,?,?)",
                          (e["id"], e["type"], e.get("name"), e.get("content"), e.get("edition")))
        self.conn.execute("DELETE FROM quarantine WHERE id=?", (e["id"],))
        self._record_docket(sha, e["id"], "ADMIT", docket)
        self.conn.commit()
        return sha

    def quarantine(self, entity: dict, docket: dict, reason: str) -> str:
        """Hold a failed/uncertain entity. CALLED ONLY BY THE GATE. Never enters `entities`."""
        self._guard()
        sha = admission_sha(entity, docket)
        self.conn.execute("""
            INSERT INTO quarantine(id,type,name,edition,entity,reason,docket,held_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET entity=excluded.entity,reason=excluded.reason,
              docket=excluded.docket,held_at=excluded.held_at
        """, (entity["id"], entity.get("type"), entity.get("name"), entity.get("edition"),
              json.dumps(entity, ensure_ascii=False), reason,
              json.dumps(docket, ensure_ascii=False), _now()))
        self._record_docket(sha, entity["id"], "QUARANTINE", docket)
        self.conn.commit()
        return sha

    def add_edge(self, rel, src_id, tgt_id, *, src_type=None, tgt_type=None, role=None,
                 edition=None, provenance=None, confidence=None, require_resolve=False) -> bool:
        """Add a typed edge. With require_resolve, refuses unless both endpoints are
        admitted entities (the VALIDATION invariant). Returns False if skipped."""
        self._guard()
        if require_resolve and not (self.exists(src_id) and self.exists(tgt_id)):
            return False
        self.conn.execute("""
            INSERT OR IGNORE INTO edges(rel,src_type,src_id,tgt_type,tgt_id,role,edition,provenance,confidence)
            VALUES(?,?,?,?,?,?,?,?,?)
        """, (rel, src_type, src_id, tgt_type, tgt_id, role, edition,
              json.dumps(provenance, ensure_ascii=False) if provenance else None, confidence))
        self.conn.commit()
        return True

    def _record_docket(self, sha, entity_id, decision, docket):
        self.conn.execute("""INSERT OR REPLACE INTO dockets(admission_sha,entity_id,decision,docket,ts)
                             VALUES(?,?,?,?,?)""",
                          (sha, entity_id, decision, json.dumps(docket, ensure_ascii=False), _now()))

    # ---- reads (safe for siblings) -----------------------------------------
    def _row_to_entity(self, r) -> dict:
        d = dict(r)
        for k in ("fields", "provenance", "curated"):
            if d.get(k):
                try: d[k] = json.loads(d[k])
                except Exception: pass
        return d

    def get(self, entity_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
        return self._row_to_entity(r) if r else None

    def exists(self, entity_id: str) -> bool:
        return self.conn.execute("SELECT 1 FROM entities WHERE id=?", (entity_id,)).fetchone() is not None

    def search(self, query: str, type: str | None = None, edition: str | None = None,
               limit: int = 20) -> list[dict]:
        terms = query.split()
        fts_q = query if any(op in query.upper() for op in (" AND ", " OR ", " NOT ", '"')) \
            else " OR ".join(terms)
        sql = ("SELECT f.entity_id, f.type, f.name, bm25(fts) AS rank "
               "FROM fts f WHERE fts MATCH ?")
        args: list = [fts_q]
        if type:    sql += " AND f.type=?";    args.append(type)
        if edition: sql += " AND f.edition=?"; args.append(edition)
        sql += " ORDER BY rank LIMIT ?"; args.append(limit)
        try:
            rows = self.conn.execute(sql, args).fetchall()
        except sqlite3.OperationalError:                       # bad FTS syntax → quote terms
            args[0] = " OR ".join(f'"{t}"' for t in terms)
            rows = self.conn.execute(sql, args).fetchall()
        return [dict(r) for r in rows]

    def list(self, type: str, limit: int = 100) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM entities WHERE type=? LIMIT ?", (type, limit)).fetchall()
        return [self._row_to_entity(r) for r in rows]

    def neighbors(self, entity_id: str, rel: str | None = None, direction: str = "out") -> list[dict]:
        col, other = ("src_id", "tgt_id") if direction == "out" else ("tgt_id", "src_id")
        sql = f"SELECT rel, {other} AS node, role FROM edges WHERE {col}=?"
        args: list = [entity_id]
        if rel: sql += " AND rel=?"; args.append(rel)
        return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def dangling_edges(self) -> list[dict]:
        """Edges whose target is not (yet) an admitted entity — VALIDATION reporting."""
        rows = self.conn.execute("""
            SELECT rel, src_id, tgt_id FROM edges
            WHERE tgt_id NOT IN (SELECT id FROM entities)""").fetchall()
        return [dict(r) for r in rows]

    def coverage(self) -> dict:
        adm = {r["type"]: r["n"] for r in self.conn.execute(
            "SELECT type, COUNT(*) n FROM entities GROUP BY type")}
        quar = {r["reason"]: r["n"] for r in self.conn.execute(
            "SELECT reason, COUNT(*) n FROM quarantine GROUP BY reason")}
        return {"admitted": adm, "admitted_total": sum(adm.values()),
                "quarantined": quar, "quarantined_total": sum(quar.values()),
                "edges": self.conn.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"]}


# --------------------------------------------------------------------------- smoke test
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # Prove the keystone on a REAL extracted envelope: A'kin from the v2 build.
    src = ROOT / "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/npc/a-kin.json"
    v2 = json.loads(src.read_text(encoding="utf-8"))

    def to_envelope(n):                                       # registry.py will formalize this
        sb = n.get("statblock", {}); d = n.get("descriptor", {}) or {}
        content = " ".join(filter(None, [
            n.get("name"), d.get("race"), d.get("faction"), sb.get("special_attacks"),
            n.get("body", ""), " ".join(f"{k}: {v}" for k, v in (n.get("sections") or {}).items())]))
        return {
            "type": "npc", "id": f"npc:uncaged:{slug(n['name'])}", "name": n["name"],
            "edition": "2e",
            "fields": {"descriptor": d, "statblock": sb, "sections": n.get("sections"),
                       "body": n.get("body")},
            "content": content,
            "provenance": {"value_sources": [{"src": "official-2e",
                            "loc": f"uncaged:p{n.get('pages',[None])[0]}"}], "method": "extraction"},
            "confidence": n.get("confidence"),
            "curated": {},
            "source_sha": (n.get("provenance") or {}).get("source_sha256"),
        }

    stub_docket = {"decision": "ADMIT",
                   "checks": [{"layer": "smoke", "name": "plumbing", "result": "pass"}],
                   "independent": {"channel": "none", "note": "smoke test — real gate is gate.py"}}

    store = HandbookStore()
    akin = to_envelope(v2)
    sha = store.admit(akin, stub_docket)
    for ref in v2.get("see_also", []):
        store.add_edge("references", akin["id"], f"npc:uncaged:{slug(ref['name'])}",
                       src_type="npc", tgt_type="npc", edition="2e",
                       provenance={"loc": f"uncaged see_also p{ref.get('page')}"})

    print(f"admitted {akin['id']}  sha={sha[:16]}…")
    print("search 'arcanaloth':", [r["entity_id"] for r in store.search("arcanaloth")])
    got = store.get(akin["id"])
    print(f"round-trip: name={got['name']!r} edition={got['edition']} "
          f"AC={got['fields']['statblock'].get('ac')} conf={got['confidence']}")
    print("A'kin references:", [n["node"] for n in store.neighbors(akin["id"], "references")])
    print("curated carried (should be {}):", got["curated"])
    print("coverage:", store.coverage())
    print(f"dangling edges (targets not yet admitted): {len(store.dangling_edges())} "
          f"— expected, the rest of the cast isn't poured yet")
    store.close()
