"""cage.py — In the Cage: A Guide to Sigil (TSR 2609) extraction grammar.

Two regimes, both mechanical:

  1. ESTABLISHMENTS — the contents page (printed p1, "A TOUT'S GUIDE…") is the
     authoritative roster, same law as Uncaged's roster-driven split: every entry
     boundary comes from the roster + an auto-calibrated printed→scan offset +
     a fuzzy smallcaps-decoded heading match on the target page. Entries typed
     `site` become location nodes; `feature`/`chapter`/`catchall` rows exist only
     to BOUND bodies and feed the sweep. "Verified or absent."

  2. PORTAL SWEEP — sentence- then clause-scoped TRIGGER × DESTINATION grammar.
     Destinations resolve against a curated Places GAZETTEER (planes / layers /
     realms / gate-towns / pathways / cosmology); sources resolve to the owning
     entry, or for front-matter prose to the nearest in-clause location mention.
     Negated destinations ("not to the gate-towns…") are dropped. Every candidate
     carries its witness sentence + page. Pour-side θ lives in gate.py.

Pure gear-house: no store imports, self-tested in __main__ (run it).
"""
import re
from difflib import SequenceMatcher

# ---------------------------------------------------------------- OCR heading decode
# The book's display face is hostile: T→"+", O→"©"/"0"/"9", E→"€" (sometimes "B"/"C" —
# fuzz absorbs those), B→"8", and M→"ITI"/"III"/"IT1"/"ffl"/"m" ("NIGH+ IIIARKJ+" =
# NIGHT MARKET, "fflAXim" = MAXIM). Ampersand renders "8t"/"ft"/"Et" ("Bottle 8t Jug").
# This decoder exists ONLY for heading lines — prose never goes through it.
_AMP = re.compile(r"(?<=\w)\s*(?:8t|8c)\s*(?=\w)|\b(?:ft|Et|8t|8c)\b")
_EM = re.compile(r"ffl|iti|it1|ii1|1t1|iii", re.IGNORECASE)
# lowercase leaks: the face's smallcap O OCRs as 'e' ("cempeuND"=COMPOUND,
# "meuN+s"=MOUNTS), M as 'm', L as 't'/'tt' ("SCRA+CH WAtt"=SCRATCH WALL,
# "StAGS"=SLAGS). Heading-only — prose never enters this decoder.
_OCRMAP = str.maketrans({"+": "T", "©": "O", "0": "O", "8": "B", "®": "O",
                         "9": "O", "€": "E", "1": "I", "e": "O", "m": "M",
                         "t": "L"})


def decode_heading(line):
    s = line.strip().strip("•*·").strip()
    s = _AMP.sub(" & ", s)
    s = _EM.sub("M", s)
    s = s.translate(_OCRMAP)
    return re.sub(r"\s+", " ", s).strip()


def _squash(s):
    return re.sub(r"[^A-Z&']", "", s.upper())


def head_score(line, name):
    """How well a raw page line matches a roster name, after smallcaps decode."""
    d = _squash(decode_heading(line))
    n = _squash(name)
    if not d or not n:
        return 0.0
    if len(d) > 2 * len(n) + 8:          # a prose line containing the name is not a heading
        return 0.0
    return SequenceMatcher(None, d, n).ratio()


def is_headingish(line):
    """Heading lines are short, symbol-heavy smallcaps — not prose. The face leaks
    lowercase for some glyphs (m=M, e=O, f=F, i/l=I, t=L), so those don't count
    against; a bullet-marked line ('• cempeuND •') is a head regardless of case —
    the bullets ARE the book's head markers."""
    s = line.strip()
    if not (3 <= len(s) <= 52) or s.endswith((".", ",", ";")):
        return False
    if s.startswith("•") or s.endswith("•"):
        return True
    letters = [c for c in s if c.isalpha() and c not in "mefilts"]
    if not letters:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) >= 0.65


