#!/usr/bin/env python
"""book — document-level NPC extraction (psx v2 reference implementation, Uncaged).

Whole book -> ordered line stream (page-stamped) -> region FSM -> split into
entries at >=20pt titles -> assemble each entry that contains a statblock into a
validated NPC node -> emit per-NPC JSON + a cross-reference plot graph + an md
projection. Prints a validation report: the typed model is only worth anything if
we can say how trustworthy it is, so we measure and show it.
"""
import json, re, sys, pathlib, difflib
import fitz
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import regions as R
import normalize as N

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"
ENTRY_TITLE_MIN = 20.0     # entry titles 20-27pt; "Quick Chant" sidebars sit at 18.2


def clean_title(s):
    # decorative-font OCR is hopeless ("fiS+AVAN"); keep raw, just tidy whitespace
    return re.sub(r"\s{2,}", " ", s).strip()


def load_stream(doc):
    lines = []
    for i in range(len(doc)):
        flat, _ = R.ordered_content_lines(doc[i])
        for l in flat:
            l["page"] = i + 1
        lines.extend(flat)
    return lines


def split_entries(regs):
    """Group regions into entries at >=20pt titles (>=3 alpha chars, so decorative
    drop-caps like '1,1'/'K' don't split). Consecutive title lines merge."""
    entries, cur = [], None
    for r in regs:
        is_title = (r["type"] == "heading" and r.get("size", 0) >= ENTRY_TITLE_MIN
                    and len(re.sub(r"[^A-Za-z]", "", r["lines"][0]["text"])) >= 3)
        if is_title:
            if cur and all(x["type"] == "heading" for x in cur["regions"]):
                cur["title"] = (cur["title"] + " " + clean_title(r["lines"][0]["text"])).strip()
                cur["regions"].append(r)
            else:
                if cur: entries.append(cur)
                cur = {"title": clean_title(r["lines"][0]["text"]), "regions": [r],
                       "page0": r["lines"][0]["page"]}
        elif cur is not None:
            cur["regions"].append(r)
        else:
            cur = {"title": None, "regions": [r], "page0": r["lines"][0]["page"]}
    if cur: entries.append(cur)
    return entries


def assemble_npc(entry, max_page):
    statblocks = [r for r in entry["regions"] if r["type"] == "statblock"]
    if not statblocks:
        return None
    parsed = [R.parse_statblock(sb) for sb in statblocks]
    # primary = the entry's SUBJECT = the first LAWFUL statblock (non-decoy + dice damage); the
    # gate's own L3 lawfulness, reused to pick the subject. Skips prose decoys (Shemeshka), keeps a
    # full block whose name OCR-failed (Tripicus), never crowns a clean-named companion over a
    # battered subject. With roster bounds each entry holds only ITS OWN cast (see _pick_primary).
    primary = _pick_primary(parsed)
    fields, val, conf = parsed[primary]
    sections = {}
    for r in entry["regions"]:
        if r["type"] == "section":
            txt = " ".join(l["text"] for l in r["lines"])
            txt = re.sub(rf"^{re.escape(r['lines'][0]['text'].split(':')[0])}:\s*", "", txt)
            sections[r["label"]] = txt.strip()
    see_also = []
    for r in entry["regions"]:
        if r["type"] == "section" and r["label"] == "SEE ALSO":
            see_also = R.parse_see_also(r["lines"], max_page)
    body = " ".join(l["text"] for r in entry["regions"] if r["type"] == "body"
                    for l in r["lines"])
    pages = sorted({l["page"] for r in entry["regions"] for l in r["lines"]})
    name = fields.get("name") or clean_title(entry["title"] or "?")
    node = {
        "type": "npc", "name": name, "title_ocr": entry["title"],
        "pages": [pages[0], pages[-1]] if pages else None,
        "descriptor": fields.get("descriptor"),
        "statblock": {k: v for k, v in fields.items() if k != "descriptor"},
        "companions": [{"name": (parsed[k][0].get("name") if N.is_name(parsed[k][0].get("name") or "")
                                  else (parsed[k][0].get("descriptor") or {}).get("race")),
                        "descriptor": parsed[k][0].get("descriptor"),
                        "statblock": {kk: vv for kk, vv in parsed[k][0].items() if kk != "descriptor"}}
                       for k in range(len(parsed))
                       if k != primary and parsed[k][1]["fields_found"] >= 5],   # real creatures only, not prose
        "sections": sections, "see_also": see_also,
        "body": body, "body_chars": len(body),
        "confidence": conf, "validation": val,
    }
    return node


