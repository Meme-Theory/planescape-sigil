#!/usr/bin/env python
"""
dndbeyond.py — index browser "save as" captures of D&D Beyond source pages
into the markdown pipeline.

Workflow:
  1. In the browser, Ctrl+S each source page ("Webpage, Complete") into the
     root `D&D Beyond/` folder (the inbox).
  2. `python pipeline/extract/dndbeyond.py ingest`
       collect : sweep inbox -> content/official/<product>/dndbeyond-saves/
       parse   : .p-article-content -> markdown, per-page provenance anchors
       build   : build/<product_slug>/<component>/{book.md,source.json,
                 images.json,entities.json,images/<page>/...}
       status  : coverage table vs the landing page's ToC -> STATUS.md
  3. `python pipeline/extract/dndbeyond.py status` — coverage only, no rebuild.

Unlike the PDF path (psx.py) there is no OCR and no page grades: the HTML *is*
the authoritative digital text (grade A by construction). The unit of
provenance is the source page slug + heading anchor:
    <!-- src:paitm/sato/character-options#Backgrounds -->
mirroring psx's `<!-- pg:NNNN grade:X -->` so downstream backends can always
point back to the exact source location. Entity tooltips (spell/item/monster/
skill links) are NOT kept inline — book.md stays clean prose; they land typed
in entities.json for the graph/plot backends.

content/ stays immutable: this script only reads the saves (collect moves
files *between* content-side folders; it never edits them).
"""

import hashlib
import json
import re
import shutil
import sys
import urllib.parse
from collections import Counter
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[2]
INBOX = ROOT / "D&D Beyond"
PRODUCT_DIR = ROOT / "content" / "official" / "Planescape_ Adventures in the Multiverse (5e)"
SAVES = PRODUCT_DIR / "dndbeyond-saves"
PRODUCT_SLUG = "planescape-adventures-in-the-multiverse"
BUILD = ROOT / "build" / PRODUCT_SLUG

BOOKS = {  # url code -> (component slug, title)
    "sato": ("paitm-sato-sigil-and-the-outlands", "Sigil and the Outlands"),
    "mpp": ("paitm-mpp-mortes-planar-parade", "Morte's Planar Parade"),
    "tofw": ("paitm-tofw-turn-of-fortunes-wheel", "Turn of Fortune's Wheel"),
}
LICENSE_NOTE = "user-owned D&D Beyond purchase; do not redistribute derived text"

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # Windows console, see psx.py


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_slug(soup: BeautifulSoup) -> str | None:
    """e.g. 'paitm/sato/character-options', or 'dnd/paitm' for the landing page."""
    el = soup.find("link", rel="canonical") or soup.find("meta", property="og:url")
    url = el and (el.get("href") or el.get("content"))
    if not url:
        return None
    path = urllib.parse.urlparse(url).path.strip("/")
    if not path.startswith("sources/"):
        return None
    slug = path[len("sources/"):]
    return slug[len("dnd/"):] if slug.startswith("dnd/paitm/") else slug


# ---------------------------------------------------------------- collect

def collect() -> list[str]:
    """Sweep the browser-save inbox into content/official.

    Never clobbers a differing file; inbox copies verified byte-identical to
    already-collected ones are removed, so an empty inbox == fully ingested.
    Loose asset files (hand-gathered maps, photos) are routed to whichever
    collected `_files` dir already references their basename, else `_loose/`."""
    moved = []
    if not INBOX.is_dir():
        return moved
    SAVES.mkdir(parents=True, exist_ok=True)
    for item in sorted(INBOX.iterdir()):
        dst = SAVES / item.name
        if item.is_file() and item.suffix.lower() in (".html", ".htm"):
            if not dst.exists():
                shutil.move(str(item), dst)
                moved.append(item.name)
            elif sha256(item) == sha256(dst):
                item.unlink()
                print(f"  collect: '{item.name}' already collected (same sha) -> deduped from inbox")
            else:
                n = 2
                while (alt := dst.with_suffix(f".v{n}.html")).exists():
                    n += 1
                shutil.move(str(item), alt)
                moved.append(alt.name)
                print(f"  collect: '{item.name}' differs from collected copy -> kept as {alt.name}")
        elif item.is_dir() and item.name.endswith("_files"):
            if not dst.exists():
                shutil.move(str(item), dst)
                moved.append(item.name)
            else:  # merge re-saved assets: move new, dedupe identical, version differing
                added = 0
                for f in sorted(item.rglob("*")):
                    if not f.is_file():
                        continue
                    rel = f.relative_to(item)
                    target = dst / rel
                    if not target.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(f), target)
                        added += 1
                    elif sha256(f) == sha256(target):
                        f.unlink()
                    else:
                        alt = target.with_name(target.stem + ".v2" + target.suffix)
                        if not alt.exists():
                            shutil.move(str(f), alt)
                            added += 1
                            print(f"  collect: asset '{rel}' differs -> kept as {alt.name}")
                        else:
                            f.unlink()
                if added:
                    moved.append(f"{item.name} (+{added} assets)")
                for d in sorted((p for p in item.rglob("*") if p.is_dir()), reverse=True):
                    if not any(d.iterdir()):
                        d.rmdir()
                if not any(item.iterdir()):
                    item.rmdir()
        elif item.is_file():
            homes = [d for d in SAVES.glob("*_files") if (d / item.name).is_file()]
            if homes and all(sha256(d / item.name) == sha256(item) for d in homes):
                item.unlink()
                print(f"  collect: loose '{item.name}' identical to collected copy -> deduped from inbox")
            elif len(homes) == 1:
                alt = (homes[0] / item.name).with_name(Path(item.name).stem + ".v2" + item.suffix)
                shutil.move(str(item), alt)
                moved.append(f"{homes[0].name}/{alt.name}")
                print(f"  collect: loose '{item.name}' differs -> kept as {alt.name}")
            else:
                loose = SAVES / "_loose"
                loose.mkdir(exist_ok=True)
                shutil.move(str(item), loose / item.name)
                moved.append(f"_loose/{item.name}")
                print(f"  collect: loose '{item.name}' has no referencing page -> _loose/ (tell the pipeline what it is)")
    return moved


