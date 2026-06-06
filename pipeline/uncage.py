#!/usr/bin/env python
"""uncage.py — reconstitute the rig on a fresh machine, and PROVE it landed.

The repo ships code, law-as-data, curations, and records — never the licensed
corpus or the stores derived from it. A new DM who owns the same books drops
their PDFs into content/official/ and this driver walks the whole chain:

    py -3.13 pipeline/uncage.py status    what's present / missing / drifted
    py -3.13 pipeline/uncage.py run       extract -> pour -> caches (idempotent)
    py -3.13 pipeline/uncage.py verify    live stores vs the pinned manifest
    py -3.13 pipeline/uncage.py pin       (curator only) re-pin manifest from live state

The oath is `verify`: it fingerprints the live stores (entity-id sets per
dimension, per-rel edge counts + a sorted-triple digest, quarantine by reason,
law_version, engine_version, text-cache shas) against pipeline/uncage-manifest.json
— the end state pinned on the curator's machine. Identical source PDFs MUST
reproduce identical fingerprints; a different scan (sha drift) downgrades the
comparison to advisory and says so out loud. Drift is reported, never papered.

Lane law: this driver only READS the engines' stores (Mimir via the shared
store lib, ledgers via sqlite ro). All writes happen inside the engines' own
entry points, invoked as subprocesses — the gate stays the only door.
Dates never enter fingerprints (admission stamps vary; identity doesn't).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
MANIFEST = HERE.parent / "uncage-manifest.json"
RULINGS_DB = ROOT / "build/mechanus/rulings.db"
RULINGS_EXPORT = ROOT / "build/mechanus/rulings-export.json"
HANDBOOK = ROOT / "build/mimir/handbook.db"
CURATIONS = ROOT / "build/mimir/curations.json"
REPORT = ROOT / "build/uncage/verify-report.json"

sys.path.insert(0, str(HERE.parent / "mimir"))            # the shared store lib

UNCAGE_VERSION = "1"

# The poured product set — gate.py main()'s whole input universe. Everything
# else inventoried (PSCS, Planewalker's, PAitM, ...) is pinned as optional.
REQUIRED_PRODUCTS = {
    "uncaged-faces-of-sigil",
    "the-factol-s-manifesto",
    "in-the-cage-a-guide-to-sigil",
    "planes-of-law",
    "planes-of-chaos",
    "planes-of-conflict",
    "hellbound-the-blood-war",
}

# Free-corpus pins (mirrors build_text_cache.SOURCES — kept inline so status/
# verify run without PyMuPDF installed). Re-download paths: content/README.md.
CORPUS = {
    "fgg":   "content/retroclones/for-gold-and-glory/For_Gold_and_Glory_2e_retroclone.pdf",
    "srd51": "content/srd/srd-5.1/SRD_CC_v5.1.pdf",
    "srd52": "content/srd/srd-5.2/SRD_CC_v5.2.1.pdf",
}

# Held-out witness corpus the gate reads at pour time (CC-BY-SA, ships in-repo
# so the confidence channel is deterministic).
WIKI_DIR = ROOT / "content/wikis/fandom-planescape"

# parse/book.py's hardwired component (Uncaged npc extraction).
UNCAGED_COMPONENT = "ps-uncaged-facesofsigil"


# --------------------------------------------------------------------- helpers
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_lines(lines: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()


def jload(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def component_registry() -> list[dict]:
    """psx inventory's source.json registry, sorted; [] on a fresh clone."""
    out = []
    for sj in sorted((ROOT / "build").glob("*/*/source.json")):
        s = jload(sj)
        out.append(s)
    return out


