"""The render ledger — content-addressed WAV provenance (the lens pattern).

Every render row: sha (cache key), what was asked (voice/registers/text/knobs),
what answered (file, duration, seeds), the lane stamp, and hit/retake counters.
Writes go through the O_EXCL lockfile; the cache key canon is THE smart-provision
law: same ask => same sha => the existing WAV is served, hit counted.

Seed policy (DABUS.md §3): seed=None means "this line, whatever take" — the
random seed is RECORDED but EXCLUDED from the key, so repeats hit cache. An
explicit integer seed names a specific take and joins the key.
"""

import hashlib
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import BUILD_DIR, DB_PATH, ENGINE_VERSION, LANE, RENDERS_DIR


class StoreError(RuntimeError):
    pass


# ---------------------------------------------------------------- cache key

def cache_key(*, model: str, voice: str, segments: list[dict],
              knobs: dict, seed: int | None) -> str:
    """Canonical content address of a render ask. Segments carry
    (register, ref_sha, ref_text, text) — swapping a reference clip or
    editing its transcript changes the sha, exactly like law_version."""
    payload = {
        "engine_version": ENGINE_VERSION,
        "model": model,
        "voice": voice,
        "segments": [{k: s[k] for k in ("register", "ref_sha", "ref_text", "text")}
                     for s in segments],
        "knobs": {k: knobs[k] for k in sorted(knobs)},
    }
    if seed is not None:
        payload["seed"] = int(seed)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- store

_SCHEMA = """
CREATE TABLE IF NOT EXISTS renders(
    render_id   TEXT PRIMARY KEY,
    sha         TEXT UNIQUE NOT NULL,
    kind        TEXT NOT NULL,             -- render | stitch
    voice       TEXT NOT NULL,
    registers   TEXT NOT NULL,             -- json list
    text        TEXT NOT NULL,
    params_json TEXT NOT NULL,
    file        TEXT NOT NULL,
    duration_s  REAL,
    seeds_json  TEXT,
    lane        TEXT NOT NULL,
    created_utc TEXT NOT NULL,
    hits        INTEGER NOT NULL DEFAULT 0,
    retakes     INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS renders_fts USING fts5(
    text, voice, content='renders', content_rowid='rowid');
CREATE TRIGGER IF NOT EXISTS renders_ai AFTER INSERT ON renders BEGIN
    INSERT INTO renders_fts(rowid, text, voice) VALUES (new.rowid, new.text, new.voice);
END;
CREATE TRIGGER IF NOT EXISTS renders_au AFTER UPDATE OF text ON renders BEGIN
    UPDATE renders_fts SET text = new.text WHERE rowid = new.rowid;
END;
"""


def _connect() -> sqlite3.Connection:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    # v1.1 migration: Mimir join-key (dialog id) — stable across re-pours
    cols = {r[1] for r in conn.execute("PRAGMA table_info(renders)")}
    if "source_ref" not in cols:
        conn.execute("ALTER TABLE renders ADD COLUMN source_ref TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_renders_source "
                     "ON renders(source_ref)")
    return conn


