"""hook_probe — cross-book plothook miner / mechanical-tagging assay.

NOT a pour. An ANALYSIS tool: it tests the hypothesis that adventure hooks in the
Planescape corpus are mechanically identifiable from raw reflow text by two signals
that need no hand-transcription:

  (1) a LEXICAL trigger — an intent/conflict/secret verb phrase (the "grammar of a hook"),
  (2) an ENTITY anchor — >=1 already-admitted Mimir entity named near the trigger.

A paragraph carrying both is a HOOK CANDIDATE. An entity that anchors hook candidates in
TWO different books is a CROSS-BOOK BRIDGE — the thing we're hunting (e.g. Aoskar tying
Cupgrass's quest in Uncaged to the Signers' scheme in the Manifesto).

Run:  py -3.13 pipeline/mimir/tools/hook_probe.py
"""
from __future__ import annotations
import re, sys, glob, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline" / "mimir"))
from store import HandbookStore, DEFAULT_DB  # noqa: E402

BOOKS = {
    "uncaged":   "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/reflow",
    "manifesto": "build/the-factol-s-manifesto/planescape-2611-the-factols-manifesto/reflow",
}

# (1) the hook grammar — auditable, tunable. Each class is a distinct hook FLAVOR.
LEX = {
    "goal":     [r"\bnext goal\b", r"\bgoal is to\b", r"\bwants? to\b", r"\bseeks?\b",
                 r"\baims? to\b", r"\bhopes? to\b", r"\bintends? to\b", r"\bplans? to\b",
                 r"\blong(?:s|ed)? (?:to|for)\b", r"\byearns?\b", r"\bdreams? of\b",
                 r"\bin search of\b", r"\bsearching for\b", r"\blooking for\b",
                 r"\bset out to\b", r"\bout to\b", r"\b['’]d love to\b", r"\bwould love to\b",
                 r"\bdesires? to\b", r"\bneeds? to find\b"],
    "scheme":   [r"\bplots? to\b", r"\bplotting\b", r"\bschem(?:e|es|ing)\b", r"\bconspir\w+",
                 r"\bsecretly\b", r"\bin secret\b", r"\bhidden agenda\b", r"\bin truth\b",
                 r"\bunknown to\b", r"\blittle does\b", r"\bbehind the scenes\b",
                 r"\bpull\w* (?:the )?strings\b", r"\breally (?:wants|seeks|plans|intends)\b",
                 r"\busurp\w*", r"\boverthrow\w*", r"\bcoup\b", r"\bbetray\w*",
                 r"\bdouble-cross\w*"],
    "conflict": [r"\bwants? \w+ dead\b", r"\bout to get\b", r"\b(?:sworn |bitter )?enem(?:y|ies)\b",
                 r"\brival\w*", r"\bfeud\w*", r"\bvendetta\b", r"\brevenge\b", r"\bat odds\b",
                 r"\bopposes?\b", r"\bshut down\b", r"\bwage\w* war\b", r"\bdestroy\b",
                 r"\bhunt(?:s|ing|ed)? (?:down|for)\b", r"\bget(?:s|ting)? even\b"],
    "quest":    [r"\bhires?\b", r"\bfor hire\b", r"\bpays? (?:any|good|well|a )\b", r"\bbounty\b",
                 r"\breward\w*", r"\bin exchange for\b", r"\bin return for\b", r"\bcan be (?:hired|paid)\b"],
}
LEX_RX = {k: re.compile("|".join(v), re.I) for k, v in LEX.items()}

# concept anchors: cross-book proper nouns that may not (yet) be Mimir entities but bridge plots.
CONCEPTS = ["aoskar", "lady of pain", "blood war", "the lady", "dabus", "great modron march",
            "unity of rings", "rule of three", "the cage", "spire", "godsmen"]

STOP = {"the", "a", "of", "and", "to", "in", "is", "it", "or", "as", "at", "an"}

# structured-field lines (Manifesto faction cards): ALREADY poured as fields/edges -> not prose hooks.
STRUCT_LINE = re.compile(
    r"^\s*(enem(?:y|ies)|allies|allied|home|sign|symbol|philosophy|members?|"
    r"eligibility|alignment|benefits?|restrictions?|factol|headquarters|hq|"
    r"sayings?|secret society|primary|joining)\b\s*[:\-]", re.I)


