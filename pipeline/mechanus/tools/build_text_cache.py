"""Build per-page text caches for the rules-lawyer agents (lemure / abishai).

content/ is immutable; caches land in build/mechanus/<slug>-text/p0NNN.txt,
one file per page, 1-based PDF page index. Filenames are PDF indices — the
printed footer number can differ; each cache's INDEX.md records the measured
offset, and a citation must use the PRINTED page.

Normalization mirrors the extract-pipeline lessons (CLAUDE.md "Windows
gotchas"): ligatures, NBSP/CR soup, and typographic quotes are folded to
grep-able ASCII before writing. Re-running is idempotent (full rewrite).

Usage:  py -3.13 pipeline/mechanus/tools/build_text_cache.py [slug ...]
"""
from __future__ import annotations

import hashlib
import re
import sys
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[3]

SOURCES: dict[str, Path] = {
    "fgg": ROOT / "content/retroclones/for-gold-and-glory/For_Gold_and_Glory_2e_retroclone.pdf",
    "srd51": ROOT / "content/srd/srd-5.1/SRD_CC_v5.1.pdf",
    "srd52": ROOT / "content/srd/srd-5.2/SRD_CC_v5.2.1.pdf",
}

# fold to grep-able ASCII; keep it conservative — text content, not layout
FOLD = str.maketrans({
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "\xa0": " ", "\r": "", "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "--", "−": "-", "•": "*",
})


def build(slug: str) -> str:
    pdf = SOURCES[slug]
    out = ROOT / "build" / "mechanus" / f"{slug}-text"
    out.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    doc = fitz.open(pdf)
    chars = 0
    for i, page in enumerate(doc, start=1):
        text = page.get_text().translate(FOLD)
        # SRD 5.1 extracts inter-word gaps as "\t  " soup (the CLAUDE.md
        # gotcha) — collapse horizontal whitespace so phrases grep cleanly
        text = re.sub(r"[ \t]+", " ", text)
        text = "\n".join(line.rstrip() for line in text.splitlines())
        chars += len(text)
        (out / f"p{i:04d}.txt").write_text(text, encoding="utf-8", newline="\n")
    n = doc.page_count
    doc.close()
    (out / "INDEX.md").write_text(
        f"# {slug} page-text cache\n\n"
        f"- source: `{pdf.relative_to(ROOT).as_posix()}`\n"
        f"- sha256: `{sha}`\n"
        f"- pages: {n} (`p0001.txt`..`p{n:04d}.txt`, 1-based PDF index)\n"
        f"- extracted: {date.today().isoformat()} via PyMuPDF {fitz.__doc__ and fitz.version[0]}\n"
        f"- normalization: ligatures/NBSP/CR/typographic-quotes folded to ASCII\n"
        f"- CITATION RULE: cite the PRINTED footer page; offset vs file index is\n"
        f"  recorded here once measured (see below).\n",
        encoding="utf-8",
    )
    return f"{slug}: {n} pages, {chars:,} chars -> {out.relative_to(ROOT).as_posix()}"


if __name__ == "__main__":
    todo = sys.argv[1:] or list(SOURCES)
    for s in todo:
        print(build(s))
