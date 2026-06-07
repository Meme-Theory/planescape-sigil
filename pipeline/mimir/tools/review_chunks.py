#!/usr/bin/env python
"""review_chunks.py — work-list dumper for the Great Audit (Phase 0).

Reads handbook.db READONLY + the reflow dirs; writes:
  build/mimir/review/chunks/chunk-NNN.json   (~20-22 entities each, by (dim, book))
  build/mimir/review/quarantine.json          (all held rows, by bucket, full envelopes)
  build/mimir/review/manifest.json            (chunk index + the exactly-once assert)

Every entity record carries `reflow_files` RESOLVED to actual on-disk paths — review
agents never do offset math. Conventions (verified empirically, see PLAN.md executor
corrections):
  uncaged / manifesto       printed page == reflow file number (as-is)
  in-the-cage via cage.py   printed page -> reflow file number + 2
  in-the-cage saying sweep  already file numbers (as-is)
  box components            scan page == reflow file number (as-is)

Run: py -3.13 pipeline/mimir/tools/review_chunks.py
"""
from __future__ import annotations
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))                    # pipeline/mimir
sys.path.insert(0, str(HERE.parents[2] / "parse"))          # pipeline/parse
import store as S                                           # noqa: E402
import planes as P                                          # noqa: E402
import boxset as B                                          # noqa: E402
import monstrous as MC                                      # noqa: E402
import cage as C                                            # noqa: E402

ROOT = S.ROOT
REVIEW = ROOT / "build/mimir/review"
CHUNKS = REVIEW / "chunks"
CHUNK_SIZE = 22

BOOK_REFLOW = {
    "uncaged":    ROOT / "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/reflow",
    "manifesto":  ROOT / "build/the-factol-s-manifesto/planescape-2611-the-factols-manifesto/reflow",
    "in-the-cage": ROOT / "build/in-the-cage-a-guide-to-sigil/ddps-inthecage/reflow",
    "hellbound":  ROOT / "build/hellbound-the-blood-war/ddps-hellboundbloodwar-ii/reflow",
    # 2620 + 2634 (audit round 2026-06-06): their pour lanes store `pages` fields as
    # REFLOW FILE numbers already (anchor-window law) — resolution is as-is, no offsets.
    "the-planewalker-s-handbook":
        ROOT / "build/the-planewalker-s-handbook/planescape-2620-the-planewalkers-handbook/reflow",
    "the-inner-planes":
        ROOT / "build/the-inner-planes/planescape-2634-inner-planes/reflow",
}
PWH = "the-planewalker-s-handbook"
INNER = "the-inner-planes"
CAGE_OFFSET = 2                                             # printed -> reflow file

MISSES: list[str] = []                                      # any unresolvable page file = dumper bug


def _file(dirpath: Path, n) -> str | None:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return None
    p = dirpath / f"page-{n:04d}.txt"
    if p.exists():
        return p.as_posix()
    MISSES.append(p.as_posix())
    return None


def _files(dirpath: Path, pages, offset=0) -> list[str]:
    out = []
    for n in pages or []:
        f = _file(dirpath, (int(n) + offset) if isinstance(n, (int, float)) else n)
        if f:
            out.append(f)
    return out


def _comp_dir(comp: str) -> Path:
    return ROOT / "build" / comp / "reflow"


def _loc_pages(loc: str) -> list[int]:
    """'p12' -> [12] · 'pp9-11' -> [9,10,11] · 'p5-6 ...' -> [5,6]"""
    m = re.search(r"pp?(\d+)\s*-\s*(\d+)", loc or "")
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return list(range(a, min(b, a + 5) + 1))            # cap runaway spans
    m = re.search(r"p(\d+)", loc or "")
    return [int(m.group(1))] if m else []


