"""The roll ledger (rolls.db): Modron's single store (MODRON.md §3).

Discipline inherited from the lens's emit_verdict: cross-process O_EXCL
lockfile around every write, SHA-unique rows (a duplicate content-address is
refused, not overwritten), no entity data, no rulings — rolls only.

Fairness protocol:
  session_open  -> seed drawn (or derived from a table-chosen phrase),
                   sha256(seed) PUBLISHED as the commitment, secret held;
  every roll    -> faces derived from (seed, counter) — see engine.DiceStream;
  session_close -> stream sealed; seed WITHHELD by default (§12 Q1: on-demand
                   cadence) — reveal=True (at close, or calling again on a
                   closed session) publishes it; then anyone recomputes the night.
Ephemeral rolls (no session) carry their seed openly in the row.

Fiat is honest: method='fiat', no faces, reason required, never disguised.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import sqlite3
import time
from pathlib import Path

from . import ENGINE_VERSION
from .engine import DiceStream, commitment, evaluate, new_seed, seed_from_phrase
from .grammar import parse

PACKAGE_DIR = Path(__file__).resolve().parent.parent     # pipeline/modron
PROJECT_ROOT = PACKAGE_DIR.parent.parent                  # C:/sandbox/Planescape
DEFAULT_LEDGER = PROJECT_ROOT / "build" / "modron" / "rolls.db"


def ledger_path() -> Path:
    return Path(os.environ.get("MODRON_LEDGER", str(DEFAULT_LEDGER)))


_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(
  session_id      TEXT PRIMARY KEY,
  label           TEXT,
  view            TEXT,
  seed_commitment TEXT NOT NULL,
  seed_secret_hex TEXT NOT NULL,
  revealed        INTEGER NOT NULL DEFAULT 0,
  status          TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
  engine_version  TEXT NOT NULL,
  counter         INTEGER NOT NULL DEFAULT 0,
  opened_ts       TEXT NOT NULL,
  closed_ts       TEXT
);
CREATE TABLE IF NOT EXISTS rolls(
  roll_id        TEXT PRIMARY KEY,
  session_id     TEXT,
  counter        INTEGER NOT NULL,
  label          TEXT,
  purpose        TEXT,
  view           TEXT,
  expr_asked     TEXT NOT NULL,
  expr_resolved  TEXT NOT NULL,
  context_ref    TEXT,
  batch_id       TEXT,
  modifiers_json TEXT NOT NULL DEFAULT '[]',
  groups_json    TEXT NOT NULL DEFAULT '[]',
  outcome_json   TEXT,
  totals_json    TEXT,
  total          INTEGER NOT NULL,
  method         TEXT NOT NULL CHECK(method IN ('rolled','fiat')),
  seed_scope     TEXT NOT NULL CHECK(seed_scope IN ('session','ephemeral','none')),
  seed_hex       TEXT,
  rounding       TEXT NOT NULL DEFAULT 'down',
  crit_effect    TEXT NOT NULL DEFAULT 'double_dice',
  engine_version TEXT NOT NULL,
  sha            TEXT NOT NULL UNIQUE,
  notes_json     TEXT,
  ts             TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rolls_session ON rolls(session_id, counter);
CREATE INDEX IF NOT EXISTS idx_rolls_batch   ON rolls(batch_id);
"""


class LedgerError(RuntimeError):
    pass


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ---------------------------------------------------------------------------
# Cross-process lock (the lens's O_EXCL discipline, sync flavor)
# ---------------------------------------------------------------------------

def _acquire_lock(timeout: float = 10.0, stale: float = 60.0) -> Path:
    lock = ledger_path().with_suffix(".db.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout
    while True:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale:
                    lock.unlink()  # holder presumed dead — steal
                    continue
            except FileNotFoundError:
                continue
            if time.time() > deadline:
                raise LedgerError(f"ledger lock timeout ({timeout:.0f}s) on {lock.name}")
            time.sleep(0.05)


def _release_lock(lock: Path) -> None:
    try:
        lock.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (label or "session").lower()).strip("-")[:32]
    return s or "session"


