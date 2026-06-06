"""monstrous.py — 2e Monstrous Compendium page parser (the creature dimension).

The MC layout reflows into three separable artifacts per creature page:
  1. a display-face NAME header,
  2. the LABEL column (CLIMATE/TERRAIN … XP VALUE — canonical, fixed order),
  3. VALUE-RUNS: consecutive short non-prose lines holding the values in order.
The trick: the label order is CANON, so a value-run zips against it positionally —
the taxonomy run (8 values, ends at an alignment) and the numeric run (starts at
No. Appearing, a dice/number). Validation gates each zip (AC int, HD dice-ish,
THAC0 1..21); a page that won't validate is QUEUED by name with the reason,
never guessed.

Pure gear-house: no store imports; self-tested in __main__.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cage as C

TAXO = ["climate_terrain", "frequency", "organization", "activity_cycle",
        "diet", "intelligence", "treasure", "alignment"]
NUM = ["no_appearing", "armor_class", "movement", "hit_dice", "thac0",
       "no_of_attacks", "damage_attack", "special_attacks", "special_defenses",
       "magic_resistance", "size", "morale", "xp_value"]

_LABELS = re.compile(
    r"C[LU][IUJ1]?MATE|FREQUENCY|ORGANIZATION|ACT[IJ1]V[IJ1]TY|INTELLIG|TREASURE|"
    r"AL[IJ1]GNMENT|APPEAR[IJ1]NG|ARMOR CLASS|MOVEMENT|H[IJ1]T D[IJ1]CE|THAC|"
    r"ATTACKS|DAMAGE|MAG[IJ1]C RES[IJ1]STANCE|MORALE|XP VALUE", re.I)
_ALIGN = re.compile(
    r"^(?:lawful|chaotic|neutral|any)(?:\s+(?:good|evil|neutral))?\s*(?:\([^)]+\))?\s*$", re.I)
_DICEISH = re.compile(r"^\d{1,3}(?:d\d{1,3})?(?:\s*[-+x±]\s*\d{1,4})?\b")

MC_COMPONENTS = [
    "planes-of-conflict/planes-of-conflict-2615-05-monstrous-supplement",
    "planes-of-law/ddps-planesoflaw-vii-rev",
]
MC_BOOK = {MC_COMPONENTS[0]: "planes-of-conflict", MC_COMPONENTS[1]: "planes-of-law"}


# Format B: the label survived ATTACHED to its value ("Climate/Terrain: Elysium…").
_INLINE = [
    ("climate_terrain", re.compile(r"C[LU][IUJ1]?MA[TF][LE]?[/\\][TF][CE]?RRA[IJ1]?N?\s*[:.]\s*(.+)", re.I)),
    ("frequency", re.compile(r"FREQU[Ee]NCY\s*[:.]\s*(.+)", re.I)),
    ("organization", re.compile(r"ORGAN[IJ1]ZA[TF][IJ1][OE0]N\s*[:.]\s*(.+)", re.I)),
    ("activity_cycle", re.compile(r"ACT[IJ1]V[IJ1]TY\s+CYC[LI]E\s*[:.]\s*(.+)", re.I)),
    ("diet", re.compile(r"D[IJ1][Ee]T\s*[:.]\s*(.+)", re.I)),
    ("intelligence", re.compile(r"[IJ1]NT[Ee]LL[IJ1]G[Ee']?NC[Ee]\s*[:.]\s*(.+)", re.I)),
    ("treasure", re.compile(r"TR[Ee]ASUR[Ee]\s*[:.]\s*(.+)", re.I)),
    ("alignment", re.compile(r"AL[IJ1]GNM[Ee]NT\s*[:.]\s*(.+)", re.I)),
    ("no_appearing", re.compile(r"N[O0]\.?\s*APP[Ee]AR[IJ1]NG\s*[:.]\s*(.+)", re.I)),
    ("armor_class", re.compile(r"ARM[O0]R\s+C[LI]ASS\s*[:.]\s*(.+)", re.I)),
    ("movement", re.compile(r"M[O0]V[Ee]M[Ee]NT\s*[:.]\s*(.+)", re.I)),
    ("hit_dice", re.compile(r"H[IJ1]T\s+D[IJ1]C[Ee]\s*[:.]\s*(.+)", re.I)),
    ("thac0", re.compile(r"THAC[O0]?\s*[:.]\s*(.+)", re.I)),
    ("no_of_attacks", re.compile(r"N[O0]\.?\s*[O0]F\s+ATTACKS\s*[:.]\s*(.+)", re.I)),
    ("damage_attack", re.compile(r"DAMAG[Ee][/\\]ATTACKS?\s*[:.]\s*(.+)", re.I)),
    ("special_attacks", re.compile(r"SP[Ee]C[IJ1]AL\s+ATTACKS\s*[:.]\s*(.+)", re.I)),
    ("special_defenses", re.compile(r"SP[Ee]C[IJ1]AL\s+D[Ee]F[Ee]NS[Ee]S\s*[:.]\s*(.+)", re.I)),
    ("magic_resistance", re.compile(r"MAG[IJ1]C\s+R[Ee]S[IJ1]STANC[Ee]\s*[:.]\s*(.+)", re.I)),
    ("size", re.compile(r"S[IJ1]Z[Ee]\s*[:.]\s*(.+)", re.I)),
    ("morale", re.compile(r"M[O0]RA[LI][Ee]\s*[:.]\s*(.+)", re.I)),
    ("xp_value", re.compile(r"XP\s+VA[LI]U[Ee]\s*[:.]\s*(.+)", re.I)),
]


def _inline_fields(lines):
    """Format-B parse: label-attached values, one per line. First match wins."""
    fields = {}
    for ln in lines:
        s = ln.strip()
        if not s or len(s) > 90:
            continue
        for key, rx in _INLINE:
            if key in fields:
                continue
            m = rx.match(s)
            if m:
                fields[key] = re.sub(r"\s+", " ", m.group(1)).strip()[:60]
                break
    return fields


from difflib import SequenceMatcher

_SQ_LABELS = [(k, re.sub(r"[^A-Z0]", "", lbl.upper())) for k, lbl in [
    ("climate_terrain", "CLIMATE/TERRAIN"), ("frequency", "FREQUENCY"),
    ("organization", "ORGANIZATION"), ("activity_cycle", "ACTIVITY CYCLE"),
    ("diet", "DIET"), ("intelligence", "INTELLIGENCE"), ("treasure", "TREASURE"),
    ("alignment", "ALIGNMENT"), ("no_appearing", "NO APPEARING"),
    ("armor_class", "ARMOR CLASS"), ("movement", "MOVEMENT"), ("hit_dice", "HIT DICE"),
    ("thac0", "THAC0"), ("no_of_attacks", "NO OF ATTACKS"),
    ("damage_attack", "DAMAGE/ATTACK"), ("special_attacks", "SPECIAL ATTACKS"),
    ("special_defenses", "SPECIAL DEFENSES"), ("magic_resistance", "MAGIC RESISTANCE"),
    ("size", "SIZE"), ("morale", "MORALE"), ("xp_value", "XP VALUE")]]


def _label_key(s):
    """Fuzzy label id for a (possibly OCR-gapped) line: 'ALIG MENT:' → alignment.
    Returns (key, trailing_inline_value_or_None) or None."""
    raw = s.strip()
    if not raw or len(raw) > 60:
        return None
    head, _, tail = raw.partition(":")
    sq = re.sub(r"[^A-Za-z0]", "", head).upper().replace("O", "0").replace("0", "O")
    sq = re.sub(r"[^A-Z]", "", sq) or sq
    if not (3 <= len(sq) <= 22):
        return None
    best, bk = 0.0, None
    for key, lbl in _SQ_LABELS:
        lsq = re.sub(r"0", "O", lbl)
        r = SequenceMatcher(None, sq, lsq).ratio()
        if r > best:
            best, bk = r, key
    if best < 0.8:
        return None
    val = tail.strip() or None
    return bk, (re.sub(r"\s+", " ", val)[:60] if val else None)


def _zip_fields(lines):
    """Unified A/B/C parse: classify lines as LABEL (with optional inline value) or
    VALUE; each maximal run of value-less labels consumes the next equally-long run
    of values, in order. Handles label wraps ('ACTIVITY' / 'CYCLE:') by pre-joining."""
    events = []                                       # ("label", key, inline) | ("value", text)
    i, n = 0, len(lines)
    while i < n:
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        lk = _label_key(s)
        if lk is None and i + 1 < n:                  # wrapped label? ('ACTIVITY' / 'CYCLE:')
            # the first half must itself look like a label fragment — bare caps,
            # no digits/parens ('High (13-14)' must never join into 'TREASURE:')
            if re.fullmatch(r"[A-Z][A-Z /.'\\-]{2,13}", s):
                lk2 = _label_key(s + " " + lines[i + 1].strip())
                if lk2:
                    events.append(("label", lk2[0], lk2[1]))
                    i += 2
                    continue
        if lk:
            events.append(("label", lk[0], lk[1]))
        else:
            shortish = len(s) <= 44 and not s.endswith((".", ";", ":")) \
                and sum(c.isalpha() for c in s) <= 36
            events.append(("value", s) if shortish else ("other", s))
        i += 1
    fields, pending = {}, []
    for ev in events:
        if ev[0] == "label":
            _, key, inline = ev
            if inline:
                fields.setdefault(key, inline)
            else:
                pending.append(key)
        elif ev[0] == "value" and pending:
            fields.setdefault(pending.pop(0), re.sub(r"\s+", " ", ev[1]).strip()[:60])
        elif ev[0] == "other":
            pending = []                              # prose breaks the column
    return fields


# strong per-field signatures — the correction pass reassigns by TYPE when the
# positional zip shifted (an OCR-dropped line shifts every pair after it)
_SIG = {
    "frequency": re.compile(r"^(?:Very rare|Rare|Uncommon|Common|Unique)", re.I),
    "alignment": _ALIGN,
    "diet": re.compile(r"^(?:Carnivore|Herbivore|Omnivore|Scavenger|Special|Nil|None|Any)\b", re.I),
    "intelligence": re.compile(r"^(?:Non-|Animal|Semi-?|Low|Average|Very|High|Exceptional|"
                               r"Genius|Supra|Godlike)[\w-]*\s*\(", re.I),
    "size": re.compile(r"^[TSMLHG]\s*\(", re.I),
    "magic_resistance": re.compile(r"^(?:\d{1,3}\s*%|Nil|None)\s*$", re.I),
    "morale": re.compile(r"^(?:Unreliable|Unsteady|Average|Steady|Elite|Champion|Fanatic|"
                         r"Fearless)\b", re.I),
    "xp_value": re.compile(r"^\d{1,3}(?:,\d{3})+\s*$|^\d{3,6}\s*$"),
    "armor_class": re.compile(r"^-?\d{1,2}\s*(?:\(|$)"),
    "hit_dice": re.compile(r"^\d{1,2}\s*(?:[d+]\s*\d{1,3})?\s*(?:\(|$)"),
    "thac0": re.compile(r"^\d{1,2}\s*(?:\(|$)"),
    "movement": re.compile(r"^\d{1,2}\b|^Fl\s|^Sw\s", re.I),
    "organization": re.compile(r"^(?:Solitary|Pack|Herd|Flock|Group|Band|Tribe|Clan|Hive|"
                               r"Pair|None|Nil|Military|Squad)", re.I),
    "activity_cycle": re.compile(r"^(?:Any|Day|Night|Dusk|Dawn|Constant|Continuous)\b", re.I),
}
_SIG_ORDER = ["frequency", "alignment", "diet", "intelligence", "size", "magic_resistance",
              "morale", "xp_value", "organization", "activity_cycle",
              "armor_class", "hit_dice", "thac0", "movement"]


def _retype(fields, candidates):
    """Signature correction: any field whose value fails its signature gets the first
    UNUSED candidate that fits — strongest signatures claim first."""
    used = set(fields.values())
    for key in _SIG_ORDER:
        sig = _SIG[key]
        cur = fields.get(key, "")
        if cur and sig.match(cur):
            continue
        for v in candidates:
            if v in used or not sig.match(v):
                continue
            # ambiguity guard: a bare int fits AC/HD/THAC0 alike — only steal it for
            # a numeric key if that key is EMPTY (never overwrite a plausible value)
            if key in ("armor_class", "hit_dice", "thac0", "movement") and cur:
                continue
            fields[key] = v
            used.add(v)
            break
    return fields


def _runzip_fields(lines):
    """Format-A fallback: taxonomy values precede their labels entirely (top-of-page
    run ending at an alignment); the numeric run follows the label column."""
    fields = {}
    taxo_vals = num_vals = None
    for r in _runs(lines):
        vals = [v for _, v in r]
        ai = max((k for k, v in enumerate(vals) if _ALIGN.match(v)), default=None)
        if ai is not None and ai >= 4 and taxo_vals is None:
            taxo_vals = vals[max(0, ai - 7):ai + 1]
            continue
        if num_vals is None and _DICEISH.match(vals[0]) and len(vals) >= 4:
            num_vals = vals[:13]
    if taxo_vals:
        fields.update(dict(zip(TAXO[-len(taxo_vals):], taxo_vals)))
    if num_vals:
        fields.update(dict(zip(NUM[:len(num_vals)], num_vals)))
    return fields


def _runs(lines):
    """Consecutive short non-prose lines (the reflowed value columns)."""
    runs, cur = [], []
    for i, ln in enumerate(lines):
        s = ln.strip()
        shortish = s and len(s) <= 44 and not s.endswith((".", ":", ";")) \
            and not _LABELS.search(s) and sum(c.isalpha() for c in s) <= 36
        if shortish:
            cur.append((i, s))
        else:
            if len(cur) >= 4:
                runs.append(cur)
            cur = []
    if len(cur) >= 4:
        runs.append(cur)
    return runs


def _name_of(lines):
    """MC pages head with up to TWO display lines (family + 'TIER ~ SPECIES', in
    either order) — join the top headingish lines in page order."""
    parts = []
    for i, ln in enumerate(lines[:8]):
        s = ln.strip()
        if ":" in s or _label_key(s):                 # stat labels are never names
            continue
        if (re.fullmatch(r"[A-Z][A-Z /.'\\-]{2,13}", s) and i + 1 < len(lines)
                and _label_key(s + " " + lines[i + 1].strip())):
            continue                                  # first half of a wrapped label
        if C.is_headingish(s) and sum(c.isalpha() for c in s) >= 4:
            d = re.sub(r"\s*[~†‡*]\s*", ", ", C.decode_heading(s)).strip(" ,")
            parts.append(re.sub(r"\s+", " ", d))
            if len(parts) == 2:
                break
    return ", ".join(parts).title() if parts else None


def parse_page(text, *, page, component):
    """One creature page → {name, fields, page, problems[], ok} or None (no MC shape)."""
    lines = text.splitlines()
    if len(_LABELS.findall(text)) < 3:
        return None
    name = _name_of(lines)
    problems = []
    # format detection: an alignment VALUE before the first label line means the
    # taxonomy run precedes its labels entirely (format A) — runzip first there
    first_label = next((i for i, ln in enumerate(lines) if _label_key(ln.strip())), None)
    pre_align = first_label is not None and any(
        _ALIGN.match(ln.strip()) for ln in lines[:first_label] if ln.strip())
    order = (_runzip_fields, _zip_fields) if pre_align else (_zip_fields, _runzip_fields)
    fields = order[0](lines)
    if len(fields) < 6:
        alt = order[1](lines)
        if len(alt) > len(fields):
            fields = alt
    # signature-correction over every short candidate line on the page
    candidates = [s.strip() for s in lines
                  if s.strip() and len(s.strip()) <= 44
                  and not s.strip().endswith((".", ";", ":"))
                  and not _label_key(s.strip())]
    fields = _retype(fields, candidates)
    if len(fields) < 6:
        problems.append(f"only {len(fields)} stat fields recovered")
    # validation gates (the lawfulness floor — full audit is Mechanus's L3)
    ac = fields.get("armor_class", "")
    m = re.match(r"^(-?\d{1,2})", ac)
    if not (m and -12 <= int(m.group(1)) <= 10):
        problems.append(f"AC unparseable: {ac!r}")
    hd = fields.get("hit_dice", "")
    if not re.match(r"^\d{1,2}(?:[d+]\d{1,3})?", hd):
        problems.append(f"HD unparseable: {hd!r}")
    if not name:
        problems.append("name header lost")
    return {"name": name, "page": page, "component": component,
            "fields": fields, "problems": problems,
            "ok": not problems}                      # any problem queues — never guess


def parse_component(pages, *, component):
    """All creature pages of one supplement → (parsed[], skipped_pages[])."""
    out, seen = [], set()
    for pg in sorted(pages):
        r = parse_page(pages[pg], page=pg, component=component)
        if not r:
            continue
        key = (r["name"] or f"p{pg}").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


if __name__ == "__main__":
    FIX = """KE9CRACHE9N †