# ---------------------------------------------------------------- toc

def extract_toc(landing_html: Path) -> dict:
    """Unique sub-pages per book, in reading order, from the landing page ToC."""
    soup = BeautifulSoup(landing_html.read_text(encoding="utf-8", errors="replace"), "html.parser")
    containers = soup.select(".compendium-toc-full-text") or [soup]  # one ToC block per book
    toc: dict[str, list[dict]] = {code: [] for code in BOOKS}
    seen = set()
    for container in containers:
        for a in container.find_all("a", href=True):
            m = re.match(r"https?://www\.dndbeyond\.com/sources/(?:dnd/)?paitm/(\w+)/([\w-]+)$", a["href"])
            if not m or m.group(0) in seen:
                continue
            seen.add(m.group(0))
            code, page = m.groups()
            if code in toc:
                toc[code].append({"page": page, "title": a.get_text(" ", strip=True)})
    return toc


def is_orphan(title: str, orphans: list[str]) -> bool:
    """Does an assets-only save exist for this ToC entry? Match the dir's leading
    title segment exactly (book names also appear in dirnames — substring lies)."""
    bare = re.sub(r"^(?:ch\.\s*\d+|introduction|part\s*\d+)\s*:\s*", "", title, flags=re.I).casefold()
    return any(o.split(" - ")[0].strip().casefold() == bare for o in orphans)


# ---------------------------------------------------------------- markdown

ENTITY_RE = re.compile(r"(\w+(?:-\w+)*)-tooltip$")


