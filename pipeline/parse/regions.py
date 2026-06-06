#!/usr/bin/env python
"""regions — stateful, content-aware region parser (psx v2 core).

Geometric reflow sorts words but understands nothing. v2 segments a page into
typed REGIONS, interprets each in the context of its region type, and VALIDATES
against that type's contract. The typed node is the source of truth; md/JSON/graph
are projections. Provenance (page, bbox, source sha256) rides every node.

Grammar here is calibrated to AD&D 2e Planescape statblocks (the "Quick Chant"
sidebar): name / (plane/sex/race/class|HD/faction/alignment) / dense stat line /
SOURCE / Notes, followed by labeled NPC sections.
"""
import argparse, difflib, json, re, sys, pathlib
import fitz

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from normalize import normalize_dice_ocr, norm_num, dehyphenate, is_name, parse_descriptor

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / "build"

# --- signals -----------------------------------------------------------------
WATERMARK = re.compile(r"\(?\bOrder\s*#?\s*\d+|©|all rights reserved", re.I)
LABEL     = re.compile(r"^[A-Z][A-Z'’\-\. ]{2,}:")
STAT_OPEN = re.compile(r"^\(.*\b(HD|/[LNC][EGN]?|F\d|M\d|C\d|T\d|P\d)\b.*\)|^A[C{]\s*-?\d")
# ALIGNMENTS, FACTIONS, CLASS_RE + the normalizers + parse_descriptor → normalize.py (the gear-house)

SECTION_LABELS = {"PERSONALITY","ALTERNATE PERSONALITY","CORE PERSONALITY","SPECIAL EQUIPMENT",
    "SPELLS","SPELL-LIKE ABILITIES","SPELL-LIKE ABILITY","LOCATION","ROLE-PLAYING","COMBAT",
    "SEE ALSO","DESCRIPTION","SOURCE","FACTION ABILITIES","FACTION ABILITY","THIEF ABILITIES",
    "BARD ABILITIES","GRANTED POWER","DM NOTE","PSIONIC WILD TALENT","SECT ABILITY"}
STAT_FIELDS = ["ac","mv","hp","thac0","num_attacks","damage","special_attacks",
               "special_defenses","magic_resistance","size","morale","intelligence","xp"]


def canon_label(raw):
    u = raw.strip().rstrip(":").strip().upper()
    if u in SECTION_LABELS: return u
    m = difflib.get_close_matches(u, SECTION_LABELS, n=1, cutoff=0.82)  # ROLE-PLAYTNG -> ROLE-PLAYING
    return m[0] if m else None


# --- line extraction in column reading order ---------------------------------
def dominant(spans):
    s = max((sp for sp in spans if sp["text"].strip()), key=lambda x: len(x["text"]), default=None)
    if not s: return None
    return {"fam": s["font"].split("+")[-1], "size": round(s["size"], 1),
            "bold": bool(s["flags"] & 16), "ital": bool(s["flags"] & 2)}


def page_lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            text = " ".join(sp["text"] for sp in l["spans"]).strip()
            st = dominant(l["spans"])
            if text and st:
                x0, y0, x1, y1 = l["bbox"]
                out.append({"text": re.sub(r"\s{2,}", " ", text), "x0": x0, "y0": y0,
                            "x1": x1, "y1": y1, **st})
    return out


def _gutter(region, cx0, cx1):
    w = cx1 - cx0
    if w <= 0 or len(region) < 2: return None
    bins, cover = 100, [0]*100
    for r in region:
        for i in range(max(0, int((r["x0"]-cx0)/w*bins)), min(bins, int((r["x1"]-cx0)/w*bins)+1)):
            cover[i] += 1
    best, i = None, 0
    while i < bins:
        if cover[i] == 0:
            j = i
            while j < bins and cover[j] == 0: j += 1
            if i > 0 and j < bins and (j-i) >= 3:
                score = (j-i) - abs((i+j)/2 - bins/2)*0.15
                if best is None or score > best[0]: best = (score, (i+j)/2)
            i = j
        else: i += 1
    return None if best is None else cx0 + best[1]/bins*w


def _order(region, cx0, cx1, depth=0):
    if depth >= 3 or len(region) < 2:
        return sorted(region, key=lambda r: (round(r["y0"]), r["x0"]))
    g = _gutter(region, cx0, cx1)
    if g is None:
        return sorted(region, key=lambda r: (round(r["y0"]), r["x0"]))
    L = [r for r in region if (r["x0"]+r["x1"])/2 < g]
    R = [r for r in region if (r["x0"]+r["x1"])/2 >= g]
    if not L or not R:
        return sorted(region, key=lambda r: (round(r["y0"]), r["x0"]))
    return _order(L, cx0, g, depth+1) + _order(R, g, cx1, depth+1)


