"""hooks.py — the mechanical plot-hook tagger (pure gear-house; no store dependency).

A hook is identified by three signals, proven on the Uncaged+Manifesto corpus
(see pipeline/mimir/tools/hook_probe.py, the assay this productionizes):

    TRIGGER  — an intent/conflict/scheme/quest verb phrase (the "grammar of a hook"),
    ANCHOR   — >=1 admitted entity (or subject-with-aliases) named near the trigger,
    PROXIMITY— trigger and anchor in the same sentence (or +-1), not just same block.

Two book-shapes, two regimes:
    prose-embedded (Uncaged)  — hooks live in the entry body; SUBJECT = the entry's NPC.
    field-structured (Manifesto) — the `Enemies:/Allies:` card fields are ALREADY poured
                                    as edges; route them out (STRUCT_LINE) so we tag the
                                    chapter PROSE, not re-count a fact we already hold.

gate.py builds the anchor index from the store and the scopes from nodes/reflow, then
calls tag_text() and pours the seeds. This module stays pure so it self-tests in __main__.
"""
from __future__ import annotations
import re

# ------------------------------------------------------------------ the hook grammar
# Four flavors. `base` is the prior that a fired trigger marks a real hook (scheme/quest are
# more hook-specific than the very common "wants to"). Patterns refined for OCR + polysemy.
LEX = {
    "scheme":   (0.85, [r"\bplots? to\b", r"\bplotting\b", r"\bschem(?:e|es|ing)\b", r"\bconspir\w+",
                        r"\bsecretly\b", r"\bin secret\b", r"\bhidden agenda\b", r"\bin truth\b",
                        r"\bunknown to\b", r"\blittle does\b", r"\bbehind the scenes\b",
                        r"\bpull\w* (?:the )?strings\b", r"\breally (?:wants|seeks|plans|intends)\b",
                        r"\busurp\w*", r"\boverthrow\w*", r"\bcoup\b", r"\bbetray\w*", r"\bdouble-cross\w*"]),
    "quest":    (0.80, [r"\bhires?\b", r"\bfor hire\b", r"\bpays? (?:any|good|well|a )\b", r"\bbounty\b",
                        r"\breward(?:s|ed)?\b", r"\bin exchange for\b", r"\bin return for\b",
                        r"\bcan be (?:hired|paid)\b", r"\bseeks? (?:your|the party'?s?) (?:help|service|aid)\b"]),
    "conflict": (0.75, [r"\bwants? \w+ dead\b", r"\bout to get\b", r"\b(?:sworn |bitter )?enem(?:y|ies)\b",
                        r"(?<!to )\brival(?:s|ry)?\b", r"\bfeud\w*", r"\bvendetta\b", r"\brevenge\b",
                        r"\bat odds\b", r"\bopposes?\b", r"\bshut down\b", r"\bwage\w* war\b",
                        r"\bhunt(?:s|ing|ed)? (?:down|for)\b", r"\bget(?:s|ting)? even\b"]),
    "goal":     (0.70, [r"\bnext goal\b", r"\bgoal is to\b", r"\bwants? to\b", r"\bseeks? to\b",
                        r"\baims? to\b", r"\bhopes? to\b", r"\bintends? to\b", r"\bplans? to\b",
                        r"\blong(?:s|ed)? (?:to|for)\b", r"\byearns?\b", r"\bdreams? of\b",
                        r"\bin search of\b", r"\bsearching for\b", r"\blooking for\b", r"\bset out to\b",
                        r"\b['’]d love to\b", r"\bwould love to\b", r"\bdesires? to\b", r"\bneeds? to find\b"]),
}
LEX_RX = {k: re.compile("|".join(pats), re.I) for k, (_, pats) in LEX.items()}
BASE = {k: b for k, (b, _) in LEX.items()}
FLAVOR_ORDER = ["scheme", "quest", "conflict", "goal"]   # most-specific first

# structured card-field lines (Manifesto): already poured as fields/edges -> NOT prose hooks.
STRUCT_LINE = re.compile(
    r"^\s*(enem(?:y|ies)|allies|allied|home|sign|symbol|philosophy|members?|eligibility|"
    r"alignment|benefits?|restrictions?|factol|headquarters|hq|sayings?|primary|joining)\b\s*[:\-]", re.I)