class PageRenderer:
    """One saved source page -> markdown + typed side-products."""

    def __init__(self, slug: str, html_path: Path, images_out: Path):
        self.slug = slug                      # paitm/sato/character-options
        self.page = slug.rsplit("/", 1)[-1]   # character-options
        self.html_path = html_path
        self.files_dir = html_path.with_name(html_path.stem + "_files")
        self.images_out = images_out          # build .../images/<page>/
        self.entities: list[dict] = []
        self.images: list[dict] = []
        self.section = ""                     # current heading anchor, for provenance
        self.lines: list[str] = []

    # -- inline -----------------------------------------------------------

    def inline(self, node) -> str:
        if isinstance(node, NavigableString):
            return "" if isinstance(node, Comment) else re.sub(r"\s+", " ", str(node))
        if not isinstance(node, Tag):
            return ""
        name = node.name
        if name in ("script", "style", "noscript", "svg", "select", "template", "button"):
            return ""
        kids = "".join(self.inline(c) for c in node.children)
        if name in ("strong", "b"):
            return f"**{kids.strip()}**" if kids.strip() else ""
        if name == "span" and any(c.endswith("-label") for c in (node.get("class") or [])):
            return f"**{kids.strip()}**" if kids.strip() else ""  # statblock field labels
        if name in ("em", "i"):
            return f"*{kids.strip()}*" if kids.strip() else ""
        if name == "br":
            return "\n"
        if name == "sup":
            return kids
        if name == "a":
            return self.link(node, kids)
        if name == "img":
            return self.image(node, inline=True)
        return kids

    def link(self, a: Tag, text: str) -> str:
        text = text.strip()
        href = a.get("href", "")
        classes = a.get("class") or []
        if not text and not a.get_text(strip=True):
            return ""  # heading self-anchor decoration
        etype = next((m.group(1) for c in classes if (m := ENTITY_RE.search(c))), None)
        if "tooltip-hover" in classes or etype:
            self.record_entity(etype or "unknown", text, href)
            return text
        if re.search(r"\.(jpe?g|png|webp)(\?|$)", href, re.I) and href.startswith(("http:", "https:")):
            # link-target asset (e.g. 'View Player Version' battle maps) — a page
            # save never downloads these; localize via basename mirror in _files
            base = Path(urllib.parse.urlparse(href).path).name
            cand = self.files_dir / base
            rec = {"page": self.page, "src_section": self.section, "role": "player-map",
                   "caption": text, "artist": "", "alt": ""}
            if cand.is_file():
                self.images_out.mkdir(parents=True, exist_ok=True)
                dst = self.images_out / base
                if not dst.exists():
                    shutil.copy2(cand, dst)
                rec["file"] = f"images/{self.page}/{base}"
                self.images.append(rec)
                return f"[{text}]({rec['file']})"
            rec["file"] = None
            rec["url"] = href
            self.images.append(rec)
            return f"[{text}]({href})"
        if "dndbeyond.com" in href or href.startswith(("#", "./", "/")):
            kind = "source-xref" if "sourcebook" in classes else "xref"
            self.record_entity(kind, text, href)
            return text
        return f"[{text}]({href})" if href.startswith("http") else text

    def record_entity(self, etype: str, name: str, href: str):
        self.entities.append({
            "type": etype, "name": name, "href": href,
            "src": f"{self.slug}#{self.section}" if self.section else self.slug,
        })

    # -- images -----------------------------------------------------------

    def image(self, img: Tag, inline=False, caption="", artist="") -> str:
        src = urllib.parse.unquote(img.get("src", ""))
        if not src:
            return ""
        rec = {"page": self.page, "src_section": self.section, "role": "art",
               "caption": caption, "artist": artist, "alt": img.get("alt", "")}
        local = None
        if not src.startswith(("http:", "https:", "data:")):
            cand = (self.html_path.parent / src).resolve()
            if cand.is_file():
                local = cand
        else:
            # lazy-loaded imgs keep CDN srcs; localize if a mirror by basename
            # was dropped into the save's _files dir (see MISSING.md §4)
            cand = self.files_dir / Path(urllib.parse.urlparse(src).path).name
            if cand.is_file():
                local = cand
        if local:
            self.images_out.mkdir(parents=True, exist_ok=True)
            dst = self.images_out / local.name
            if not dst.exists():
                shutil.copy2(local, dst)
            rel = f"images/{self.page}/{local.name}"
            rec["file"] = rel
            self.images.append(rec)
            label = caption or img.get("alt", "") or local.stem
            return f"![{label}]({rel})"
        if src.startswith(("http:", "https:")):
            rec["file"] = None
            rec["url"] = src
            self.images.append(rec)
            return f"![{caption or img.get('alt','')}]({src})"
        return ""

    # -- blocks -----------------------------------------------------------

    def emit(self, text=""):
        self.lines.append(text)

    def block(self, node: Tag):
        for child in node.children:
            if isinstance(child, NavigableString):
                if not isinstance(child, Comment) and child.strip():
                    self.emit(re.sub(r"\s+", " ", str(child)).strip())
                    self.emit()
                continue
            if not isinstance(child, Tag):
                continue
            name = child.name
            classes = child.get("class") or []
            if name in ("script", "style", "noscript", "svg", "template") or "nav-select" in classes:
                continue
            if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.heading(child)
            elif name == "p":
                text = self.inline(child).strip()
                if text:
                    if any(c.endswith(("--action-header", "-header")) for c in classes):
                        self.emit(f"#### {text}")  # statblock section cue (Actions / Bonus Actions / …)
                    else:
                        self.emit(text)
                    self.emit()
            elif name in ("ul", "ol"):
                self.list_block(child)
                self.emit()
            elif name in ("div", "span", "section") and self.block_extra(child, classes):
                pass
            elif name == "div" and "monster--stats" in classes:
                # ability grid: flat <p> label/value pairs -> one compact table
                cells = [self.inline(p).strip() for p in child.find_all("p", recursive=False)]
                labels, values = cells[0::2], cells[1::2]
                if labels and len(labels) == len(values):
                    self.emit("| " + " | ".join(labels) + " |")
                    self.emit("|" + "|".join([" --- "] * len(labels)) + "|")
                    self.emit("| " + " | ".join(values) + " |")
                    self.emit()
                else:  # unexpected shape: fall back to generic descent
                    self.block(child)
            elif name == "table" or (name == "div" and "table-overflow-wrapper" in classes):
                t = child if name == "table" else child.find("table")
                if t:
                    self.table(t)
            elif name == "figure":
                self.figure(child)
            elif name == "aside" or "text--rules-sidebar" in classes or "text--quote-box" in classes:
                self.aside(child)
            elif name == "blockquote":
                inner = PageRenderer.render_sub(self, child)
                for ln in inner.strip().splitlines():
                    self.emit(f"> {ln}")
                self.emit()
            elif name == "hr":
                self.emit("---")
                self.emit()
            elif name == "img":
                md = self.image(child)
                if md:
                    self.emit(md)
                    self.emit()
            else:  # div/section/span wrappers (incl. stat-block frames): descend
                self.block(child)

    @staticmethod
    def render_sub(parent: "PageRenderer", node: Tag) -> str:
        sub = object.__new__(PageRenderer)
        sub.__dict__.update(parent.__dict__)
        sub.lines = []
        sub.block(node)
        parent.entities, parent.images = sub.entities, sub.images
        return "\n".join(sub.lines)

    def heading(self, h: Tag):
        level = int(h.name[1])
        text = self.inline(h).strip()
        if not text:
            return
        hid = h.get("id", "")
        if hid:
            self.section = hid
            self.emit(f"<!-- src:{self.slug}#{hid} -->")
        self.emit(f"{'#' * level} {text}")
        self.emit()

    def list_block(self, node: Tag, depth=0):
        ordered = node.name == "ol"
        for i, li in enumerate(node.find_all("li", recursive=False), 1):
            sublists = li.find_all(("ul", "ol"), recursive=False)
            for s in sublists:
                s.extract()
            marker = f"{i}." if ordered else "-"
            text = self.inline(li).strip()
            self.emit(f"{'  ' * depth}{marker} {text}")
            for s in sublists:
                self.list_block(s, depth + 1)

    def table(self, t: Tag):
        cap = t.find("caption")
        if cap:
            self.emit(f"**{self.inline(cap).strip()}**")
            self.emit()
        rows = []
        for tr in t.find_all("tr"):
            cells = []
            for cell in tr.find_all(("th", "td")):
                txt = self.inline(cell).strip().replace("\n", " ").replace("|", "\\|")
                cells.append(txt)
                span = int(cell.get("colspan", 1) or 1)
                cells.extend([""] * (span - 1))
            rows.append(cells)
        if not rows:
            return
        width = max(len(r) for r in rows)
        rows = [r + [""] * (width - len(r)) for r in rows]
        header, *body = rows
        self.emit("| " + " | ".join(header) + " |")
        self.emit("|" + "|".join([" --- "] * width) + "|")
        for r in body:
            self.emit("| " + " | ".join(r) + " |")
        self.emit()

    def figure(self, fig: Tag):
        fid = fig.get("id", "")
        if fid:
            self.section = fid
            self.emit(f"<!-- src:{self.slug}#{fid} figure -->")
        artist = fig.find("span", class_="artist-credit")
        artist_txt = artist.get_text(" ", strip=True) if artist else ""
        figcap = fig.find("figcaption")
        cap_txt = figcap.get_text(" ", strip=True) if figcap else ""
        img = fig.find("img")
        if img:
            md = self.image(img, caption=cap_txt, artist=artist_txt)
            if md:
                self.emit(md)
        if figcap:
            # render through inline() — figcaptions carry real links
            # (e.g. 'View Player Version' battle maps that need localizing)
            cap_md = self.inline(figcap).strip()
            if cap_md:
                self.emit(f"*{cap_md}*")
        if artist_txt:
            self.emit(f"*Art: {artist_txt}*")
        self.emit()

    QUOTE_ASIDES = ("epigraph", "text--mimir-notes", "text--morte-notes",
                    "text--read-aloud", "text--quote-box")  # quote-box = read-aloud narration

    def aside(self, node: Tag):
        classes = node.get("class") or []
        kind = next((c for c in classes if c in self.QUOTE_ASIDES or c.startswith("text--")), "sidebar")
        hid = node.get("id", "")
        if hid:
            self.section = hid
            self.emit(f"<!-- src:{self.slug}#{hid} aside:{kind} -->")
        elif kind != "sidebar":
            self.emit(f"<!-- aside:{kind} -->")
        inner = PageRenderer.render_sub(self, node).strip()
        lines = inner.splitlines()
        # titled rules sidebars get their first line bolded; quote asides
        # (epigraphs, mimir/morte notes, read-alouds) stay plain quotation
        if kind not in self.QUOTE_ASIDES:
            for i, ln in enumerate(lines):
                if ln.strip():
                    if not ln.startswith(("#", "|", "<!--", "!", ">", "*", "-")):
                        lines[i] = f"**{ln.strip()}**"
                    break
        for ln in lines:
            self.emit(f"> {ln}" if ln.strip() else ">")
        self.emit()

    # -- entry ------------------------------------------------------------

    INLINE_ROW_RE = re.compile(
        r"mon-stat-block__(?:attribute|tidbit|meta|name)$|^ddb-statblock-item$")

    def block_extra(self, child: Tag, classes: list[str]) -> bool:
        """Tooltip-page (compendium) markup. Returns True if handled."""
        if any(self.INLINE_ROW_RE.search(c) for c in classes):
            text = self.inline(child).strip()
            if text and text != getattr(self, "page_heading", None):  # name row dupes the ## heading
                self.emit(re.sub(r"\s+", " ", text))
                self.emit()
            return True
        if "ability-block" in classes:
            labels = [d.get_text(" ", strip=True) for d in child.select(".ability-block__heading")]
            values = [d.get_text(" ", strip=True) for d in child.select(".ability-block__data")]
            if labels and len(labels) == len(values):
                self.emit("| " + " | ".join(labels) + " |")
                self.emit("|" + "|".join([" --- "] * len(labels)) + "|")
                self.emit("| " + " | ".join(values) + " |")
                self.emit()
                return True
        if "mon-stat-block__separator" in classes:
            return True
        return False

    ROOTS = (".p-article-content", ".detail-content", ".details-container-content")

    def render(self, heading: str | None = None) -> str:
        soup = BeautifulSoup(self.html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
        art = next((el for sel in self.ROOTS if (el := soup.select_one(sel))), None)
        if art is None:
            raise ValueError(f"no known content container in {self.html_path.name}")
        self.emit(f"<!-- src:{self.slug} sha256:{sha256(self.html_path)} -->")
        if heading:
            self.page_heading = heading
            self.emit(f"## {heading}")
            self.emit()
        self.block(art)
        md = "\n".join(self.lines)
        return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


# ---------------------------------------------------------------- build

CAPTURE_TYPES = ("monsters", "spells", "magic-items", "equipment", "feats", "backgrounds")


def canonical_url(soup: BeautifulSoup) -> str | None:
    el = soup.find("link", rel="canonical") or soup.find("meta", property="og:url")
    return el and (el.get("href") or el.get("content"))


def discover() -> tuple[dict[str, Path], Path | None, list[str]]:
    pages, landing, orphans, _, _, _ = discover_all()
    return pages, landing, orphans


def discover_all():
    """Classify every saved html: product page / tooltip capture / foreign / junk.
    Nothing in the saves folder may go unaccounted — silence is how content rots."""
    pages: dict[str, Path] = {}
    captures: dict[str, list[Path]] = {}   # 'monsters/16789-archmage' -> [paths] (dupes kept)
    foreign: list[tuple[str, Path]] = []
    junk: list[tuple[str, Path]] = []
    landing = None
    htmls = set()
    for f in sorted(SAVES.glob("*.htm*")):
        soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="replace"), "html.parser")
        url = canonical_url(soup)
        htmls.add(f.stem)
        path = urllib.parse.urlparse(url).path.strip("/") if url else ""
        slug = canonical_slug(soup)
        if slug == "dnd/paitm":
            landing = f
        elif slug and slug.startswith("paitm/"):
            pages[slug.removeprefix("paitm/")] = f  # 'sato/character-options'
        elif path.split("/")[0] in CAPTURE_TYPES:
            captures.setdefault(path, []).append(f)
        elif url and "marketplace." in url:
            junk.append((url, f))
        else:
            foreign.append((url or f"(no canonical: {f.name})", f))
    orphans = [d.name.removesuffix("_files") for d in sorted(SAVES.glob("*_files"))
               if d.is_dir() and d.name.removesuffix("_files") not in htmls]
    return pages, landing, orphans, captures, foreign, junk


