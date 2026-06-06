"""boxset.py — the box-section harvest: proxy · sect · settlement · saying · adventure.

Five extractors over the already-distilled box components. Mechanical where the books
give anchors (the literal `proxy of`, `SECT PHILOSOPHY` field heads, `SYNOPSIS:` cards,
attribution-dashed pull-quotes); curated-with-attestation where they don't (settlements,
prose sects) — the planes-round law: a curated claim pours only with page witnesses.

Pure gear-house: no store imports; self-tested in __main__.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cage as C                       # decode_heading / is_headingish (the display face)

# ---------------------------------------------------------------- components
LAW = "planes-of-law/ddps-planesoflaw-"
CHAOS = "planes-of-chaos/tsr2603-planes-of-chaos"
BENEV = "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae"
MALEV = "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae"
ADV4 = "planes-of-conflict/planes-of-conflict-2615-04-adventures"
CAGE = "in-the-cage-a-guide-to-sigil/ddps-inthecage"

COMPONENT_PLANE = {                     # booklet → its plane (for set_in / located_in)
    LAW + "i": None,                    # box overview — multi-plane
    LAW + "ii": "plane:acheron", LAW + "iii": "plane:arcadia", LAW + "iv": "plane:baator",
    LAW + "v": "plane:mechanus", LAW + "vi": "plane:mount-celestia",
    CHAOS: None, BENEV: None, MALEV: None, ADV4: None, CAGE: "location:sigil",
}
BOOK_OF = {LAW + k: "planes-of-law" for k in ("i", "ii", "iii", "iv", "v", "vi")}
BOOK_OF.update({CHAOS: "planes-of-chaos", BENEV: "planes-of-conflict",
                MALEV: "planes-of-conflict", ADV4: "planes-of-conflict",
                CAGE: "in-the-cage"})

SWEEP_COMPONENTS = [LAW + "i", LAW + "ii", LAW + "iii", LAW + "iv", LAW + "v", LAW + "vi",
                    CHAOS, BENEV, MALEV]


# ---------------------------------------------------------------- proxy sweep
# "the Sphinx, a shared proxy of Ra and Osiris" · "Krenurum (Px/2 orc/F14/LN), is a
# proxy of Meriadar" · "proxy of the dwarven power Reorx, a blustery dwarf named X"
_PRX_NAMED_BEFORE = re.compile(
    r"(?:[Tt]he\s+)?([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)\s*(?:\(([^)]{0,60})\))?,?\s+"
    r"(?:is\s+|who\s+is\s+)?(?:a\s+|the\s+)?(?:shared\s+|indirect\s+|lesser\s+|mighty\s+)?"
    r"prox(?:y|ies)\s+of\s+(?:the\s+[a-z]+\s+power\s+)?"
    r"([A-Z][\w'-]+(?:\s+(?:and\s+)?[A-Z][\w'-]+){0,3})")
_PRX_NAMED_AFTER = re.compile(
    r"prox(?:y|ies)\s+of\s+(?:the\s+[a-z]+\s+power\s+)?([A-Z][\w'-]+)"
    r"[^.;\n]{0,60}?named\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+)?)")
_PRX_STOP = {"There", "The", "His", "Her", "Its", "Their", "This", "That", "These", "Those",
             "All", "Most", "Some", "Any", "Both", "Even", "Such", "Many", "Few", "Each",
             "Proxies", "Proxy", "When", "While", "Note", "But", "And"}


def sweep_proxies(text, *, page, component):
    """Named-proxy bindings: (proxy_name, powers[], descriptor, page, witness)."""
    out = []
    flat = re.sub(r"\s+", " ", text)
    for m in _PRX_NAMED_BEFORE.finditer(flat):
        name, desc, powers = m.group(1).strip(), m.group(2), m.group(3)
        if name.split()[0] in _PRX_STOP or len(name) < 3:
            continue
        plist = [p.strip() for p in re.split(r"\s+and\s+", powers) if p.strip()
                 and p.strip().split()[0] not in _PRX_STOP]
        if not plist:
            continue
        out.append({"name": name, "powers": plist, "descriptor": desc, "page": page,
                    "component": component,
                    "witness": flat[max(0, m.start() - 20):m.end() + 30].strip()[:200],
                    "confidence": 0.85 if desc else 0.75})
    for m in _PRX_NAMED_AFTER.finditer(flat):
        power, name = m.group(1).strip(), m.group(2).strip()
        if name.split()[0] in _PRX_STOP or power.split()[0] in _PRX_STOP:
            continue
        out.append({"name": name, "powers": [power], "descriptor": None, "page": page,
                    "component": component,
                    "witness": flat[max(0, m.start() - 20):m.end() + 30].strip()[:200],
                    "confidence": 0.7})
    return out


# ---------------------------------------------------------------- sect cards (curated + attested)
# Card-format sects carry literal `SECT PHILOSOPHY.` field heads; prose sects are
# curated here and ATTESTED like every other card. (name, component, page_hint,
# plane_id, aliases, gloss)
SECT_CARDS = [
    ("The Order of the Planes-Militant", LAW + "vi", 12, "plane:mount-celestia",
     ["planes-militant"], "crusading sect: defend the Mount, carry law-and-good outward"),
    ("The Mathematicians", LAW + "v", 13, "plane:mechanus",
     ["mathematicians"], "Mechanus sect seeking the multiverse's governing equations"),
    ("The Ring-Givers", CHAOS, 112, "plane:ysgard",
     ["ring-givers"], "Ysgardian sect: wealth exists to be given away — the gift binds fate"),
    ("The Banished", CHAOS, 95, "plane:pandemonium",
     ["banished"], "exiles who embrace the howling dark of Pandemonium"),
    ("The Converts", CHAOS, 10, "plane:limbo",  # Great Audit card fix (Meme ADOPTED 2026-06-06)
     ["converts sect", "converts"],
     "chaos-side sect of the newly persuaded; strongest in Limbo (scan p161)"),
    ("The Verdant Guild", BENEV, 8, "plane:the-beastlands",  # Great Audit card fix (Meme ADOPTED 2026-06-06)
     ["verdant guild", "wylders", "the wylders"],
     "Beastlands sect: protect the wild against civilization (called the Wylders, pp9/17/23)"),
]


def attest_sect(card, pages):
    name, comp, hint, plane, aliases, gloss = card
    rxs = [C._squash(name)] + [C._squash(a) for a in aliases]
    hits = []
    for pg, txt in pages.items():
        sq = C._squash(C.decode_heading(txt) if False else txt)   # plain squash of raw text
        if any(r and r in sq for r in rxs):
            hits.append(pg)
    return sorted(hits)


# ---------------------------------------------------------------- settlements (curated + attested)
# (name, kind, parent_id, component, aliases, gloss)
SETTLEMENT_CARDS = [
    ("Zoronor", "city", "layer:ocanthus", LAW + "ii",
     ["city of shadows"], "the bladelings' shadowed city on Ocanthus"),
    ("Vorkehan", "city", "layer:avalas", LAW + "ii",  # Great Audit card fix (Meme ADOPTED 2026-06-06)
     [], "the Mercykillers' fume-clogged city of gleaming metal"),
    ("The Mines of Marsellin", "mining settlement", "layer:thuldanin", LAW + "ii",
     ["mines of marselun", "marsellin"], "duergar pit-works in Thuldanin's hulks"),
    ("Darkspine", "town", "layer:avernus", LAW + "iv",
     [], "a huddled stop on Avernus's blasted plain"),
    ("Jangling Hiter", "city", "layer:minauros", LAW + "iv",
     ["city of chains"], "the kyton city of chains above the sinking swamp"),
    ("Shra'kt'lor", "city", "plane:limbo", CHAOS,
     ["shra'kt"], "the githzerai war-capital, held coherent by will"),
    ("The Floating City", "city", "plane:limbo", CHAOS,
     ["floating city"], "Limbo's drifting trade-anarchy"),
    ("Heart's Faith", "celestial burg", "layer:lunia", LAW + "vi",  # Great Audit card fix (Meme ADOPTED 2026-06-06)
     ["heart's faith"], "a lantern-archon-lit port of pilgrims"),
    ("Soqed Hezi", "city", "layer:mertion", LAW + "vi",  # Great Audit card fix (Meme ADOPTED 2026-06-06)
     ["soqed"], "the city of swords"),
    ("Windglum", "town", "layer:phlegethon", CHAOS,
     [], "a wind-scoured burg in Pandemonium's third layer"),
    ("Howler's Crag", "landmark-burg", "layer:cocytus", CHAOS,
     ["howler's"], "the crag where every shout reaches a name"),
    ("Torch", None, None, None, [], None),       # sentinel: replaced below — see self-test
]
SETTLEMENT_CARDS = [c for c in SETTLEMENT_CARDS if c[1]]   # drop sentinels


def attest_settlement(card, pages):
    name, kind, parent, comp, aliases, gloss = card
    rxs = [C._squash(name)] + [C._squash(a) for a in aliases if a]
    return sorted(pg for pg, txt in pages.items()
                  if any(r and r in C._squash(txt) for r in rxs))


# ---------------------------------------------------------------- sayings (pull-quotes)
_ATT = re.compile(r"^\s*[—\-~]{1,2}\s*(.{2,48})$")
_THETA_SAYING = 0.6


def _display_line(s):
    """Display-face quote lines are MOSTLY CAPS. Prose is mostly lowercase — and the
    heading decoder (t→L, e→O) wrecks real prose, so the gate must be strict-upper."""
    s = s.strip()
    if not (2 <= len(s) <= 60):
        return False
    letters = [c for c in s if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if c.isupper()) / len(letters) >= 0.5


def _clean_ratio(s):
    """How word-like the decoded text reads — sayings OCR hard; θ-gate the mush.
    Letter-spaced soup ('T H E C H A N T') decodes into single-letter 'words':
    those count AGAINST (only a/I are real one-letter words)."""
    words = s.split()
    if not words:
        return 0.0
    ok = sum(1 for w in words
             if re.fullmatch(r"[A-Za-z][A-Za-z'!?,.-]{0,14}", w)
             and (len(w.strip("'!?,.-")) >= 2 or w in ("a", "A", "I")))
    return ok / len(words)


_PROSE_WORDS = re.compile(
    r"\b(?:the|and|of|to|from|with|his|her|its|their|an|a|or|in|is|it|was|are|has|have|"
    r"that|this|who|which|for|on|at|by|be|as|not|but|so|if|when|where|all|any|one)\b")


def _att_ok(raw):
    """An attribution is a NAME in the display face ('fflAXim', 'FACTOL RHYS') — its
    leak chars defeat case tests, but real prose betrays itself with lowercase
    function words ('an excerpt from…')."""
    s = raw.strip()
    if not (2 <= len(s) <= 48) or sum(c.isalpha() for c in s) < 2:
        return False
    return not _PROSE_WORDS.search(s)


def sweep_sayings(text, *, page, component):
    """Attribution-dashed pull-quotes: collect the display block above each '— SPEAKER'
    line, decode the face, score cleanliness. Returns saying dicts (θ-gating is the
    pour's job — everything ships with its confidence)."""
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        m = _ATT.match(ln)
        if not m:
            continue
        raw_att = m.group(1).strip()
        if not _att_ok(raw_att):                       # prose after a dash ≠ an attribution
            continue
        letters = [c for c in raw_att if c.isalpha()]
        displayish = letters and sum(1 for c in letters if c.isupper()) / len(letters) >= 0.4
        # decode ONLY display-face speakers — the decoder wrecks real prose case
        att = (C.decode_heading(raw_att) if displayish else raw_att).strip(" .—-~")
        block = []
        for j in range(i - 1, max(-1, i - 10), -1):
            s = lines[j].strip()
            if not s:
                if block:
                    break
                continue
            if _display_line(s):
                block.append(C.decode_heading(s))
            else:
                break
        if not block:
            continue
        quote = re.sub(r"\s+", " ", " ".join(reversed(block))).strip()
        if len(quote) < 8:
            continue
        conf = round(min(0.95, 0.5 * _clean_ratio(quote) + 0.5 * _clean_ratio(att)), 2)
        out.append({"text": quote[:240], "speaker": att[:60], "page": page,
                    "component": component, "confidence": conf})
    return out


# ---------------------------------------------------------------- adventure cards
# grab a window after the anchor, cut at OUTLINE if present — a terminator-required
# non-greedy dies whenever OUTLINE sits more than the window away
_SYN = re.compile(r"SYNOPSIS\s*[:.]\s*(.{30,500})", re.DOTALL)
_OUTLINE = re.compile(r"OUTLINE\s*[:.]")
_FIELD = {
    "levels": re.compile(r"LEVELS\s*[:.]\s*([^\n]{0,60})"),
    "n_pcs": re.compile(r"NUMBER OF PCS\s*[:.]\s*([^\n]{0,40})", re.I),
    "factions": re.compile(r"FACTIONS\s*[:.]\s*([^\n]{0,80})", re.I),
}


# Adventure recoveries (Great Audit court -> Meme ADOPTED 2026-06-06): cards the
# SYNOPSIS sweep missed (display-font anchor shredded). Witnessed: page card + ToC.
ADVENTURE_RECOVERIES = {
    "planes-of-chaos/tsr2603-planes-of-chaos": [
        {"page": 192, "title": "The Book of Lies", "levels": "High.",
         "n_pcs": "Two or more.",
         "factions": "Sensates and the Sign of One are most likely, because of their dislike of the Dustmen.",
         "synopsis": 'The PCs "acquire" a magical tome from the Dustmen. Titled the Book of Lies, '
                     "the tome contains every untruth ever uttered. But the PCs learn such knowledge "
                     "can be less a boon than a curse.",
         "why": "p192 card + p186 ToC 'The Book of Lies (High)' — sweep anchor shredded"},
    ],
}


def sweep_adventures(pages, *, component):
    """One card per SYNOPSIS-anchored page: title from the page's best display header,
    fields from the literal field lines."""
    out = [dict(r) for r in ADVENTURE_RECOVERIES.get(component, [])]
    for pg in sorted(pages):
        txt = pages[pg]
        sm = _SYN.search(txt)
        if not sm:
            continue
        title = None
        for ln in txt.splitlines():
            s = ln.strip()
            if C.is_headingish(s) and len(s) >= 6:
                d = C.decode_heading(s)
                if (sum(c.isalpha() for c in d) >= 6
                        and not re.search(r"ADVENTURE|SYNOPSIS|OUTLINE|LEVELS|FACTIONS|"
                                          r"NUMBER OF|PCS|PREFERRED|WARNING|CHARACTERS",
                                          d, re.I)):
                    title = d.title()
                    break
        fields = {}
        for k, rx in _FIELD.items():
            fm = rx.search(txt)
            if fm:
                fields[k] = re.sub(r"\s+", " ", fm.group(1)).strip()[:80]
        body = sm.group(1)
        om = _OUTLINE.search(body)
        if om:
            body = body[:om.start()]
        synopsis = re.sub(r"\s+", " ", body).strip()[:400]
        if not synopsis or len(synopsis) < 30:
            continue
        out.append({"title": title, "page": pg, "component": component,
                    "synopsis": synopsis, **fields})
    return out


# ---------------------------------------------------------------- timeline (Hellbound)
HELLBOUND = "hellbound-the-blood-war/ddps-hellboundbloodwar-ii"

# The war's mythic sequence, narrated in The Dark of the War pp11-16. Each card
# carries a distinctive witness phrase the pour verifies in the reflow — sequence
# index gives before/after edges; all nest part_of event:the-blood-war.
# (event_id, name, seq, witness_phrase, page_hint, gloss)
TIMELINE_CARDS = [
    ("event:the-coming-of-the-baernaloths", "The Coming of the Baernaloths", 1,
     "stagger forth from the mists of creation", 11,
     "the planes form; the baernaloths emerge, already hatching plans for evil"),
    ("event:the-spawning-of-the-yugoloths", "The Spawning of the Yugoloths", 2,
     "spawned some millennia afterward", 11,
     "the baernaloths' children begin implementing the plan"),
    ("event:the-disappearance-of-the-baernaloths", "The Disappearance of the Baernaloths", 3,
     "DISAPPEARANCE OF THE BAERNALOTHS", 12,
     "the creators withdraw from sight; their existence becomes a barmy's guess"),
    ("event:the-ships-of-chaos", "The Building of the Ships of Chaos", 4,
     "ships of chaos", 16,
     "tanar'ri entropy-vessels meant to annihilate the baatezu — not yet unleashed"),
]


def attest_phrase(phrase, pages):
    low = phrase.lower()
    return sorted(pg for pg, txt in pages.items() if low in txt.lower())


# ---------------------------------------------------------------- self-test
if __name__ == "__main__":
    # proxy patterns
    p1 = sweep_proxies("There's the Sphinx, a shared proxy of Ra and Osiris; brave too.",
                       page=10, component="x")
    assert p1 and p1[0]["name"] == "Sphinx" and p1[0]["powers"] == ["Ra", "Osiris"], p1
    p2 = sweep_proxies("Krenurum (Px/2 orc/F14/LN), is a proxy of Meriadar who tends peace.",
                       page=24, component="x")
    assert p2[0]["name"] == "Krenurum" and p2[0]["powers"] == ["Meriadar"]
    assert p2[0]["confidence"] == 0.85                       # descriptor present
    p3 = sweep_proxies("the proxy of the dwarven power Reorx, a smith named Flamewright Orun.",
                       page=10, component="x")
    assert any(x["name"].startswith("Flamewright") and x["powers"] == ["Reorx"] for x in p3), p3
    p4 = sweep_proxies("There's three proxies of note who've got a presence here.",
                       page=11, component="x")
    assert p4 == [], p4                                       # no stop-word junk

    # sayings: block + attribution, cleanliness gate
    text = ("prose before\n\nLIVING\nis A HARD\nHABI+ +© BREAK.\n— fflAXim\n\n"
            "x\n+ H E C H A N + ,\nR 0 + G U +\n— BARMY SOD\n")
    ss = sweep_sayings(text, page=59, component="x")
    assert any("LIVING" in s["text"] and s["confidence"] >= _THETA_SAYING for s in ss), ss
    mush = [s for s in ss if "BARMY" in s["speaker"]]
    assert mush and mush[0]["confidence"] < _THETA_SAYING     # letter-spaced soup queues

    # adventures
    adv = sweep_adventures({27: "THE LOS+ GEAR SPIRI+\nNUMBER OF PCS: 4-6\nLEVELS: 5-9\n"
                                "FACTIONS: Fraternity of Order\nSYNOPSIS: When the spirit of "
                                "a lost gear begins to sing, the PCs must track its song "
                                "across the cogs before rivals do. OUTLINE: 1."},
                           component="x")
    assert adv and adv[0]["levels"] == "5-9" and "lost gear" in adv[0]["synopsis"].lower()
    assert adv[0]["title"] and "GEAR" in adv[0]["title"].upper()

    # settlement + sect attestation
    assert attest_settlement(("Zoronor", "city", "layer:ocanthus", "x", [], ""),
                             {25: "the city of Zoronor gleams darkly"}) == [25]
    assert attest_settlement(("Nowhere", "city", None, "x", [], ""), {1: "nothing"}) == []
    assert attest_sect(("The Ring-Givers", "x", 1, None, ["ring-givers"], ""),
                       {112: "THE RING-GIVERS keep nothing"}) == [112]

    # timeline cards: phrase attestation
    assert attest_phrase("ships of chaos", {16: "the Ships of Chaos wait"}) == [16]
    assert attest_phrase("nonsense xyz", {1: "nothing"}) == []
    seqs = [c[2] for c in TIMELINE_CARDS]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)

    print("boxset.py self-test: all green")
