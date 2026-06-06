#!/usr/bin/env python
"""coverage — account for every source line. The validator measures what it knows
to check; this measures what we THREW AWAY. A line is either: furniture (stripped),
noise (filtered), in an NPC node (statblock/section/body), or orphaned (real content
in an entry that produced no node — intro chapters, fiction handouts, plot
appendices, tables). Orphans are the silent gaps.
"""
import sys, json, pathlib, collections
import fitz
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "parse"))
import regions as R, book as B

ROOT = pathlib.Path(__file__).resolve().parents[2]
slug = "ps-uncaged-facesofsigil"
src = json.loads(next((ROOT / "build").glob(f"*/{slug}/source.json")).read_text(encoding="utf-8"))
doc = fitz.open(ROOT / src["file"])

# 1) furniture vs content, per page
furn = content = 0
for i in range(len(doc)):
    flat, dropped = R.ordered_content_lines(doc[i])
    furn += len(dropped); content += len(flat)

# 2) region accounting over the whole stream
stream = B.load_stream(doc)
regs = R.segment(stream)
in_regions = sum(len(r["lines"]) for r in regs)
noise = len(stream) - in_regions
by_type = collections.Counter()
for r in regs:
    by_type[r["type"]] += len(r["lines"])

# 3) entry accounting
entries = B.split_entries(regs)
has_sb = lambda e: any(r["type"] == "statblock" for r in e["regions"])
eline = lambda e: sum(len(r["lines"]) for r in e["regions"])
echar = lambda e, t: sum(len(l["text"]) for r in e["regions"] if r["type"] == t for l in r["lines"])
npc = [e for e in entries if e.get("title") and has_sb(e)]
orphan = [e for e in entries if not (e.get("title") and has_sb(e))]

# 4) body-truncation gap: node stores body_excerpt[:240] only
full_body = sum(echar(e, "body") for e in npc)
kept_body = sum(min(240, echar(e, "body")) for e in npc)

print("=== UNCAGED COVERAGE AUDIT ===")
print(f"raw lines (content+furniture): {content + furn}")
print(f"  furniture stripped : {furn:5}  ({furn/(content+furn)*100:.1f}%)  watermark/running-heads")
print(f"  content lines      : {content:5}")
print(f"  └ noise-filtered   : {noise:5}  (OCR crumbs, lone punctuation)")
print(f"  └ in regions       : {in_regions:5}")
for t, n in by_type.most_common():
    print(f"       {t:9}: {n:5}")
print(f"\nentries: {len(entries)}  ->  NPC nodes: {len(npc)}   orphan (no node): {len(orphan)}")
print(f"  lines in NPC entries : {sum(eline(e) for e in npc):5}")
print(f"  lines ORPHANED       : {sum(eline(e) for e in orphan):5}   <-- real content dropped from output")
print(f"\nbody-prose truncation gap (node keeps only body_excerpt[:240]):")
print(f"  full body chars: {full_body:6}   kept in nodes: {kept_body:6}   "
      f"LOST: {full_body-kept_body:6} ({(full_body-kept_body)/max(1,full_body)*100:.0f}%)")

print("\n=== largest ORPHANED spans (silent content gaps) ===")
for e in sorted(orphan, key=eline, reverse=True)[:14]:
    p = e["regions"][0]["lines"][0]["page"]
    why = "no-title" if not e.get("title") else "no-statblock"
    txt = next((l["text"] for r in e["regions"] for l in r["lines"]), "")[:46]
    print(f"  p{p:<3} {eline(e):4}ln [{why:12}] title={str(e.get('title'))[:18]:18} | {txt}")