# ---- static maps from the parse modules -----------------------------------------
def build_maps():
    maps = {}
    maps["plane_comp"] = {c["id"]: c["component"] for c in P.PLANE_CARDS}
    layer_comp = {}
    gt_comp = {}
    for c in P.PLANE_CARDS:
        for (nm, _ord, _al, override) in c["layers"]:
            layer_comp[override or f"layer:{S.slug(nm)}"] = c["component"]
        if c.get("gate_town"):
            gt_comp[f"gate-town:{S.slug(c['gate_town'])}"] = c["component"]
    maps["layer_comp"] = layer_comp
    maps["gt_comp"] = gt_comp
    maps["realm_comp"] = {f"realm:{S.slug(card[0])}": card[4] for card in P.REALM_CARDS}
    maps["sect_comp"] = {f"sect:{S.slug(card[0])}": card[1] for card in B.SECT_CARDS}
    maps["settlement_comp"] = {f"settlement:{S.slug(card[0])}": card[3] for card in B.SETTLEMENT_CARDS}
    sweep_by_book = defaultdict(list)
    for comp in B.SWEEP_COMPONENTS:
        sweep_by_book[B.BOOK_OF[comp]].append(comp)
    maps["sweep_by_book"] = dict(sweep_by_book)
    maps["saying_comps"] = {**dict(sweep_by_book), "in-the-cage": [B.CAGE]}
    maps["adv_comps"] = {
        "planes-of-law": [B.LAW + x for x in ("ii", "iii", "iv", "v", "vi")],
        "planes-of-conflict": [B.ADV4],
        "planes-of-chaos": [B.CHAOS],
    }
    maps["mc_by_dir"] = {comp.split("/")[-1]: comp for comp in MC.MC_COMPONENTS}
    maps["mc_by_book"] = defaultdict(list)
    for comp, book in MC.MC_BOOK.items():
        maps["mc_by_book"][book].append(comp)
    # uncaged npc printed pages, from the build JSONs (slug(name) -> pages)
    npc_pages = {}
    npcdir = ROOT / "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/npc"
    for pth in sorted(npcdir.glob("*.json")):
        if pth.name == "graph.json":
            continue
        node = json.loads(pth.read_text(encoding="utf-8"))
        if node.get("name"):
            npc_pages[f"npc:uncaged:{S.slug(node['name'])}"] = node.get("pages") or []
    maps["npc_pages"] = npc_pages
    return maps


# ---- per-entity reflow resolution ------------------------------------------------
STRUCTURAL_SRCS = ("setting", "npc-descriptor-aggregation", "catalog", "uncaged:p130",
                   "manifesto:fated", "uncaged:passim", "ddps-inthecage", "hellbound")