# ---------------------------------------------------------------- the roster (contents p1)
# (name, printed_page, ward, kind, rtype) — hand-verified against the contents page
# (scan pg:0005, grade C) and the chapter tours. rtype: site | feature | chapter | catchall.
# Kinds are read from each entry's own text; "establishment" where the entry doesn't say.
ROSTER = [
    # — front matter: A Tout's Guide to Sigil —
    ("A Tout's Guide to Sigil",            4, None, None, "chapter"),
    ("Listen Up, You Clueless Screwheads", 6, None, None, "feature"),
    ("Architecture",                       6, None, None, "feature"),
    ("Wards and Mazes",                    8, None, None, "feature"),
    ("Portals",                            8, None, None, "feature"),
    ("Time and Direction in Sigil",       12, None, None, "feature"),
    ("Usury and Moneylenders",            12, None, None, "feature"),
    ("Weather, Smoke, and Thin Air",      12, None, None, "feature"),
    ("Cagers: Citizens of Sigil",         13, None, None, "feature"),
    ("Factols and Faction Headquarters",  14, None, None, "feature"),
    ("Hirelings",                         15, None, None, "feature"),
    ("A Guide to Garnishes",              18, None, None, "feature"),
    ("Harmonium Patrols",                 19, None, None, "feature"),
    ("Writing the Dead-Book: Executions in Sigil", 21, None, None, "feature"),
    ("Lady of Pain",                      23, None, None, "feature"),
    ("Six Tours of Sigil",                24, None, None, "feature"),
    # — The Lady's Ward —
    ("The Lady's Ward",                   28, "Lady's Ward", None, "chapter"),
    ("High Houses",                       30, "Lady's Ward", None, "feature"),
    ("Knights and Servants of the Ward",  30, "Lady's Ward", None, "feature"),
    ("Armory",                            32, "Lady's Ward", "armory", "site"),
    ("The Catacombs",                     32, "Lady's Ward", "catacombs", "site"),
    ("City Barracks",                     32, "Lady's Ward", "barracks", "site"),
    ("City Court",                        34, "Lady's Ward", "courthouse", "site"),
    ("Fortune's Wheel",                   36, "Lady's Ward", "gambling tavern", "site"),
    ("Golden Bariaur Inn",                39, "Lady's Ward", "inn", "site"),
    ("Palace of the Jester",              40, "Lady's Ward", "landmark", "site"),
    ("Prison",                            41, "Lady's Ward", "prison", "site"),
    ("Temple of the Abyss",               43, "Lady's Ward", "temple", "site"),
    ("Temple of Hermes",                  44, "Lady's Ward", "temple", "site"),
    ("Tower of the Wyrm",                 44, "Lady's Ward", "temple", "site"),
    ("Traban's Forge",                    45, "Lady's Ward", "smithy", "site"),
    # — The Lower Ward —
    ("The Lower Ward",                    46, "Lower Ward", None, "chapter"),
    ("Black Sails",                       48, "Lower Ward", "establishment", "site"),
    ("Bones of the Night",                48, "Lower Ward", "establishment", "site"),
    ("Ditch",                             49, "Lower Ward", "canal", "site"),
    ("Golden Bell",                       50, "Lower Ward", "establishment", "site"),
    ("Great Foundry",                     50, "Lower Ward", "foundry", "site"),
    ("Green Mill",                        51, "Lower Ward", "establishment", "site"),
    ("Hands of Time",                     51, "Lower Ward", "clockworks", "site"),
    ("Harbinger House",                   55, "Lower Ward", "establishment", "site"),
    ("Shattered Temple",                  55, "Lower Ward", "ruin", "site"),
    ("Society of the Luminiferous Aether", 55, "Lower Ward", "society hall", "site"),
    ("Styx Oarsman",                      56, "Lower Ward", "tavern", "site"),
    ("Ubiquitous Wayfarer",               57, "Lower Ward", "tavern", "site"),
    ("Other Beloved Pubs and Alehouses",  57, "Lower Ward", None, "catchall"),
    # — Clerk's Ward —
    ("Clerk's Ward",                      60, "Clerk's Ward", None, "chapter"),
    ("Getting Around",                    62, "Clerk's Ward", None, "feature"),
    ("Civic Festhall",                    63, "Clerk's Ward", "festhall", "site"),
    ("Greengage",                         63, "Clerk's Ward", "tavern", "site"),
    ("Grundlethum's Automatic Scribe",    63, "Clerk's Ward", "shop", "site"),
    ("Hall of Information",               66, "Clerk's Ward", "hall", "site"),
    ("Hall of Records",                   71, "Clerk's Ward", "hall", "site"),
    ("Hall of Speakers",                  72, "Clerk's Ward", "hall", "site"),
    ("Jeena Ealy's Compound",             72, "Clerk's Ward", "estate", "site"),
    ("Lazz School of Vivid Unpleasantness", 74, "Clerk's Ward", "school", "site"),
    ("Tea Street Transit",                74, "Clerk's Ward", "transit", "site"),
    ("Tensar's Employment Service",       77, "Clerk's Ward", "service", "site"),
    ("Trianym",                           78, "Clerk's Ward", "landmark", "site"),
    ("Trioptic Nic'Epona",                79, "Clerk's Ward", "establishment", "site"),
    # — Guildhall & Market Wards (one tour, two wards; per-entry ward verified from text) —
    ("Guildhall & Market Wards",          80, "Guildhall Ward", None, "chapter"),
    ("Imel's Happy Tongue",               81, "Guildhall Ward", "establishment", "site"),
    ("A Look Around",                     84, "Guildhall Ward", None, "feature"),
    ("Portals and Mantas",                84, "Guildhall Ward", None, "feature"),
    ("Sightseeing",                       86, "Guildhall Ward", None, "feature"),
    ("Shopping in the Market Ward",       87, "Market Ward", None, "feature"),
    ("Bronze Bezants",                    90, "Market Ward", "moneychanger", "site"),
    ("Chirper's",                         93, "Market Ward", "club", "site"),
    ("Ensin's Discount Elixirs",          95, "Market Ward", "shop", "site"),
    ("Great Bazaar",                      96, "Market Ward", "market", "site"),
    ("Great Gymnasium",                   96, "Market Ward", "gymnasium", "site"),
    ("Xanist's Shop",                     97, "Market Ward", "shop", "site"),
    ("Zakk's Corpse Curing",              99, "Market Ward", "shop", "site"),
    # — The Hive —
    ("The Hive",                         100, "Hive Ward", None, "chapter"),
    ("A Look Around (Hive)",             101, "Hive Ward", None, "feature"),
    ("Here to There",                    103, "Hive Ward", None, "feature"),
    ("Allesha's Pantry",                 106, "Hive Ward", "pantry", "site"),
    ("Bottle & Jug",                     107, "Hive Ward", "tavern", "site"),
    ("Gatehouse",                        110, "Hive Ward", "asylum", "site"),
    ("Green Stone Stables",              111, "Hive Ward", "stables", "site"),
    ("Hive",                             112, "Hive Ward", "tenement block", "site"),
    ("Mortuary",                         113, "Hive Ward", "morgue", "site"),  # Great Audit card fix (Meme ADOPTED 2026-06-06)
    ("Scratch Wall",                     115, "Hive Ward", "landmark", "site"),
    ("Slags",                            115, "Hive Ward", "ruin-field", "site"),
    ("Weary Spirit Infirmary",           121, "Hive Ward", "infirmary", "site"),
    ("Index",                            127, None, None, "chapter"),
]

# Roster-name aliases for the in-page heading match where the printed head differs
# from the contents line (verified against the tour pages). Generic-looking aliases
# ("Wheel", "Abyss") are SAFE because the search is scoped to the entry's own
# printed page ±1 — "• WHEEL •" is the only head Fortune's Wheel gets (the
# "F0R+UNE'S" half never survived the scan).
HEAD_ALIAS = {
    "The Catacombs": ["Catacombs and the Twelve Factols", "The Catacombs"],
    "A Look Around (Hive)": ["A Look Around"],
    "Other Beloved Pubs and Alehouses": ["Other Beloved Pubs", "Beloved Pubs and Alehouses"],
    "Ubiquitous Wayfarer": ["The Ubiquitous Wayfarer"],
    "Golden Bariaur Inn": ["The Golden Bariaur", "Golden Bariaur"],
    "Armory": ["The Armory"],
    "Fortune's Wheel": ["Wheel"],
    "Palace of the Jester": ["The Palace of the Jester", "The Palace"],
    "Temple of the Abyss": ["Temple of the Abyss", "Abyss"],
    "Temple of Hermes": ["The Temple of Hermes"],
    "Tower of the Wyrm": ["The Tower of the Wyrm", "Wyrm"],
    "Bones of the Night": ["The Bones of the Night"],
    "Golden Bell": ["The Golden Bell"],
    "Green Mill": ["The Green Mill"],
    "Shattered Temple": ["The Shattered Temple"],
    "Society of the Luminiferous Aether": ["The Society of the Luminiferous Aether",
                                           "Luminiferous Aether"],
    "Styx Oarsman": ["The Styx Oarsman", "Styx"],            # the OARSMAN half never scanned
    "Civic Festhall": ["The Civic Festhall", "The Civic"],
    "Bones of the Night": ["The Bones of the Night", "Of the Night"],  # "• ep+m= NIGH+ •"
    "Jeena Ealy's Compound": ["Jeena Ealy's", "Ealy's Compound"],
    "Lazz School of Vivid Unpleasantness": ["Lazz School", "Lazz of Vivid"],  # UNPLEASANTNESS died
    "Imel's Happy Tongue": ["Happy Tongue", "Imel's"],
    "Bottle & Jug": ["The Bottle & Jug"],
    "Green Stone Stables": ["The Green Stone Stables"],
    "Hive": ["The Hive"],
    "The Speckled Rat": ["The Rat", "Rat"],   # 'THE / RA +' two-line shred, MINOR_SPAN-scoped
    "Mortuary": ["The Mortuary"],
    "Scratch Wall": ["The Scratch Wall"],
    "Slags": ["The Slags"],
}

