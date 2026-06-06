#!/usr/bin/env python
"""psx — Planescape sourcebook extractor.

Foundation layer: PDF -> page-anchored text + renders + art + quality scores -> markdown.
Design rules:
  * content/official/ is IMMUTABLE. Everything derived lands in build/.
  * Page = unit of provenance. Every artifact traces to (component, page, sha256).
  * Re-entrant: any page can be re-transcribed by a later, better pass (tesseract,
    vision model) by overwriting its text/page-NNNN.txt; assemble re-runs cheaply.
  * Windows-safe: explicit UTF-8 everywhere, no /tmp, forward slashes via pathlib.

Subcommands:
  inventory             register every official PDF (sha256, pages, TSR code guess)
  text [--slug S]       extract OCR text layer per page (sorted reading order)
  quality [--slug S]    score every page's text against corpus vocabulary
  render --slug S       render pages to JPEG (vision-pass fuel)
  images [--slug S]     extract embedded art objects w/ bbox (skips full-page scan base)
  assemble [--slug S]   emit page-anchored book.md per component
  pilot --slug S        text+quality+render+images+assemble for one component
  status                corpus-wide quality triage table
"""
import argparse, hashlib, json, re, sys, time
from pathlib import Path

import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]          # C:/sandbox/Planescape
OFFICIAL = ROOT / "content" / "official"
SRD_MD = ROOT / "content" / "srd" / "srd-5.1" / "markdown"
BUILD = ROOT / "build"

FULL_PAGE_COVERAGE = 0.88     # image covering >=88% of page = scan base layer, not art
RENDER_DPI = 120
JPEG_QUALITY = 80

TSR_CODE_RE = re.compile(r"(?:TSR)?-?(2[56]\d{2})")
WORD_RE = re.compile(r"[A-Za-z']{3,}")


def slugify(s: str) -> str:
    s = re.sub(r"\(2e\)|\.pdf$", "", s, flags=re.I)
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return re.sub(r"-{2,}", "-", s)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def component_dirs():
    """Yield (build_dir, source.json dict) for every inventoried component."""
    for sj in sorted(BUILD.glob("*/*/source.json")):
        yield sj.parent, json.loads(sj.read_text(encoding="utf-8"))


def pick(slug):
    out = [(d, s) for d, s in component_dirs()
           if slug in (s["component"], s["product_slug"], f"{s['product_slug']}/{s['component']}")]
    if not out:
        sys.exit(f"no component matching slug {slug!r} — run inventory first / check status")
    return out


# ---------------------------------------------------------------- inventory
def cmd_inventory(_):
    n = 0
    for pdf in sorted(OFFICIAL.rglob("*.pdf")):
        product = pdf.parent.name if pdf.parent != OFFICIAL else "loose"
        pslug, cslug = slugify(product), slugify(pdf.stem)
        bdir = BUILD / pslug / cslug
        sj = bdir / "source.json"
        if sj.exists() and json.loads(sj.read_text(encoding="utf-8")).get("sha256"):
            continue  # already registered; sources are immutable
        bdir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(pdf)
        m = TSR_CODE_RE.search(pdf.name) or TSR_CODE_RE.search(product)
        meta = {
            "product": product, "product_slug": pslug, "component": cslug,
            "file": str(pdf.relative_to(ROOT)), "sha256": sha256(pdf),
            "pages": doc.page_count, "tsr_code": m.group(1) if m else None,
            "edition": "2e", "ocr": "embedded-textlayer",
            "registered": time.strftime("%Y-%m-%d"),
            "license_note": "user-owned purchase; do not redistribute derived text",
        }
        doc.close()
        sj.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"registered {pslug}/{cslug}  ({meta['pages']}p, tsr={meta['tsr_code']})")
        n += 1
    print(f"inventory: {n} new, {sum(1 for _ in component_dirs())} total components")


# ---------------------------------------------------------------- text
def cmd_text(a):
    targets = pick(a.slug) if a.slug else list(component_dirs())
    for bdir, src in targets:
        tdir = bdir / "text"
        if tdir.exists() and len(list(tdir.glob("page-*.txt"))) == src["pages"] and not a.force:
            continue
        tdir.mkdir(exist_ok=True)
        doc = fitz.open(ROOT / src["file"])
        for i, page in enumerate(doc, 1):
            txt = page.get_text("text", sort=True)
            (tdir / f"page-{i:04d}.txt").write_text(txt, encoding="utf-8")
        doc.close()
        print(f"text: {src['product_slug']}/{src['component']} ({src['pages']}p)")