def resolve(ent: dict, edges_in: list, maps: dict) -> tuple[list[str], str]:
    """-> (reflow_files, page_convention). Empty + 'structural' when no page witness
    exists by design (internal-consistency review only)."""
    t, eid = ent["type"], ent["id"]
    f = ent.get("fields") or {}
    srcs = ((ent.get("provenance") or {}).get("value_sources")) or []
    src0 = str(srcs[0].get("src", "")) if srcs else ""
    files: list[str] = []
    conv = "structural"

    def add(d, pages, off=0):
        nonlocal files
        files += _files(d, pages, off)

    if t == "npc":
        if eid in maps["npc_pages"]:
            add(BOOK_REFLOW["uncaged"], maps["npc_pages"][eid])
            conv = "printed"
        # factol seeds: no pages -> structural
    elif t == "dialog":
        owner = f.get("owner")
        pages = maps["npc_pages"].get(owner) or ([f["page"]] if f.get("page") else [])
        add(BOOK_REFLOW["uncaged"], pages)
        conv = "printed"
    elif t == "item":
        for e in edges_in:                                   # wielder's entry pages
            if e["rel"] == "wields":
                add(BOOK_REFLOW["uncaged"], maps["npc_pages"].get(e["other"], []))
        conv = "printed" if files else "structural"
        if any(s.get("src") == PWH for s in srcs):           # PWH equipment card (file nums)
            had = bool(files)
            add(BOOK_REFLOW[PWH], f.get("pages") or [])
            conv = "mixed" if had else "scan"
    elif t == "fiction":
        for s in srcs:
            add(BOOK_REFLOW["uncaged"], _loc_pages(str(s.get("src", ""))))
        conv = "printed"
    elif t == "hook":
        book = f.get("book") or ("uncaged" if "uncaged" in src0 else None)
        pages = f.get("pages") or []
        if not pages:                                        # curated plots: src 'uncaged:p125-126 plots'
            for s in srcs:
                pages += _loc_pages(str(s.get("src", "")))
            book = book or "uncaged"
        if book == "in-the-cage":
            add(BOOK_REFLOW["in-the-cage"], pages, CAGE_OFFSET)
            conv = "printed+2"
        elif book in ("uncaged", "manifesto"):
            add(BOOK_REFLOW[book], pages)
            conv = "printed"
    elif t == "organization":
        add(BOOK_REFLOW["uncaged"], [125, 126])             # back-matter plot statements
        conv = "printed"
    elif t == "faction":
        if any("factols-manifesto" == s.get("src") for s in srcs):
            add(BOOK_REFLOW["manifesto"], [5, 6])           # Factions at a Glance
            conv = "printed"
    elif t == "location":
        if f.get("cage_page"):
            add(BOOK_REFLOW["in-the-cage"], [f["cage_page"]], CAGE_OFFSET)
            conv = "printed+2"
        elif src0 == "in-the-cage":
            for s in srcs:
                if s.get("src") == "in-the-cage":
                    add(BOOK_REFLOW["in-the-cage"], _loc_pages(str(s.get("loc", ""))), CAGE_OFFSET)
            conv = "printed+2"
        if any(s.get("src") == "uncaged:locations-by-ward" for s in srcs):
            add(BOOK_REFLOW["uncaged"], [130])              # the index witness
            conv = conv if files and conv != "structural" else "printed"
        if any(s.get("src") == "factols-manifesto" for s in srcs) and not files:
            add(BOOK_REFLOW["manifesto"], [5, 6])
            conv = "printed"
        if any(s.get("src") == INNER for s in srcs):         # 2634 site card (file nums)
            add(BOOK_REFLOW[INNER], f.get("pages") or [])
            conv = "scan"
    elif t == "portal":
        add(BOOK_REFLOW["in-the-cage"], f.get("pages") or [], CAGE_OFFSET)
        conv = "printed+2"
    elif t == "plane":
        for s in srcs:                                       # cage gazetteer attestation
            if s.get("src") == "in-the-cage":
                add(BOOK_REFLOW["in-the-cage"], _loc_pages(str(s.get("loc", ""))), CAGE_OFFSET)
                conv = "printed+2"
        for e in edges_in:                                   # children layers' first box pages
            if e["rel"] == "layer_of" and e.get("other_fields"):
                lf = e["other_fields"]
                comp = maps["layer_comp"].get(e["other"])
                if comp and lf.get("pages"):
                    add(_comp_dir(comp), lf["pages"][:1])
                    conv = "mixed" if conv == "printed+2" else "scan"
        if any(s.get("src") == INNER for s in srcs):         # 2634 card + creature-index witness
            had = bool(files)
            add(BOOK_REFLOW[INNER], f.get("pages") or [])
            add(BOOK_REFLOW[INNER], f.get("inhabitants_pages") or [])
            conv = "mixed" if had else "scan"
    elif t == "layer":
        comp = maps["layer_comp"].get(eid)
        if comp and any(s.get("src", "").startswith("planes-of") for s in srcs):
            add(_comp_dir(comp), f.get("pages") or [])
            conv = "scan"
        elif src0 == "in-the-cage":
            add(BOOK_REFLOW["in-the-cage"], f.get("pages") or [], CAGE_OFFSET)
            conv = "printed+2"
    elif t == "realm":
        if any(s.get("src") == INNER for s in srcs):         # 2634 double-witness pages
            add(BOOK_REFLOW[INNER], (f.get("realm_pages") or []) + (f.get("power_pages") or []))
            conv = "scan"
        comp = maps["realm_comp"].get(eid)
        if comp:
            add(_comp_dir(comp), f.get("pages") or [])
            conv = "scan"
        elif not files and src0 == "in-the-cage":
            add(BOOK_REFLOW["in-the-cage"], f.get("pages") or [], CAGE_OFFSET)
            conv = "printed+2"
    elif t == "deity":
        for s in srcs:
            ss, loc = str(s.get("src", "")), str(s.get("loc", ""))
            if ss.startswith("uncaged"):
                add(BOOK_REFLOW["uncaged"], _loc_pages(ss))
                conv = "printed"
            elif ss.startswith("manifesto"):
                add(BOOK_REFLOW["manifesto"], _loc_pages(ss))
                conv = "printed"
            elif ss.startswith("planes-of"):
                pages = _loc_pages(loc)
                comps = []
                for rid in (f.get("realms") or []):          # realm-card power: the realm's comp
                    if maps["realm_comp"].get(rid):
                        comps.append(maps["realm_comp"][rid])
                if not comps:                                # proxy-sweep power: candidates
                    comps = maps["sweep_by_book"].get(ss, [])
                for comp in comps:
                    add(_comp_dir(comp), pages)
                conv = "scan"
            elif ss == INNER:                                # 2634 power stub (loc = witness page)
                add(BOOK_REFLOW[INNER], _loc_pages(loc) or f.get("pages") or [])
                conv = "scan"
    elif t == "event":
        for s in srcs:
            ss = str(s.get("src", ""))
            if ss == "hellbound":
                add(BOOK_REFLOW["hellbound"], f.get("pages") or [])
                conv = "scan"
            elif ss.startswith("manifesto:p"):
                add(BOOK_REFLOW["manifesto"], _loc_pages(ss))
                conv = "printed"
            elif ss.startswith("uncaged:p"):
                add(BOOK_REFLOW["uncaged"], _loc_pages(ss))
                conv = "printed"
    elif t == "gate-town":
        if src0 == "in-the-cage":
            add(BOOK_REFLOW["in-the-cage"], f.get("pages") or [], CAGE_OFFSET)
            conv = "printed+2"
        else:
            comp = maps["gt_comp"].get(eid)
            if comp:
                add(_comp_dir(comp), f.get("pages") or [])
                conv = "scan"
    elif t in ("settlement", "sect"):
        comp = maps[f"{t}_comp"].get(eid)
        if comp:
            add(_comp_dir(comp), f.get("pages") or [])
            conv = "scan"
    elif t == "saying":
        book = eid.split(":")[1]
        for comp in maps["saying_comps"].get(book, []):
            add(_comp_dir(comp), [f.get("page")])
            conv = "scan"
    elif t == "adventure":
        book = eid.split(":")[1]
        for comp in maps["adv_comps"].get(book, []):
            add(_comp_dir(comp), [f.get("page")])
        conv = "scan"
    elif t == "proxy":
        book = src0
        for comp in maps["sweep_by_book"].get(book, []):
            add(_comp_dir(comp), [f.get("page")])
        if src0 == INNER:                                    # 2634 proxy (pages list, file nums)
            add(BOOK_REFLOW[INNER], f.get("pages") or [])
        conv = "scan"
    elif t in ("race", "class", "spell"):                    # PWH dims: pages = file nums
        if any(s.get("src") == PWH for s in srcs):
            add(BOOK_REFLOW[PWH], f.get("pages") or [])
            for v in (f.get("variants") or []):              # genasi's four attest individually
                add(BOOK_REFLOW[PWH], v.get("pages") or [])
            conv = "scan"
    elif t == "creature":
        comp = maps["mc_by_dir"].get(f.get("mc_component", ""))
        if comp:
            add(_comp_dir(comp), [f.get("page")])
            conv = "scan"
    elif t in ("cosmology", "pathway"):
        add(BOOK_REFLOW["in-the-cage"], f.get("pages") or [], CAGE_OFFSET)
        conv = "printed+2"
    # source / sigil: structural

    # de-dup, keep order
    seen, out = set(), []
    for x in files:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out, (conv if out else "structural")