def open_session(label: str, view: str | None = None,
                 seed_phrase: str | None = None) -> dict:
    seed = seed_from_phrase(seed_phrase) if seed_phrase else new_seed()
    commit = commitment(seed)
    session_id = f"ses:{_slug(label)}-{commit[:6]}"
    lock = _acquire_lock()
    try:
        with _connect() as conn:
            if conn.execute("SELECT 1 FROM sessions WHERE session_id=?",
                            (session_id,)).fetchone():
                raise LedgerError(f"session {session_id} already exists "
                                  "(same label + same seed — reuse it or change one)")
            conn.execute(
                "INSERT INTO sessions(session_id,label,view,seed_commitment,seed_secret_hex,"
                "engine_version,opened_ts) VALUES (?,?,?,?,?,?,?)",
                (session_id, label, view, commit, seed.hex(), ENGINE_VERSION, _now()))
    finally:
        _release_lock(lock)
    return {"session_id": session_id, "label": label, "view": view,
            "seed_commitment": commit, "engine_version": ENGINE_VERSION,
            "note": "commitment published BEFORE any die falls; seed stays "
                    "withheld until revealed on demand — session_close(reveal=true)",
            "seed_phrase_used": bool(seed_phrase)}


def close_session(session_id: str, reveal: bool = False) -> dict:
    """Seal the session. The seed stays WITHHELD unless reveal=True (§12 Q1:
    on-demand cadence) — calling again on a closed session with reveal=True is
    the on-demand reveal; without it, a re-close is still an error."""
    lock = _acquire_lock()
    try:
        with _connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id=?",
                               (session_id,)).fetchone()
            if not row:
                raise LedgerError(f"unknown session {session_id!r}")
            if row["status"] == "closed" and not reveal:
                raise LedgerError(f"session {session_id} already closed "
                                  "(reveal=true to publish its seed on demand)")
            if row["status"] == "closed":   # on-demand reveal of a sealed night
                conn.execute("UPDATE sessions SET revealed=1 WHERE session_id=?",
                             (session_id,))
            else:
                conn.execute("UPDATE sessions SET status='closed', revealed=?, "
                             "closed_ts=? WHERE session_id=?",
                             (1 if reveal else 0, _now(), session_id))
            n = conn.execute("SELECT COUNT(*) c FROM rolls WHERE session_id=?",
                             (session_id,)).fetchone()["c"]
    finally:
        _release_lock(lock)
    out = {"session_id": session_id, "status": "closed", "rolls": n,
           "seed_commitment": row["seed_commitment"]}
    if reveal:
        out["seed_revealed_hex"] = row["seed_secret_hex"]
        out["verify"] = ("sha256(bytes.fromhex(seed_revealed_hex)) == seed_commitment; "
                         "then verify(session_id) recomputes every roll")
    else:
        out["seed"] = ("WITHHELD — on-demand cadence (MODRON §12 Q1): "
                       "session_close(session_id, reveal=true) publishes it; "
                       "verify(session_id) works DM-side regardless")
    return out


def get_session(session_id: str) -> sqlite3.Row:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id=?",
                           (session_id,)).fetchone()
    if not row:
        raise LedgerError(f"unknown session {session_id!r} (session_open first)")
    return row


def session_view(session_id: str | None) -> str | None:
    if not session_id:
        return None
    try:
        return get_session(session_id)["view"]
    except LedgerError:
        return None


# ---------------------------------------------------------------------------
# Rolls
# ---------------------------------------------------------------------------

def _roll_sha(expr_resolved: str, seed_id: str, counter: int, groups: list,
              total: int, method: str) -> str:
    payload = "|".join([
        "modron:roll:v1", method, expr_resolved, seed_id, str(counter),
        json.dumps(groups, sort_keys=True, separators=(",", ":")), str(total),
    ])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def next_stream(session_id: str | None) -> tuple[DiceStream, dict]:
    """Reserve the next counter on a session (or mint an ephemeral seed).

    Returns (stream, meta) where meta carries scope/seed bookkeeping for the row.
    """
    if session_id:
        lock = _acquire_lock()
        try:
            with _connect() as conn:
                row = conn.execute("SELECT * FROM sessions WHERE session_id=?",
                                   (session_id,)).fetchone()
                if not row:
                    raise LedgerError(f"unknown session {session_id!r} (session_open first)")
                if row["status"] != "open":
                    raise LedgerError(f"session {session_id} is closed")
                counter = row["counter"] + 1
                conn.execute("UPDATE sessions SET counter=? WHERE session_id=?",
                             (counter, session_id))
        finally:
            _release_lock(lock)
        seed = bytes.fromhex(row["seed_secret_hex"])
        return DiceStream(seed, counter), {
            "session_id": session_id, "counter": counter, "seed_scope": "session",
            "seed_hex": None, "seed_id": row["seed_commitment"],
            "roll_id": f"rol:{session_id.split(':', 1)[1]}:{counter:05d}"}
    seed = new_seed()
    return DiceStream(seed, 0), {
        "session_id": None, "counter": 0, "seed_scope": "ephemeral",
        "seed_hex": seed.hex(), "seed_id": seed.hex(), "roll_id": None}