# ---------------------------------------------------------------- quality
def load_vocab():
    cache = BUILD / "_vocab.json"
    if cache.exists():
        return set(json.loads(cache.read_text(encoding="utf-8")))
    vocab = set()
    for md in SRD_MD.rglob("*.md"):
        vocab.update(w.lower() for w in WORD_RE.findall(md.read_text(encoding="utf-8", errors="ignore")))
    # planescape-flavored floor so cant doesn't get scored as garbage
    vocab.update("""berk cutter sigil cant chant jink kip barmy addle clueless tout sod
        factol factotum namer githzerai githyanki tanari baatezu yugoloth modron axani
        bariaur tiefling aasimar planar planewalker portal outlands gatetown ward hive
        razorvine dabus mazes uncaged factions harmonium athar godsmen bleakers xaositects
        anarchists guvners hardheads mercykillers sensates ciphers dustmen indeps""".split())
    BUILD.mkdir(exist_ok=True)
    cache.write_text(json.dumps(sorted(vocab)), encoding="utf-8")
    return vocab


def grade(ratio, words):
    if words < 12:   return "blank"     # cover/art/map page
    if ratio >= .90: return "A"
    if ratio >= .80: return "B"
    if ratio >= .65: return "C"
    return "D"


def cmd_quality(a):
    vocab = load_vocab()
    targets = pick(a.slug) if a.slug else list(component_dirs())
    for bdir, src in targets:
        tdir = bdir / "text"
        if not tdir.exists():
            continue
        pages = {}
        for tf in sorted(tdir.glob("page-*.txt")):
            words = WORD_RE.findall(tf.read_text(encoding="utf-8"))
            hits = sum(1 for w in words if w.lower() in vocab)
            ratio = hits / len(words) if words else 0.0
            pages[int(tf.stem.split("-")[1])] = {
                "words": len(words), "dict_ratio": round(ratio, 3),
                "grade": grade(ratio, len(words)),
            }
        graded = [p["grade"] for p in pages.values() if p["grade"] != "blank"]
        summary = {g: graded.count(g) for g in "ABCD"}
        summary["blank"] = len(pages) - len(graded)
        (bdir / "quality.json").write_text(
            json.dumps({"summary": summary, "pages": pages}, indent=1), encoding="utf-8")
        print(f"quality: {src['product_slug']}/{src['component']} -> {summary}")


# ---------------------------------------------------------------- render
def cmd_render(a):
    for bdir, src in pick(a.slug):
        pdir = bdir / "pages"
        pdir.mkdir(exist_ok=True)
        doc = fitz.open(ROOT / src["file"])
        for i, page in enumerate(doc, 1):
            out = pdir / f"page-{i:04d}.jpg"
            if out.exists() and not a.force:
                continue
            pix = page.get_pixmap(dpi=RENDER_DPI, colorspace=fitz.csRGB)
            out.write_bytes(pix.tobytes("jpeg", jpg_quality=JPEG_QUALITY))
        doc.close()
        print(f"render: {src['product_slug']}/{src['component']} ({src['pages']}p @ {RENDER_DPI}dpi)")


# ---------------------------------------------------------------- images
def cmd_images(a):
    targets = pick(a.slug) if a.slug else list(component_dirs())
    for bdir, src in targets:
        idir = bdir / "images"
        idir.mkdir(exist_ok=True)
        doc = fitz.open(ROOT / src["file"])
        manifest, art_n, base_n = [], 0, 0
        for pno, page in enumerate(doc, 1):
            parea = abs(page.rect)
            for k, info in enumerate(page.get_images(full=True), 1):
                xref = info[0]
                rects = page.get_image_rects(xref)
                cov = max((abs(r) / parea for r in rects), default=0)
                entry = {"page": pno, "xref": xref, "coverage": round(cov, 3),
                         "bbox": [round(v, 1) for v in rects[0]] if rects else None}
                if cov >= FULL_PAGE_COVERAGE:
                    entry["role"] = "scan-base"; base_n += 1     # the page scan itself
                else:
                    entry["role"] = "art"
                    img = doc.extract_image(xref)
                    fn = f"img-p{pno:04d}-{k:02d}.{img['ext']}"
                    (idir / fn).write_bytes(img["image"])
                    entry["file"] = fn; art_n += 1
                manifest.append(entry)
        doc.close()
        (bdir / "images.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        print(f"images: {src['product_slug']}/{src['component']} -> {art_n} art, {base_n} scan-base"
              + ("  [pure scan: art lives inside page renders -> vision-pass crop job]" if art_n == 0 else ""))


