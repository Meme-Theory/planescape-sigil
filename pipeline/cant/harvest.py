"""harvest.py — compile the cant engine's store: curated lexicon + corpus attestations.

The cant MCP (pipeline/cant/server.py; /cant skill is its table veneer) transmutes
English into Sigil's cant. Its vocabulary is curated data (data/lexicon.json); its
EXAMPLES are harvested here, from Mimir's handbook — every admitted `dialog` line
(the voice vector, register and all) plus cant-bearing snippets from entity prose.
Re-run after each book pours and the engine gets richer without touching code:

    py -3.13 pipeline/cant/harvest.py            # build/cant/cant.json

Discipline (the family's law applies):
  - handbook.db is opened READ-ONLY via Mimir's own store lib (importlib seam,
    same as Modron's — the lib is the schema, no raw SQL, no drift).
  - Admitted entities only; quarantine stays quarantined.
  - Every attestation carries provenance: entity id, speaker, page, register.
  - A lexicon term that's too common in plain English carries match: "phrase"
    or "none" — the harvester HONORS that, so attestations stay honest. A false
    attestation is provenance fraud, not free flavor.
  - Tolerates a missing/empty handbook (pre-pour worlds): compiles lexicon-only
    and says so.

Candidates channel: hyphenated compounds seen in dialog but absent from the
lexicon land in `candidates` for human review — promotion into lexicon.json is
a curation act (mirrors curations.json: fix a berk once), never automatic.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
PROJECT_ROOT = HERE.parent.parent
LEXICON_PATH = HERE / "data" / "lexicon.json"
HANDBOOK_DB = PROJECT_ROOT / "build" / "mimir" / "handbook.db"
MIMIR_LIB = PROJECT_ROOT / "pipeline" / "mimir"
OUT_PATH = PROJECT_ROOT / "build" / "cant" / "cant.json"

from cant.gears import Matcher, candidate_compounds, find_terms, normalize, snippet
from cant.gears import _selftest as _gears_selftest

DIALOG_CAP = 8      # attestations kept per term per channel (counts stay exact)
PROSE_CAP = 8
SNIPPET_W = 110     # chars either side of a prose match before trimming


# ---------------------------------------------------------------------------- mimir seam
_MIMIR_STORE_MOD = None


def _mimir_store():
    """Mimir's store lib via importlib — her lib IS the schema (ARCHITECTURE.md);
    no sys.path pollution (her dir holds server.py/gate.py that must not shadow)."""
    global _MIMIR_STORE_MOD
    if _MIMIR_STORE_MOD is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("mimir_store", MIMIR_LIB / "store.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MIMIR_STORE_MOD = mod
    return _MIMIR_STORE_MOD


# ---------------------------------------------------------------------------- harvest
def load_lexicon(path: Path = LEXICON_PATH) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def open_handbook():
    """(store, note). store=None with an honest note when the handbook is absent."""
    if not HANDBOOK_DB.exists():
        return None, f"handbook absent ({HANDBOOK_DB}) — lexicon-only compile"
    try:
        hb = _mimir_store().HandbookStore(HANDBOOK_DB, readonly=True)
        return hb, None
    except Exception as e:                                    # pre-pour / locked worlds
        return None, f"handbook unreadable ({e}) — lexicon-only compile"


def harvest(db_path: Path = HANDBOOK_DB, lexicon_path: Path = LEXICON_PATH) -> dict:
    lex = load_lexicon(lexicon_path)
    entries = lex["terms"]
    matchers = [Matcher(e) for e in entries]
    by_term = {e["term"]: e for e in entries}
    known = {normalize(e["term"]) for e in entries}
    for e in entries:
        known.update(normalize(v) for v in e.get("variants", []))
        known.update(normalize(p) for p in e.get("phrases", []))

    attested: dict[str, dict] = {}
    voice_lines: list[dict] = []
    candidates: dict[str, list[str]] = {}
    npc_names: dict[str, str] = {}
    handbook_note = None
    dialog_count = prose_scanned = 0

    global HANDBOOK_DB
    HANDBOOK_DB = Path(db_path)
    hb, handbook_note = open_handbook()
    if hb is not None:
        try:
            def speaker_name(owner_id):
                if owner_id and owner_id not in npc_names:
                    ent = hb.get(owner_id)
                    npc_names[owner_id] = ent["name"] if ent else owner_id
                return npc_names.get(owner_id)

            # ---- dialog: every admitted line IS an exemplar (the voice vector)
            for d in hb.list("dialog", limit=100000):
                f = d.get("fields", {})
                text = f.get("text") or d.get("name") or ""
                if not text:
                    continue
                dialog_count += 1
                terms = find_terms(matchers, text)
                line = {
                    "text": text,
                    "register": f.get("register", "main"),
                    "speaker": f.get("owner"),
                    "speaker_name": speaker_name(f.get("owner")),
                    "page": f.get("page"),
                    "id": d["id"],
                    "confidence": d.get("confidence"),
                    "terms": terms,
                }
                voice_lines.append(line)
                for t in terms:
                    slot = attested.setdefault(t, {"dialog": [], "prose": [],
                                                   "counts": {"dialog": 0, "prose": 0}})
                    slot["counts"]["dialog"] += 1
                    if len(slot["dialog"]) < DIALOG_CAP:
                        slot["dialog"].append({k: line[k] for k in
                                               ("text", "register", "speaker_name", "page", "id")})
                for comp in candidate_compounds(text, known):
                    candidates.setdefault(comp, []).append(d["id"])

            # ---- prose: cant-bearing snippets from every other admitted dimension
            types = [t for t in hb.coverage().get("admitted", {}) if t != "dialog"]
            for typ in types:
                for ent in hb.list(typ, limit=100000):
                    content = ent.get("content") or ""
                    if len(content) < 40:
                        continue
                    prose_scanned += 1
                    nt = normalize(content)
                    for m in matchers:
                        if not (m.active and m.hit(nt)):
                            continue
                        slot = attested.setdefault(m.term, {"dialog": [], "prose": [],
                                                            "counts": {"dialog": 0, "prose": 0}})
                        slot["counts"]["prose"] += 1
                        if len(slot["prose"]) < PROSE_CAP:
                            rx = next(rx for rx in m.rxs if rx.search(nt))
                            src = (ent.get("provenance", {}).get("value_sources") or [{}])[0].get("src")
                            slot["prose"].append({"snippet": snippet(content, rx),
                                                  "entity": ent["id"], "name": ent.get("name"),
                                                  "loc": src})
        finally:
            hb.close()

    # ---- assemble: lexicon entries + their attestations, in lexicon order
    terms_out = []
    for e in entries:
        row = dict(e)
        if e["term"] in attested:
            row["attested"] = attested[e["term"]]
        terms_out.append(row)

    tier_counts: dict[str, int] = {}
    for e in entries:
        tier_counts[e["tier"]] = tier_counts.get(e["tier"], 0) + 1

    return {
        "_meta": {
            "built": date.today().isoformat(),
            "builder": "pipeline/cant/harvest.py",
            "lexicon": str(lexicon_path.relative_to(PROJECT_ROOT)),
            "handbook": None if hb is None else str(Path(db_path)),
            "handbook_note": handbook_note,
            "dialog_lines": dialog_count,
            "prose_entities_scanned": prose_scanned,
            "terms": tier_counts | {"total": len(entries)},
            "terms_attested": len(attested),
            "sources": lex["_meta"]["sources"],
            "tiers": lex["_meta"]["tiers"],
            "refresh": "re-run after each book pours: py -3.13 pipeline/cant/harvest.py",
        },
        "terms": terms_out,
        "voice_lines": voice_lines,
        "candidates": [{"compound": c, "seen_in": ids} for c, ids in sorted(candidates.items())],
    }


# ---------------------------------------------------------------------------- vectors (semantic lane)
def embed_lexicon(compiled: dict, lexicon_path: Path, out_dir: Path, quiet: bool) -> str:
    """Encode every lexicon def → build/cant/vectors.npz (CANT.md D9).

    The sidecar carries the lexicon's file sha: the engine refuses vectors
    that no longer match the lexicon they were cut from (a stale ranking is
    a silent lie). Lane unavailable ⇒ honest skip, the compile still stands."""
    from cant import embed as embed_mod
    emb, why = embed_mod.boot()
    if emb is None:
        return f"vectors: SKIPPED ({why})"
    import numpy as np
    from datetime import date as _date
    terms = [e["term"] for e in compiled["terms"]]
    texts = [f"{e['term']}: {e['def']}" for e in compiled["terms"]]
    vecs = emb.encode(texts)
    meta = {
        "model_id": embed_mod.MODEL_ID,
        "model_sha": emb.model_sha,
        "dim": int(vecs.shape[1]),
        "lexicon_sha": embed_mod.file_sha256(Path(lexicon_path)),
        "built": _date.today().isoformat(),
        "pooling": "masked-mean, L2-normalized",
    }
    out = out_dir / "vectors.npz"
    np.savez_compressed(out, vectors=vecs, terms=np.array(terms, dtype=object),
                        meta=np.array(json.dumps(meta)))
    return f"vectors: {vecs.shape[0]}×{vecs.shape[1]} → {out} (model {emb.model_sha[:12]}…)"


# ---------------------------------------------------------------------------- self-test
def _selftest():
    _gears_selftest()                       # matcher law lives in cant/gears.py — one source


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compile build/cant/cant.json from lexicon + handbook")
    ap.add_argument("--db", type=Path, default=HANDBOOK_DB, help="handbook.db path")
    ap.add_argument("--lexicon", type=Path, default=LEXICON_PATH)
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    ap.add_argument("--no-embed", action="store_true",
                    help="skip the vector sidecar (semantic lane data)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    _selftest()                                               # the gears prove sound at every pour

    compiled = harvest(db_path=args.db, lexicon_path=args.lexicon)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(compiled, f, ensure_ascii=False, indent=1)

    vec_note = "vectors: skipped (--no-embed)"
    if not args.no_embed:
        vec_note = embed_lexicon(compiled, args.lexicon, args.out.parent, args.quiet)

    if not args.quiet:
        m = compiled["_meta"]
        print(f"cant.json compiled → {args.out}")
        print(f"  lexicon: {m['terms']['total']} terms "
              f"({m['terms'].get('core', 0)} core / {m['terms'].get('ext', 0)} ext)")
        if m["handbook"]:
            print(f"  handbook: {m['dialog_lines']} dialog lines, "
                  f"{m['prose_entities_scanned']} prose entities scanned")
            print(f"  attested: {m['terms_attested']} terms carry corpus witnesses")
            print(f"  candidates: {len(compiled['candidates'])} unknown compounds for review")
        else:
            print(f"  handbook: {m['handbook_note']}")
        print(f"  {vec_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