def build(toc: dict, pages: dict[str, Path], orphans: list[str]) -> dict:
    today = date.today().isoformat()
    coverage = {}
    for code, (component, title) in BOOKS.items():
        comp_dir = BUILD / component
        comp_dir.mkdir(parents=True, exist_ok=True)
        body, sources, all_entities, all_images = [], [], [], []
        n_saved = 0
        for entry in toc.get(code, []):
            key = f"{code}/{entry['page']}"
            slug = f"paitm/{key}"
            url = f"https://www.dndbeyond.com/sources/dnd/{slug}"
            if key in pages:
                r = PageRenderer(slug, pages[key], comp_dir / "images" / entry["page"])
                body.append(r.render())
                sources.append({
                    "slug": slug, "title": entry["title"], "url": url,
                    "file": str(pages[key].relative_to(ROOT)),
                    "sha256": sha256(pages[key]), "saved": True,
                })
                all_entities.extend(r.entities)
                all_images.extend(r.images)
                n_saved += 1
            else:
                assets_only = is_orphan(entry["title"], orphans)
                state = "ASSETS-ONLY (re-save: html missing)" if assets_only else "MISSING (not saved)"
                body.append(f"<!-- src:{slug} {state} url:{url} -->\n")
                sources.append({"slug": slug, "title": entry["title"], "url": url,
                                "saved": False, "assets_only": assets_only})
        total = len(toc.get(code, []))
        front = "\n".join([
            "---",
            f"title: {title} — Planescape: Adventures in the Multiverse (5e)",
            f"component: {component}",
            "edition: 5e",
            f"pages_saved: {n_saved}/{total}",
            "pipeline: dndbeyond-html v0 (authoritative digital text; no OCR, no grades)",
            "---", "",
        ])
        (comp_dir / "book.md").write_text(front + "\n\n".join(body), encoding="utf-8")
        (comp_dir / "source.json").write_text(json.dumps({
            "product": "Planescape: Adventures in the Multiverse (5e)",
            "product_slug": PRODUCT_SLUG, "component": component, "edition": "5e",
            "ocr": "dndbeyond-html-save", "registered": today,
            "license_note": LICENSE_NOTE, "pages": sources,
        }, indent=1), encoding="utf-8")
        (comp_dir / "images.json").write_text(json.dumps(all_images, indent=1), encoding="utf-8")
        (comp_dir / "entities.json").write_text(json.dumps(all_entities, indent=1), encoding="utf-8")
        coverage[code] = sources
    return coverage