# ------------------------------------------------------------ live fingerprints
def fingerprint_mimir() -> dict | None:
    """Date-free identity of the poured store: id sets, edge triples, quarantine."""
    if not HANDBOOK.exists():
        return None
    import store as S                                     # pipeline/mimir/store.py
    st = S.HandbookStore(HANDBOOK, readonly=True)
    try:
        conn = st.conn
        by_type: dict[str, list[str]] = {}
        for r in conn.execute("SELECT id, type FROM entities ORDER BY id"):
            by_type.setdefault(r["type"], []).append(r["id"])
        try:
            edge_rows = [(r["rel"], r["src_id"], r["tgt_id"], r["role"] or "")
                         for r in conn.execute("SELECT rel, src_id, tgt_id, role FROM edges")]
        except Exception:                                  # older schema: no role column
            edge_rows = [(r["rel"], r["src_id"], r["tgt_id"], "")
                         for r in conn.execute("SELECT rel, src_id, tgt_id FROM edges")]
        rel_counts: dict[str, int] = {}
        for rel, *_ in edge_rows:
            rel_counts[rel] = rel_counts.get(rel, 0) + 1
        try:
            quar = [(r["id"], r["reason"]) for r in
                    conn.execute("SELECT id, reason FROM quarantine ORDER BY id")]
        except Exception:
            quar = [(r["id"], "") for r in conn.execute("SELECT id FROM quarantine ORDER BY id")]
        q_by_reason: dict[str, int] = {}
        for _, reason in quar:
            q_by_reason[reason] = q_by_reason.get(reason, 0) + 1
        n_dockets = conn.execute("SELECT COUNT(*) c FROM dockets").fetchone()["c"]
    finally:
        st.close()
    return {
        "entities_total": sum(len(v) for v in by_type.values()),
        "edges_total": len(edge_rows),
        "by_type": {t: {"count": len(ids), "ids": ids} for t, ids in sorted(by_type.items())},
        "edges_by_rel": dict(sorted(rel_counts.items())),
        "edges_sha256": sha256_lines(["|".join(e) for e in edge_rows]),
        "quarantine": {"count": len(quar),
                       "by_reason": dict(sorted(q_by_reason.items())),
                       "ids": sorted(q for q, _ in quar)},
        "dockets_count": n_dockets,
        "curations_sha256": sha256_file(CURATIONS) if CURATIONS.exists() else None,
    }


def mechanus_state() -> dict:
    sys.path.insert(0, str(ROOT / "pipeline/mechanus"))
    from mechanus import law_version                       # content-addressed law set
    caches = {}
    for slug in CORPUS:
        idx = ROOT / f"build/mechanus/{slug}-text/INDEX.md"
        if idx.exists():
            m = re.search(r"sha256: `([0-9a-f]{64})`", idx.read_text(encoding="utf-8"))
            caches[slug] = {
                "pages": len(list(idx.parent.glob("p*.txt"))),
                "source_sha256": m.group(1) if m else None,
            }
        else:
            caches[slug] = None
    n_rulings = None
    if RULINGS_DB.exists():
        import sqlite3
        c = sqlite3.connect(f"file:{RULINGS_DB.as_posix()}?mode=ro", uri=True)
        try:
            n_rulings = c.execute("SELECT COUNT(*) FROM rulings").fetchone()[0]
        finally:
            c.close()
    return {"law_version": law_version(), "text_caches": caches, "rulings_count": n_rulings}


def modron_state() -> dict:
    sys.path.insert(0, str(ROOT / "pipeline/modron"))
    from modron import ENGINE_VERSION
    data = {}
    for p in sorted((ROOT / "pipeline/modron/data").rglob("*.json")):
        data[p.relative_to(ROOT).as_posix()] = sha256_file(p)
    return {"engine_version": ENGINE_VERSION, "data_sha256": data}


def witness_state() -> dict:
    return {p.relative_to(ROOT).as_posix(): sha256_file(p)
            for p in sorted(WIKI_DIR.glob("export_*.xml"))}