@contextmanager
def _locked():
    """O_EXCL write lock (family pattern). Read paths don't take it."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    lock = DB_PATH.with_suffix(".db.lock")
    for _ in range(50):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.1)
    else:
        raise StoreError(f"could not acquire {lock} — stale lock? remove it if no "
                         f"dabus write is in flight")
    try:
        os.close(fd)
        yield
    finally:
        try:
            os.unlink(lock)
        except OSError:
            pass


def _row_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["registers"] = json.loads(d["registers"])
    d["params"] = json.loads(d.pop("params_json"))
    d["seeds"] = json.loads(d.pop("seeds_json")) if d.get("seeds_json") else None
    return d


def get_by_sha(sha: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM renders WHERE sha=?", (sha,)).fetchone()
        return _row_dict(row) if row else None
    finally:
        conn.close()


def lookup(ref: str) -> dict | None:
    """render_id | sha (or prefix >= 8) | file path | source_ref (Mimir
    dialog id — newest render wins; re-poured text supersedes by recency)."""
    conn = _connect()
    try:
        for q, arg in (("render_id=?", ref), ("sha=?", ref), ("file=?", ref)):
            row = conn.execute(f"SELECT * FROM renders WHERE {q}", (arg,)).fetchone()
            if row:
                return _row_dict(row)
        row = conn.execute("SELECT * FROM renders WHERE source_ref=? "
                           "ORDER BY created_utc DESC LIMIT 1", (ref,)).fetchone()
        if row:
            return _row_dict(row)
        if len(ref) >= 8:
            row = conn.execute("SELECT * FROM renders WHERE sha LIKE ?",
                               (ref + "%",)).fetchone()
            if row:
                return _row_dict(row)
        return None
    finally:
        conn.close()


def bump_hit(sha: str) -> None:
    with _locked():
        conn = _connect()
        try:
            conn.execute("UPDATE renders SET hits = hits + 1 WHERE sha=?", (sha,))
            conn.commit()
        finally:
            conn.close()


def record(*, sha: str, kind: str, voice: str, registers: list[str], text: str,
           params: dict, file: str, duration_s: float | None,
           seeds: list[int] | None, retake: bool = False,
           source_ref: str | None = None) -> dict:
    """Insert a render row, or — on a retake of an existing sha — update the
    row in place (new take supersedes; the file was overwritten on disk)."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _locked():
        conn = _connect()
        try:
            existing = conn.execute("SELECT * FROM renders WHERE sha=?", (sha,)).fetchone()
            if existing:
                if not retake:
                    raise StoreError(f"sha collision without retake flag: {sha[:12]}")
                conn.execute(
                    "UPDATE renders SET file=?, duration_s=?, seeds_json=?, "
                    "retakes = retakes + 1, created_utc=? WHERE sha=?",
                    (file, duration_s, json.dumps(seeds), now, sha))
                conn.commit()
                return _row_dict(conn.execute(
                    "SELECT * FROM renders WHERE sha=?", (sha,)).fetchone())
            render_id = "rnd:" + sha[:12]
            conn.execute(
                "INSERT INTO renders(render_id, sha, kind, voice, registers, text, "
                "params_json, file, duration_s, seeds_json, lane, created_utc, "
                "source_ref) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (render_id, sha, kind, voice, json.dumps(registers), text,
                 json.dumps(params, ensure_ascii=False), file, duration_s,
                 json.dumps(seeds), LANE, now, source_ref))
            conn.commit()
            return _row_dict(conn.execute(
                "SELECT * FROM renders WHERE sha=?", (sha,)).fetchone())
        finally:
            conn.close()


def search(query: str | None, voice: str | None, limit: int = 20) -> list[dict]:
    conn = _connect()
    try:
        if query:
            try:
                safe = '"' + query.replace('"', '""') + '"'
                rows = conn.execute(
                    "SELECT r.* FROM renders_fts f JOIN renders r ON r.rowid=f.rowid "
                    "WHERE renders_fts MATCH ? "
                    + ("AND r.voice=? " if voice else "")
                    + "ORDER BY rank LIMIT ?",
                    ((safe, voice, limit) if voice else (safe, limit))).fetchall()
            except sqlite3.OperationalError:
                rows = []
            if not rows:  # FTS found nothing — substring fallback
                rows = conn.execute(
                    "SELECT * FROM renders WHERE text LIKE ? "
                    + ("AND voice=? " if voice else "")
                    + "ORDER BY created_utc DESC LIMIT ?",
                    ((f"%{query}%", voice, limit) if voice
                     else (f"%{query}%", limit))).fetchall()
        elif voice:
            rows = conn.execute("SELECT * FROM renders WHERE voice=? "
                                "ORDER BY created_utc DESC LIMIT ?",
                                (voice, limit)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM renders ORDER BY created_utc DESC "
                                "LIMIT ?", (limit,)).fetchall()
        return [_row_dict(r) for r in rows]
    finally:
        conn.close()


def stats() -> dict:
    conn = _connect()
    try:
        n, dur, hits = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(duration_s),0), COALESCE(SUM(hits),0) "
            "FROM renders").fetchone()
        by_voice = {r["voice"]: r["c"] for r in conn.execute(
            "SELECT voice, COUNT(*) c FROM renders GROUP BY voice")}
        return {"renders": n, "total_audio_s": round(dur, 1),
                "cache_hits_served": hits, "by_voice": by_voice,
                "db": str(DB_PATH), "renders_dir": str(RENDERS_DIR)}
    finally:
        conn.close()


def slug(text: str, n: int = 40) -> str:
    s = "".join(c if c.isalnum() else "-" for c in text.lower())
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")[:n].rstrip("-") or "line"


def render_path(voice: str, sha: str, text: str) -> Path:
    d = RENDERS_DIR / voice
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{sha[:12]}__{slug(text)}.wav"