def record_roll(meta: dict, *, expr_asked: str, expr_resolved: str, total: int,
                groups: list, view: str | None = None, label: str | None = None,
                purpose: str | None = None, context_ref: str | None = None,
                batch_id: str | None = None, modifiers: list | None = None,
                outcome: dict | None = None, totals: list | None = None,
                notes: list | None = None, rounding: str = "down",
                crit_effect: str = "double_dice", method: str = "rolled") -> dict:
    sha = _roll_sha(expr_resolved, meta["seed_id"], meta["counter"], groups, total, method)
    roll_id = meta.get("roll_id") or \
        (f"rol:fiat:{sha[:12]}" if method == "fiat" else f"rol:eph:{sha[:12]}")
    row = {
        "roll_id": roll_id, "session_id": meta.get("session_id"),
        "counter": meta["counter"], "label": label, "purpose": purpose, "view": view,
        "expr_asked": expr_asked, "expr_resolved": expr_resolved,
        "context_ref": context_ref, "batch_id": batch_id,
        "modifiers_json": json.dumps(modifiers or [], ensure_ascii=False),
        "groups_json": json.dumps(groups, ensure_ascii=False),
        "outcome_json": json.dumps(outcome, ensure_ascii=False) if outcome else None,
        "totals_json": json.dumps(totals) if totals is not None else None,
        "total": total, "method": method,
        "seed_scope": meta["seed_scope"], "seed_hex": meta.get("seed_hex"),
        "rounding": rounding, "crit_effect": crit_effect,
        "engine_version": ENGINE_VERSION, "sha": sha,
        "notes_json": json.dumps(notes or [], ensure_ascii=False), "ts": _now(),
    }
    lock = _acquire_lock()
    try:
        with _connect() as conn:
            try:
                conn.execute(
                    f"INSERT INTO rolls({','.join(row)}) VALUES ({','.join('?' * len(row))})",
                    tuple(row.values()))
            except sqlite3.IntegrityError as e:
                raise LedgerError(f"duplicate roll refused (sha {sha[:12]}…): {e}")
    finally:
        _release_lock(lock)
    return {"roll_id": roll_id, "sha": sha, "session_id": meta.get("session_id"),
            "counter": meta["counter"]}


def record_fiat(value: int, *, reason: str, expr: str | None = None,
                session_id: str | None = None, label: str | None = None,
                view: str | None = None, context_ref: str | None = None) -> dict:
    """DM fiat: ledgered as fiat, never disguised (MODRON.md §3)."""
    if not reason or not str(reason).strip():
        raise LedgerError("fiat requires a reason — the rogue modron is labeled")
    meta = {"session_id": session_id, "counter": 0, "seed_scope": "none",
            "seed_hex": None, "seed_id": "fiat", "roll_id": None}
    if session_id:
        get_session(session_id)  # must exist; fiat doesn't consume a counter
    notes = [f"FIAT: {reason}"]
    return record_roll(meta, expr_asked=expr or "(fiat)", expr_resolved=expr or "(fiat)",
                       total=int(value), groups=[], view=view, label=label,
                       purpose="fiat", context_ref=context_ref, notes=notes,
                       method="fiat")


# ---------------------------------------------------------------------------
# Reads, replay, verify
# ---------------------------------------------------------------------------

def get_roll(roll_id: str) -> dict:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM rolls WHERE roll_id=?", (roll_id,)).fetchone()
    if not row:
        raise LedgerError(f"unknown roll {roll_id!r}")
    return dict(row)


def history(session_id: str | None = None, purpose: str | None = None,
            batch_id: str | None = None, limit: int = 50) -> list[dict]:
    q = "SELECT * FROM rolls"
    cond, args = [], []
    if session_id:
        cond.append("session_id=?")
        args.append(session_id)
    if purpose:
        cond.append("purpose=?")
        args.append(purpose)
    if batch_id:
        cond.append("batch_id=?")
        args.append(batch_id)
    if cond:
        q += " WHERE " + " AND ".join(cond)
    q += " ORDER BY ts DESC, counter DESC LIMIT ?"
    args.append(max(1, min(int(limit), 500)))
    with _connect() as conn:
        rows = [dict(r) for r in conn.execute(q, args).fetchall()]
    return rows


