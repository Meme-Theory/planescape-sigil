# Pipeline — Sourcebook Foundation Layer

> Build the cage before unlocking it. Transcription fidelity first; the 5e uplift
> inherits every sin committed here, so we commit none.

## Philosophy

1. **`content/` is immutable.** Pipelines only read it. Everything derived lands in `build/`.
2. **The page is the unit of provenance.** Every text file, render, art crop, and
   quality grade traces to `(product, component, page, source sha256)`. Markdown
   carries `<!-- pg:NNNN grade:X -->` anchors so downstream backends can always
   point back to the exact scanned page.
3. **Re-entrant by design.** v0 text comes from the embedded OCR layer. Any page can
   be *individually* re-transcribed by a better pass — tesseract re-OCR, or a vision
   model reading `pages/page-NNNN.jpg` — by overwriting `text/page-NNNN.txt` and
   re-running `assemble`. Nothing downstream breaks; the grade in `quality.json`
   tells us exactly which pages deserve the expensive treatment.
4. **Scan reality:** most 2e PDFs are one full-page scan image per page
   (`role: scan-base` in `images.json`). Discrete art objects get extracted when they
   exist; for pure scans, art extraction = cropping regions from page renders, which
   is a vision-pass job (region detection + caption), queued after text quality.

## Stages (v0 → v3)

| Stage | What | Status |
|---|---|---|
| v0 `psx.py` | inventory → text layer → quality grades → renders → art → page-anchored `book.md` | **built** |
| v1a `reflow` | column-aware XY-cut reading order; de-welds column-bleed. Lossless audit across corpus: +6,698 tokens recovered (5,400+ welds split), 0 components lost content. `assemble` prefers `reflow/` over `text/`. | **built** |
| v1b re-transcription | grade C/D pages (~120 corpus-wide) re-OCR'd via tesseract / vision pass; systematic statblock OCR normalization (`Id4`→`1d4`, `THACO`→`THAC0`, `l`/`1`/`I` & `O`/`0`); cant-aware proofing | next |
| v2 region model (`parse/regions.py`, `parse/book.py`) | **stateful, content-aware**: rich spans → furniture-strip (watermark/running-heads) → column order → region FSM (heading/body/statblock/section) → per-type parse **+ validation contract** → typed nodes (provenance: page+bbox+sha256, confidence). Markdown/graph are projections, not the source. | **built (ref impl)** |
| └ Uncaged reference run | 29 NPC nodes, 26/29 statblocks valid (≥10/13 fields, char-conservation≥0.95), descriptor parsed (plane/race/class/faction/alignment), multi-mode movement, OCR anomalies *logged not hidden*, cross-ref **plot graph** (150 edges, 50 reciprocal, 0 unresolved) that **heals its own node names** by inbound-reference consensus. Outputs: `build/.../npc/*.json` + `graph.json` + `cast.md`. | **built** |
| v2-tail | review pile (multi-statblock / page-split: Shemeshka, the fensir twins, Sly Nye) + descriptor sub-field OCR cruft (`PS (BragO`, `Px [Arawnl`) → candidates for the v1b vision pass | open |
| v3 schema extraction | generalize ref impl across 28 books; statblocks/NPCs/locations/portals → typed JSON (the 5e uplift's input; diff against the WotC 5e box as answer key) | next |

## Usage

```bash
cd C:/sandbox/Planescape
python pipeline/extract/psx.py inventory          # register sources (sha256, TSR codes)
python pipeline/extract/psx.py text               # all components, embedded OCR layer
python pipeline/extract/psx.py quality            # grade every page A–D
python pipeline/extract/psx.py status             # corpus triage table
python pipeline/extract/psx.py pilot --slug ps-uncaged-facesofsigil   # full single-book run
```

Grades: **A** ≥90% dictionary-hit · **B** ≥80% · **C** ≥65% · **D** below (re-OCR mandatory) ·
**blank** = art/map/cover page (<12 words). Vocabulary = SRD 5.1 corpus + cant lexicon,
cached at `build/_vocab.json`.

## Windows gotchas (learned the hard way)

- Native `jq`/tools emit CRLF — `tr -d '\r'` anything feeding APIs (see `content/_meta/`).
- `/tmp` doesn't resolve for native exes in Git Bash — use explicit project paths.
- Always `encoding="utf-8"` in Python; console is reconfigured in `psx.py`.