def ordered_content_lines(page):
    raw = page_lines(page)
    lines = [l for l in raw if "Helvetica" not in l["fam"] and not WATERMARK.search(l["text"])]
    dropped = [l for l in raw if "Helvetica" in l["fam"] or WATERMARK.search(l["text"])]
    if not lines: return [], dropped
    cx0, cx1 = min(l["x0"] for l in lines), max(l["x1"] for l in lines)
    span_thresh = 0.66*(cx1-cx0)
    bands, cur = [], []
    for l in sorted(lines, key=lambda r: r["y0"]):
        if (l["x1"]-l["x0"]) >= span_thresh:
            if cur: bands.append(cur); cur = []
            bands.append([l])
        else: cur.append(l)
    if cur: bands.append(cur)
    flat = []
    for band in bands:
        flat.extend(_order(band, cx0, cx1))
    return flat, dropped


# --- stateful segmentation ---------------------------------------------------
def is_noise(text):
    return len(re.sub(r"[^A-Za-z0-9]", "", text)) <= 1


def is_heading(l):
    return l["size"] >= 14 or (l["bold"] and "Arial" in l["fam"] and l["size"] >= 12)


def _is_section(line):
    m = LABEL.match(line["text"])
    return canon_label(m.group(0)) if m else None


def segment(lines):
    """FSM: group ordered lines into typed regions. Inside a statblock we STAY
    there (context) until a section label or entry heading ends it."""
    regions, i, n = [], 0, len(lines)
    while i < n:
        l = lines[i]
        if is_noise(l["text"]):
            i += 1; continue
        sec = _is_section(l)
        if sec:
            body = [l]; i += 1
            while i < n and not _is_section(lines[i]) and not STAT_OPEN.match(lines[i]["text"]) \
                    and not is_heading(lines[i]):
                if not is_noise(lines[i]["text"]): body.append(lines[i])
                i += 1
            regions.append({"type": "section", "label": sec, "lines": body})
        elif STAT_OPEN.match(l["text"]):
            block = []
            if regions and regions[-1]["type"] == "body" and len(regions[-1]["lines"][-1]["text"].split()) <= 3:
                block.append(regions[-1]["lines"].pop())
                if not regions[-1]["lines"]: regions.pop()
            while i < n and not _is_section(lines[i]) and not is_heading(lines[i]):
                if not is_noise(lines[i]["text"]): block.append(lines[i])
                i += 1
            regions.append({"type": "statblock", "lines": block})
        elif is_heading(l):
            regions.append({"type": "heading", "size": l["size"], "lines": [l]}); i += 1
        else:
            if regions and regions[-1]["type"] == "body":
                regions[-1]["lines"].append(l)
            else:
                regions.append({"type": "body", "lines": [l]})
            i += 1
    return regions


# --- value normalizers (norm_num / norm_dice / normalize_dice_ocr) → normalize.py ------------


def parse_movement(s, anomalies):
    s = re.sub(r"M\.?V|7WV", "", s).strip()
    modes = []
    g = re.match(r"\s*([0-9IlSO]+)", s)
    if g: modes.append({"mode": "ground", "rate": norm_num(g.group(1), anomalies, "MV")})
    for m in re.finditer(r"\b(Fl|Sw|Br|Jp|Wb|Cl)\s*([0-9IlSO]+)\s*(?:[\(C]([A-FO]+)\)?)?", s):
        modes.append({"mode": m.group(1), "rate": norm_num(m.group(2), anomalies, m.group(1)),
                      "maneuverability": (m.group(3) or "").replace("O", "C") or None})
    return modes


# parse_descriptor → normalize.py (hardened, positional: race from the 2nd slot, never the plane)