# ---------------------------------------------------------------- reflow (v1a)
def find_gutter(region, cont_x0, cont_x1):
    """x of the widest internal whitespace channel spanning the region, or None."""
    width = cont_x1 - cont_x0
    if width <= 0 or len(region) < 2:
        return None
    bins = 100
    cover = [0] * bins
    for b in region:
        a = int((b[0] - cont_x0) / width * bins)
        z = int((b[2] - cont_x0) / width * bins)
        for i in range(max(0, a), min(bins, z + 1)):
            cover[i] += 1
    best = None
    i = 0
    while i < bins:
        if cover[i] == 0:
            j = i
            while j < bins and cover[j] == 0:
                j += 1
            if i > 0 and j < bins:                 # internal gap only (not a margin)
                w = j - i
                if w >= 3:                         # >= ~3% of content width
                    score = w - abs((i + j) / 2 - bins / 2) * 0.15   # prefer central
                    if best is None or score > best[0]:
                        best = (score, (i + j) / 2)
            i = j
        else:
            i += 1
    return None if best is None else cont_x0 + best[1] / bins * width


def order_region(region, cont_x0, cont_x1, depth=0):
    """Recursive XY-cut: split on vertical gutters, read columns left-to-right."""
    if depth >= 3 or len(region) < 2:
        return sorted(region, key=lambda b: (round(b[1]), b[0]))
    gut = find_gutter(region, cont_x0, cont_x1)
    if gut is None:
        return sorted(region, key=lambda b: (round(b[1]), b[0]))
    left = [b for b in region if (b[0] + b[2]) / 2 < gut]
    right = [b for b in region if (b[0] + b[2]) / 2 >= gut]
    if not left or not right:
        return sorted(region, key=lambda b: (round(b[1]), b[0]))
    return (order_region(left, cont_x0, gut, depth + 1)
            + order_region(right, gut, cont_x1, depth + 1))


def reflow_blocks(blocks):
    """Column-aware reading order. Full-width blocks band the page (headers, wide
    titles); narrow blocks within a band get XY-cut into columns. Fixes the
    prose/statblock-sidebar interleaving that get_text(sort=True) produces."""
    if not blocks:
        return ""
    cont_x0 = min(b[0] for b in blocks)
    cont_x1 = max(b[2] for b in blocks)
    span_thresh = 0.66 * (cont_x1 - cont_x0)
    bands, cur = [], []
    for b in sorted(blocks, key=lambda b: b[1]):
        if (b[2] - b[0]) >= span_thresh:           # spanning block -> own band
            if cur:
                bands.append(cur); cur = []
            bands.append([b])
        else:
            cur.append(b)
    if cur:
        bands.append(cur)
    out = []
    for band in bands:
        for b in order_region(band, cont_x0, cont_x1):
            t = b[4].strip()
            if t:
                out.append(t)
    return "\n\n".join(out)


def cmd_reflow(a):
    targets = pick(a.slug) if a.slug else list(component_dirs())
    for bdir, src in targets:
        rdir = bdir / "reflow"
        if rdir.exists() and len(list(rdir.glob("page-*.txt"))) == src["pages"] and not a.force:
            continue
        rdir.mkdir(exist_ok=True)
        doc = fitz.open(ROOT / src["file"])
        for i, page in enumerate(doc, 1):
            blocks = [b for b in page.get_text("blocks")
                      if len(b) >= 7 and b[6] == 0 and b[4].strip()]
            (rdir / f"page-{i:04d}.txt").write_text(reflow_blocks(blocks), encoding="utf-8")
        doc.close()
        print(f"reflow: {src['product_slug']}/{src['component']} ({src['pages']}p, column-aware)")