def build_captures(captures: dict[str, list[Path]]) -> dict:
    """Render tooltip-page captures (monsters/spells/items/equipment) into
    build/<product>/_compendium-captures/<type>.md + captures.json."""
    if not captures:
        return {}
    out_dir = BUILD / "_compendium-captures"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    bodies: dict[str, list[tuple[str, str]]] = {}
    today = date.today().isoformat()
    for path_slug, files in sorted(captures.items()):
        uniq: dict[str, Path] = {}
        for f in sorted(files, key=lambda p: len(p.name)):
            uniq.setdefault(sha256(f), f)
        f = sorted(uniq.values(), key=lambda p: p.stat().st_mtime)[-1]  # newest distinct save
        ctype, entry = path_slug.split("/", 1)
        soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="replace"), "html.parser")
        title = (soup.title.get_text() if soup.title else entry).split(" - ")[0].strip()
        r = PageRenderer(path_slug, f, out_dir / "images" / entry)
        try:
            md = r.render(heading=title)
        except ValueError as e:
            print(f"  captures: SKIP {f.name}: {e}")
            continue
        bodies.setdefault(ctype, []).append((title, md))
        manifest[path_slug] = {
            "title": title, "type": ctype, "file": str(f.relative_to(ROOT)),
            "sha256": sha256(f), "url": f"https://www.dndbeyond.com/{path_slug}",
            "duplicate_saves": len(files) - 1,
        }
    for ctype, entries in bodies.items():
        front = "\n".join([
            "---",
            f"title: Compendium captures — {ctype} (hand-saved D&D Beyond tooltip pages)",
            f"entries: {len(entries)}",
            "pipeline: dndbeyond-html v0 (tooltip-page capture)",
            f"registered: {today}",
            "---", "",
        ])
        body = "\n\n".join(md for _t, md in sorted(entries))
        (out_dir / f"{ctype}.md").write_text(front + body, encoding="utf-8")
    (out_dir / "captures.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def write_status(coverage: dict, landing: Path | None,
                 manifest: dict | None = None, foreign: list | None = None,
                 junk: list | None = None) -> str:
    out = ["# Planescape: Adventures in the Multiverse — D&D Beyond capture status", ""]
    out.append(f"Landing page (ToC source): {'saved' if landing else 'MISSING — save https://www.dndbeyond.com/sources/dnd/paitm'}")
    out.append("")
    resave, missing = [], []
    for code, (component, title) in BOOKS.items():
        srcs = coverage.get(code, [])
        n = sum(1 for s in srcs if s["saved"])
        out.append(f"## {title} — {n}/{len(srcs)}")
        for s in srcs:
            if s["saved"]:
                mark = "✅"
            elif s.get("assets_only"):
                mark = "⚠ assets-only — **re-save** (html never hit disk)"
                resave.append(s)
            else:
                mark = "☐ not saved"
                missing.append(s)
            out.append(f"- {mark} {s['title']} — <{s['url']}>")
        out.append("")
    if resave or missing:
        out.append("## To capture (Ctrl+S → 'Webpage, Complete' → into the root `D&D Beyond/` folder, then `python pipeline/extract/dndbeyond.py ingest`)")
        for s in resave + missing:
            out.append(f"- {s['url']}")
        out.append("")
    if manifest:
        from collections import Counter as _C
        counts = _C(m["type"] for m in manifest.values())
        out.append(f"## Compendium captures (hand-saved tooltip pages) — {len(manifest)} entries")
        out.append("- " + ", ".join(f"{t}: {n}" for t, n in sorted(counts.items())) +
                   " → `_compendium-captures/<type>.md`")
        out.append("")
    if foreign:
        out.append("## Foreign captures (other products — NOT indexed; say the word to wire them up)")
        for url, f in sorted(set(foreign)):
            out.append(f"- {f.name} — <{url}>")
        out.append("")
    if junk:
        out.append("## Junk captures (storefront pages, no game content — safe to delete)")
        for url, f in sorted(set(junk)):
            out.append(f"- {f.name} — <{url}>")
        out.append("")
    text = "\n".join(out)
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "STATUS.md").write_text(text, encoding="utf-8")
    return text


# ---------------------------------------------------------------- verify

WORD_RE = re.compile(r"[A-Za-z0-9’'’-]+")


