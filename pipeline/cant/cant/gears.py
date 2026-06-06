"""gears.py — the cant family's shared text gears (single-sourced matcher law).

harvest.py (attestation) and engine.py (transmutation/decode) both run on these
gears; a matching rule strengthened here strengthens both, with a self-test
(normalize.py's discipline: strengthen the rule with a self-test before
reaching for a per-item patch).

Match policy (honored everywhere):
  word    — boundary match on the term + variants, with s/'s/es and -y→-ies
            inflection. The default.
  phrase  — ONLY the listed phrases match, edges are hard boundaries
            ('a blood' never matches 'a bloodbath').
  none    — never auto-matched (too common in plain English: case, music, box…).
            decode() may opt in loosely, but flags the hit `loose`.
"""
from __future__ import annotations

import re

_CURLY = {"‘": "'", "’": "'", "“": '"', "”": '"',
          "–": "-", "—": "-", " ": " "}


def normalize(s: str) -> str:
    """Lowercase, straighten curly quotes/dashes, hyphen→space, collapse
    whitespace. Needle and haystack both pass through, so bone-box == bone box."""
    for k, v in _CURLY.items():
        s = s.replace(k, v)
    s = s.lower().replace("-", " ")
    return re.sub(r"\s+", " ", s)


def needle_rx(phrase: str, inflect: bool) -> re.Pattern:
    """Word-boundary regex for a normalized phrase. Single words (inflect=True)
    also take s/'s/es, and -y → -ies. Phrase edges are hard boundaries."""
    words = normalize(phrase).split()
    if inflect and len(words) == 1:
        w = words[0]
        body = re.escape(w[:-1]) + r"(?:y|ies)" if w.endswith("y") else re.escape(w) + r"(?:'?s|es)?"
    else:
        body = r"\s+".join(re.escape(w) for w in words)
    return re.compile(r"(?<![a-z'])" + body + r"(?![a-z])")


class Matcher:
    """One lexicon term's attestation policy, compiled."""

    def __init__(self, entry: dict):
        self.term = entry["term"]
        self.entry = entry
        policy = entry.get("match", "word")
        self.policy = policy
        self.active = policy != "none"
        needles: list[tuple[str, bool]] = []
        if policy == "word":
            needles.append((entry["term"], True))
            needles += [(v, True) for v in entry.get("variants", [])]
        elif policy == "phrase":
            needles += [(p, False) for p in entry.get("phrases", [])]
            needles += [(v, False) for v in entry.get("variants", [])]
        self.rxs = [needle_rx(n, inf) for n, inf in needles]
        # decode's loose door: none-policy terms AND phrase-policy headwords
        # still have shapes worth spotting when the READER asks what a cant
        # text means ('no jink, no chant' — bare 'chant' is the term). Loose
        # hits are flagged `?` downstream; recall over precision, honestly.
        self.loose_rxs = []
        if policy in ("none", "phrase"):
            head = re.sub(r"^the\s+", "", normalize(entry["term"]))
            self.loose_rxs.append(needle_rx(head, inflect=len(head.split()) == 1))

    def hit(self, normalized_text: str) -> bool:
        return self.active and any(rx.search(normalized_text) for rx in self.rxs)

    def find(self, normalized_text: str, loose: bool = False):
        """First match object (strict, then loose if asked), or None.
        Returns (match, is_loose)."""
        for rx in self.rxs:
            m = rx.search(normalized_text)
            if m:
                return m, False
        if loose:
            for rx in self.loose_rxs:
                m = rx.search(normalized_text)
                if m:
                    return m, True
        return None, False


def find_terms(matchers: list[Matcher], text: str) -> list[str]:
    nt = normalize(text)
    return [m.term for m in matchers if m.hit(nt)]


_HYPHEN_COMPOUND = re.compile(r"\b([a-z]{3,})-([a-z]{3,})\b")