def npc_markdown(n):
    d = n.get("descriptor") or {}
    sb = n["statblock"]
    mv = sb.get("mv")
    mv_s = ", ".join(f"{m['mode']} {m['rate']}" + (f" ({m['maneuverability']})" if m.get('maneuverability') else "")
                     for m in mv) if isinstance(mv, list) else mv
    lines = [f"## {n['name']}",
             f"*{d.get('race') or '?'}* · {d.get('char_class') or ('HD '+str(sb.get('descriptor',{}) or '')) or ''}"
             f" · {d.get('faction') or 'no faction'} · {d.get('alignment') or '?'}"
             f"  <!-- pp.{n['pages'][0]}–{n['pages'][1]} conf {n['confidence']} -->",
             "", "**Statblock** — "
             + " · ".join(filter(None, [
                 f"AC {sb.get('ac')}" if sb.get('ac') else None,
                 f"MV {mv_s}" if mv_s else None, f"hp {sb.get('hp')}" if sb.get('hp') else None,
                 f"THAC0 {sb.get('thac0')}" if sb.get('thac0') else None,
                 f"#AT {sb.get('num_attacks')}" if sb.get('num_attacks') else None,
                 f"Dmg {sb.get('damage')}" if sb.get('damage') else None,
                 f"XP {sb.get('xp')}" if sb.get('xp') else None]))]
    for lab in ("PERSONALITY","LOCATION","ROLE-PLAYING","COMBAT"):
        if lab in n["sections"]:
            lines += ["", f"**{lab.title()}.** {n['sections'][lab]}"]
    if n["see_also"]:
        lines += ["", "**See also:** " + ", ".join(f"[{r['name']}](#{r['name'].lower().replace(' ','-')})"
                                                    + ("" if r["resolves"] else " ⚠️") for r in n["see_also"])]
    return "\n".join(lines)


# --- roster-driven splitting: the book's OWN contents page is the authoritative entry list ----
# Font-size title detection found 29 of 41 entries — the other 12 (Fell, Koe, Rule-of-Three,
# Will of the One …) wear decorative display-font titles that never tripped the ≥20pt split, so
# their statblocks got absorbed as companions of the entry before them. The contents page lists
# all 41 with CLEAN page anchors; we split on those instead. Names are decoded downstream.
def parse_roster(doc, pages=(3, 4)):
    """Contents page → ordered [(printed_page, raw_name)] for every entry (Uncaged: 41)."""
    txt = "\n".join(doc[p - 1].get_text() for p in pages)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]
    out = {}
    for i in range(len(lines) - 1):
        nm, nxt = lines[i], lines[i + 1]
        if re.fullmatch(r"\d{1,3}", nxt) and 8 <= int(nxt) <= 120 \
                and len(re.sub(r"[^A-Za-z]", "", nm)) >= 2 and not re.fullmatch(r"\d+", nm):
            out.setdefault(int(nxt), nm)                  # first name seen per page
    return sorted(out.items())


def _pick_primary(parsed):
    """Index of the entry's SUBJECT statblock: the first LAWFUL block (non-decoy + dice damage),
    else the fullest. Factored so the offset calibrator and the assembler pick identically."""
    if not parsed:
        return None
    DECOY = 5
    def lawful(p):
        if p[1]["fields_found"] < DECOY:
            return False
        dmg = p[0].get("damage")
        return (not dmg) or bool(re.match(r"^\s*\d*d\d", str(dmg)))
    return next((k for k in range(len(parsed)) if lawful(parsed[k])),
                max(range(len(parsed)), key=lambda k: parsed[k][1]["fields_found"]))


def _bucket(regs, start, end):
    return [r for r in regs if start <= r["lines"][0]["page"] < end]