def _seed_for(row: dict) -> bytes | None:
    if row["seed_scope"] == "ephemeral":
        return bytes.fromhex(row["seed_hex"])
    if row["seed_scope"] == "session":
        ses = get_session(row["session_id"])
        return bytes.fromhex(ses["seed_secret_hex"])
    return None  # fiat


def verify_roll(roll_id: str) -> dict:
    """Re-derive the stream, re-evaluate, re-hash. PASS or the diff."""
    row = get_roll(roll_id)
    if row["method"] == "fiat":
        return {"roll_id": roll_id, "verdict": "FIAT",
                "note": "fiat rows have no dice to verify; the label is the point"}
    seed = _seed_for(row)
    stream = DiceStream(seed, row["counter"])
    result = evaluate(parse(row["expr_resolved"]), stream,
                      rounding=row["rounding"], crit_effect=row["crit_effect"])
    groups = [g.to_dict() for g in result.groups]
    stored_groups = json.loads(row["groups_json"])
    sha = _roll_sha(row["expr_resolved"], _seed_id_for(row), row["counter"],
                    stored_groups, row["total"], row["method"])
    ok_faces = groups == stored_groups
    ok_total = result.total == row["total"]
    ok_sha = sha == row["sha"]
    verdict = "PASS" if (ok_faces and ok_total and ok_sha) else "FAIL"
    out = {"roll_id": roll_id, "verdict": verdict, "engine_version": row["engine_version"],
           "faces_match": ok_faces, "total_match": ok_total, "sha_match": ok_sha}
    if verdict == "FAIL":
        out["recomputed"] = {"total": result.total, "groups": groups, "sha": sha}
        out["stored"] = {"total": row["total"], "groups": stored_groups, "sha": row["sha"]}
    return out


def _seed_id_for(row: dict) -> str:
    if row["seed_scope"] == "session":
        return get_session(row["session_id"])["seed_commitment"]
    if row["seed_scope"] == "ephemeral":
        return row["seed_hex"]
    return "fiat"


def verify_session(session_id: str) -> dict:
    """Re-derive EVERY roll of the session — a dedicated unclamped read, not
    history()'s capped page (audit F-1-design-docs-02: the old limit=500 sweep
    could PASS a long night with its oldest rolls unchecked)."""
    ses = get_session(session_id)
    with _connect() as conn:
        ids = [r["roll_id"] for r in conn.execute(
            "SELECT roll_id FROM rolls WHERE session_id=? ORDER BY counter, ts",
            (session_id,))]
    results = [verify_roll(rid) for rid in ids]
    fails = [r for r in results if r["verdict"] == "FAIL"]
    fiats = [r for r in results if r["verdict"] == "FIAT"]
    out = {"session_id": session_id, "status": ses["status"],
           "seed_commitment": ses["seed_commitment"],
           "seed_revealed": bool(ses["revealed"]),
           "rolls_checked": len(results), "fiat_rows": len(fiats),
           "verdict": "PASS" if not fails else "FAIL",
           "failures": fails}
    # cross-check: session-scope rolled rows must equal the session counter
    rolled = len(results) - len(fiats)
    if rolled != ses["counter"]:
        out["verdict"] = "FAIL"
        out["count_mismatch"] = (f"sessions.counter={ses['counter']} but "
                                 f"{rolled} rolled rows verified")
    return out


def replay(roll_id: str) -> dict:
    """Re-run a roll's stream (identical faces) and show it — verify's show-your-work."""
    row = get_roll(roll_id)
    if row["method"] == "fiat":
        raise LedgerError("fiat rows don't replay — nothing was rolled")
    seed = _seed_for(row)
    result = evaluate(parse(row["expr_resolved"]), DiceStream(seed, row["counter"]),
                      rounding=row["rounding"], crit_effect=row["crit_effect"])
    return {"roll_id": roll_id, "expr_resolved": row["expr_resolved"],
            "total": result.total, "groups": [g.to_dict() for g in result.groups],
            "identical_to_ledger": result.total == row["total"]}