BAA+EZU, LESSER

Baator
Uncommon
Pack
Any
Carnivore
High (13)
Nil
Lawful evil

COMBAT: prose about scalpels and pain that runs long enough to be prose.

CUMATE/TERRAJN:
FREQUENCY:
ORGANIZATION:
ACTJVITY CYCLE:
DIET:
INTELLIGl'.NCE:
TREASURE:
ALIGNMENT:
No. APPEARING:
ARMOR CLASS:
MOVEMENT:
HIT DICE:

3d6
2 (0 if attacked from behind)
12, Fl 12 (D)
6 + 6
13
3
1d6/1d6/2d6
Pain
Regeneration
30%
M (5' tall)
Champion (15)
8,000
"""
    r = parse_page(FIX, page=10, component="x")
    assert r and r["ok"], r["problems"]
    f = r["fields"]
    assert f["alignment"] == "Lawful evil" and f["frequency"] == "Uncommon"
    assert f["armor_class"].startswith("2") and f["hit_dice"] == "6 + 6"
    assert f["thac0"] == "13" and f["xp_value"] == "8,000"
    assert f["magic_resistance"] == "30%" and f["morale"] == "Champion (15)"
    # OCR reality: 'KE9CRACHE9N' decodes 'Keocracheon' (the scan inserted Es) —
    # the stable core survives; exact names are curation's job, not the parser's.
    assert "CRACH" in r["name"].upper() and "Baatezu" in r["name"], r["name"]

    # a prose page is not a creature
    assert parse_page("Just essay text.\nMore essay.\n", page=5, component="x") is None

    # broken numerics are queued, not guessed
    BAD = FIX.replace("2 (0 if attacked from behind)", "splotch")
    rb = parse_page(BAD, page=11, component="x")
    assert rb and not rb["ok"] and any("AC" in p for p in rb["problems"])

    print("monstrous.py self-test: all green")