def html_words(html_path: Path) -> list[str]:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    art = next((el for sel in PageRenderer.ROOTS if (el := soup.select_one(sel))), None)
    for el in art.find_all(("script", "style", "noscript", "svg", "select", "template", "button")):
        el.decompose()
    return WORD_RE.findall(art.get_text(" "))


def md_words(segment: str) -> list[str]:
    s = re.sub(r"<!--.*?-->", " ", segment, flags=re.S)
    s = re.sub(r"^\|[-| ]+\|$", " ", s, flags=re.M)        # table separator rows
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r" \1 ", s)      # images -> alt text
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r" \1 ", s)       # links -> text
    s = re.sub(r"^\*Art: .*?\*$", " ", s, flags=re.M)      # our added credit lines
    return WORD_RE.findall(s)


def verify(pages: dict[str, Path]) -> bool:
    """Conservation + integrity gate. Word counts per page (html vs book.md
    segment), every image/path on disk, sha agreement. Fails loud."""
    ok = True
    for code, (component, _title) in BOOKS.items():
        comp_dir = BUILD / component
        book = comp_dir / "book.md"
        if not book.is_file():
            continue
        text = book.read_text(encoding="utf-8")
        src = json.loads((comp_dir / "source.json").read_text(encoding="utf-8"))
        # split book.md into per-page segments on the sha markers
        marks = [(m.start(), m.group(1), m.group(2)) for m in
                 re.finditer(r"<!-- src:paitm/(\w+/[\w-]+) sha256:([0-9a-f]{64}) -->", text)]
        segs = {slug.split("/", 1)[1]: (text[a: marks[i + 1][0] if i + 1 < len(marks) else len(text)], sha)
                for i, (a, slug, sha) in enumerate(marks)}
        for p in src["pages"]:
            if not p.get("saved"):
                continue
            key = p["slug"].removeprefix("paitm/")
            page = key.split("/", 1)[1]
            seg, md_sha = segs.get(page, ("", None))
            f = pages.get(key)
            problems = []
            if f is None or md_sha is None:
                problems.append("page segment missing from book.md")
            else:
                disk_sha = sha256(f)
                if not (md_sha == p["sha256"] == disk_sha):
                    problems.append(f"sha drift (md:{md_sha[:8]} json:{p['sha256'][:8]} disk:{disk_sha[:8]})")
                hw, mw = html_words(f), md_words(seg)
                ratio = len(mw) / max(1, len(hw))
                if not (0.98 <= ratio <= 1.06):
                    missing = Counter(w.casefold() for w in hw) - Counter(w.casefold() for w in mw)
                    top = ", ".join(f"{w}×{n}" for w, n in missing.most_common(8))
                    problems.append(f"word conservation {ratio:.3f} ({len(mw)}/{len(hw)}); top missing: {top}")
            for prob in problems:
                ok = False
                print(f"  VERIFY FAIL {key}: {prob}")
        # every image path referenced by book.md and images.json exists
        for rel in re.findall(r"\]\((images/[^)]+)\)", text):
            if not (comp_dir / urllib.parse.unquote(rel)).is_file():
                ok = False
                print(f"  VERIFY FAIL {component}: missing file {rel}")
        for rec in json.loads((comp_dir / "images.json").read_text(encoding="utf-8")):
            if rec.get("file") and not (comp_dir / rec["file"]).is_file():
                ok = False
                print(f"  VERIFY FAIL {component}: images.json entry not on disk: {rec['file']}")
    # tooltip captures: sha agreement + word conservation per entry
    cj = BUILD / "_compendium-captures" / "captures.json"
    if cj.is_file():
        manifest = json.loads(cj.read_text(encoding="utf-8"))
        segs: dict[str, str] = {}
        for md_file in (BUILD / "_compendium-captures").glob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            marks = [(m.start(), m.group(1)) for m in
                     re.finditer(r"<!-- src:([\w./ ’'-]+/[\w./ ’'-]+) sha256:[0-9a-f]{64} -->", text)]
            for i, (a, slug) in enumerate(marks):
                segs[slug] = text[a: marks[i + 1][0] if i + 1 < len(marks) else len(text)]
        for slug, m in manifest.items():
            f = ROOT / m["file"]
            if not f.is_file():
                ok = False
                print(f"  VERIFY FAIL capture {slug}: source file gone: {m['file']}")
                continue
            if sha256(f) != m["sha256"]:
                ok = False
                print(f"  VERIFY FAIL capture {slug}: sha drift vs manifest")
            seg = segs.get(slug)
            if seg is None:
                ok = False
                print(f"  VERIFY FAIL capture {slug}: no segment in {m['type']}.md")
                continue
            hw, mw = html_words(f), md_words(seg)
            ratio = len(mw) / max(1, len(hw))
            if len(hw) >= 120 and not (0.95 <= ratio <= 1.15):
                ok = False
                print(f"  VERIFY FAIL capture {slug}: word conservation {ratio:.3f} ({len(mw)}/{len(hw)})")
    print("verify: " + ("ALL CLEAN" if ok else "FAILURES — see above"))
    return ok


# ---------------------------------------------------------------- audit

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.casefold())


def name_variants(name: str) -> set[str]:
    """Normalized candidates tolerant of plural/parenthetical drift:
    'swarms of sunflies' must hit anchor 'SwarmofSunflies'."""
    base = re.sub(r"[\(\[].*?[\)\]]", "", name).strip()
    cands = {base}
    if base.endswith(("s", "i")):
        cands.add(base[:-1])
    if base.endswith("es"):
        cands.add(base[:-2])
    if base.endswith("ies"):
        cands.add(base[:-3] + "y")
    m = re.match(r"^swarms? of (.+)$", base, re.I)
    if m:
        inner = m.group(1)
        cands |= {f"{inner} swarm", f"{inner.rstrip('s')} swarm"}
    toks = base.split()
    if len(toks) > 1:
        def sing(t):
            if t.endswith("ies"):
                return t[:-3] + "y"
            return t[:-1] if t.endswith("s") and len(t) > 3 else t
        cands.add(" ".join(sing(t) for t in toks))            # all tokens
        cands.add(" ".join([sing(toks[0])] + toks[1:]))       # 'swarms of X' -> 'swarm of X'
        cands.add(" ".join(toks[:-1] + [sing(toks[-1])]))     # trailing plural only
        cands.add(" ".join(sorted(sing(t) for t in toks)))    # word-order drift
    return {norm(c) for c in cands if c}