# anchors that name the setting itself match nearly everything -> heavy specificity penalty.
SETTING_SCALE = {"sigil", "the cage", "the multiverse", "the planes", "the city", "cage"}
STOP = {"the", "a", "of", "and", "to", "in", "is", "it", "or", "as", "at", "an"}
MAX_ANCHORS = 3   # >this many distinct entities near ONE trigger = a name-LIST, not a hook. The diffuse
                  # relationship-web (Uncaged's "Bigwigs with Jink", the Manifesto cards) is already
                  # structured data (PLOT_EDGES / allied_with) — re-tagging it fans out false hooks.


def anchor_specificity(name: str) -> float:
    """How discriminating is this anchor name? Setting-scale -> 0.4, short -> 0.7, else 1.0."""
    n = name.lower().strip()
    if n in SETTING_SCALE:
        return 0.4
    if len(n) <= 5:
        return 0.7
    return 1.0


def build_index(records):
    """records: iterable of (id, type, name, aliases:list[str]) -> {name_lower: (id, type, spec)}.
    Longer/more-specific keys win collisions; short/common keys dropped."""
    idx = {}
    for eid, typ, name, aliases in records:
        cands = {name, *(aliases or [])}
        for c in list(cands):                                    # leading-'the' + distinctive head
            c2 = re.sub(r"^the\s+", "", c, flags=re.I).strip()
            if c2 and c2 != c:
                cands.add(c2)
        for c in cands:
            cl = (c or "").lower().strip()
            if len(cl) < 4 or cl in STOP:
                continue
            spec = anchor_specificity(cl)
            prev = idx.get(cl)
            if prev is None or spec > prev[2]:                   # prefer the more-specific owner
                idx[cl] = (eid, typ, spec)
    return idx


_AMBIG = re.compile(r"\b(rival|reward|out to)\b", re.I)   # tokens whose hook-sense is shaky


def _find_anchors(window: str, idx):
    low = window.lower()
    out = []
    for name, (eid, typ, spec) in idx.items():
        if re.search(r"(?<![a-z])" + re.escape(name) + r"(?![a-z])", low):
            out.append((eid, typ, name, spec))
    return out


def split_sentences(text):
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)        # join hyphenation across wraps
    text = re.sub(r"\s+", " ", text).strip()
    return re.split(r"(?<=[.!?])\s+", text)


def score(flavor, anchor_spec, proximity, subject_known, ambiguous):
    """confidence = base[flavor] x anchor x proximity x subject, halved if the trigger is ambiguous."""
    conf = BASE[flavor] * anchor_spec * proximity * subject_known
    if ambiguous:
        conf *= 0.5
    return round(min(conf, 0.98), 2)


def tag_text(text, idx, *, owner_id=None, owner_type=None, page=None, book=None, subject_known=1.0):
    """Scan one prose scope, return hook-seed dicts. owner = the entry's subject (Uncaged NPC) or
    the dominant faction (Manifesto). An anchor equal to the owner is skipped (no self-hook)."""
    seeds, sents = [], split_sentences(text)
    for i, s in enumerate(sents):
        if STRUCT_LINE.match(s):
            continue
        fired = [k for k in FLAVOR_ORDER if LEX_RX[k].search(s)]
        if not fired:
            continue
        flavor = fired[0]
        nxt = sents[i + 1] if i + 1 < len(sents) else ""
        in_sent = _find_anchors(s, idx)
        anchors = in_sent or _find_anchors(s + " " + nxt, idx)
        prox = 1.0 if in_sent else 0.8
        # collapse alias collisions to one entry per id (best specificity wins), drop the self-anchor
        byid = {}
        for eid, typ, name, spec in anchors:
            if eid == owner_id:                              # don't hook an entry to itself
                continue
            if eid not in byid or spec > byid[eid][3]:
                byid[eid] = (eid, typ, name, spec)
        if not byid or len(byid) > MAX_ANCHORS:              # no anchor, or a name-LIST -> not a clean hook
            continue
        trig = LEX_RX[flavor].search(s).group(0)
        ambiguous = bool(_AMBIG.search(trig))
        for eid, typ, name, spec in byid.values():
            seeds.append({
                "owner": owner_id, "owner_type": owner_type,
                "object_id": eid, "object_type": typ, "object_name": name,
                "flavor": flavor, "trigger": trig,
                "sentence": s.strip()[:240], "page": page, "book": book,
                "confidence": score(flavor, spec, prox, subject_known, ambiguous),
            })
    return seeds