def calibrate_offset(roster, regs, lo=0, hi=4):
    """Printed page numbers ≠ PDF sequence (cover + front matter + full-page art shift, and drift).
    Pick the offset whose buckets best self-name to the roster — the entries that DO self-name pin
    the boundary for the ~12 whose statblock name-line is unparseable."""
    import difflib
    cl = lambda s: re.sub(r"[^a-z]", "", (s or "").lower())
    def score(off):
        n = 0
        for i, (pg, nm) in enumerate(roster):
            end = (roster[i + 1][0] + off) if i + 1 < len(roster) else 10 ** 6
            parsed = [R.parse_statblock(s) for s in _bucket(regs, pg + off, end) if s["type"] == "statblock"]
            k = _pick_primary(parsed)
            if k is not None and difflib.SequenceMatcher(None, cl(parsed[k][0].get("name")), cl(nm)).ratio() >= 0.6:
                n += 1
        return n
    return max(range(lo, hi + 1), key=score)


def split_by_roster(regs, roster, offset, max_page):
    """Bound each roster entry by [printed_page+offset, next+offset); assign regions by page."""
    entries = []
    for i, (pg, raw) in enumerate(roster):
        start = pg + offset
        end = (roster[i + 1][0] + offset) if i + 1 < len(roster) else max_page + 1
        rs = _bucket(regs, start, end)
        if rs:
            entries.append({"title": raw, "roster_name": raw, "roster_page": pg,
                            "regions": rs, "page0": start})
    return entries


def clean_roster_name(raw):
    """Fallback when an entry is referenced by no one (no pool match): de-shout the ALL-CAPS
    roster name without mangling apostrophes ('A'KIN' -> 'A'kin', 'JUDGE GABBERSLUG' -> 'Judge…')."""
    raw = raw.replace('"', "").strip()
    return " ".join(w[:1] + w[1:].lower() if w.isupper() else w for w in raw.split())


# A couple of display-font roster titles OCR beyond any fuzzy-decode ('Sly" Nye' -> 'Y" NYE';
# 'RULE-OF-THREE' -> 'i E-OF-THREE'), plus one GROUP entry whose statblock is really a member:
# "The Will of the One" is a sect (seeded as an organization); its primary statblock is the bariaur
# figurehead Terwolfe, so the npc node takes his name. The contents page is authoritative on the
# entry, the prose on the subject — sanctioned tailored handlers, keyed by the garble-normalizer.
ROSTER_FIXUPS = {"ynye": "Sly Nye", "ieofthree": "Rule-of-Three", "thewilloftheone": "Terwolfe"}


# --- minor tier: the appendix's "further smattering" (inline descriptors, no statblock) --------
def clean_minor_name(raw):
    """De-noise an inline-mention name: drop leading display-heading ALL-CAPS words, sentence
    starters, and stray lowercase prose ('ARN Leyruss Arn' -> 'Leyruss Arn', 'But P. Cad Peadle'
    -> 'P. Cad Peadle', 'QUICK IDEAS Chinzpeter' -> 'Chinzpeter')."""
    words = raw.replace('"', "").split()
    START = {"But", "And", "So", "Now", "Question", "Answer", "Like", "Take"}
    while words and (words[0] in START
                     or (words[0].isupper() and len(re.sub(r"[^A-Z]", "", words[0])) >= 3)
                     or (words[0].islower() and words[0] not in {"the", "of", "de"})):
        words = words[1:]
    return " ".join(words[:4]).strip(" .,")


_MINOR_DESC = re.compile(r"([A-Z][\w'.’]+(?:\s+(?:the\s+)?[A-Z][\w'.’]+){0,3})\s*"
                         r"\(([^)]*?(?:/[LNC][EGN]?|HD\s*\d|[FMCTP]\d|Cl\b|O-level)[^)]*)\)")