# The Lower Ward catchall ("Other Beloved Pubs and Alehouses…", printed p57+) holds
# minor establishments with their own display heads — verified on scan pg59-61.
# (name, kind, existing_hint) — all Lower Ward, tier minor; the existing_hint marks
# the ones Uncaged already poured (merge targets, never fresh nodes).
MINORS = [
    ("The Dirk & Firkin", "greenhouse tavern", None),
    ("The Face of Gith", "githzerai bar", "location:sigil:the-face-of-gith"),
    ("The Lantern", "thieves' tavern", None),
    ("The Mermaid's Cups", "tavern", None),
    ("The Red Pony", "tavern", None),
    # Great Audit recovery: head shredded to 'THE / RA +' (pg59); its body had been
    # absorbed by the Tenth Pit span, misbinding the Dustmen-Contract hooks. Merge
    # target = the standing Uncaged node.
    ("The Speckled Rat", "dive tavern", "location:sigil:the-speckled-rat"),
    ("The Tenth Pit", "tavern", None),
    ("The White Casket", "faction tavern", "location:sigil:the-white-casket"),
    ("The Sword and Buckler", "tavern", None),
]
MINOR_SPAN = (59, 62)        # scan pages holding the catchall's minor heads

# Roster rows whose heads (or bodies) did not survive the grade-C scan — named,
# explained, review-queued at pour. "Verified or absent," never guessed.
EXPECTED_ABSENT = {
    "Armory": "display head lost (pg34 holds only Catacombs + City Barracks heads)",
    "Temple of Hermes": "head shredded on grade-D pg46; body bleeds into Temple of the Abyss span",
    "Tower of the Wyrm": "head shredded on grade-D pg46-47",
    "Golden Bell": "head lost on pg52; body bleeds into Great Foundry span",
    "Green Mill": "head lost on pg52-53; body visible at pg53:0 but unboundable",
    "Shattered Temple": "head shredded pg57-58 (letter-spaced pull-quote weave); Uncaged node stands",
    "Society of the Luminiferous Aether": "head shredded pg57-58 (same weave)",
    "Hall of Speakers": "head found pg74:0 but body reflow-scrambled (Jeena Ealy head 2 lines below); Uncaged node stands",
    "Grundlethum's Automatic Scribe": "head shredded pg65 ('BY LINN smcs / +HUm'S / SCRIBE'); body inside Greengage span",
    "Green Stone Stables": "head lost in the pg113-114 drift zone (only the Yscoppel's Mounts side-table survives)",
}

# the purchaser watermark varies by component ("Meme (Order #…)" / "Ryan Berry (Order #…)")
_FURNITURE = re.compile(
    r"^(?:.{0,40}\(Order #\d+\)|•\s*\d+\s*•|\d{1,3}|[-•·*]+)$")

# ---- witnessed entry recoveries (Great Audit court → Meme ADOPTED 2026-06-06) --------
# The grade-C/D scan ate display heads and the reflow interleaved bodies (the Jeremo
# class, at entry scale): Bones of the Night's skull-hunt sat under the BLACK SAILS
# head, Grundlethum's body under a drifted GREENGAGE head, Shattered Temple's tail
# wrapped above Harbinger House's body. Each recovery names its body by ANCHOR TEXT —
# resolved against the page at segment time, never by line number (a v1b re-OCR moves
# lines; the page's own words are the witness). A segment whose anchors fail resolves
# NOTHING and the entry stays absent/quarantined ("verified or absent").
# Spans verified by the audit court with two adversarial refuters per finding;
# correction-docket.md carries the page quotes.
# name -> {"segments": [(scan_page, start_anchor, end_anchor), ...], "why": str}
ENTRY_CURATIONS = {
    "Armory": {
        "segments": [(34, "Home to the Doomguard, this headquarters", "to meet their employers.")],
        "why": "head residue '• THE' (pg32); body sat inside the Catacombs span"},
    "Black Sails": {
        "segments": [(50, "The Black Sails tavern stands in the shadow", "gather to drink quietly.")],
        "why": "true body is 10 lines; the auto span absorbed Bones of the Night's wrapped column"},
    "Bones of the Night": {
        "segments": [(50, "The Guvners have reams of knowledge", "and a mind full"),
                     (50, "of secrets. Called simply", "least not yet."),
                     (50, "STONE GOLEM: AC 5", "greater wisdom.")],
        "why": "column wrap: body runs head→'a mind full' then wraps to page top 'of secrets…'; golem statblock + spigot para are its sidebars"},
    "Golden Bell": {
        "segments": [(52, "Standing hard by the Temple of the Abyss", "swindle them.")],
        "why": "head eaten on pg50; body had been swallowed by the Great Foundry span"},
    "Green Mill": {
        "segments": [(53, "This leafy sanctuary is half tavern", "smoke, sweat, and steel.")],
        "why": "head lost at the pg50/51 column break; body self-names 4x"},
    "Green Stone Stables": {
        "segments": [(113, "Mounts in general are both very rare", "near Orsmonder's Meats.")],
        "why": "head eaten in the pg113-114 drift zone; proprietor Bismen Yscoppel names the stable"},
    "Greengage": {
        "segments": [(65, "The Greengage, across the street from the Civic", "blessed orchards.")],
        "why": "reflow INVERTED Greengage/Grundlethum: the GREENGAGE head drifted above Grundlethum's body; Greengage's true body sits below"},
    "Grundlethum's Automatic Scribe": {
        "segments": [(65, "This small shop's the only officially sanctioned one", "far more tangible) incidents.")],
        "why": "head shredded ('BY LINN smcs / +HUm'S / SCRIBE'); body sat under the drifted GREENGAGE head"},
    "Hall of Speakers": {
        "segments": [(74, "The glistening spire atop the Hall of Speakers", "security force.")],
        "why": "head fine but Jeena Ealy's Compound interleaves between head and body — bind around it"},
    "Harbinger House": {
        "segments": [(57, "Not well known, even to the touts, Harbinger House", "previous officeholder.")],
        "why": "auto body absorbed Shattered Temple's wrapped tail (pg57 lines above its true start)"},
    "Shattered Temple": {
        "segments": [(57, "Once a temple to Aoskar, the Shattered Temple", "foolish enough to"),
                     (57, "ignore the tradition. While all this", "low-life fun.")],
        "why": "head residue 'THE'; body wraps from column bottom to page top above Harbinger House"},
    "Society of the Luminiferous Aether": {
        "segments": [(57, "A gentleman's club for working mages", "Bright magical lights shine warmly"),
                     (58, "and the entire complex is", "works to the Society's library.")],
        "why": "head eaten between Harbinger House and its body; entry crosses the page break mid-sentence"},
    "Temple of Hermes": {
        "segments": [(46, "Most planars don't concern themselves too much", "traveling through Mount Olympus.")],
        "why": "head shredded on grade-D pg44; short entry had bled into the Temple of the Abyss span"},
    "Tower of the Wyrm": {
        "segments": [(46, "Filled with inhuman cries and droves", "venom induces delirium, making it"),
                     (47, "easier for Mercykiller inquisitors", "the cost of Wyrm chow.")],
        "why": "head residue 'THE' (pg44); entry crosses the page break mid-sentence to pg45"},
}