# ---------------------------------------------------------------------------- self-test
def _selftest():
    # a tiny anchor index: Aoskar (subject, with the oblique aliases) + the Sensates faction.
    idx = build_index([
        ("subject:aoskar", "subject", "Aoskar", ["god of portals", "dead god of portals"]),
        ("faction:society-of-sensation", "faction", "Society of Sensation", ["Sensates"]),
        ("faction:harmonium", "faction", "Harmonium", ["Hardheads"]),
        ("faction:dustmen", "faction", "Dustmen", ["the Dead"]),
    ])
    # 1) prose-embedded goal hook, exact subject = Cupgrass; anchors Aoskar by NAME.
    body = ("Wooly Cupgrass runs a lab in the Lady's Ward. The bariaur's next goal is to find a bit "
            "of the blood of the dead god Aoskar; he's heard the chant about its use as a gate key.")
    s1 = tag_text(body, idx, owner_id="npc:uncaged:wooly-cupgrass", owner_type="npc", page=23, book="uncaged")
    assert any(x["object_id"] == "subject:aoskar" and x["flavor"] == "goal" for x in s1), s1
    assert all(x["owner"] == "npc:uncaged:wooly-cupgrass" for x in s1)
    assert len([x for x in s1 if x["object_id"] == "subject:aoskar"]) == 1, "alias dupes must collapse"

    # 2) OBLIQUE manifesto reference: the portfolio epithet "god of portals" resolves to Aoskar
    #    via alias even though the name "Aoskar" never appears -> the payoff of subject-as-node.
    rite = ("The Signers secretly plot to restore the god of portals to the heavens. "
            "Such a resurrection would shake Sigil to its foundations.")
    s2 = tag_text(rite, idx, owner_id="faction:sign-of-one", owner_type="faction", page=20,
                  book="manifesto", subject_known=0.7)
    assert any(x["object_id"] == "subject:aoskar" for x in s2), s2          # alias caught the oblique ref

    # 3) struct-field line is routed out (Enemies: ... is not a prose hook).
    assert tag_text("Enemies: Harmonium, Dustmen", idx, owner_id="faction:athar") == []

    # 4) self-hook is skipped; ambiguous 'reward'-as-adjective doesn't fire as quest.
    assert tag_text("The Sensates seek to grow. The Society of Sensation wants to expand.", idx,
                    owner_id="faction:society-of-sensation") == []          # only self-anchor -> dropped
    assert "quest" not in [x["flavor"] for x in
                           tag_text("She had a rewarding life among the Sensates.", idx,
                                    owner_id="x")], "rewarding-life must not fire as a quest"

    # 5) confidence ordering: specific in-sentence scheme > setting-scale goal.
    hi = tag_text("The Harmonium secretly plot against the Sensates.", idx, owner_id="x")[0]["confidence"]
    assert hi >= 0.7, hi

    # 6) LIST-DENSITY: one trigger near >MAX_ANCHORS distinct entities is a relationship-list
    #    (already structured as PLOT_EDGES/allied_with), not a clean hook -> drop the whole sentence.
    crowd = ("Zadara secretly schemes with the Society of Sensation, the Harmonium, the Dustmen, "
             "the god of portals, and Aoskar all at once.")          # 4 distinct ids near one trigger
    assert tag_text(crowd, idx, owner_id="npc:zadara") == [], tag_text(crowd, idx, owner_id="npc:zadara")
    # but a trigger near exactly two anchors still yields hooks (Aoskar collapses via alias):
    ok = tag_text("Zadara secretly plots against the Harmonium and Aoskar.", idx, owner_id="npc:zadara")
    assert {x["object_id"] for x in ok} == {"faction:harmonium", "subject:aoskar"}, ok

    print(f"hooks.py self-test OK  (cupgrass->aoskar conf={[x['confidence'] for x in s1]}, "
          f"oblique manifesto seeds={len(s2)}, scheme-conf={hi}, list-density dropped)")


if __name__ == "__main__":
    _selftest()