def load_index(store):
    """name/alias -> (id, type). Lowercased, word-boundary-safe; short/ambiguous names dropped."""
    idx, ents = {}, {}
    for t in ("npc", "faction", "location", "organization", "item", "hook", "fiction", "source"):
        for n in store.list(t, limit=10000):
            eid, name = n["id"], (n.get("name") or "").strip()
            ents[eid] = {"type": t, "name": name}
            cands = {name}
            # faction/org nicknames live in fields; harvest light aliases
            f = n.get("fields") or {}
            for key in ("nickname", "aka", "aliases", "also_known_as", "short"):
                v = f.get(key)
                if isinstance(v, str): cands.add(v)
                elif isinstance(v, list): cands.update(x for x in v if isinstance(x, str))
            # drop leading "the ", take the distinctive head for multiword names
            for c in list(cands):
                c2 = re.sub(r"^the\s+", "", c, flags=re.I).strip()
                if c2 != c: cands.add(c2)
            for c in cands:
                cl = c.lower().strip()
                if len(cl) < 4 or cl in STOP:        # too short/common -> noise
                    continue
                idx.setdefault(cl, (eid, t))
    return idx, ents


def page_paras(path):
    """Reflowed page -> de-hyphenated paragraphs (blank-line separated, lines joined)."""
    raw = Path(path).read_text(encoding="utf-8")
    raw = re.sub(r"(\w)-\n(\w)", r"\1\2", raw)        # join hyphenation across line wraps
    for block in re.split(r"\n\s*\n", raw):
        para = re.sub(r"\s+", " ", block).strip()
        if len(para) >= 40:
            yield para


def entity_hits(text, idx):
    low = text.lower()
    hits = set()
    for name, (eid, t) in idx.items():
        # word-boundary-ish: avoid substring false hits inside longer words
        if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", low):
            hits.add((eid, t, name))
    cons = {c for c in CONCEPTS if re.search(r"(?<![a-z])" + re.escape(c) + r"(?![a-z])", low)}
    return hits, cons


def main():
    store = HandbookStore(DEFAULT_DB, readonly=True)
    idx, ents = load_index(store)
    print(f"entity index: {len(idx)} name-keys over {len(ents)} entities\n")

    # entity_id -> set(books it is hook-anchored in); also keep a sample sentence per (book,entity)
    bridge = collections.defaultdict(set)
    samples = {}            # (eid, book) -> (flavor, sentence)
    concept_bridge = collections.defaultdict(set)
    concept_samp = {}
    per_book = collections.Counter()
    flavor_ct = collections.Counter()

    skipped_struct = collections.Counter()
    for book, reldir in BOOKS.items():
        for path in sorted(glob.glob(str(ROOT / reldir / "page-*.txt"))):
            for para in page_paras(path):
                if STRUCT_LINE.match(para):           # whole para is a card field -> structured channel
                    skipped_struct[book] += 1
                    continue
                sents = re.split(r"(?<=[.!?]) ", para)
                for i, s in enumerate(sents):
                    if STRUCT_LINE.match(s):
                        continue
                    fired = [k for k, rx in LEX_RX.items() if rx.search(s)]
                    if not fired:
                        continue
                    window = s + " " + (sents[i + 1] if i + 1 < len(sents) else "")  # proximity ±1
                    hits, cons = entity_hits(window, idx)
                    if not hits and not cons:
                        continue
                    per_book[book] += 1
                    flavor = fired[0]
                    for k in fired: flavor_ct[k] += 1
                    for eid, t, name in hits:
                        bridge[eid].add(book)
                        samples.setdefault((eid, book), (flavor, s[:220]))
                    for c in cons:
                        concept_bridge[c].add(book)
                        concept_samp.setdefault((c, book), (flavor, s[:220]))
    print("struct-field paras routed out of prose channel:", dict(skipped_struct))

    print("hook-candidate paragraphs per book:", dict(per_book))
    print("hook flavor distribution:", dict(flavor_ct.most_common()), "\n")

    cross = sorted([e for e, bks in bridge.items() if len(bks) >= 2],
                   key=lambda e: (ents[e]["type"], ents[e]["name"]))
    print(f"===== CROSS-BOOK ENTITY BRIDGES ({len(cross)}) =====")
    for eid in cross:
        e = ents[eid]
        print(f"\n[{e['type']}] {e['name']}  ({eid})")
        for book in BOOKS:
            if (eid, book) in samples:
                fl, s = samples[(eid, book)]
                print(f"  {book:9} ({fl}): {s}")

    ccross = sorted([c for c, bks in concept_bridge.items() if len(bks) >= 2])
    print(f"\n===== CROSS-BOOK CONCEPT BRIDGES ({len(ccross)}) — candidate new anchors =====")
    for c in ccross:
        print(f"\n* {c}")
        for book in BOOKS:
            if (c, book) in concept_samp:
                fl, s = concept_samp[(c, book)]
                print(f"  {book:9} ({fl}): {s}")
    store.close()


if __name__ == "__main__":
    main()