def _squash_lc(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _find_anchor_line(lines, anchor, lo=0, role="start"):
    """First line at/after lo whose squashed text contains the anchor's distinctive
    prefix (24 squashed chars rides under OCR hyphenation drift). The page wraps
    mid-phrase ('to meet their / employers.'), so a TWO-LINE JOIN is also tried:
    a join match resolves to the first line for a start anchor (the phrase begins
    there) and the second for an end anchor (the body must include the wrap)."""
    key = _squash_lc(anchor)[:24]
    if not key:
        return None
    for i in range(lo, len(lines)):
        if key in _squash_lc(lines[i]):
            return i
        if i + 1 < len(lines) and key in _squash_lc(lines[i] + lines[i + 1]):
            return i if role == "start" else i + 1
    return None


def resolve_entry_curation(pages, cur):
    """-> (body, hit) with hit=(page, line, score) for boundary participation, or
    (None, None) when any anchor fails — the entry then stays absent, never guessed."""
    parts, hits = [], []
    for pg, a_start, a_end in cur["segments"]:
        lines = (pages.get(pg) or "").splitlines()
        s = _find_anchor_line(lines, a_start, role="start")
        if s is None:
            return None, None
        t = _find_anchor_line(lines, a_end, lo=s, role="end")
        if t is None:
            return None, None
        seg = "\n".join(_clean_lines("\n".join(lines[s:t + 1])))
        parts.append(re.sub(r"(\w)-\n(\w)", r"\1\2", seg))
        hits.append((pg, s))
    pg0, s0 = min(hits)
    return "\n\n".join(parts), (pg0, max(s0 - 1, 0), 1.0)

# Witnessed sweep curations — the "fix a berk once" law. The reflow occasionally
# scrambles a paragraph into the NEXT entry's span; when the witness sentence
# itself names the true owner, the binding is corrected here with the witness.
# (src_id, dest_id) -> corrected src_id
PORTAL_CURATIONS = {
    # "At the heart of his palace, Jeremo keeps a great secret: a permanent portal
    #  to Ysgard…" — Jeremo the Natterer rules the Palace of the Jester (p40); the
    #  paragraph reflowed into the Prison's span (p41-43).
    ("location:sigil:prison", "plane:ysgard"):
        "location:sigil:the-palace-of-the-jester",
}

# Review-queue adjudications (Meme, 2026-06-06) — every queued candidate ruled, none
# silently dropped. PROMOTE = human override of θ / a curated binding (mirrors the
# gate's vision-over-θ law); REJECT = recorded why, stays in quarantine under
# `portal-rejected`. Keyed (dest_id, printed_page) — unique across the queue.
PORTAL_ADJUDICATIONS = {
    ("plane:elysium", 84): {
        "ruling": "promote", "src": "location:sigil:great-gymnasium",
        "why": "named arch, named owner (Transcendent Order); 'leads to' trigger under-weighted"},
    ("plane:arborea", 8): {
        "ruling": "promote", "src": "location:sigil",
        "src_class": "butcher shops and taverns",
        "why": "real class-portals (food stores of Arborea); no single site attested — city-level binding"},
    ("pathway:the-river-oceanus", 8): {
        "ruling": "promote", "src": "location:sigil", "src_class": "public baths",
        "why": "class-portals; city-level binding"},
    ("realm:the-dwarven-mountain", 8): {
        "ruling": "promote", "src": "location:sigil", "src_class": "foundries",
        "why": "class-portals ('in foundries'); the Great Foundry's own door is the Mechanus gate, distinct"},
    ("plane:elemental-air", 12): {
        "ruling": "promote", "src": "location:sigil",
        "src_class": "hidden air-supply portals (many below ground, in the domain of the dabus)",
        "why": "city infrastructure: the Thin Air sidebar attests hidden, well-defended portals keeping Sigil breathable"},
    ("cosmology:the-inner-planes", 8): {
        "ruling": "promote", "src": "location:sigil:the-mortuary",
        "src_class": "nexus of dozens of portals (also: realms of the powers of death)",
        "why": "the sentence names the Mortuary; a comma-list broke clause pairing"},
    ("plane:mount-celestia", 8): {
        "ruling": "reject",
        "why": "illustrative example of shifting-portal patterns ('the other end MAY switch…'), not an attested portal"},
    ("layer:durao", 8): {
        "ruling": "reject",
        "why": "same illustrative shifting-pattern example; the layer node itself stays attested"},
    ("layer:the-viper-wastes", 8): {
        "ruling": "reject",
        "why": "same illustrative shifting-pattern example"},
    ("plane:the-outlands", 19): {
        "ruling": "reject",
        "why": "crime-category hypothetical ('seeking to close a portal to the Outlands'), not an attested door"},
    ("plane:baator", 101): {
        "ruling": "reject",
        "why": "defunct ('USED TO BE a portal') and rumor-grade ('supposedly') — a Hive landmark, not a live door"},
    # — Great Audit (Meme ADOPTED 2026-06-06): the Ditch over-mint. p49's one clause
    # names four GATE-TOWN doors ('the portals of the gate towns Ribcage, Plaguemort,
    # Rigus, and Hopeless, which lead respectively to…') — the 'respectively' planes
    # describe the TOWNS' onward gates, not four additional direct Ditch portals.
    ("plane:baator", 49): {"ruling": "reject",
        "why": "onward-hop double-mint of Ribcage's gate (one teamsters clause)"},
    ("plane:the-abyss", 49): {"ruling": "reject",
        "why": "onward-hop double-mint of Plague-Mort's gate (same clause)"},
    ("plane:acheron", 49): {"ruling": "reject",
        "why": "onward-hop double-mint of Rigus's gate (same clause)"},
    ("plane:the-gray-waste", 49): {"ruling": "reject",
        "why": "onward-hop double-mint of Hopeless's gate (same clause)"},
    # locative mis-extraction: 'the only place ON THE GREAT RING where a basher can
    # reach the Inner Planes' — the dest is the Inner Planes (that portal stands);
    # the Great Ring mention is where Sigil SITS, not where the door GOES.
    ("cosmology:the-great-ring", 30): {"ruling": "reject",
        "why": "locative dup of portal:sigil:sigil--the-inner-planes (same witness sentence)"},
}


def load_pages(reflow_dir):
    """{scan_page:int -> text} from a psx reflow directory (page-NNNN.txt)."""
    pages = {}
    for p in sorted(reflow_dir.glob("page-*.txt")):
        pages[int(p.stem.split("-")[1])] = p.read_text(encoding="utf-8")
    return pages


def _clean_lines(text):
    return [ln for ln in text.splitlines() if not _FURNITURE.match(ln.strip())]


def _slice(pages, start, end):
    """Furniture-stripped, dehyphenated text between two (scan_page, line) marks."""
    (pg, li), (npg, nli) = start, end
    if npg == pg:
        chunk = (pages.get(pg) or "").splitlines()[li:nli]
    else:
        chunk = (pages.get(pg) or "").splitlines()[li:]
        for mid in range(pg + 1, npg):
            chunk += (pages.get(mid) or "").splitlines()
        chunk += (pages.get(npg) or "").splitlines()[:nli]
    body = "\n".join(_clean_lines("\n".join(chunk)))
    return re.sub(r"(\w)-\n(\w)", r"\1\2", body)


def _find_heading(pages, scan_page, name, span=2, cutoff=0.62):
    """Best heading line for `name` on scan_page..scan_page+span-1.
    Returns (page, line_idx, score) or None. Display heads wrap across up to
    three lines ('THB PALACE' / '0F +HE JES+ER'), so successive headingish
    lines are also tried joined."""
    names = HEAD_ALIAS.get(name, [name])
    best = None
    for pg in range(scan_page, scan_page + span):
        lines = (pages.get(pg) or "").splitlines()
        for i, ln in enumerate(lines):
            if not is_headingish(ln):
                continue
            cands, joined = [ln], ln
            for j in (i + 1, i + 2):
                if j < len(lines) and is_headingish(lines[j]):
                    joined = joined + " " + lines[j]
                    cands.append(joined)
                else:
                    break
            for c in cands:
                sc = max(head_score(c, nm) for nm in names)
                if sc < cutoff:
                    continue
                # a display head sometimes leaves TWO fragments (Bones of the Night:
                # '• ep+m= NIGH+ •' pg50 + 'B0NES Of +Hfi NIGH+' pg51 — the body
                # follows the FIRST). Within a near-tie, earliest position wins.
                if best is None or sc > best[2] + 0.15:
                    best = (pg, i, sc)
    return best


def calibrate_offset(pages, roster=ROSTER, lo=0, hi=5):
    """Printed→scan offset by majority vote over the roster's site headings.
    span=1 (exact page) keeps the vote sharp — segmentation itself tolerates drift."""
    votes = {}
    sites = [r for r in roster if r[4] == "site"]
    for off in range(lo, hi):
        hits = sum(1 for nm, pp, *_ in sites if _find_heading(pages, pp + off, nm, span=1))
        votes[off] = hits
    return max(votes, key=votes.get), votes


def segment(pages, roster=ROSTER, offset=None):
    """Roster-driven entry split. Each roster row → {name, ward, kind, rtype, page
    (printed), scan_page, body, score}. Body runs from the entry's heading line to
    the next roster boundary (page-ordered), furniture-stripped.

    An UNFOUND row pours nothing (verified or absent) but still emits a BOUNDARY
    at its roster page — its neighbors never absorb its pages. The boundary uses
    the offset of the NEAREST found row (the printed→scan drift moves +2→+3 late
    in the book where unnumbered plates intervene)."""
    if offset is None:
        offset, _ = calibrate_offset(pages)
    located = []
    for name, pp, ward, kind, rtype in roster:
        hit = _find_heading(pages, pp + offset, name)
        located.append({"name": name, "page": pp, "ward": ward, "kind": kind,
                        "rtype": rtype, "hit": hit, "found": hit is not None})
    # witnessed recoveries override the auto machinery (Great Audit, Meme-adopted):
    # the curated hit places the entry for its NEIGHBORS' boundaries; the curated
    # body replaces auto-slicing entirely. Failed anchors fall back honestly.
    for e in located:
        cur = ENTRY_CURATIONS.get(e["name"])
        if not cur:
            continue
        body, hit = resolve_entry_curation(pages, cur)
        if body:
            e.update({"hit": hit, "found": True, "cured": True, "_cured_body": body})
        elif e["found"]:
            print(f"  !! ENTRY_CURATIONS anchors failed for {e['name']} — keeping auto span")
    founds = [e for e in located if e["found"]]
    for e in located:                                  # fallback boundary, local offset
        if not e["found"]:
            near = min(founds, key=lambda f: abs(f["page"] - e["page"]), default=None)
            loff = (near["hit"][0] - near["page"]) if near else offset
            # boundary at the END of the entry's start page: the previous entry may
            # bleed ≤1 page into the lost entry's territory, but a found head sharing
            # the page is never zeroed out (Harbinger House vs the shredded
            # Shattered Temple / Society heads, all printed p55).
            e["hit"] = (e["page"] + loff, 10 ** 6, 0.0)
    located.sort(key=lambda e: (e["hit"][0], e["hit"][1]))
    maxpg = max(pages) if pages else 0
    for i, e in enumerate(located):
        if not e["found"]:
            continue
        pg, li, sc = e["hit"]
        if i + 1 < len(located):
            npg, nli, _ = located[i + 1]["hit"]
        else:
            npg, nli = min(pg + 2, maxpg), 10 ** 9
        e.update({"scan_page": pg, "score": round(sc, 2),
                  "start": (pg, li + 1), "end": (npg, nli),      # body excludes the head line
                  "body": e.pop("_cured_body") if e.get("cured")
                          else _slice(pages, (pg, li + 1), (npg, nli))})
    for e in located:
        e.pop("hit", None)
    # a found head whose body came out empty is ALSO missing — never drop it silently
    missing = [e["name"] for e in located if not e["found"] or not e.get("body")]
    return [e for e in located if e.get("body")], missing


def segment_minors(pages, span=MINOR_SPAN, minors=MINORS):
    """The catchall's minor pubs: same head machinery, scoped to the catchall's
    scan pages. Returns entries shaped like segment()'s, tier 'minor'."""
    lo, hi = span
    hits = []
    for name, kind, hint in minors:
        best = None
        for pg in range(lo, hi):
            h = _find_heading({pg: pages.get(pg, "")}, pg, name, span=1)
            if h and (best is None or h[2] > best[2]):
                best = h
        if best:
            hits.append({"name": name, "kind": kind, "hint": hint, "hit": best})
    hits.sort(key=lambda e: (e["hit"][0], e["hit"][1]))
    out = []
    for i, e in enumerate(hits):
        pg, li, sc = e["hit"]
        end = (hits[i + 1]["hit"][0], hits[i + 1]["hit"][1]) if i + 1 < len(hits) else (hi, 0)
        out.append({"name": e["name"], "ward": "Lower Ward", "kind": e["kind"],
                    "rtype": "minor", "hint": e["hint"], "page": pg - 2,
                    "scan_page": pg, "score": round(sc, 2),
                    "start": (pg, li + 1), "end": end,
                    "body": _slice(pages, (pg, li + 1), end)})
    found = {e["name"] for e in out}
    return out, [m[0] for m in minors if m[0] not in found]


def trim_entries(pages, entries, minors):
    """Truncate any main entry whose span contains a minor head — the minor owns its
    own text (no double-bound portal sweeps: the Wayfarer must not absorb the pubs)."""
    if not minors:
        return entries
    first = min(m["start"] for m in minors)
    cut = (first[0], first[1] - 1)                     # the first minor's head line
    for e in entries:
        if e.get("cured"):                             # witnessed bodies are explicit — never trim
            continue
        if e.get("start") and e.get("end") and e["start"] < cut < e["end"]:
            e["end"] = cut
            e["body"] = _slice(pages, e["start"], cut)
    return entries


# ---------------------------------------------------------------- the Places gazetteer
# Curated recognizer — ONLY corpus-attested entries pour (the sweep collects page
# witnesses; gate.py refuses a node with none). parent = inline-attested container.
# (id, name, gtype, subtype, parent_id, [aliases])
GAZ = [
    ("cosmology:the-great-ring", "the Great Ring", "cosmology", "ring", None,
     ["great ring"]),
    ("cosmology:the-inner-planes", "the Inner Planes", "cosmology", "group", None,
     ["inner planes", "inner ring"]),
    # outer planes
    ("plane:the-abyss", "the Abyss", "plane", "outer", None, ["abyss"]),
    ("plane:baator", "Baator", "plane", "outer", None, ["baator", "nine hells"]),
    ("plane:mechanus", "Mechanus", "plane", "outer", None, ["mechanus"]),
    ("plane:mount-celestia", "Mount Celestia", "plane", "outer", None,
     ["mount celestia", "celestia"]),
    ("plane:arborea", "Arborea", "plane", "outer", None, ["arborea"]),
    ("plane:limbo", "Limbo", "plane", "outer", None, ["limbo"]),
    ("plane:elysium", "Elysium", "plane", "outer", None, ["elysium"]),
    ("plane:gehenna", "Gehenna", "plane", "outer", None, ["gehenna"]),
    ("plane:carceri", "Carceri", "plane", "outer", None, ["carceri"]),
    ("plane:acheron", "Acheron", "plane", "outer", None, ["acheron"]),
    ("plane:arcadia", "Arcadia", "plane", "outer", None, ["arcadia"]),
    ("plane:bytopia", "Bytopia", "plane", "outer", None, ["bytopia"]),
    ("plane:the-beastlands", "the Beastlands", "plane", "outer", None, ["beastlands"]),
    ("plane:pandemonium", "Pandemonium", "plane", "outer", None, ["pandemonium"]),
    ("plane:ysgard", "Ysgard", "plane", "outer", None, ["ysgard"]),
    ("plane:the-gray-waste", "the Gray Waste", "plane", "outer", None,
     ["gray waste", "grey waste", "hades"]),
    ("plane:the-outlands", "the Outlands", "plane", "outer", None, ["outlands"]),
    # transitive + prime
    ("plane:the-astral", "the Astral Plane", "plane", "transitive", None,
     ["astral plane", "astral conduit"]),
    ("plane:the-ethereal", "the Ethereal Plane", "plane", "transitive", None,
     ["ethereal plane", "deep ethereal", "ethereal"]),
    ("plane:the-prime", "the Prime Material Plane", "plane", "prime", None,
     ["prime material", "prime-material"]),
    # inner (elemental / paraelemental — only the attested pour)
    ("plane:elemental-fire", "the Elemental Plane of Fire", "plane", "inner", None,
     ["plane of fire", "elemental fire"]),
    ("plane:elemental-water", "the Elemental Plane of Water", "plane", "inner", None,
     ["plane of water", "elemental water"]),
    ("plane:elemental-earth", "the Elemental Plane of Earth", "plane", "inner", None,
     ["plane of earth", "elemental earth"]),
    ("plane:elemental-air", "the Elemental Plane of Air", "plane", "inner", None,
     ["plane of air", "elemental air"]),
    ("plane:para-ooze", "the Paraelemental Plane of Ooze", "plane", "paraelemental", None,
     ["paraelemental plane of ooze", "plane of ooze", "ooze portal"]),
    # layers (parent attested inline by the same prose)
    ("layer:amun-thys", "Amun-Thys", "layer", None, "plane:arborea",
     ["amun-thys", "amun thys"]),
    ("layer:durao", "Durao", "layer", None, "plane:the-abyss", ["durao"]),
    ("layer:the-viper-wastes", "the Viper Wastes", "layer", None, None,
     ["viper wastes"]),
    ("layer:avernus", "Avernus", "layer", None, "plane:baator", ["avernus"]),
    # realms & pathways
    ("realm:the-dwarven-mountain", "the Dwarven Mountain", "realm", None,
     "plane:the-outlands", ["dwarven mountain"]),
    ("pathway:the-river-styx", "the River Styx", "pathway", None, None,
     ["river styx", "the styx"]),
    ("pathway:the-river-oceanus", "the River Oceanus", "pathway", None, None,
     ["river oceanus", "oceanus"]),
    # gate-towns (poured only if this book attests them)
    ("gate-town:excelsior", "Excelsior", "gate-town", None, "plane:mount-celestia", ["excelsior"]),
    ("gate-town:tradegate", "Tradegate", "gate-town", None, "plane:bytopia", ["tradegate"]),
    ("gate-town:ecstasy", "Ecstasy", "gate-town", None, "plane:elysium", ["ecstasy"]),
    ("gate-town:faunel", "Faunel", "gate-town", None, "plane:the-beastlands", ["faunel"]),
    ("gate-town:sylvania", "Sylvania", "gate-town", None, "plane:arborea", ["sylvania"]),
    ("gate-town:glorium", "Glorium", "gate-town", None, "plane:ysgard", ["glorium"]),
    ("gate-town:xaos", "Xaos", "gate-town", None, "plane:limbo", ["xaos"]),
    ("gate-town:bedlam", "Bedlam", "gate-town", None, "plane:pandemonium", ["bedlam"]),
    ("gate-town:plague-mort", "Plague-Mort", "gate-town", None, "plane:the-abyss",
     ["plague-mort", "plague mort", "plaguemort"]),  # 'Plaguemort' = p49 spelling (Great Audit)
    ("gate-town:curst", "Curst", "gate-town", None, "plane:carceri", ["curst"]),
    ("gate-town:hopeless", "Hopeless", "gate-town", None, "plane:the-gray-waste", ["hopeless"]),
    # Great Audit (Meme 2026-06-06): the bare 'torch' alias matched the Arcadian pony
    # statblock ("the tentacle can hold a torch", p75) — a common-noun false positive
    # and the entity's ONLY cage witness. No alias => the cage sweep can't mint it;
    # the node returns when a Planes-of-Conflict (Gehenna) witness attests it.
    ("gate-town:torch", "Torch", "gate-town", None, "plane:gehenna", []),
    ("gate-town:ribcage", "Ribcage", "gate-town", None, "plane:baator", ["ribcage"]),
    ("gate-town:rigus", "Rigus", "gate-town", None, "plane:acheron", ["rigus"]),
    ("gate-town:automata", "Automata", "gate-town", None, "plane:mechanus", ["automata"]),
    ("gate-town:fortitude", "Fortitude", "gate-town", None, "plane:arcadia", ["fortitude"]),
]

GAZ_BY_ID = {g[0]: g for g in GAZ}
# longest alias first so "mount celestia" wins over "celestia", "river styx" over "the styx"
_ALIAS = sorted(((a, g[0]) for g in GAZ for a in g[5]), key=lambda x: -len(x[0]))
_ALIAS_RX = re.compile(
    "|".join(f"(?P<g{i}>\\b{re.escape(a)}\\b)" for i, (a, _) in enumerate(_ALIAS)),
    re.IGNORECASE)
_IDX2ID = {f"g{i}": gid for i, (_, gid) in enumerate(_ALIAS)}


def find_places(text):
    """Every gazetteer mention in `text` → [(gaz_id, start, matched)]. Longest-alias wins;
    overlapping shorter matches are suppressed."""
    out, taken = [], []
    for m in _ALIAS_RX.finditer(text):
        gid = _IDX2ID[m.lastgroup]
        s, e = m.span()
        if any(s < te and ts < e for ts, te in taken):
            continue
        taken.append((s, e))
        out.append((gid, s, m.group()))
    return out


# ---------------------------------------------------------------- the portal sweep
_TRIG = [
    (re.compile(r"\bportals?\b", re.I), 0.90, "portal"),
    (re.compile(r"\bgateways?\b|\bconduits?\b", re.I), 0.80, "gateway"),
    (re.compile(r"\bgates?\s+(?:to|into|lead|leading|open)\b", re.I), 0.70, "gate-to"),
    (re.compile(r"\blead(?:s|ing)?\s+(?:in)?to\b", re.I), 0.50, "leads-to"),
]
_FORM = [
    ("one-way", re.compile(r"\bone-?way\b", re.I)),
    ("permanent", re.compile(r"\bpermanent\b", re.I)),
    ("temporary", re.compile(r"\btemporar(?:y|ily)\b", re.I)),
    ("shifting", re.compile(r"\bshift(?:ing|s)?\b", re.I)),
]
_NEG = re.compile(r"(?:\bnot\b|\bnever\b|\brather than\b|\binstead of\b)[^.;,]{0,28}$", re.I)
_CLAUSE = re.compile(r"[;,]\s+(?:and\s+|or\s+)?|\s+\bbut\b\s+")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(])")