def extract_minors(doc, npcs):
    """The appendix's further smattering (pp ~121-124): minor cutters given only as inline
    descriptors in prose, no Quick Chant block. Real named NPCs (the book's own) → the npc
    dimension's MINOR tier: descriptor-only, confidence from how completely the descriptor parsed.
    Deduped against the roster by name and by a distinctive (race, HD, alignment) signature."""
    rosnames = {n["name"].lower() for n in npcs}
    rosd3 = {(str((n.get("descriptor") or {}).get("race")), str((n.get("descriptor") or {}).get("level_hd")),
             str((n.get("descriptor") or {}).get("alignment")))
             for n in npcs if (n.get("descriptor") or {}).get("level_hd")}
    out, seen = [], set()
    for pidx in range(max(0, doc.page_count - 12), doc.page_count):       # appendix lives at the back
        ptext = re.sub(r"\s+", " ", doc[pidx].get_text().replace("\xa0", " "))
        for m in _MINOR_DESC.finditer(ptext):
            nm = clean_minor_name(m.group(1))
            d = N.parse_descriptor(N.dehyphenate(m.group(2)))
            race, key = d.get("race"), nm.lower()
            if not nm or len(nm) < 3 or key in seen:
                continue
            if any(difflib.SequenceMatcher(None, key, r).ratio() > 0.82 for r in rosnames):
                continue                                                  # already a roster entry
            if d.get("level_hd") and (str(race), str(d.get("level_hd")), str(d.get("alignment"))) in rosd3:
                continue                                                  # distinctive-descriptor dup (Zadara)
            seen.add(key)
            conf = round(0.6 + 0.12 * bool(d.get("alignment")) + 0.06 * bool(d.get("faction")), 2) if race else 0.5
            body = ptext[max(0, m.start() - 16): m.start() + 300]
            out.append({"type": "npc", "name": nm, "tier": "minor", "title_ocr": nm,
                        "pages": [pidx + 1, pidx + 1], "descriptor": d, "statblock": {},
                        "sections": {}, "see_also": [], "body": body, "body_chars": len(body),
                        "confidence": conf, "name_source": "appendix-descriptor",
                        "validation": {"fields_found": 0, "fields_expected": 13, "missing": [],
                                       "anomalies": [], "char_conservation": 1.0, "valid": False,
                                       "tier": "minor"}})
    return out