def candidate_compounds(text: str, known: set[str]) -> list[str]:
    """Hyphenated compounds are the cant's signature word-shape (bone-box,
    addle-cove). Any compound the lexicon doesn't know is a review candidate."""
    out = []
    for m in _HYPHEN_COMPOUND.finditer(text.lower()):
        comp = f"{m.group(1)}-{m.group(2)}"
        if normalize(comp) not in known:
            out.append(comp)
    return out


def snippet(text: str, rx: re.Pattern, width: int = 110) -> str | None:
    """Sentence-trimmed window around rx's first hit in normalize(text)."""
    nt = normalize(text)
    m = rx.search(nt)
    if not m:
        return None
    lo, hi = max(0, m.start() - width), min(len(nt), m.end() + width)
    win = nt[lo:hi]
    head = win.find(". ")
    if 0 <= head < width - 20:
        win = win[head + 2:]
    tail = win.rfind(". ")
    if tail > len(win) - width + 20:
        win = win[:tail + 1]
    win = win.strip()
    if len(win) < 20:                       # over-trimmed (degenerate content) — raw window
        win = nt[lo:hi].strip()
    return ("…" if lo > 0 else "") + win + ("…" if hi < len(nt) else "")


# ---------------------------------------------------------------------------- self-test
def _selftest():
    mk = lambda **kw: Matcher({"term": kw.pop("term"), **kw})

    # 1) word match takes plain/plural/possessive, boundary-guarded
    m = mk(term="berk")
    assert m.hit(normalize("Pike it, berk!")) and m.hit(normalize("those berks again"))
    assert m.hit(normalize("a berk's jink")) and not m.hit(normalize("berserker rage"))

    # 2) -y inflects to -ies
    assert mk(term="barmy").hit(normalize("the barmies of the Gatehouse"))

    # 3) phrase policy: ONLY the listed phrases, edges are hard boundaries
    m = mk(term="blood", match="phrase", phrases=["a blood", "real blood"])
    assert m.hit(normalize("she's a blood with a chiv"))
    assert not m.hit(normalize("a bloodbath among high-ups"))
    assert not m.hit(normalize("blood dripped from the blade"))

    # 4) none policy never auto-attests — but decode's loose door spots it
    m = mk(term="case", match="none")
    assert not m.hit(normalize("in that case, fine"))
    hit, loose = m.find(normalize("a tidy little case in the Lady's Ward"), loose=True)
    assert hit and loose
    # 4b) phrase policy decodes loosely on its bare headword ('no chant')
    m = mk(term="the chant", match="phrase", phrases=["the chant", "chant's"])
    assert not m.hit(normalize("no jink, no chant"))
    hit, loose = m.find(normalize("no jink, no chant"), loose=True)
    assert hit and loose

    # 5) hyphen≡space both directions; curly apostrophes straightened
    assert mk(term="bone-box").hit(normalize("rattle your bone box"))
    m = mk(term="give 'em the laugh", match="phrase", phrases=["give 'em the laugh"])
    assert m.hit(normalize("she'll give ’em the laugh yet"))

    # 6) variants ride along under word policy
    assert mk(term="leatherhead", variants=["leatherheaded"]).hit(normalize("a leatherheaded scheme"))

    # 7) candidates: unknown hyphen compounds only
    assert candidate_compounds("his bone-box and his razor-claw both",
                               {normalize("bone-box")}) == ["razor-claw"]

    # 8) snippet windows trim, ellipsize, and survive degenerate content
    rx = needle_rx("the dark of", inflect=False)
    s = snippet("First sentence here. The dark of it is that Shemeshka owns the deed. More.", rx)
    assert s and "dark of it" in s, s
    s2 = snippet("the dark of it.", rx)
    assert s2 and "dark of it" in s2, s2

    print("gears.py self-test OK (word/inflect/phrase-boundary/none+loose/hyphen/curly/"
          "variants/candidates/snippet)")


if __name__ == "__main__":
    _selftest()
