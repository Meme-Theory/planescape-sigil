"""The rulings ledger — Mechanus's one writable store (MECHANUS.md §6).

build/mechanus/rulings.db, written ONLY through record_ruling/overrule: the
emit_verdict discipline inherited from the lens — schema-forced dockets,
cross-process lockfile, content-address SHA uniqueness, supersedes chains that
preserve history. Precedent is sticky like curation: same question, same
answer, unless the DM overrules — and the overrule is itself a docket.

Rolls are Modron's: a docket cites roll_ids; it never contains dice.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import tables

DEFAULT_DB = Path(__file__).resolve().parents[3] / "build" / "mechanus" / "rulings.db"

_ID_OK = set("abcdefghijklmnopqrstuvwxyz0123456789:-'")
KINDS = ("ruling", "house-rule")
SCOPE_PREFIXES = ("campaign:", "table:", "global")
FATES = ("ADOPTED", "rejected")


class DocketError(ValueError):
    """The docket failed the forced schema — nothing was written."""


def _canonical_sha(docket: dict[str, Any]) -> str:
    """Content-address of the ruling CONTENT — id and stamps excluded, so a
    re-submission under a fresh id is still the same ruling and still a dup."""
    body = {k: v for k, v in docket.items()
            if k not in ("sha", "ts", "superseded_by", "ruling_id", "law_version")}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_docket(d: dict[str, Any]) -> None:
    """Schema-forced: every field the docket law demands, or DocketError."""
    def need(cond: bool, msg: str) -> None:
        if not cond:
            raise DocketError(msg)

    need(isinstance(d, dict), "docket must be a dict")
    rid = d.get("ruling_id", "")
    need(isinstance(rid, str) and rid.startswith("rul:") and len(rid) > 6
         and set(rid.lower()) <= _ID_OK, f"ruling_id must match rul:<scope>:<slug>[:<seq>], got {rid!r}")
    need(bool(str(d.get("question", "")).strip()), "question is required")
    need(bool(str(d.get("view", "")).strip()), "view is required (5e-2014 | 5e-2024 | 2e | ...)")
    scope = d.get("scope", "")
    need(isinstance(scope, str) and (scope == "global" or scope.startswith(SCOPE_PREFIXES[:2])),
         f"scope must be global | campaign:<id> | table:<id>, got {scope!r}")
    need(d.get("kind", "ruling") in KINDS, f"kind must be one of {KINDS}")

    ladder = d.get("ladder_path")
    need(isinstance(ladder, list) and ladder and all(isinstance(s, str) for s in ladder),
         "ladder_path must be a non-empty list of steps (the §6 ladder, walked)")

    cands = d.get("candidates")
    need(isinstance(cands, list) and cands, "candidates[] required — a ruling that considered one reading isn't arbitration")
    adopted = [c for c in cands if c.get("fate") == "ADOPTED"]
    need(len(adopted) == 1, f"exactly one candidate must be ADOPTED, got {len(adopted)}")
    for c in cands:
        need(c.get("fate") in FATES, f"candidate fate must be in {FATES}")
        need(bool(str(c.get("position", "")).strip()), "every candidate needs a position")
        if c["fate"] == "rejected":
            need(bool(str(c.get("why", "")).strip()),
                 "loser preservation: rejected candidates must record why")

    for q in d.get("raw_quotes") or []:
        need(bool(str(q.get("text", "")).strip()) and bool(str(q.get("loc", "")).strip()),
             "raw_quotes entries need text AND loc (verbatim + citation, or nothing)")

    conf = d.get("confidence")
    need(isinstance(conf, (int, float)) and 0.0 <= conf <= 1.0, "confidence must be in [0, 1]")
    need(bool(str(d.get("adjudicator", "")).strip()), "adjudicator required (auto | human:<name> | workflow:<id>)")

    rolls = d.get("rolls") or []
    need(isinstance(rolls, list) and all(isinstance(r, str) and r for r in rolls),
         "rolls must be a list of Modron roll_id strings — dockets cite dice, never contain them")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS rulings (
  ruling_id     TEXT PRIMARY KEY,
  kind          TEXT NOT NULL,
  question      TEXT NOT NULL,
  view          TEXT NOT NULL,
  scope         TEXT NOT NULL,
  docket        TEXT NOT NULL,        -- full JSON, the source of truth
  sha           TEXT NOT NULL UNIQUE, -- content-address (sans ts/sha/superseded_by)
  supersedes    TEXT,
  superseded_by TEXT,
  law_version   TEXT NOT NULL,
  ts            TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS rulings_fts USING fts5(
  ruling_id UNINDEXED, question
);
"""