# ---------------------------------------------------------------- assemble
def clean_page_text(txt: str) -> str:
    txt = re.sub(r"(\w)-\n(\w)", r"\1\2", txt)        # de-hyphenate line wraps
    txt = re.sub(r"[ \t]+\n", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def cmd_assemble(a):
    targets = pick(a.slug) if a.slug else list(component_dirs())
    for bdir, src in targets:
        tdir = bdir / "text"
        if not tdir.exists():
            continue
        rdir = bdir / "reflow"
        q = json.loads((bdir / "quality.json").read_text(encoding="utf-8"))["pages"] \
            if (bdir / "quality.json").exists() else {}
        imgs = json.loads((bdir / "images.json").read_text(encoding="utf-8")) \
            if (bdir / "images.json").exists() else []
        art_by_page = {}
        for e in imgs:
            if e.get("role") == "art":
                art_by_page.setdefault(e["page"], []).append(e["file"])
        out = [f"---\ntitle: {src['product']} — {src['component']}\n"
               f"tsr_code: {src['tsr_code']}\nedition: {src['edition']}\n"
               f"source_sha256: {src['sha256']}\npages: {src['pages']}\n"
               f"pipeline: psx-v0 (embedded text layer; see quality.json before trusting any page)\n---\n"]
        for tf in sorted(tdir.glob("page-*.txt")):
            n = int(tf.stem.split("-")[1])
            g = q.get(str(n), q.get(n, {})).get("grade", "?")
            rf = rdir / tf.name
            src_file, layer = (rf, "reflow") if rf.exists() else (tf, "textlayer")
            out.append(f"\n<!-- pg:{n:04d} grade:{g} src:{layer} -->\n")
            for fn in art_by_page.get(n, []):
                out.append(f"![art p{n}](images/{fn})\n")
            out.append(clean_page_text(src_file.read_text(encoding="utf-8")) + "\n")
        (bdir / "book.md").write_text("".join(out), encoding="utf-8")
        print(f"assemble: {src['product_slug']}/{src['component']} -> book.md "
              f"({(bdir/'book.md').stat().st_size//1024}KB)")


# ---------------------------------------------------------------- status
def cmd_status(_):
    rows = []
    for bdir, src in component_dirs():
        qf = bdir / "quality.json"
        s = json.loads(qf.read_text(encoding="utf-8"))["summary"] if qf.exists() else {}
        rows.append((src["product_slug"], src["component"], src["pages"], s))
    wp = max((len(r[0]) for r in rows), default=10)
    wc = max((len(r[1]) for r in rows), default=10)
    print(f"{'product':{wp}}  {'component':{wc}}  pages  A    B    C    D   blank")
    bundles = False
    for p, c, n, s in rows:
        if isinstance(n, list):          # dndbeyond-save bundle: pages is a parts manifest, not a count
            cell, bundles = f"{len(n)}pt", True
        else:
            cell = str(n)
        print(f"{p:{wp}}  {c:{wc}}  {cell:>5}  " +
              ("-" if not s else f"{s.get('A',0):<4} {s.get('B',0):<4} {s.get('C',0):<4} "
                                 f"{s.get('D',0):<4} {s.get('blank',0):<4}"))
    if bundles:
        print("  (Npt = N-part D&D Beyond save bundle; no page-grade pass)")


def cmd_pilot(a):
    cmd_text(a); cmd_reflow(a); cmd_quality(a); cmd_render(a); cmd_images(a); cmd_assemble(a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="psx")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("inventory", "text", "reflow", "quality", "render", "images", "assemble", "pilot", "status"):
        sp = sub.add_parser(name)
        if name != "inventory" and name != "status":
            sp.add_argument("--slug", default=None, required=(name in ("render", "pilot")))
            sp.add_argument("--force", action="store_true")
    args = ap.parse_args()
    {"inventory": cmd_inventory, "text": cmd_text, "reflow": cmd_reflow, "quality": cmd_quality,
     "render": cmd_render, "images": cmd_images, "assemble": cmd_assemble,
     "pilot": cmd_pilot, "status": cmd_status}[args.cmd](args)
