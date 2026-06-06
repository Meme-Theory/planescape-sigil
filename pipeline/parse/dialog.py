"""dialog.py — bind an NPC's spoken lines (the voice vector). Pure gear-house, no store dependency.

A bound utterance = a quoted span that is SPEECH attributed to the entry's NPC, carrying a **register**
read from the speech verb (snarled→stern · chuckled→amused · whispered→grave · says→main) so the line
lands render-ready against `tools/voices/grace.toml`'s register axis. `gate.py.pour_dialog` admits each
as a `dialog` node + `spoken_by` edge; `trace_entity(npc)` then shows their whole voice, and the voice
stack pulls it via the edge. (tools/ is out-of-band — Mimir owns the text, never depends on F5-TTS.)

Guards (mirroring hooks.py's discipline): OCR column-bleed (over-long / mid-clause-dash spans),
emphasis-quotes (a label in quotes, not speech — "silent couriers"), fragments, and FOREIGN speakers
(another named cutter's line doesn't bind to this entry's NPC).
"""
from __future__ import annotations
import re

# speech verb stems -> register (the grace.toml emotion dial). Order matters: specific before `main`.
REGISTER = {
    "amused": ["laugh", "chuckl", "grin", "beam", "smil", "tease", "jok", "snicker", "wink", "quip", "purr"],
    "stern":  ["snarl", "growl", "demand", "order", "warn", "snap", "bark", "hiss", "threaten", "spit",
               "roar", "command", "sneer", "retort"],
    "grave":  ["whisper", "murmur", "sigh", "mutter", "intone", "breathe", "mourn", "grumbl", "rasp"],
    "main":   ["say", "said", "ask", "repl", "state", "explain", "note", "observ", "tell", "call", "add",
               "continu", "declar", "remark", "answer", "exclaim", "cry", "shout", "whine", "offer", "insist"],
}
VERB_REG = {stem: reg for reg, stems in REGISTER.items() for stem in stems}
_VERB_RX = re.compile(r"\b(" + "|".join(VERB_REG) + r")\w*", re.I)

QUOTE_RX = re.compile(r"[\"“]([^\"”“]{6,200})[\"”]")    # paired straight/curly marks, bounded length
_PRON = (" i ", " i'", " you ", " your ", " my ", " we ", " me ", " us ", " it ", " it'", " that'")
_WORD = re.compile(r"[A-Za-z]")
# OCR column-bleed leaks NARRATION into a quote span (a speaker doesn't narrate themselves in 3rd
# person). Strong tell: 3rd-person narration verbs / brackets INSIDE the span. (Seamus's entry, p?)
_BLEED = re.compile(r"[\[\]]|\b(leapt|selected|proclaim\w*|nodded|shrugged|gestured|imagines|sneered|"
                    r"grinned)\b|\bgave (?:a|why|him|her)\b|\bfelt (?:he|she)\b|"
                    r"\bthe \w+ (?:said|leapt|gave|felt|pushed)\b|\b[A-Z][a-z]+ pushed\b", re.I)
_FUSION = re.compile(r"[a-z][A-Z]")                    # OCR word-fusion across a column seam (SeamusxanFact)
THETA_DIALOG = 0.6


def _is_speech(s: str) -> bool:
    """A spoken line, not an emphasis-label ('silent couriers') or a fragment."""
    if len(s) < 6 or not _WORD.search(s):
        return False
    words = s.split()
    if len(words) < 2:
        return False
    low = " " + s.lower() + " "
    has_pron = any(p in low for p in _PRON)
    return has_pron or len(words) >= 4 or bool(re.search(r"[.!?]['\"”]?$", s))


def _register(window: str):
    """The speech verb nearest the quote → its register + the verb stem (None if no verb in window)."""
    m = _VERB_RX.search(window)
    if not m:
        return None, None
    stem = m.group(1).lower()
    return VERB_REG.get(stem, "main"), stem


def _cleanliness(s: str) -> float:
    """Down-weight OCR column-bleed: over-long spans, runaway word counts, mid-clause dashes."""
    c, words = 1.0, s.split()
    if _BLEED.search(s) or _FUSION.search(s):          # narration / word-fusion leaked in (column-bleed)
        c *= 0.4
    if ":" in s and len(words) > 4:                    # mid-quote colon = a label bleed, not speech
        c *= 0.6
    if len(s) > 160:
        c *= 0.6
    if len(words) > 30:
        c *= 0.6
    if " - " in s and len(s) > 80:                     # reflow merged a neighbouring column into the quote
        c *= 0.7
    if not re.search(r"[.!?,]['\"”]?$", s) and not any(p in (" " + s.lower() + " ") for p in _PRON):
        c *= 0.8
    return c


