#!/usr/bin/env python
"""normalize — the gear-house.

Every OCR-repair and structured-field rule lives here, factored out of the extractor so the
machine can grow to ten billion gears without seizing: dice repair, text de-hyphenation, the
see-also name guard, and the positional AD&D-2e descriptor parser. Each gear is small, named,
and (where it matters) self-tested in __main__ — "if it machines."

Tailored per-case handlers belong here too: when a general rule can't reach a case, add a
narrow handler beside the general one rather than bending the general rule out of true.
"""
import re
import difflib

# ─────────────────────────────────────────────────────────────── dice repair
# OCR digit lookalikes — applied ONLY inside dice tokens, where count/sides MUST be numeric, so a
# letter there is a misread digit. A plausible-die-size guard means prose is never corrupted.
_DIGIT_OCR = str.maketrans({"I": "1", "l": "1", "|": "1", "!": "1", "O": "0", "o": "0",
                            "B": "8", "S": "5", "Z": "2", "G": "6", "V": "4"})
_DICE_OCR_RE = re.compile(r"(?<![A-Za-z0-9])([0-9IlO|B]*)[dD]([0-9IlOBSZGV]+)(\s*[+\-]\s*[0-9IlOBSZGV]+)?")
_STD_DICE = {1, 2, 3, 4, 6, 8, 10, 12, 20, 100}


def normalize_dice_ocr(s, anomalies=None):
    """Id4/ld4/ldV/ldlO+1/2dB -> 1d4/1d4/1d4/1d10+1/2d8. Touches only dice tokens whose normalized
    sides are a real die; every other character is left exactly as-is."""
    def fix(m):
        nc = m.group(1).translate(_DIGIT_OCR)
        ns = m.group(2).translate(_DIGIT_OCR)
        nm = re.sub(r"\s+", "", m.group(3) or "").translate(_DIGIT_OCR)
        if re.fullmatch(r"\d*", nc) and re.fullmatch(r"\d+", ns) and int(ns) in _STD_DICE \
                and re.fullmatch(r"(?:[+\-]\d+)?", nm):
            out = f"{nc}d{ns}{nm}"
            if out != m.group(0).strip() and anomalies is not None:
                anomalies.append(f"dice OCR {m.group(0).strip()!r}->{out!r}")
            return out
        return m.group(0)
    return _DICE_OCR_RE.sub(fix, s)


def norm_num(tok, anomalies, ctx):
    """Numeric-context OCR repair (e.g. movement rates): 'IS' -> '15', 'lO' -> '10'."""
    if re.fullmatch(r"[0-9IlSO]+", tok) and re.search(r"[IlSO]", tok):
        fixed = tok.translate(str.maketrans("IlSO", "1150"))
        anomalies.append(f"{ctx} OCR num {tok!r}->{fixed!r}")
        return fixed
    return tok


# ─────────────────────────────────────────────────────────────── text
def dehyphenate(text):
    """Join line-wrap hyphen splits inside a token: 'She- meshka' -> 'Shemeshka'."""
    return re.sub(r"(\w)-\s+(\w)", r"\1\2", text)


_SEE_CONNECTORS = {"the", "of", "de", "von", "la", "le", "el", "da", "and"}


def is_name(nm):
    """A proper name = 1-6 Title-case words joined only by connectors — not a prose run.
    Rejects 'Adamok sticking knives into her head in a Ebon'; keeps 'Shemeshka the Marauder'."""
    ws = nm.split()
    return bool(ws) and len(ws) <= 6 and not [
        w for w in ws if w[:1].islower() and w.lower() not in _SEE_CONNECTORS]


# ─────────────────────────────────────────────────── 2e descriptor parser
ALIGNMENTS = {"LG", "NG", "CG", "LN", "N", "CN", "LE", "NE", "CE", "TN"}
FACTIONS = ["Athar", "Believers of the Source", "Bleak Cabal", "Doomguard", "Dustmen", "Fated",
            "Fraternity of Order", "Free League", "Harmonium", "Mercykillers", "Revolutionary League",
            "Sign of One", "Society of Sensation", "Transcendent Order", "Xaositects",
            "Incantifier", "Prolonger", "Merkhant", "Sodkillers", "Sons of Mercy"]
# class codes tolerate a space ('Pal 13', 'Ill 12') and multi-class ('F7,M4')
CLASS_RE = re.compile(r"^(?:[FMCTPRB]|Ill|Pal|Wil|Psi|Pri|Wiz|Bd|Th)\s*\d|^O-level", re.I)
PLANE_CODES = {"Pl": "Pl", "PI": "Pl", "P1": "Pl", "Pr": "Pr", "Pe": "Pr",
               "Px": "Px", "M": "M", "Pm": "Pm", "Pd": "Pd"}
# the glyph alphabet of a leading sex/level marker (♂♀ and levels OCR'd a dozen ways)
_SEX_GLYPHS = set("0123456789cCJ<>$?dDsSgG*.♂♀ƒ+")