# --- type-specific parse + validation ----------------------------------------
def parse_statblock(region):
    text = " ".join(l["text"] for l in region["lines"])
    anomalies = []
    text = normalize_dice_ocr(text, anomalies)        # statblock-wide dice repair before field extraction
    text = text.replace("M.V", "MV").replace("THACO", "THAC0").replace("{", "(")
    f = {}
    name = re.match(r"^([A-Z][\w''’\-]*(?:\s+[A-Z][\w''’\-]*){0,2}?)\s*\(", text)
    f["name"] = (name.group(1).strip() if name else
                 (region["lines"][0]["text"].strip() if region["lines"] else None))
    paren = re.search(r"\(([^)]*(?:HD|/[LNC]|F\d|M\d|C\d|T\d|P\d)[^)]*)\)", text)
    if paren:
        f["descriptor"] = parse_descriptor(paren.group(1), anomalies)
    pats = {"ac": r"AC\s*(-?\d+(?:\s*,\s*-?\d+)*)", "hp": r"hp\s*(see below|\d+)",
            "num_attacks": r"[#*]AT\s*(\d+)",
            "damage": r"D(?:mg|rag|r)\s*([^;]+)", "special_attacks": r"SA\s*([^;]+)",
            "special_defenses": r"SD\s*([^;]+)", "magic_resistance": r"MR\s*(\d+%)",
            "size": r"SZ\s*([A-Z](?:\s*\([^)]*\))?)", "morale": r"ML\s*([^;(]+(?:\(\d+\))?)",
            "intelligence": r"(?:Int|Lnt)\s*([^;(]+(?:\(\d+\))?)", "xp": r"XP\s*([\d,]+)"}
    for k, p in pats.items():
        m = re.search(p, text)
        if m: f[k] = m.group(1).strip()
    mv = re.search(r"MV\s*([^;]+?)(?:;|hp|$)", text)
    if mv: f["mv"] = parse_movement(mv.group(1), anomalies)
    # THAC0 is a numeric slot, so a letter there is a misread digit ('THACO S'->5, 'IS'->15).
    # Capture the lookalike token, repair via the numeric-OCR gear, and range-guard to lawful
    # 2e THAC0 (1..20) so a bad token is dropped, never admitted as garbage. (V&V D2)
    th = re.search(r"THAC0\s*([0-9IlSO]+)", text)
    if th:
        val = norm_num(th.group(1), anomalies, "THAC0")
        if val.isdigit() and 1 <= int(val) <= 20:
            f["thac0"] = val
    # damage already repaired statblock-wide by normalize_dice_ocr (above)
    src = re.search(r"SOURCE:\s*([^.;]+)", text)
    if src: f["source"] = src.group(1).strip()
    # validation contract
    found = [k for k in STAT_FIELDS if f.get(k)]
    missing = [k for k in STAT_FIELDS if not f.get(k)]
    src_chars = re.sub(r"\s", "", text)
    flat = json.dumps(f, ensure_ascii=False)
    parsed_chars = re.sub(r'[\s\[\]{}":,]|name|descriptor|raw|null|true|false', "", flat)
    conservation = round(sum(c in src_chars for c in parsed_chars) / max(1, len(parsed_chars)), 3)
    valid = len(found) >= 10 and conservation >= 0.95
    # type-aware denominator: class-based humanoids legitimately lack SA/MR — scoring them out of
    # the full monster 13 wrongly under-confidences every NPC who isn't a monster.
    expected = 11 if (f.get("descriptor") or {}).get("char_class") else len(STAT_FIELDS)
    conf = round(min(1.0, len(found) / expected) * (1 - 0.04 * len(anomalies)), 2)
    return f, {"fields_found": len(found), "fields_expected": len(STAT_FIELDS),
               "missing": missing, "anomalies": anomalies,
               "char_conservation": conservation, "valid": valid}, conf


# _SEE_CONNECTORS / is_name → normalize.py


def parse_see_also(lines, max_page):
    text = dehyphenate(" ".join(l["text"] for l in lines))
    refs = []
    for m in re.finditer(r"([A-Z][\w''’\- ]+?)\s*\(pg\.?\s*(\d+)\)", text):
        nm = m.group(1).strip(" .—-")
        if is_name(nm):                                   # drop prose that leaked into the name capture
            refs.append({"name": nm, "page": int(m.group(2)), "resolves": 1 <= int(m.group(2)) <= max_page})
    return refs


# --- single-page debug driver ------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True); ap.add_argument("--page", type=int, required=True)
    a = ap.parse_args()
    src = json.loads(next(BUILD.glob(f"*/{a.slug}/source.json")).read_text(encoding="utf-8"))
    doc = fitz.open(ROOT / src["file"])
    lines, dropped = ordered_content_lines(doc[a.page-1])
    regions = segment(lines)
    print(f"=== {src['component']} p{a.page}: {len(regions)} regions; furniture: {[d['text'] for d in dropped]}")
    for r in regions:
        print(f"  {r['type']:9}{('/'+r.get('label','')):16} [{len(r['lines'])}ln] {r['lines'][0]['text'][:48]}")
    sb = next((r for r in regions if r["type"] == "statblock"), None)
    if sb:
        f, v, c = parse_statblock(sb)
        print("\n=== statblock node ===")
        print(json.dumps({"confidence": c, "fields": f, "validation": v}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