def _attribute(pre: str, owner_name: str, others: set):
    """Who is speaking? (speaker_confidence, why) or (None, _) if foreign / unattributable.
    `pre` = the ~60 chars before the quote (where the speech tag usually sits)."""
    low = pre.lower()
    owner_head = re.split(r"[ '’]", owner_name.lower())[0]
    # a FOREIGN named speaker right before the quote → not this NPC's line
    for o in others:
        oh = re.split(r"[ '’]", o.lower())[0]
        if len(oh) >= 4 and oh != owner_head and re.search(r"(?<![a-z])" + re.escape(oh) + r"(?![a-z])", low):
            return None, "foreign-speaker"
    has_verb = bool(_VERB_RX.search(pre))
    if len(owner_head) >= 3 and re.search(r"(?<![a-z])" + re.escape(owner_head) + r"(?![a-z])", low):
        return 0.9, "named-subject"                    # "...A'kin says,"
    if has_verb:
        return 0.85, "entry-subject+verb"              # a speech tag, no rival named → the entry's NPC
    if re.search(r"\b(he|she|they)\b", low) and has_verb:
        return 0.8, "pronoun-subject"
    return 0.6, "first-person"                         # bare quote in the entry, owner's voice by default


def extract(text: str, *, owner_id: str, owner_name: str, page=None, book=None, others=None) -> list[dict]:
    """Pull dialog utterances spoken BY owner from a prose scope. `others` = other NPC names (foreign
    speaker guard). Returns utterance dicts with register + a confidence (attribution × cleanliness)."""
    others = set(others or ())
    out, seen = [], set()
    for m in QUOTE_RX.finditer(text):
        span = re.sub(r"\s+", " ", m.group(1)).strip().strip("-—– ")
        span = re.sub(r"(\w)-\s+(\w)", r"\1\2", span)             # join OCR hyphen-splits ("shop- keep")
        if not _is_speech(span) or span.lower() in seen:
            continue
        pre = text[max(0, m.start() - 60):m.start()]
        post = text[m.end():m.end() + 40]
        speaker_conf, why = _attribute(pre, owner_name, others)
        if speaker_conf is None:
            continue
        reg, verb = _register(pre + " " + post)
        conf = round(speaker_conf * _cleanliness(span), 2)
        seen.add(span.lower())
        out.append({"text": span, "register": reg or "main", "verb": verb, "owner": owner_id,
                    "page": page, "book": book, "confidence": conf, "attribution": why})
    return out


# ---------------------------------------------------------------------------- self-test
def _selftest():
    others = {"Ensin", "Shemeshka the Marauder"}

    # 1) named subject + register from the verb (beams -> amused)
    a = extract('A friendly fellow, A\'kin beams, "Come in, come in! I won\'t bite." His shop is warm.',
                owner_id="npc:uncaged:a-kin", owner_name="A'kin", page=12, book="uncaged", others=others)
    assert len(a) == 1 and a[0]["register"] == "amused" and a[0]["confidence"] >= 0.85, a

    # 2) register from a darker verb (snarled -> stern); first-person content
    s = extract('The tiefling snarled, "You\'ll get nothing from me, berk!"',
                owner_id="npc:uncaged:x", owner_name="Xeg", others=others)
    assert s and s[0]["register"] == "stern", s

    # 3) emphasis-quote is NOT speech (a label, not a line) -> dropped
    assert extract('They call them the "silent couriers" of the Cage.',
                   owner_id="npc:uncaged:y", owner_name="Yvarr", others=others) == []

    # 4) FOREIGN speaker named before the quote -> does not bind to this entry's NPC
    f = extract('Then Ensin says, "Mind the portal, friend." A\'kin only nodded.',
                owner_id="npc:uncaged:a-kin", owner_name="A'kin", others=others)
    assert f == [], f

    # 5) OCR column-bleed (over-long, mid-clause dash) -> admitted-shape but low confidence
    bleed = ('She says, "I\'ve and all the wondrous magic of its portals - she imagines had to work '
             'twice as hard to get my good reputation, and the shop runs itself these days you know."')
    b = extract(bleed, owner_id="npc:uncaged:alluvius", owner_name="Alluvius Ruskin", others=others)
    assert b and b[0]["confidence"] < 0.6, b      # cleanliness penalty drops it below θ → review

    # 6) NARRATION column-bleed inside the span (3rd-person verb leaked in) -> below θ → review
    nb = extract('He says, "Service! the mephit proclaimed, and ever after I leapt to the counter."',
                 owner_id="npc:uncaged:seamus", owner_name="Seamus", others=others)
    assert nb and nb[0]["confidence"] < 0.6, nb
    # 7) OCR hyphen-split is joined
    h = extract('He says, "I am a humble shop- keep, friend."',
                owner_id="npc:uncaged:a-kin", owner_name="A'kin", others=others)
    assert h and "shopkeep" in h[0]["text"], h

    print(f"dialog.py self-test OK  (a-kin reg={a[0]['register']}/{a[0]['confidence']}, "
          f"stern={s[0]['register']}, emphasis/foreign/bleed/narration-dropped, hyphen-joined)")


if __name__ == "__main__":
    _selftest()