def primary_book(ent: dict, scope: tuple = ()) -> str:
    """Scoped runs label by the scoped book FIRST (a merged plane audits under 2634,
    not its older cage label); unscoped keeps the great-audit ordering, new books last."""
    srcs = ((ent.get("provenance") or {}).get("value_sources")) or []
    src0 = str(srcs[0].get("src", "")) if srcs else ""
    eid = ent["id"]
    for marker in (*scope,
                   "planes-of-law", "planes-of-chaos", "planes-of-conflict", "hellbound",
                   "in-the-cage", "factols-manifesto", "manifesto", "uncaged", PWH, INNER):
        if any(marker in str(s.get("src", "")) or marker in str(s.get("loc", ""))
               for s in srcs):
            return marker.replace("factols-manifesto", "manifesto")
    if ent["type"] in ("saying", "adventure") and ":" in eid:
        return eid.split(":")[1]
    if src0:
        return "structural"
    return "unknown"


# ---- quarantine resolution -------------------------------------------------------
def quarantine_reflow(row_type: str, env: dict, reason: str, maps: dict) -> list[str]:
    f = env.get("fields") or {}
    if reason.startswith("pwh-spell"):                      # 2620 buckets: pages = file nums
        return _files(BOOK_REFLOW[PWH], f.get("pages") or [])
    if reason == "cage-head-lost":                          # pages hide in the why text
        pages = [int(m) for m in re.findall(r"pg(\d+)", env.get("content") or "")]
        return _files(BOOK_REFLOW["in-the-cage"], pages, CAGE_OFFSET)
    if reason == "low-confidence-dialog":
        pages = maps["npc_pages"].get(f.get("owner"), []) or ([f["page"]] if f.get("page") else [])
        return _files(BOOK_REFLOW["uncaged"], pages)
    if reason == "low-confidence-hook":
        book = f.get("book")
        if book == "in-the-cage":
            return _files(BOOK_REFLOW["in-the-cage"], f.get("pages") or [], CAGE_OFFSET)
        if book in ("uncaged", "manifesto"):
            return _files(BOOK_REFLOW[book], f.get("pages") or [])
        return []
    if reason in ("portal-rejected", "portal-review"):
        return _files(BOOK_REFLOW["in-the-cage"], [f.get("page")], CAGE_OFFSET)
    if reason == "mc-parse":
        srcs = ((env.get("provenance") or {}).get("value_sources")) or []
        book = str(srcs[0].get("src", "")) if srcs else ""
        out = []
        for comp in maps["mc_by_book"].get(book, []):
            out += _files(_comp_dir(comp), [f.get("page")])
        return out
    if reason == "realm-unattested":
        comp = maps["realm_comp"].get(f"realm:{S.slug(env.get('name') or '')}")
        if comp:                                            # no attested pages — give the comp's span
            d = _comp_dir(comp)
            return [p.as_posix() for p in sorted(d.glob("page-*.txt"))[:0]]  # none; court reads on demand
    return []


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Great-Audit chunk dumper (optionally book-scoped)")
    ap.add_argument("--books", default="", help="csv of provenance src names to scope the dump to")
    ap.add_argument("--out", default="", help="subdir under build/mimir/review (REQUIRED with --books)")
    args = ap.parse_args(argv)
    scope = tuple(b.strip() for b in args.books.split(",") if b.strip())
    if scope and not args.out:
        print("--books requires --out — scoped runs never clobber the great-audit chunks")
        return 2
    review = (REVIEW / args.out) if args.out else REVIEW
    chunks_dir = review / "chunks"

    store = S.HandbookStore(S.DEFAULT_DB, readonly=True)
    maps = build_maps()
    conn = store.conn

    fields_of = {}
    ents = []
    for r in conn.execute("SELECT * FROM entities"):
        e = store._row_to_entity(r)
        fields_of[e["id"]] = e.get("fields") or {}
        ents.append(e)

    def cites_scope(env: dict) -> bool:
        ss = ((env.get("provenance") or {}).get("value_sources")) or []
        return any(str(s.get("src", "")) in scope for s in ss)

    if scope:                                                # merged nodes ride in: any src hit
        ents = [e for e in ents if cites_scope(e)]

    edges_out = defaultdict(list)
    edges_in = defaultdict(list)
    for g in conn.execute("SELECT rel, src_id, tgt_id, role FROM edges"):
        edges_out[g["src_id"]].append({"rel": g["rel"], "other": g["tgt_id"], "role": g["role"]})
        edges_in[g["tgt_id"]].append({"rel": g["rel"], "other": g["src_id"], "role": g["role"]})

    # group by (dim, book) then split
    groups = defaultdict(list)
    for e in ents:
        groups[(e["type"], primary_book(e, scope))].append(e)

    chunks_dir.mkdir(parents=True, exist_ok=True)
    for old in chunks_dir.glob("chunk-*.json"):
        old.unlink()

    # Pack (dim, book) groups into ~CHUNK_SIZE batches. Small same-book groups SHARE a
    # chunk (sorted by book first so one agent stays inside one book's reflow); large
    # groups split. ~824/22 -> ~38 chunks, the plan's agent budget.
    batches: list[tuple[str, str, list]] = []               # (dim-label, book, members)
    cur: list = []
    cur_books: set[str] = set()
    cur_dims: set[str] = set()

    def flush():
        nonlocal cur, cur_books, cur_dims
        if cur:
            batches.append(("+".join(sorted(cur_dims)), "+".join(sorted(cur_books)), cur))
            cur, cur_books, cur_dims = [], set(), set()

    for (dim, book), members in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        members.sort(key=lambda e: e["id"])
        for i in range(0, len(members), CHUNK_SIZE):
            part = members[i:i + CHUNK_SIZE]
            if len(part) >= CHUNK_SIZE - 4:                  # big slice -> its own chunk
                flush()
                batches.append((dim, book, part))
                continue
            if cur and (len(cur) + len(part) > CHUNK_SIZE or book not in cur_books):
                flush()
            cur += part
            cur_books.add(book)
            cur_dims.add(dim)
    flush()

    manifest = {"chunks": [], "total_entities": 0, "misses": 0, "scope": list(scope)}
    seen_ids = set()
    cn = 0
    for dim, book, batch in batches:
        cn += 1
        if True:
            recs = []
            for e in batch:
                ein = edges_in[e["id"]]
                # planes need their layers' fields for box-page resolution
                if e["type"] == "plane":
                    ein = [dict(x, other_fields=fields_of.get(x["other"])) if x["rel"] == "layer_of"
                           else x for x in ein]
                files, conv = resolve(e, ein, maps)
                recs.append({
                    "id": e["id"], "name": e["name"], "type": e["type"],
                    "edition": e.get("edition"), "fields": e.get("fields"),
                    "provenance": e.get("provenance"), "confidence": e.get("confidence"),
                    "curated": e.get("curated") or None,
                    "edges_out": edges_out[e["id"]],
                    "edges_in": [{k: v for k, v in x.items() if k != "other_fields"} for x in ein],
                    "reflow_files": files, "page_convention": conv,
                })
                assert e["id"] not in seen_ids, f"duplicate dump: {e['id']}"
                seen_ids.add(e["id"])
            out = chunks_dir / f"chunk-{cn:03d}.json"
            out.write_text(json.dumps({"chunk": cn, "dim": dim, "book": book,
                                       "entities": recs}, indent=1, ensure_ascii=False),
                           encoding="utf-8")
            manifest["chunks"].append({"file": out.as_posix(), "dim": dim, "book": book,
                                       "n": len(recs),
                                       "ids": [r["id"] for r in recs]})
    manifest["total_entities"] = len(seen_ids)

    # quarantine, by bucket
    buckets = defaultdict(list)
    for r in conn.execute("SELECT id, type, name, entity, reason, docket, held_at FROM quarantine"):
        env = json.loads(r["entity"]) if r["entity"] else {}
        if scope and not cites_scope(env):
            continue
        docket = json.loads(r["docket"]) if r["docket"] else {}
        buckets[r["reason"]].append({
            "id": r["id"], "type": r["type"], "name": r["name"], "reason": r["reason"],
            "held_at": r["held_at"], "envelope": env, "docket": docket,
            "reflow_files": quarantine_reflow(r["type"], env, r["reason"], maps),
        })
    qtotal = sum(len(v) for v in buckets.values())
    (review / "quarantine.json").write_text(
        json.dumps({"total": qtotal, "buckets": {k: sorted(v, key=lambda x: x["id"])
                                                 for k, v in sorted(buckets.items())}},
                   indent=1, ensure_ascii=False), encoding="utf-8")
    for k, v in buckets.items():                            # one file per court bucket
        (review / f"quarantine-{k}.json").write_text(
            json.dumps({"bucket": k, "n": len(v), "items": sorted(v, key=lambda x: x["id"])},
                       indent=1, ensure_ascii=False), encoding="utf-8")

    n_ent = conn.execute("SELECT COUNT(*) c FROM entities").fetchone()["c"]
    store.close()

    manifest["misses"] = len(MISSES)
    manifest["miss_paths"] = sorted(set(MISSES))
    (review / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False),
                                          encoding="utf-8")

    n_struct = 0
    for c in manifest["chunks"]:
        data = json.loads(Path(c["file"]).read_text(encoding="utf-8"))
        n_struct += sum(1 for r in data["entities"] if r["page_convention"] == "structural")
    print(f"chunks: {cn} files · {len(seen_ids)} entities (store has {n_ent}) · "
          f"{n_struct} structural · quarantine {qtotal} in {len(buckets)} buckets · "
          f"page-misses {len(MISSES)}")
    if scope:
        from collections import Counter
        dims = Counter(e["type"] for e in ents)
        print("scoped dims: " + " · ".join(f"{k} {v}" for k, v in sorted(dims.items())))
        assert len(seen_ids) == len(ents), \
            f"coverage hole: dumped {len(seen_ids)} != scoped population {len(ents)}"
    else:
        assert len(seen_ids) == n_ent, f"coverage hole: dumped {len(seen_ids)} != store {n_ent}"
    if MISSES:
        print("MISSING PAGE FILES (dumper bug or convention error):")
        for mp in sorted(set(MISSES)):
            print("  ", mp)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