def parse_plane(part):
    """First slot -> (plane_code, power). 'Px [Aoskar]' -> ('Px','Aoskar'); 'PI' -> ('Pl', None)."""
    m = re.match(r"\s*([A-Za-z][A-Za-z0-9]?)\s*(?:[\[(]([^\])]+)[\])]?)?", part)
    if not m:
        toks = part.split()
        return (toks[0] if toks else None), None
    code = PLANE_CODES.get(m.group(1), m.group(1))
    power = m.group(2).strip().rstrip("l").strip() if m.group(2) else None  # 'Aoskarl' OCR tail
    return code, power


def split_sex_race(part):
    """'0 dabus' -> ('0','dabus'); 'c? human' -> ('c?','human'); 'pack of 112 rats' -> (None, whole);
    'eladrin [firre]' -> (None, 'eladrin [firre]'). A leading all-glyph token is the sex/level marker."""
    part = part.strip()
    toks = part.split()
    if len(toks) >= 2 and toks[0] and all(c in _SEX_GLYPHS for c in toks[0]):
        return toks[0], " ".join(toks[1:])
    return None, part


def parse_descriptor(s, anomalies=None):
    """Positional parse of '(PLANE/[sex] RACE/CLASS|HD/[FACTION]/ALIGN)'. Race comes from the
    SECOND slot — never confused with the plane (the Fell 'Px [Aoskar]' bug) — and the leading
    sex/level glyph is split off it."""
    raw = s
    parts = [p.strip() for p in s.split("/") if p.strip()]
    d = {"raw": raw, "plane": None, "power": None, "sex": None, "race": None,
         "char_class": None, "level_hd": None, "faction": None, "alignment": None, "uncertain": []}
    if not parts:
        return d
    d["plane"], d["power"] = parse_plane(parts[0])
    # alignment = last slot, if it reads as one
    body = parts[1:]
    if body and body[-1].replace(" ", "") in ALIGNMENTS:
        d["alignment"] = body[-1].replace(" ", "")
        body = body[:-1]
    # race = the SECOND slot (the being descriptor), minus any leading sex/level glyph
    middle = []
    if body:
        d["sex"], d["race"] = split_sex_race(body[0])
        middle = body[1:]
    for p in middle:                                   # class / HD / faction slots
        if re.match(r"HD\b", p):
            d["level_hd"] = re.sub(r"^HD\s*", "", p).strip()
        elif CLASS_RE.match(p):
            d["char_class"] = p
            if not d["level_hd"]:
                lv = re.search(r"\d+(?:,\d+)*", p)
                d["level_hd"] = lv.group() if lv else None
        elif difflib.get_close_matches(p, FACTIONS, n=1, cutoff=0.72):
            d["faction"] = difflib.get_close_matches(p, FACTIONS, n=1, cutoff=0.72)[0]
        else:
            d["uncertain"].append(f"slot:{p}")
    for k in ("plane", "race", "alignment"):
        if not d[k]:
            d["uncertain"].append(k)
    return d


# ─────────────────────────────────────────── garbled display-title decoder
# Display-font titles OCR badly but consistently: 'fARRew'→Farrow, 'VERDfiN'→Verden,
# 'fiS+AVAN'→Estavan, 'AU+0CH0N'→Autochon. We don't decode blind — we light-normalize the title
# and fuzzy-match it against a pool of CLEAN names (the cross-reference vocabulary), so the garbled
# title only has to land NEARER the right name than any other. That's robust where blind OCR isn't.
_TITLE_SUBS = [("fi", "e"), ("+", "t"), ("0", "o"), ("1", "l"), ("9", "g"), ("$", "s"), ("€", "e")]


def _norm_garbled(t):
    t = (t or "").lower()
    for a, b in _TITLE_SUBS:
        t = t.replace(a, b)
    return re.sub(r"[^a-z]", "", t)


def name_keys(name):
    """Lookup keys for a clean name: the whole thing, plus its first significant word."""
    base = re.sub(r"[^a-z]", "", (name or "").lower())
    keys = {base} if base else set()
    toks = (name or "").split()
    if toks:
        first = re.sub(r"[^a-z]", "", toks[0].lower())
        if len(first) >= 4:
            keys.add(first)
    return keys


def decode_title(title, pool, cutoff=0.66):
    """Decode a garbled display title to a clean name from `pool` ({key: full_name}).
    Returns (name, ratio) or (None, ratio) when nothing clears the cutoff."""
    g = _norm_garbled(title)
    if len(g) < 3 or not pool:
        return None, 0.0
    best, best_r = None, 0.0
    for key, full in pool.items():
        r = difflib.SequenceMatcher(None, g, key).ratio()
        if r > best_r:
            best, best_r = full, r
    return (best, round(best_r, 2)) if best_r >= cutoff else (None, round(best_r, 2))