def extract_toc_anchors(landing_html: Path) -> dict[str, list[dict]]:
    """All ToC entries incl. #fragments: page-key -> [{anchor,title},...]."""
    soup = BeautifulSoup(landing_html.read_text(encoding="utf-8", errors="replace"), "html.parser")
    out: dict[str, list[dict]] = {}
    for container in soup.select(".compendium-toc-full-text"):
        for a in container.find_all("a", href=True):
            m = re.match(r"https?://www\.dndbeyond\.com/sources/(?:dnd/)?paitm/(\w+)/([\w-]+)#(\w+)$", a["href"])
            if m:
                code, page, frag = m.groups()
                out.setdefault(f"{code}/{page}", []).append(
                    {"anchor": frag, "title": a.get_text(" ", strip=True)})
    return out


def audit(toc: dict, toc_anchors: dict, pages: dict[str, Path], orphans: list[str],
          manifest: dict | None = None):
    """EXACT gap report: pages to re-save, sections lost inside saved pages,
    hover-only entity content, remote-only images, physical-only components."""
    page_ids: dict[str, set] = {}      # page-key -> all element ids in saved html
    remote_imgs: list[dict] = []
    statblock_names: set[str] = set()   # adventure statblocks have no element ids
    for key, f in pages.items():
        soup = BeautifulSoup(f.read_text(encoding="utf-8", errors="replace"), "html.parser")
        art = soup.select_one(".p-article-content")
        page_ids[key] = {el["id"] for el in (art or soup).find_all(id=True)}
        for sb in (art or soup).select(".monster--stat-block"):
            h = sb.find(("h3", "h4", "h5")) or sb.find("p")
            if h:
                statblock_names.add(h.get_text(" ", strip=True))
        for el in (art or soup).find_all(("a", "img")):
            url = el.get("href") if el.name == "a" else el.get("src")
            if not url or not re.search(r"\.(jpe?g|png|webp)(\?|$)", url, re.I):
                continue
            if url.startswith(("http:", "https:")):  # never localized by the save
                base = Path(urllib.parse.urlparse(url).path).name
                if (f.with_name(f.stem + "_files") / base).is_file():
                    continue  # basename mirror present -> ingest localizes it
                label = el.get_text(" ", strip=True) or el.get("alt", "") or el.get("data-title", "")
                remote_imgs.append({"page": key, "url": url.split("?")[0], "label": label})

    # 1. page-level
    missing_pages, assets_only_pages = [], []
    for code in BOOKS:
        for e in toc[code]:
            key = f"{code}/{e['page']}"
            if key in pages:
                continue
            url = f"https://www.dndbeyond.com/sources/dnd/paitm/{key}"
            (assets_only_pages if is_orphan(e["title"], orphans) else missing_pages).append(
                {"key": key, "title": e["title"], "url": url, "book": BOOKS[code][1]})

    # 2. section-level inside saved pages (lazy-render losses)
    lost_sections = []
    for key, expected in toc_anchors.items():
        if key not in pages:
            continue
        for ent in expected:
            if ent["anchor"] not in page_ids[key]:
                lost_sections.append({"page": key, **ent})

    # 3. entity-level: where does each referenced entity's full text live?
    captured_ids = set().union(*page_ids.values()) if page_ids else set()
    captured_ids |= {re.sub(r"statblock$", "", i, flags=re.I) for i in captured_ids}  # 'Sytristatblock' -> 'Sytri'
    captured_ids |= statblock_names
    captured_norm = {norm(i) for i in captured_ids}
    bestiary_anchors = {norm(e["anchor"]): e["title"] for e in toc_anchors.get("mpp/bestiary-a-to-z", [])}
    ents: dict[tuple, dict] = {}
    for comp_dir in BUILD.iterdir():
        ej = comp_dir / "entities.json"
        if not ej.is_file():
            continue
        for x in json.loads(ej.read_text(encoding="utf-8")):
            if x["type"] in ("xref", "source-xref", "skill", "condition", "rule", "unknown"):
                continue  # core-rules noise / internal links
            k = (x["type"], norm(x["name"]))
            if x["name"] and k not in ents:
                ents[k] = x
    captured_sorted_norm = {norm(" ".join(sorted(re.findall(r"[A-Z][a-z0-9]*|[a-z0-9]+", i)))) for i in captured_ids}
    capture_paths = set(manifest or {})
    inline_ok, in_unsaved_bestiary, captured_tooltip, external = [], [], [], []
    AGE_WORDS = {"adult", "ancient", "young"}  # bare link-split artifacts of dragon entries
    for (etype, n), x in sorted(ents.items()):
        if n in AGE_WORDS:
            continue
        vs = name_variants(x["name"])
        href_path = urllib.parse.urlparse(x.get("href", "")).path.strip("/")
        if vs & captured_norm or n in captured_norm or vs & captured_sorted_norm:
            inline_ok.append(x)            # full text already captured on a saved page
        elif href_path in capture_paths:
            captured_tooltip.append(x)     # hand-saved tooltip page covers it
        elif etype == "monster" and (n in bestiary_anchors or vs & set(bestiary_anchors)):
            in_unsaved_bestiary.append(x)  # lands when bestiary html is saved
        else:
            external.append(x)             # lives outside this product: hover/snapshot or other owned source

    # ---- write
    out = ["# PAitM — EXACT missing-content audit", ""]
    out.append("## 1. Whole pages")
    if not (missing_pages or assets_only_pages):
        out.append("- none — all 13 book pages captured ✅")
    for p in assets_only_pages:
        out.append(f"- ⚠ **{p['book']} / {p['title']}** — assets on disk, html never written. RE-SAVE: <{p['url']}>")
    for p in missing_pages:
        out.append(f"- ☐ **{p['book']} / {p['title']}** — not saved. SAVE: <{p['url']}>")
    out.append("")
    out.append("## 2. Sections lost inside saved pages (save rendered incompletely)")
    if lost_sections:
        for s in lost_sections:
            out.append(f"- {s['page']}#{s['anchor']} — “{s['title']}”")
    else:
        out.append("- none — every ToC anchor present in its saved page ✅")
    out.append("")
    out.append("## 3. Hover/tooltip content (referenced, full text NOT in this product's captures)")
    out.append(f"- {len(inline_ok)} referenced entities already have full text inline in captured pages — no action")
    if captured_tooltip:
        out.append(f"- {len(captured_tooltip)} resolved by hand-saved tooltip pages (`_compendium-captures/`): "
                   + ", ".join(sorted({x['name'] for x in captured_tooltip}, key=str.casefold)))
    if in_unsaved_bestiary:
        out.append(f"- {len(in_unsaved_bestiary)} monster refs resolve to **Bestiary A to Z** — fixed automatically once you re-save that one page:")
        names = sorted({x['name'] for x in in_unsaved_bestiary})
        out.append(f"  - {', '.join(names)}")
    if external:
        unsaved_books = sorted({BOOKS[code][1] for code in BOOKS for e in toc[code]
                                if f"{code}/{e['page']}" not in pages})
        out.append(f"- {len(external)} distinct entities live OUTSIDE this product (Monster Manual / PHB / DMG / MotM pages on D&D Beyond).")
        if unsaved_books:
            out.append(f"  NOTE: some may actually live in still-unsaved pages ({', '.join(unsaved_books)} — e.g. adventure NPC statblocks like Morte) and will reclassify on the next ingest after you save those.")
        out.append("  These are *references*, not book content — the book text is complete without them. Hover-snapshot only if you want them local:")
        by_type: dict[str, dict] = {}
        for x in external:
            by_type.setdefault(x["type"], {}).setdefault(norm(x["name"]), x["name"])
        for t, names in sorted(by_type.items()):
            shown = sorted(names.values(), key=str.casefold)
            out.append(f"  - **{t}** ({len(shown)}): {', '.join(shown)}")
    out.append("")
    out.append("## 4. Images that stayed remote in the saves (not on disk)")
    if remote_imgs:
        seen = set()
        for r in remote_imgs:
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            out.append(f"- {r['page']}: {r['label'] or '(unlabeled)'} — <{r['url']}>")
        out.append("  (two causes: lazy-load imgs that never scrolled into view before Ctrl+S, and link-target")
        out.append("   assets like 'View Player Version' maps, which a page save NEVER downloads.")
        out.append("   Fix A (lazy imgs only): scroll the whole page to the bottom, then re-save.")
        out.append("   Fix B (both): download each URL into the page's `_files` dir keeping the basename — ingest localizes by basename match.)")
    else:
        out.append("- none — every image referenced by saved pages is on disk ✅")
    out.append("")
    out.append("## 5. Physical-only components (no D&D Beyond page exists — meatspace photo territory)")
    out.append("- Double-sided poster map (Sigil / the Outlands) — chapter art includes downscaled versions; the poster is the high-res source")
    out.append("- DM screen (4-panel, slipcase edition)")
    out.append("- Slipcase + cover art as physical artifacts (covers do appear as page art)")
    text = "\n".join(out) + "\n"
    (BUILD / "MISSING.md").write_text(text, encoding="utf-8")
    return text


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "ingest"
    moved = collect()
    if moved:
        print(f"collected {len(moved)} item(s) from inbox:")
        for m in moved:
            print(f"  + {m}")
    pages, landing, orphans, captures, foreign, junk = discover_all()
    if landing is None:
        sys.exit("FATAL: landing page save not found (need its ToC) — save https://www.dndbeyond.com/sources/dnd/paitm")
    toc = extract_toc(landing)
    (BUILD).mkdir(parents=True, exist_ok=True)
    (BUILD / "toc.json").write_text(json.dumps(toc, indent=1), encoding="utf-8")
    cj = BUILD / "_compendium-captures" / "captures.json"
    if cmd == "status":
        manifest = json.loads(cj.read_text(encoding="utf-8")) if cj.is_file() else {}
        coverage = {}
        for code in BOOKS:
            coverage[code] = [{"slug": f"paitm/{code}/{e['page']}", "title": e["title"],
                               "url": f"https://www.dndbeyond.com/sources/dnd/paitm/{code}/{e['page']}",
                               "saved": f"{code}/{e['page']}" in pages,
                               "assets_only": is_orphan(e["title"], orphans)}
                              for e in toc[code]]
        print(write_status(coverage, landing, manifest, foreign, junk))
        return
    if cmd == "audit":
        manifest = json.loads(cj.read_text(encoding="utf-8")) if cj.is_file() else {}
        print(audit(toc, extract_toc_anchors(landing), pages, orphans, manifest))
        return
    if cmd == "verify":
        sys.exit(0 if verify(pages) else 1)
    coverage = build(toc, pages, orphans)
    manifest = build_captures(captures)
    print(write_status(coverage, landing, manifest, foreign, junk))
    audit(toc, extract_toc_anchors(landing), pages, orphans, manifest)
    n_pages = sum(1 for s in sum(coverage.values(), []) if s["saved"])
    print(f"built {n_pages} page(s) + {len(manifest)} capture(s) -> {BUILD.relative_to(ROOT)} (+ MISSING.md audit)")
    verify(pages)


if __name__ == "__main__":
    main()