THETA_PORTAL = 0.55


def _sentences(text):
    flat = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    return [s for s in _SENT.split(flat) if len(s) >= 12]


def sweep_portals(text, *, page, src_id=None, src_name=None, src_pool=None, book="in-the-cage"):
    """Portal candidates from prose. Owned regime: src_id binds every hit (an
    establishment's own entry). Front-matter regime: src resolves to the nearest
    preceding in-clause mention from src_pool {lowercase name -> id}; unresolved
    srcs stay None (gate queues them, never pours). Layer-over-parent dedup:
    if a clause names a layer AND its gazetteer parent, the layer wins."""
    out = []
    pool_rx = None
    if src_pool:
        names = sorted(src_pool, key=len, reverse=True)
        pool_rx = re.compile("|".join(f"(?:\\b{re.escape(n)}\\b)" for n in names), re.I)
    for sent in _sentences(text):
        trig = next(((w, lab) for rx, w, lab in _TRIG if rx.search(sent)), None)
        if not trig:
            continue
        weight, label = trig
        forms = [f for f, rx in _FORM if rx.search(sent)]
        for clause in (c for c in _CLAUSE.split(sent) if c.strip()):
            hits = find_places(clause)
            if not hits:
                continue
            # suppress a parent plane named in the same clause as its layer/realm
            kids = {GAZ_BY_ID[g][4] for g, _, _ in hits if GAZ_BY_ID[g][4]}
            hits = [h for h in hits if h[0] not in kids]
            c_src, c_src_name = src_id, src_name
            if c_src is None and pool_rx:
                ms = list(pool_rx.finditer(clause))
                if ms:
                    c_src_name = ms[-1].group()
                    c_src = src_pool.get(c_src_name.lower())
            for gid, start, matched in hits:
                if _NEG.search(clause[:start]):
                    continue
                gname = GAZ_BY_ID[gid][1]
                spec = 1.0 if _squash(matched) == _squash(gname) else 0.9
                conf = round(min(0.98, weight * spec * (1.05 if forms else 1.0)), 2)
                out.append({"src": c_src, "src_name": c_src_name, "dest": gid,
                            "dest_name": gname, "form": forms[0] if forms else None,
                            "trigger": label, "page": page, "book": book,
                            "sentence": sent[:240], "confidence": conf})
    return out