# ─────────────────────────────────────────────── Sigil location parser
SIGIL_WARDS = ["Lady's Ward", "Lower Ward", "Hive Ward", "Clerk's Ward", "Market Ward", "Guildhall Ward"]


def parse_location(text):
    """Pull Sigil geography from an NPC's LOCATION line: the ward (the canonical six) plus a named
    site when the line leads with one ('The Friendly Fiend, a magic shop in the Lower Ward')."""
    text = dehyphenate(text or "")
    ward = next((w for w in SIGIL_WARDS
                 if re.search(r"(?:The )?" + w.replace("'", "['’]?"), text)), None)
    m = re.match(r"\s*(?:at |in )?((?:The )?[A-Z][\w'’&]+(?:\s+(?:of |the )?[A-Z][\w'’&]+){0,3})"
                 r"\s*,\s*(?:an?|the)\b", text)
    site = m.group(1).strip() if m else None
    return {"ward": ward, "site": site, "in_sigil": bool(ward) or "Sigil" in text}


# ─────────────────────────────────────────────────────────────── self-test
if __name__ == "__main__":
    CASES = [
        # raw descriptor                                  plane  race                  class  faction        align
        ("Px [Aoskar]/0 dabus/HD 7/Sign of One/N",        "Px",  "dabus",              None,  "Sign of One",  "N"),
        ("PI/6* arcanaloth/HD 12+24/NE",                  "Pl",  "arcanaloth",         None,  None,           "NE"),
        ("Pl/cJ tiefling/B4/Xaositect/CN",                "Pl",  "tiefling",           "B4",  "Xaositects",   "CN"),
        ("Pr/cJ human/Pal 13/Harmonium/LG",              "Pr",  "human",              "Pal 13", "Harmonium", "LG"),
        ("Pl/pack of 112 cranium rats/HD 1 each/NE",      "Pl",  "pack of 112 cranium rats", None, None,     "NE"),
        ("M/razorvine/5 hp per vine/N",                   "M",   "razorvine",          None,  None,           "N"),
        ("PI/? eladrin [firre]/HD 7+10/CN",               "Pl",  "eladrin [firre]",    None,  None,           "CN"),
    ]
    ok = 0
    for raw, plane, race, klass, fac, align in CASES:
        d = parse_descriptor(raw)
        bad = []
        if d["plane"] != plane: bad.append(f"plane={d['plane']!r}≠{plane!r}")
        if d["race"] != race: bad.append(f"race={d['race']!r}≠{race!r}")
        if klass and d["char_class"] != klass: bad.append(f"class={d['char_class']!r}≠{klass!r}")
        if fac and d["faction"] != fac: bad.append(f"faction={d['faction']!r}≠{fac!r}")
        if d["alignment"] != align: bad.append(f"align={d['alignment']!r}≠{align!r}")
        print(("  OK  " if not bad else "FAIL  ") + raw)
        if bad: print("        " + "; ".join(bad))
        ok += not bad
    print(f"\n{ok}/{len(CASES)} descriptor cases machine.")

    POOL = {}
    for nm in ["Farrow", "Fell", "Verden", "Xideous", "Tripicus", "Estavan",
               "Autochon the Bellringer", "Shemeshka the Marauder", "A'kin", "Cirily"]:
        for k in name_keys(nm):
            POOL.setdefault(k, nm)
    TITLE_CASES = [("fARRew", "Farrow"), ("VERDfiN", "Verden"), ("xiDEeus", "Xideous"),
                   ("TRIPICUS", "Tripicus"), ("fiS+AVAN", "Estavan"),
                   ("AU+0CH0N +HE BELLRINGER", "Autochon the Bellringer"),
                   ("SHEfTlESHKA", "Shemeshka the Marauder")]
    tok = 0
    for garbled, want in TITLE_CASES:
        got, r = decode_title(garbled, POOL)
        print(("  OK  " if got == want else "FAIL  ") + f"{garbled!r:28} -> {got!r} (r={r}; want {want!r})")
        tok += got == want
    print(f"{tok}/{len(TITLE_CASES)} title-decode cases machine.")

    LOC_CASES = [
        ("The Friendly Fiend, a magic shop in the Lower Ward.", "Lower Ward", "The Friendly Fiend"),
        ("Tiwum's Antiquities, a five-story shop in the Market Ward.", "Market Ward", "Tiwum's Antiquities"),
        ("Fortune's Wheel, a gambling tavern in The Lady's Ward.", "Lady's Ward", "Fortune's Wheel"),
        ("hidden in tunnels under the Slags of the Hive Ward.", "Hive Ward", None),
        ("anywhere in Sigil.", None, None),
    ]
    lok = 0
    for text, ward, site in LOC_CASES:
        p = parse_location(text)
        good = p["ward"] == ward and p["site"] == site
        print(("  OK  " if good else "FAIL  ") + f"ward={p['ward']!r} site={p['site']!r}  | {text[:48]}")
        lok += good
    print(f"{lok}/{len(LOC_CASES)} location cases machine.")