# ------------------------------------------------------------------------- pin
def export_rulings() -> int:
    """Dump the rulings ledger as a versioned record (REFERENCE data for a new
    table — never auto-imported; the ledger's write guard stays the only door)."""
    import sqlite3
    c = sqlite3.connect(f"file:{RULINGS_DB.as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        rows = [dict(r) for r in c.execute("SELECT * FROM rulings ORDER BY ruling_id")]
    finally:
        c.close()
    RULINGS_EXPORT.write_text(
        json.dumps({"_doc": "Mechanus rulings ledger export — citable precedent from the "
                            "curator's table. A fresh ledger starts empty and may CITE these; "
                            "imports never bypass record_ruling.",
                    "count": len(rows), "rulings": rows},
                   indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(rows)


def cmd_pin(_a) -> int:
    mim = fingerprint_mimir()
    if mim is None:
        print("no handbook.db — pour before pinning"); return 1
    n_rul = export_rulings() if RULINGS_DB.exists() else 0
    mech = mechanus_state()
    sources, bundles = [], 0
    for s in component_registry():
        if not s.get("file") or not s.get("sha256"):
            bundles += 1                       # D&D Beyond save bundles (PAitM) — parts
            continue                           # manifest, never a required pour input
        sources.append({
            "product_slug": s["product_slug"], "component": s["component"],
            "file": s["file"].replace("\\", "/"), "sha256": s["sha256"],
            "pages": s["pages"], "tsr_code": s.get("tsr_code"),
            "required": s["product_slug"] in REQUIRED_PRODUCTS,
        })
    missing = REQUIRED_PRODUCTS - {s["product_slug"] for s in sources}
    if missing:
        print(f"required products not in inventory: {sorted(missing)} — run psx inventory first")
        return 1
    manifest = {
        "_doc": "uncage end-state manifest — pinned on the curator's machine. "
                "`verify` proves a fresh reconstitution reached this exact state; "
                "source-sha drift (a different scan) downgrades counts to advisory.",
        "uncage_version": UNCAGE_VERSION,
        "pinned": __import__("datetime").date.today().isoformat(),
        "python": "3.13",
        "sources": {
            "official": sources,
            "corpus": [{"role": k, "file": v,
                        "sha256": sha256_file(ROOT / v) if (ROOT / v).exists() else None}
                       for k, v in CORPUS.items()],
            "witness": witness_state(),
        },
        "expected": {
            "mimir": mim,
            "mechanus": {**mech, "rulings_exported": n_rul,
                         "rulings_export_sha256": sha256_file(RULINGS_EXPORT)
                         if RULINGS_EXPORT.exists() else None},
            "modron": modron_state(),
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    print(f"pinned -> {MANIFEST.relative_to(ROOT)}")
    print(f"  mimir   : {mim['entities_total']} entities · {mim['edges_total']} edges · "
          f"{mim['quarantine']['count']} quarantined · {mim['dockets_count']} dockets")
    print(f"  mechanus: law {mech['law_version']} · {n_rul} rulings exported")
    print(f"  sources : {len(sources)} components ({sum(1 for s in sources if s['required'])} required"
          + (f" · {bundles} dndbeyond bundles unpinned)" if bundles else ")"))
    return 0


# ----------------------------------------------------------------------- status
def load_manifest() -> dict | None:
    return jload(MANIFEST) if MANIFEST.exists() else None


def source_status(man: dict, hash_present: bool = True) -> list[dict]:
    """Per required component: is the PDF where the pour expects it, and is it
    OUR scan? (Filenames are load-bearing — psx slugs and the parse modules'
    reflow paths derive from them.)"""
    out = []
    for s in man["sources"]["official"]:
        if not s["required"]:
            continue
        p = ROOT / s["file"]
        row = {**s}
        if not p.exists():
            row["state"] = "MISSING-PDF"
        elif hash_present and sha256_file(p) != s["sha256"]:
            row["state"] = "SHA-DRIFT"
        else:
            row["state"] = "OK"
        bdir = ROOT / "build" / s["product_slug"] / s["component"]
        row["extracted"] = (bdir / "book.md").exists() and (bdir / "reflow").is_dir()
        if s["component"] == UNCAGED_COMPONENT:
            row["npc_nodes"] = len(list((bdir / "npc").glob("*.json"))) if (bdir / "npc").is_dir() else 0
        out.append(row)
    return out


def cmd_status(a) -> int:
    man = load_manifest()
    if man is None:
        print("no pinned manifest — this clone predates `pin`, or you removed it. "
              "Only the curator's machine pins."); return 1
    rows = source_status(man, hash_present=not a.fast)
    wp = max(len(r["product_slug"]) for r in rows)
    wc = max(len(r["component"]) for r in rows)
    print(f"{'product':{wp}}  {'component':{wc}}  source      extracted")
    todo_pdf, todo_extract = [], []
    for r in rows:
        ex = "yes" if r["extracted"] else "NO"
        if r["component"] == UNCAGED_COMPONENT:
            ex += f" (npc:{r.get('npc_nodes', 0)})"
        print(f"{r['product_slug']:{wp}}  {r['component']:{wc}}  {r['state']:10}  {ex}")
        if r["state"] == "MISSING-PDF":
            todo_pdf.append(r)
        elif not r["extracted"]:
            todo_extract.append(r)
    print()
    for k, v in CORPUS.items():
        p = ROOT / v
        pin = next(c for c in man["sources"]["corpus"] if c["role"] == k)
        st = ("MISSING" if not p.exists() else
              "OK" if a.fast or pin["sha256"] is None or sha256_file(p) == pin["sha256"]
              else "SHA-DRIFT")
        print(f"corpus {k:6} {st:10} {v}")
    wn = len(list(WIKI_DIR.glob("export_*.xml")))
    print(f"witness      {wn} wiki exports (in-repo, CC-BY-SA)")
    print(f"stores       handbook.db: {'present' if HANDBOOK.exists() else 'ABSENT'} · "
          f"rulings.db: {'present' if RULINGS_DB.exists() else 'absent (fresh ledger on first ruling)'}")
    if todo_pdf:
        print("\nnext: place these purchased PDFs at EXACTLY these paths (filenames are "
              "load-bearing), then re-run status:")
        for r in todo_pdf:
            print(f"  {r['file']}    (sha256 {r['sha256'][:16]}… · {r['pages']}p"
                  + (f" · {r['tsr_code']}" if r["tsr_code"] else "") + ")")
        print("  buy-list & links: content/official/CATALOG.md")
    elif todo_extract or not HANDBOOK.exists():
        print("\nnext: py -3.13 pipeline/uncage.py run")
    else:
        print("\nnext: py -3.13 pipeline/uncage.py verify")
    return 0


# -------------------------------------------------------------------------- run
def _sub(args: list[str], what: str) -> None:
    print(f"\n=== {what} ===")
    r = subprocess.run([sys.executable, *args], cwd=ROOT)
    if r.returncode != 0:
        if "gate.py" in " ".join(args):
            print("  (WinError 32 here usually means an MCP server holds handbook.db — "
                  "/mcp reconnect to release it, then re-run)")
        sys.exit(f"{what} failed (exit {r.returncode})")


def cmd_run(a) -> int:
    man = load_manifest()
    if man is None:
        print("no pinned manifest — nothing to reconstitute against"); return 1
    try:
        import fitz  # noqa: F401
    except ImportError:
        sys.exit("PyMuPDF missing — py -3.13 -m pip install -r pipeline/requirements.txt")
    rows = source_status(man, hash_present=False)
    missing = [r for r in rows if r["state"] == "MISSING-PDF"]
    if missing:
        print("cannot run — required PDFs missing (see status):")
        for r in missing:
            print(f"  {r['file']}")
        return 1
    _sub(["pipeline/extract/psx.py", "inventory"], "psx inventory")
    for r in rows:
        if not r["extracted"] or a.force:
            _sub(["pipeline/extract/psx.py", "pilot", "--slug", r["component"]]
                 + (["--force"] if a.force else []), f"psx pilot {r['component']}")
    unc = next(r for r in rows if r["component"] == UNCAGED_COMPONENT)
    if not unc.get("npc_nodes") or a.force:
        _sub(["pipeline/parse/book.py"], "parse/book.py (Uncaged npc nodes)")
    _sub(["pipeline/mimir/gate.py"], "mimir gate (full 26-dimension pour)")
    if all((ROOT / v).exists() for v in CORPUS.values()):
        _sub(["pipeline/mechanus/tools/build_text_cache.py"], "mechanus text caches")
    else:
        print("\n(corpus PDFs missing — skipped lawyer text caches; see status)")
    print("\nnext: py -3.13 pipeline/uncage.py verify")
    return 0


# ----------------------------------------------------------------------- verify
def _diff_ids(pinned: list[str], live: list[str]) -> tuple[list[str], list[str]]:
    ps, ls = set(pinned), set(live)
    return sorted(ls - ps), sorted(ps - ls)


def cmd_verify(_a) -> int:
    man = load_manifest()
    if man is None:
        print("no pinned manifest"); return 1
    findings: list[str] = []
    advisory = False

    # -- sources first: sha drift downgrades everything downstream to advisory
    rows = source_status(man)
    for r in rows:
        if r["state"] != "OK":
            findings.append(f"source {r['state']:10} {r['file']}")
            advisory = True
    if not HANDBOOK.exists():
        print("handbook.db absent — run `uncage run` first"); return 1

    live_mim = fingerprint_mimir()
    pin_mim = man["expected"]["mimir"]
    mim_ok = True
    for t in sorted(set(pin_mim["by_type"]) | set(live_mim["by_type"])):
        p = pin_mim["by_type"].get(t, {"count": 0, "ids": []})
        l = live_mim["by_type"].get(t, {"count": 0, "ids": []})
        if p["ids"] != l["ids"]:
            mim_ok = False
            extra, lost = _diff_ids(p["ids"], l["ids"])
            msg = f"mimir {t}: {l['count']} vs pinned {p['count']}"
            if lost:
                msg += f" · missing {lost[:8]}{'…' if len(lost) > 8 else ''}"
            if extra:
                msg += f" · unexpected {extra[:8]}{'…' if len(extra) > 8 else ''}"
            findings.append(msg)
    if live_mim["edges_sha256"] != pin_mim["edges_sha256"]:
        mim_ok = False
        deltas = {r: (live_mim["edges_by_rel"].get(r, 0), pin_mim["edges_by_rel"].get(r, 0))
                  for r in set(live_mim["edges_by_rel"]) | set(pin_mim["edges_by_rel"])}
        changed = {r: f"{a}≠{b}" for r, (a, b) in sorted(deltas.items()) if a != b}
        findings.append(f"mimir edges digest differs ({live_mim['edges_total']} vs "
                        f"{pin_mim['edges_total']}) · per-rel deltas: {changed or 'membership only'}")
    if live_mim["quarantine"]["ids"] != pin_mim["quarantine"]["ids"]:
        mim_ok = False
        extra, lost = _diff_ids(pin_mim["quarantine"]["ids"], live_mim["quarantine"]["ids"])
        findings.append(f"mimir quarantine: {live_mim['quarantine']['count']} vs pinned "
                        f"{pin_mim['quarantine']['count']} · missing {lost[:6]} · unexpected {extra[:6]}")
    if live_mim["curations_sha256"] != pin_mim["curations_sha256"]:
        mim_ok = False
        findings.append("mimir curations.json sha differs — local adjudications diverge from repo")

    # -- the other session's structural checker is a free witness when present
    integ = ROOT / "pipeline/mimir/tools/integrity.py"
    integ_note = "not present"
    if integ.exists():
        r = subprocess.run([sys.executable, str(integ)], cwd=ROOT, capture_output=True, text=True)
        integ_note = "0 hard" if r.returncode == 0 else "HARD VIOLATIONS — see build/mimir/review/integrity-report.json"
        if r.returncode != 0:
            mim_ok = False
            findings.append(f"mimir integrity: {integ_note}")

    live_mech = mechanus_state()
    pin_mech = man["expected"]["mechanus"]
    mech_ok = live_mech["law_version"] == pin_mech["law_version"]
    if not mech_ok:
        findings.append(f"mechanus law_version {live_mech['law_version']} != pinned "
                        f"{pin_mech['law_version']} — law data edited?")
    for slug, pin_c in pin_mech["text_caches"].items():
        live_c = live_mech["text_caches"].get(slug)
        if pin_c and not live_c:
            findings.append(f"mechanus {slug}-text cache absent — run build_text_cache.py")
            mech_ok = False
        elif pin_c and live_c and (live_c["pages"], live_c["source_sha256"]) != \
                (pin_c["pages"], pin_c["source_sha256"]):
            findings.append(f"mechanus {slug}-text cache differs (pages/source sha)")
            mech_ok = False

    live_mod = modron_state()
    pin_mod = man["expected"]["modron"]
    mod_ok = live_mod == pin_mod
    if not mod_ok:
        if live_mod["engine_version"] != pin_mod["engine_version"]:
            findings.append(f"modron engine_version {live_mod['engine_version']} != "
                            f"pinned {pin_mod['engine_version']}")
        for f, sha in pin_mod["data_sha256"].items():
            if live_mod["data_sha256"].get(f) != sha:
                findings.append(f"modron pack edited: {f}")

    wit_ok = witness_state() == man["sources"]["witness"]
    if not wit_ok:
        findings.append("witness corpus differs from pinned wiki exports — gate confidence drifts")

    verdict = ("RECONSTITUTED" if mim_ok and mech_ok and mod_ok and wit_ok and not advisory
               else "DRIFT-EXPLAINED (source scans differ — counts advisory; adjudicate "
                    "real gaps via curations.json)" if advisory
               else "DRIFTED")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(
        {"verdict": verdict, "findings": findings,
         "live": {"mimir": {k: v for k, v in live_mim.items() if k != "by_type"},
                  "mimir_counts": {t: d["count"] for t, d in live_mim["by_type"].items()},
                  "mechanus": live_mech, "modron": {"engine_version": live_mod["engine_version"]}},
         "pinned": man["pinned"], "uncage_version": UNCAGE_VERSION},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"mimir    : {live_mim['entities_total']} entities · {live_mim['edges_total']} edges · "
          f"{live_mim['quarantine']['count']} quarantined · "
          f"{'MATCH' if mim_ok else 'DIFFERS'} · integrity {integ_note}")
    print(f"mechanus : law {live_mech['law_version']} · caches "
          f"{[s for s, c in live_mech['text_caches'].items() if c]} · "
          f"{'MATCH' if mech_ok else 'DIFFERS'}")
    print(f"modron   : engine {live_mod['engine_version']} · "
          f"{len(live_mod['data_sha256'])} pack files · {'MATCH' if mod_ok else 'DIFFERS'}")
    print(f"witness  : {'MATCH' if wit_ok else 'DIFFERS'}")
    for f in findings:
        print(f"  ! {f}")
    print(f"\nverdict: {verdict}")
    print(f"report -> {REPORT.relative_to(ROOT)}")
    return 0 if verdict == "RECONSTITUTED" else 2


# ------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(prog="uncage", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("status", help="sources/stages triage vs the pinned manifest")
    sp.add_argument("--fast", action="store_true", help="skip sha256 of present PDFs")
    sp = sub.add_parser("run", help="extract -> pour -> caches (idempotent)")
    sp.add_argument("--force", action="store_true", help="re-extract even if stages exist")
    sub.add_parser("verify", help="live stores vs pipeline/uncage-manifest.json")
    sub.add_parser("pin", help="(curator) pin manifest + rulings export from live state")
    a = ap.parse_args()
    return {"status": cmd_status, "run": cmd_run, "verify": cmd_verify, "pin": cmd_pin}[a.cmd](a)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