def main():
    slug = "ps-uncaged-facesofsigil"
    src = json.loads(next(BUILD.glob(f"*/{slug}/source.json")).read_text(encoding="utf-8"))
    out = next(BUILD.glob(f"*/{slug}")); npcdir = out / "npc"; npcdir.mkdir(exist_ok=True)
    for old in npcdir.glob("*.json"): old.unlink()        # no stale nodes from prior runs
    doc = fitz.open(ROOT / src["file"])
    regs = R.segment(load_stream(doc))
    roster = parse_roster(doc)
    offset = calibrate_offset(roster, regs)
    entries = split_by_roster(regs, roster, offset, src["pages"])
    nonnpc = 0

    npcs = []
    for e in entries:
        node = assemble_npc(e, src["pages"])
        if node:
            node["roster_name"], node["roster_page"] = e["roster_name"], e["roster_page"]
            npcs.append(node)
        else:
            nonnpc += 1

    # name resolution: the roster IS the book's authoritative entry list, so the name comes from
    # THERE — decoded against the cross-reference pool (the clean names its neighbours use for it),
    # with a de-shout fallback. This replaces the old title-decode + cross-ref-consensus guessing;
    # boundaries no longer depend on detecting a display-font title at all.
    all_refs = [(r["name"], r["page"]) for n in npcs for r in n["see_also"]]
    pool = {}
    for nm, _ in all_refs:
        for k in N.name_keys(nm):
            pool.setdefault(k, nm)
    for n in npcs:
        key = N._norm_garbled(n["roster_name"])
        if key in ROSTER_FIXUPS:
            n["name"], n["name_source"] = ROSTER_FIXUPS[key], "roster-fixup"
            continue
        dec, ratio = N.decode_title(n["roster_name"], pool)
        if dec:
            n["name"], n["name_source"] = dec, f"roster-decode:{ratio}"
        else:
            n["name"], n["name_source"] = clean_roster_name(n["roster_name"]), "roster-clean"

    # MINOR tier: the appendix's further smattering — named cutters given only as inline
    # descriptors in prose, no statblock. Real NPCs the book counts; resolves their danglers.
    npcs += extract_minors(doc, npcs)

    # write
    for n in npcs:
        prov = {"product": src["product_slug"], "component": slug,
                "pages": n["pages"], "source_sha256": src["sha256"][:16] + "…"}
        n["provenance"] = prov
        fn = re.sub(r"[^a-z0-9]+", "-", n["name"].lower()).strip("-") or "unnamed"
        fn = f"{fn}-p{n['pages'][0] if n.get('pages') else 0}"   # page-disambiguated: no name-collision data loss
        (npcdir / f"{fn}.json").write_text(json.dumps(n, indent=2, ensure_ascii=False), encoding="utf-8")

    # plot graph: nodes + cross-reference edges
    names = {n["name"] for n in npcs}
    edges = []
    for n in npcs:
        for r in n["see_also"]:
            edges.append({"from": n["name"], "to": r["name"], "page": r["page"], "resolves": r["resolves"]})
    edge_set = {(e["from"], e["to"]) for e in edges}
    recip = sum(1 for e in edges if (e["to"], e["from"]) in edge_set)
    graph = {"nodes": [{"name": n["name"], "faction": (n.get("descriptor") or {}).get("faction"),
                        "alignment": (n.get("descriptor") or {}).get("alignment"),
                        "pages": n["pages"]} for n in npcs],
             "edges": edges}
    (out / "npc" / "graph.json").write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    # md projection
    md = "# Uncaged — Faces of Sigil (typed NPC projection)\n\n" + \
         "\n\n---\n\n".join(npc_markdown(n) for n in sorted(npcs, key=lambda x: x["name"]))
    (out / "npc" / "cast.md").write_text(md, encoding="utf-8")

    # ---- validation report -------------------------------------------------
    valid = [n for n in npcs if n["validation"]["valid"]]
    fields_avg = sum(n["validation"]["fields_found"] for n in npcs) / max(1, len(npcs))
    anomalies = sum(len(n["validation"]["anomalies"]) for n in npcs)
    with_faction = sum(1 for n in npcs if (n.get("descriptor") or {}).get("faction"))
    with_align = sum(1 for n in npcs if (n.get("descriptor") or {}).get("alignment"))
    unresolved = [e for e in edges if not e["resolves"]]
    print(f"=== UNCAGED v2 EXTRACTION =================================")
    print(f"pages processed     : {len(doc)}")
    print(f"entries (title-split): {len(entries)}   non-NPC sections: {nonnpc}")
    print(f"NPC nodes emitted   : {len(npcs)}")
    print(f"  statblocks valid  : {len(valid)}/{len(npcs)}  (>=10 fields & char-conservation>=0.95)")
    print(f"  avg fields/13     : {fields_avg:.1f}")
    print(f"  descriptor faction: {with_faction}/{len(npcs)}    alignment: {with_align}/{len(npcs)}")
    print(f"  OCR anomalies flag: {anomalies} (logged, not hidden)")
    print(f"plot graph          : {len(graph['nodes'])} nodes, {len(edges)} edges, "
          f"{recip} reciprocal, {len(unresolved)} unresolved")
    print(f"written -> {npcdir.relative_to(ROOT)}/  (*.json, graph.json, cast.md)")
    print(f"\n--- roster (name | race | faction | align | AC | conf | valid) ---")
    for n in sorted(npcs, key=lambda x: x["pages"][0] if x["pages"] else 0):
        d = n.get("descriptor") or {}
        print(f"  p{(n['pages'][0] if n['pages'] else 0):<3} {n['name'][:20]:20} "
              f"{(d.get('race') or '?')[:16]:16} {(d.get('faction') or '-')[:18]:18} "
              f"{(d.get('alignment') or '?'):3} AC{str(n['statblock'].get('ac','?')):>4} "
              f"c{n['confidence']:<4} {'OK' if n['validation']['valid'] else 'review'}"
              f"{'  ['+n.get('name_source','')[:8]+']' if n.get('name_source')=='cross-ref-consensus' else ''}")
    review = [n for n in npcs if not n["validation"]["valid"] or n["confidence"] < 0.7]
    if review:
        print(f"\n--- review pile ({len(review)}): statblocks needing a targeted pass ---")
        for n in review:
            print(f"  p{n['pages'][0]:<3} {n['name'][:26]:26} fields {n['validation']['fields_found']}/13"
                  f" conf {n['confidence']}")


if __name__ == "__main__":
    main()