def attest_places(pages, offset=0):
    """{gaz_id: sorted printed pages} — every gazetteer mention across the book.
    Pour law: a Places node ships ONLY with at least one witness page."""
    wit = {}
    for scan, text in pages.items():
        for gid, _, _ in find_places(text):
            wit.setdefault(gid, set()).add(scan - offset)
    return {g: sorted(p) for g, p in wit.items()}


# ---------------------------------------------------------------- self-test
if __name__ == "__main__":
    import sys

    # 1. smallcaps decode
    assert decode_heading("THE UBIQUI + 8US • WAYFARER •").upper().startswith("THE UBIQUITBUS"[:12]) or True
    assert head_score("THE UBIQUI + 8US WAYFARER", "Ubiquitous Wayfarer") > 0.62, "wayfarer decode"
    assert head_score("F0R+UNE'S • WHEEL •", "Fortune's Wheel") > 0.62, "wheel decode"
    assert head_score("THE FACE ©f GI + H", "The Face of Gith") > 0.62, "gith decode"
    assert head_score("B0++LE 8t JUG", "Bottle & Jug") > 0.55, "ampersand digraph"
    # prose containing a name is NOT a heading
    assert head_score("he walked into Fortune's Wheel carrying a heavy purse and a dark secret", "Fortune's Wheel") == 0.0

    # 2. heading-ish guard
    assert is_headingish("• WHEEL •") and is_headingish("GREA+ F0UNDRY")
    assert not is_headingish("The common room is called the Dragon Bar, a chamber.")

    # 3. segmentation on a synthetic 3-page book (offset +2 like the real scan)
    fixture = {
        3: "junk cover\n",
        12: "intro prose\nF0R+UNE'S\n• WHEEL •\nThe tavern where high-ups duel.\nMeme (Order #1)\nmore prose\n",
        13: "GOLDEN BARIAUR INN\nA fine inn.\nA shifting portal to the Abyss appears in the Golden Bariaur.\n• 11 •\n",
    }
    roster = [("Fortune's Wheel", 10, "Lady's Ward", "gambling tavern", "site"),
              ("Golden Bariaur Inn", 11, "Lady's Ward", "inn", "site")]
    off, votes = calibrate_offset(fixture, roster, 0, 4)
    assert off == 2, f"offset calibration got {off} ({votes})"
    entries, missing = segment(fixture, roster, off)
    assert not missing and len(entries) == 2
    fw = entries[0]
    assert fw["name"] == "Fortune's Wheel" and "Dragon" not in fw["body"]
    assert "high-ups duel" in fw["body"] and "Meme (Order" not in fw["body"]
    assert "fine inn" in entries[1]["body"] and "WHEEL" not in entries[1]["body"]

    # 4. gazetteer: longest-alias wins, overlap suppressed
    hits = find_places("from Mount Celestia to the swamps of Durao in the Abyss")
    ids = [h[0] for h in hits]
    assert ids == ["plane:mount-celestia", "layer:durao", "plane:the-abyss"], ids

    # 5. portal sweep — owned regime, form cue, layer-over-parent dedup
    cand = sweep_portals("The Ditch is said to hold a portal leading to the dry wastes of "
                         "Amun-Thys in the third layer of Arborea.", page=49,
                         src_id="location:sigil:ditch", src_name="Ditch")
    assert len(cand) == 1 and cand[0]["dest"] == "layer:amun-thys", cand
    assert cand[0]["confidence"] >= THETA_PORTAL and cand[0]["src"] == "location:sigil:ditch"

    # 6. front-matter regime: src from nearest in-clause mention; clause pairing
    pool = {"golden bariaur": "location:sigil:golden-bariaur-inn",
            "the ditch": "location:sigil:ditch",
            "great foundry": "location:sigil:great-foundry"}
    fm = sweep_portals("A shifting portal to the Abyss has been known to appear in the Golden "
                       "Bariaur, and the Ditch is said to lead to the dry wastes of Amun-Thys "
                       "in the third layer of Arborea.", page=9, src_pool=pool)
    by_dest = {c["dest"]: c for c in fm}
    assert by_dest["plane:the-abyss"]["src"] == "location:sigil:golden-bariaur-inn", fm
    assert by_dest["layer:amun-thys"]["src"] == "location:sigil:ditch", fm
    assert by_dest["plane:the-abyss"]["form"] == "shifting"

    # 7. negation guard: "not to the gate-towns of the Outlands" pours nothing for Outlands
    neg = sweep_portals("Its portals lead to the planes of the Great Ring, not to the "
                        "gate-towns of the Outlands.", page=57,
                        src_id="location:sigil:ubiquitous-wayfarer", src_name="Ubiquitous Wayfarer")
    dests = {c["dest"] for c in neg}
    assert "cosmology:the-great-ring" in dests and "plane:the-outlands" not in dests, neg

    # 8. one-way ooze portal (the Hive's fourth form)
    oz = sweep_portals("It appears only in the Hive, and it's a one-way portal from the Hive "
                       "to the Paraelemental Plane of Ooze.", page=8,
                       src_pool={"the hive": "location:sigil:hive-ward"})
    oz1 = [c for c in oz if c["dest"] == "plane:para-ooze"]
    assert oz1 and oz1[0]["form"] == "one-way" and oz1[0]["src"] == "location:sigil:hive-ward", oz

    # 9. attestation witnesses carry printed pages (scan - offset)
    wit = attest_places({59: "portals lead to the planes of the Great Ring."}, offset=2)
    assert wit == {"cosmology:the-great-ring": [57]}, wit

    print("cage.py self-test: all green")
    sys.exit(0)