class Ledger:
    def __init__(self, db_path: str | Path = DEFAULT_DB):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock_path = self.db_path.with_suffix(".lock")
        with self._conn() as cx:
            cx.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        cx = sqlite3.connect(self.db_path)
        cx.row_factory = sqlite3.Row
        return cx

    # -- the lock (lens discipline: O_EXCL create, stale takeover) -----------
    def _acquire(self, timeout: float = 10.0, stale: float = 60.0) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return
            except FileExistsError:
                try:
                    if time.time() - self._lock_path.stat().st_mtime > stale:
                        self._lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError(f"rulings.db lock held past {timeout}s: {self._lock_path}")
                time.sleep(0.05)

    def _release(self) -> None:
        self._lock_path.unlink(missing_ok=True)

    # -- writes (the only two) ------------------------------------------------
    def record_ruling(self, docket: dict[str, Any]) -> dict[str, Any]:
        """Validate, content-address, and append a ruling. Returns the stamped docket."""
        validate_docket(docket)
        d = dict(docket)
        d["sha"] = _canonical_sha(d)
        d["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        d.setdefault("kind", "ruling")
        d["law_version"] = tables.law_version()

        self._acquire()
        try:
            with self._conn() as cx:
                dup = cx.execute("SELECT ruling_id FROM rulings WHERE sha = ?", (d["sha"],)).fetchone()
                if dup:
                    raise DocketError(f"identical docket already ledgered as {dup['ruling_id']} (sha {d['sha'][:12]})")
                if cx.execute("SELECT 1 FROM rulings WHERE ruling_id = ?", (d["ruling_id"],)).fetchone():
                    raise DocketError(f"ruling_id {d['ruling_id']} already exists — overrule it, don't overwrite it")
                sup = d.get("supersedes")
                if sup:
                    row = cx.execute("SELECT superseded_by FROM rulings WHERE ruling_id = ?", (sup,)).fetchone()
                    if row is None:
                        raise DocketError(f"supersedes target {sup!r} not in ledger")
                    if row["superseded_by"]:
                        raise DocketError(f"{sup} already superseded by {row['superseded_by']} — chain from the head")
                cx.execute(
                    "INSERT INTO rulings (ruling_id, kind, question, view, scope, docket, sha,"
                    " supersedes, superseded_by, law_version, ts) VALUES (?,?,?,?,?,?,?,?,NULL,?,?)",
                    (d["ruling_id"], d["kind"], d["question"], d["view"], d["scope"],
                     json.dumps(d, ensure_ascii=False), d["sha"], sup, d["law_version"], d["ts"]))
                if sup:
                    cx.execute("UPDATE rulings SET superseded_by = ? WHERE ruling_id = ?",
                               (d["ruling_id"], sup))
                cx.execute("INSERT INTO rulings_fts (ruling_id, question) VALUES (?, ?)",
                           (d["ruling_id"], d["question"]))
        finally:
            self._release()
        return d

    def overrule(self, old_ruling_id: str, new_docket: dict[str, Any]) -> dict[str, Any]:
        """DM changed their mind: new docket supersedes the old; history preserved."""
        nd = dict(new_docket)
        nd["supersedes"] = old_ruling_id
        return self.record_ruling(nd)

    # -- reads ----------------------------------------------------------------
    def get(self, ruling_id: str, follow: bool = True) -> dict[str, Any] | None:
        """Fetch a ruling; follow=True walks to the head of its supersedes chain."""
        with self._conn() as cx:
            row = cx.execute("SELECT docket, superseded_by FROM rulings WHERE ruling_id = ?",
                             (ruling_id,)).fetchone()
            if row is None:
                return None
            while follow and row["superseded_by"]:
                row = cx.execute("SELECT docket, superseded_by FROM rulings WHERE ruling_id = ?",
                                 (row["superseded_by"],)).fetchone()
            return json.loads(row["docket"])

    def precedents(self, topic: str, scope: str | None = None, limit: int = 10,
                   include_superseded: bool = False) -> list[dict[str, Any]]:
        """FTS over questions — what has this table already ruled?"""
        sql = ("SELECT r.docket FROM rulings_fts f JOIN rulings r ON r.ruling_id = f.ruling_id "
               "WHERE rulings_fts MATCH ?")
        args: list[Any] = [topic]
        if not include_superseded:
            sql += " AND r.superseded_by IS NULL"
        if scope:
            sql += " AND (r.scope = ? OR r.scope = 'global')"
            args.append(scope)
        sql += " ORDER BY rank LIMIT ?"
        args.append(limit)
        with self._conn() as cx:
            return [json.loads(r["docket"]) for r in cx.execute(sql, args)]

    def house_rules(self, scope: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT docket FROM rulings WHERE kind = 'house-rule' AND superseded_by IS NULL"
        args: list[Any] = []
        if scope:
            sql += " AND (scope = ? OR scope = 'global')"
            args.append(scope)
        with self._conn() as cx:
            return [json.loads(r["docket"]) for r in cx.execute(sql + " ORDER BY ts", args)]

    def chain(self, ruling_id: str) -> list[str]:
        """The full supersedes chain through a ruling, oldest first."""
        with self._conn() as cx:
            ids = [ruling_id]
            row = cx.execute("SELECT supersedes FROM rulings WHERE ruling_id = ?", (ruling_id,)).fetchone()
            while row and row["supersedes"]:
                ids.insert(0, row["supersedes"])
                row = cx.execute("SELECT supersedes FROM rulings WHERE ruling_id = ?", (row["supersedes"],)).fetchone()
            row = cx.execute("SELECT superseded_by FROM rulings WHERE ruling_id = ?", (ruling_id,)).fetchone()
            while row and row["superseded_by"]:
                ids.append(row["superseded_by"])
                row = cx.execute("SELECT superseded_by FROM rulings WHERE ruling_id = ?", (row["superseded_by"],)).fetchone()
            return ids
