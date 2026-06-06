"""engine.py — the transmuter: English in, SUGGESTED cant out. Deterministic.

Boundary (the family's lane law): cant SUGGESTS style. It judges no law, rolls
no dice, asserts no canon, performs no fiat. Attestations cite Mimir's ids but
the authority is Mimir's; the caller's bone-box makes the final call.

Three data files, all live-reloaded on mtime change (no held handles — a
harvest re-run or lexicon edit lands on the next call, no reconnect ceremony):

  data/lexicon.json    — curated terms (tiered core/ext, match policy)
  data/rewrites.json   — EN→cant transformation law (templates/subs/seasoning)
  build/cant/cant.json — harvest-compiled: lexicon + corpus attestations +
                         voice_lines (the dialog dimension's register-tagged
                         exemplars). Absent ⇒ engine runs lexicon-only and
                         says so in every answer.

Determinism: rule choices hash on (input, rule id, density) via crc32 — same
ask, same answer, byte-identical (chance belongs to Modron; hash() is salted
and NEVER used). ENGINE_VERSION stamps every answer; bump on composition-law
change.

The model door (transmute method="model") is the Haiku fallback Meme asked
for: OFF unless an API key env is set; the refusal explains how to enable.
Rule output rides along either way — the model dresses, the rules witness.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import zlib
from pathlib import Path

from . import ENGINE_VERSION
from .gears import Matcher, needle_rx, normalize

PACKAGE_DIR = Path(__file__).resolve().parent
CANT_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = CANT_DIR.parent.parent
LEXICON_PATH = CANT_DIR / "data" / "lexicon.json"
REWRITES_PATH = CANT_DIR / "data" / "rewrites.json"
COMPILED_PATH = PROJECT_ROOT / "build" / "cant" / "cant.json"
VECTORS_PATH = PROJECT_ROOT / "build" / "cant" / "vectors.npz"
HANDBOOK_DB = PROJECT_ROOT / "build" / "mimir" / "handbook.db"
VOICES_DIR = PROJECT_ROOT / "tools" / "voices"   # dabus's casting data — READ-ONLY seam

DENSITY = {"light": 0, "street": 1, "heavy": 2}
REGISTERS = ("main", "amused", "stern", "grave")

# semantic lane thresholds (CANT.md D9) — calibrated on MiniLM-L6-v2 cosines
SEM_INCLUDE = 0.35      # semantic-only inclusion floor (no lexical hit needed)
SEM_FLOOR = 0.30        # below this, semantic contributes nothing to ranking
SEM_OFF_ENV = "CANT_SEMANTIC"   # set to "off" to keep the lane shut (ops hatch)

API_KEY_ENVS = ("CANT_API_KEY", "ANTHROPIC_API_KEY")
MODEL_DEFAULT = "claude-haiku-4-5-20251001"
API_URL = "https://api.anthropic.com/v1/messages"


# ---------------------------------------------------------------------------- store (mtime-fresh)
class _Fresh:
    """A JSON file that reloads itself when its mtime moves. Never holds the
    handle open (Windows lock law — a held handle blocks the next re-pour)."""

    def __init__(self, path: Path, required: bool):
        self.path, self.required = path, required
        self._mtime, self._data = None, None

    def get(self):
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            if self.required:
                raise FileNotFoundError(f"required data file missing: {self.path}")
            self._mtime, self._data = None, None
            return None
        if mtime != self._mtime:
            with open(self.path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            self._mtime = mtime
        return self._data


class Engine:
    def __init__(self, lexicon_path=LEXICON_PATH, rewrites_path=REWRITES_PATH,
                 compiled_path=COMPILED_PATH, vectors_path=VECTORS_PATH,
                 voices_dir=VOICES_DIR):
        self._lexicon = _Fresh(Path(lexicon_path), required=True)
        self._rewrites = _Fresh(Path(rewrites_path), required=True)
        self._compiled = _Fresh(Path(compiled_path), required=False)
        self._lex_cache = None          # (id(lexicon), index dict, matchers)
        self._voices_dir = Path(voices_dir)
        self._vectors_path = Path(vectors_path)
        self._embedder = None           # boots once (eager via enable_semantic, else lazy)
        self._emb_why = None
        self._emb_booted = False
        self._vec_cache = None          # (mtime, {"vectors","terms","meta"} | None, why)

    # ------------------------------------------------------------------ data views
    def lexicon(self) -> dict:
        return self._lexicon.get()

    def rewrites(self) -> dict:
        return self._rewrites.get()

    def compiled(self) -> dict | None:
        return self._compiled.get()

    def _lex_index(self):
        """term/variant → entry index over the BEST source: compiled (carries
        attestations) when present, raw lexicon otherwise. Rebuilt on reload."""
        comp = self.compiled()
        entries = (comp or self.lexicon())["terms"]
        if self._lex_cache and self._lex_cache[0] is entries:
            return self._lex_cache[1], self._lex_cache[2]
        idx = {}
        for e in entries:
            idx[normalize(e["term"])] = e
            for v in e.get("variants", []):
                idx.setdefault(normalize(v), e)
        matchers = [Matcher(e) for e in entries]
        self._lex_cache = (entries, idx, matchers)
        return idx, matchers

    def lookup(self, term: str) -> dict | None:
        idx, _ = self._lex_index()
        return idx.get(normalize(term))

    def voice_lines(self) -> list[dict]:
        comp = self.compiled()
        return comp["voice_lines"] if comp else []

    # ------------------------------------------------------------------ choice law
    @staticmethod
    def _pick(options: list[str], key: str, density: str) -> str:
        """Deterministic choice: light=plainest, street=among the first two,
        heavy=anywhere (ornate tail reachable). crc32 — NEVER random."""
        if not options:
            raise ValueError("rule with empty out[]")
        n = {"light": 1, "street": min(2, len(options)), "heavy": len(options)}[density]
        return options[zlib.crc32(key.encode("utf-8")) % n]

    @staticmethod
    def _awake(rule: dict, density: str) -> bool:
        return DENSITY[density] >= DENSITY.get(rule.get("min_density", "light"), 0)

    # ------------------------------------------------------------------ the rule composer
    def _compose(self, text: str, density: str, attitude: str) -> dict:
        rw = self.rewrites()
        applied: list[dict] = []
        out = text

        def fire(rule, kind, s):
            rx = re.compile(rule["en"], re.IGNORECASE)
            m = rx.search(s)
            if not m or not self._awake(rule, density):
                return s
            choice = self._pick(rule["out"], f"{text}|{rule['id']}|{density}", density)
            try:
                repl = m.expand(choice.replace("{addr}", "\x00addr\x00"))
            except re.error:
                repl = choice.replace("{addr}", "\x00addr\x00")
            new = s[:m.start()] + repl + s[m.end():]
            applied.append({"rule": rule["id"], "kind": kind, "from": m.group(0),
                            "to": repl.replace("\x00addr\x00", "{addr}"),
                            "term": rule.get("term"), "note": rule.get("note")})
            return new

        for t in rw["templates"]:
            out = fire(t, "template", out)
        for s_rule in rw["substitutions"]:
            out = fire(s_rule, "sub", out)
        for sn in rw["seasoning"]:
            out = fire(sn, "seasoning", out)

        # address law: ONE address per line (a Cager names you once). If the
        # post-substitution text ALREADY carries an address term (friend→cutter
        # vocatives — the "Lady's grace, cutter — cutter!" collision, engine v2),
        # every placeholder strips; else the FIRST fills at street+.
        addr_pool = rw["address"].get(attitude) or rw["address"]["neutral"]
        addr = self._pick(addr_pool, f"{text}|addr|{attitude}", "heavy")
        addr_term_rx = re.compile(r"\b(?:cutter|berk|basher|blood|sod|addle-cove|cobber)s?\b",
                                  re.IGNORECASE)
        has_addr = "\x00addr\x00" in out
        already_addressed = bool(addr_term_rx.search(out.replace("\x00addr\x00", "")))
        if has_addr and density != "light" and not already_addressed:
            out = out.replace("\x00addr\x00", addr, 1)
        out = re.sub(r"[,—\s]*\x00addr\x00", "", out)
        if (not has_addr and density != "light"
                and re.search(r"\byou(?:r|'re|'ll)?\b", out, re.IGNORECASE)
                and not addr_term_rx.search(out)):
            out = re.sub(r"([.!?])\s*$", "", out).rstrip()
            out = f"{out}, {addr}" + (text.strip()[-1] if text.strip()[-1:] in ".!?" else ".")
            applied.append({"rule": "address-inject", "kind": "address", "from": "",
                            "to": addr, "term": addr, "note": None})

        # capitalization repair at sentence starts
        out = re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)
        return {"density": density, "text": out, "applied": applied}

    # ------------------------------------------------------------------ suggestions payload
    def _entry_view(self, entry: dict) -> dict:
        att = entry.get("attested", {})
        counts = att.get("counts", {})
        view = {"term": entry["term"], "def": entry["def"], "tier": entry["tier"],
                "cat": entry["cat"],
                "attested": {"dialog": counts.get("dialog", 0), "prose": counts.get("prose", 0)}}
        if att.get("dialog"):
            a = att["dialog"][0]
            view["corpus_example"] = {"text": a["text"], "speaker": a.get("speaker_name"),
                                      "register": a.get("register"), "page": a.get("page"),
                                      "id": a.get("id")}
        if entry.get("use"):
            view["use"] = entry["use"]
        return view

    def _suggestions(self, text: str) -> list[dict]:
        """Every rewrite rule that sees something in the ORIGINAL text, with its
        cant options dressed from the lexicon — the caller's palette, density
        gates ignored (suggesting is free)."""
        rw = self.rewrites()
        out = []
        for kind in ("templates", "substitutions", "seasoning"):
            for rule in rw[kind]:
                m = re.search(rule["en"], text, re.IGNORECASE)
                if not m:
                    continue
                options = []
                for opt in rule["out"]:
                    plain = re.sub(r"\\\d+|\{addr\}", "", opt).strip(" ,—")
                    e = self.lookup(plain) or (self.lookup(rule["term"]) if rule.get("term") else None)
                    options.append({"cant": opt} | ({"lexicon": self._entry_view(e)} if e else {}))
                row = {"span": m.group(0), "rule": rule["id"], "kind": kind[:-1],
                       "options": options}
                if rule.get("note"):
                    row["note"] = rule["note"]
                if rule.get("min_density"):
                    row["min_density"] = rule["min_density"]
                out.append(row)
        return out

    def _corpus_examples(self, register: str | None, terms: list[str], limit: int = 3):
        """Voice lines from the handbook — same-register first, term-sharing
        first within that. The corpus outranks invention."""
        lines = self.voice_lines()
        if not lines:
            return []

        def score(ln):
            s = 0
            if register and ln.get("register") == register:
                s += 2
            if set(ln.get("terms", [])) & set(terms):
                s += 3
            elif ln.get("terms"):
                s += 1
            return s

        ranked = sorted(lines, key=lambda ln: (-score(ln), -(ln.get("confidence") or 0)))
        out = []
        for ln in ranked[:limit]:
            if score(ln) == 0 and out:
                break
            out.append({k: ln[k] for k in ("text", "register", "speaker_name", "page", "id")
                        if k in ln})
        return out

    # ------------------------------------------------------------------ the semantic lane (D9)
    def enable_semantic(self, embedder=None) -> dict:
        """Boot the lane eagerly (the server calls this BEFORE stdio parks —
        dabus D8 wire law: C-extension DLL loads deadlock after). CLI/pytest
        paths boot lazily through _sem_ready(). Injectable for tests."""
        if os.environ.get(SEM_OFF_ENV, "").lower() == "off":
            self._embedder, self._emb_why = None, f"{SEM_OFF_ENV}=off (ops hatch)"
            self._emb_booted = True
            return self.semantic_status()
        if embedder is not None:
            self._embedder, self._emb_why, self._emb_booted = embedder, None, True
            return self.semantic_status()
        if not self._emb_booted:
            from . import embed as embed_mod
            self._embedder, self._emb_why = embed_mod.boot()
            self._emb_booted = True
        return self.semantic_status()

    def _vectors(self):
        """vectors.npz, mtime-fresh, lexicon-sha cross-checked. (data|None, why)."""
        try:
            mtime = self._vectors_path.stat().st_mtime
        except OSError:
            return None, f"no vector sidecar at {self._vectors_path} — py -3.13 pipeline/cant/harvest.py"
        if self._vec_cache and self._vec_cache[0] == mtime:
            return self._vec_cache[1], self._vec_cache[2]
        import numpy as np
        from . import embed as embed_mod
        try:
            with np.load(self._vectors_path, allow_pickle=True) as z:
                data = {"vectors": z["vectors"], "terms": list(z["terms"]),
                        "meta": json.loads(str(z["meta"]))}
        except Exception as e:
            self._vec_cache = (mtime, None, f"vector sidecar unreadable: {e}")
            return None, self._vec_cache[2]
        why = None
        live_sha = embed_mod.file_sha256(self._lexicon.path)
        if data["meta"].get("lexicon_sha") != live_sha:
            data, why = None, ("vectors were cut from a different lexicon (sha mismatch) — "
                               "stale rankings are silent lies; re-run harvest.py")
        elif len(data["terms"]) != data["vectors"].shape[0]:
            data, why = None, "vector/term count mismatch — sidecar corrupt, re-run harvest.py"
        self._vec_cache = (mtime, data, why)
        return data, why

    def _sem_ready(self):
        """(embedder, vectors) when the lane serves, else (None, why)."""
        if not self._emb_booted:
            self.enable_semantic()
        if self._embedder is None:
            return None, self._emb_why
        vec, why = self._vectors()
        if vec is None:
            return None, why
        if vec["meta"].get("model_sha") != self._embedder.model_sha:
            return None, ("vectors were cut by a different model than the one serving — "
                          "re-run harvest.py (ranking drift law)")
        return (self._embedder, vec), None

    def semantic_status(self) -> dict:
        lane, why = self._sem_ready()
        if lane is None:
            return {"enabled": False, "why": why,
                    "thresholds": {"include": SEM_INCLUDE, "floor": SEM_FLOOR}}
        emb, vec = lane
        return {"enabled": True,
                "model_id": vec["meta"]["model_id"],
                "model_sha": (emb.model_sha or "")[:12],
                "vectors": int(vec["vectors"].shape[0]),
                "dim": vec["meta"]["dim"],
                "vectors_built": vec["meta"]["built"],
                "thresholds": {"include": SEM_INCLUDE, "floor": SEM_FLOOR},
                "law": "suggestions only — semantic hits NEVER fire rewrites (D9)"}

    def _semantic_scores(self, text: str):
        """cosine per lexicon term for `text`, or (None, why). Deterministic
        (single-threaded ORT; pinned model)."""
        lane, why = self._sem_ready()
        if lane is None:
            return None, why
        emb, vec = lane
        q = emb.encode_one(text)
        return {t: float(c) for t, c in zip(vec["terms"], vec["vectors"] @ q)}, None

    def _concepts(self, text: str, exclude: set, limit: int = 6) -> list[dict]:
        """Semantic-only suggestions for transmute: terms whose MEANING is near
        the sentence but whose surface never appears. Palette, never rewrite."""
        scores, _ = self._semantic_scores(text)
        if not scores:
            return []
        out = []
        for term, cos in sorted(scores.items(), key=lambda kv: -kv[1]):
            if cos < SEM_INCLUDE or len(out) >= limit:
                break
            if term in exclude:
                continue
            e = self.lookup(term)
            if e is None:
                continue
            out.append({"cosine": round(cos, 4)} | self._entry_view(e))
        return out

    # ------------------------------------------------------------------ public tools
    def transmute(self, text: str, density: str = "street", attitude: str = "neutral",
                  register: str | None = None, method: str = "rule") -> dict:
        if not text or not text.strip():
            raise ValueError("transmute needs a sentence — an empty bone-box says nothing")
        if density not in DENSITY:
            raise ValueError(f"density must be one of {sorted(DENSITY)}")
        if attitude not in ("friendly", "neutral", "hostile"):
            raise ValueError("attitude must be friendly | neutral | hostile")
        if register is not None and register not in REGISTERS:
            raise ValueError(f"register must be one of {REGISTERS} (the dialog dimension's axis)")
        if method not in ("rule", "model"):
            raise ValueError("method must be rule | model")

        order = [density] + [d for d in ("light", "street", "heavy") if d != density]
        candidates = [self._compose(text, d, attitude) for d in order]
        terms_in_play = [a["term"] for c in candidates for a in c["applied"] if a.get("term")]
        suggestions = self._suggestions(text)
        # concepts (D9): meaning-near terms the surface pass missed. Exclude
        # what's already on the table — surface-matched terms + palette links.
        _, matchers = self._lex_index()
        nt = normalize(text)
        exclude = {m.term for m in matchers if m.hit(nt)} | set(terms_in_play)
        for s in suggestions:
            for o in s["options"]:
                if "lexicon" in o:
                    exclude.add(o["lexicon"]["term"])
        comp = self.compiled()
        result = {
            "input": text,
            "method": "rule",
            "engine_version": ENGINE_VERSION,
            "density_requested": density,
            "attitude": attitude,
            "register": register,
            "candidates": candidates,
            "suggestions": suggestions,
            "concepts": self._concepts(text, exclude),
            "corpus_examples": self._corpus_examples(register, terms_in_play),
            "store": self._store_note(comp),
            "notes": ["cant suggests — the table's bone-box decides; nothing here is law or canon",
                      "concepts are semantic-near palette picks — they never rewrote anything (D9)"],
        }
        if method == "model":
            result = self._model_door(text, density, attitude, register, result)
        return result

    # ------------------------------------------------------------------ the dabus handoff (D11)
    def _read_toml(self, path: Path) -> dict | None:
        """Open-close per call, READ-ONLY (the family seam: data, not servers).
        None when absent/unparsable — the caller words the why."""
        import tomllib
        try:
            with open(path, "rb") as f:
                return tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            return None

    def _cast_voice(self, voice: str | None, npc: str | None):
        """Resolve the voice per dabus's own law: explicit pack name, or the
        speakers.toml cast for an npc id. Cant NEVER guesses a voice — an
        uncast npc yields (None, why), mirroring dabus's refusal."""
        if voice and npc:
            raise ValueError("give voice OR npc, not both — casting must be unambiguous")
        if npc:
            table = self._read_toml(self._voices_dir / "speakers.toml")
            if table is None:
                return None, (f"speakers.toml unreadable under {self._voices_dir} — "
                              "dabus casting data absent; pass voice= explicitly")
            cast = (table.get("speakers") or {}).get(npc)
            if not cast:
                return None, (f"{npc} is UNCAST in tools/voices/speakers.toml — dabus refuses "
                              "unknown speakers; cast it there (a DM's creative choice), or pass voice=")
            return cast, None
        if voice:
            return voice, None
        return None, "no voice given — pass voice=<pack> or npc=<mimir id>"

    def _pack_registers(self, voice: str):
        """(servable register set, aliases, pack_found). Pack shape per DABUS.md:
        top-level ref = main; [voices.<name>] blocks add registers; optional
        [register_aliases] route the shared axis onto pack-specific names."""
        pack = self._read_toml(self._voices_dir / f"{voice}.toml")
        if pack is None:
            return None, {}, False
        regs = {"main"} | set((pack.get("voices") or {}).keys())
        aliases = {k: v for k, v in (pack.get("register_aliases") or {}).items()}
        return regs, aliases, True

    def voiceover(self, text: str, voice: str | None = None, npc: str | None = None,
                  density: str = "street", attitude: str = "neutral",
                  register: str = "main", method: str = "rule") -> dict:
        """English in → a dabus-READY utterance out: the transmuted line plus the
        exact `speak` payload. The chain stays caller-fired (no MCP-over-MCP);
        this makes the chaining mechanical. Deterministic transmute +
        dabus's content-addressed renders ⇒ same ask, same WAV."""
        t = self.transmute(text, density=density, attitude=attitude,
                           register=register if register in REGISTERS else None,
                           method=method)
        chosen = t["candidates"][0]                       # requested density leads

        cast, cast_why = self._cast_voice(voice, npc)
        speakable, casting = None, {"voice": cast, "how": None, "why": cast_why}
        if cast:
            casting["how"] = f"speakers.toml cast for {npc}" if npc else "explicit"
            regs, aliases, pack_found = self._pack_registers(cast)
            tag, reg_note = register, None
            if not pack_found:
                casting["pack_found"] = False
                reg_note = (f"pack {cast}.toml not found under tools/voices — speakable emitted "
                            "unvalidated; dabus will refuse if the pack truly isn't there")
            else:
                casting["pack_found"] = True
                casting["registers"] = sorted(regs)
                if register not in regs:
                    if register in aliases:
                        tag, reg_note = aliases[register], f"register {register!r} routed via pack alias → {aliases[register]!r}"
                    else:
                        tag, reg_note = "main", (f"register {register!r} not in pack {cast} "
                                                 f"(has {sorted(regs)}) — falling back to [main]")
            speakable = {"server": "dabus", "tool": "speak",
                         "args": {"voice": cast, "text": f"[{tag}] {chosen['text']}"}}
            if reg_note:
                casting["register_note"] = reg_note

        return {
            "input": text,
            "line": chosen["text"],
            "register": register,
            "density": density,
            "speakable": speakable,
            "casting": casting,
            "transmute_trace": {"applied": chosen["applied"],
                                "alternates": [{"density": c["density"], "text": c["text"]}
                                               for c in t["candidates"][1:]],
                                "engine_version": t["engine_version"],
                                "store": t["store"]},
            "notes": [
                "fire speakable via the dabus MCP yourself — cant performs no renders (lane law)",
                "deterministic transmute + content-addressed renders: same ask ⇒ same render_id",
            ],
        }

    def decode(self, text: str) -> dict:
        """Cant → plain English glosses. Strict matchers first; none-policy terms
        join loosely (flagged — 'case' might just be a case)."""
        if not text or not text.strip():
            raise ValueError("decode needs text")
        _, matchers = self._lex_index()
        # length-preserving normalize so spans map onto the original text
        kept = text
        for k, v in {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}.items():
            kept = kept.replace(k, v)
        kept = kept.lower().replace("-", " ")

        hits = []
        for m in matchers:
            found, loose = m.find(kept, loose=True)
            if not found:
                continue
            e = m.entry
            short = re.split(r"[;—]", e["def"])[0].strip()
            hits.append({"term": e["term"], "span": text[found.start():found.end()],
                         "start": found.start(), "def": e["def"], "short": short,
                         "tier": e["tier"], "loose": loose})
        hits.sort(key=lambda h: (h["start"], -len(h["span"])))
        chosen, taken = [], -1
        for h in hits:
            if h["start"] > taken:
                chosen.append(h)
                taken = h["start"] + len(h["span"]) - 1
        glossed = text
        for h in reversed(chosen):
            ins = h["start"] + len(h["span"])
            mark = f" [{h['short']}{'?' if h['loose'] else ''}]"
            glossed = glossed[:ins] + mark + glossed[ins:]
        for h in chosen:
            h.pop("start", None)
        return {"input": text, "glossed": glossed, "hits": chosen,
                "engine_version": ENGINE_VERSION,
                "notes": ["loose hits (marked ?) are common-English collisions — read in context"]}

    def suggest_terms(self, query: str, cat: str | None = None, tier: str | None = None,
                      limit: int = 12, semantic: bool = True) -> dict:
        if not query or not query.strip():
            raise ValueError("suggest_terms needs a concept to chase")
        comp = self.compiled()
        entries = (comp or self.lexicon())["terms"]
        q_tokens = set(re.findall(r"[a-z']+", query.lower()))

        def _hits(qs: set, toks: set) -> int:
            """Prefix-stemmed overlap: 'kill' meets 'killed', 'murder' meets
            'murdered' — cheap morphology for a reverse dictionary."""
            n = 0
            for q in qs:
                for t in toks:
                    if q == t or (len(q) >= 4 and t.startswith(q)) or (len(t) >= 4 and q.startswith(t)):
                        n += 1
                        break
            return n

        def score(e):
            t_tokens = set(re.findall(r"[a-z']+", e["term"]))
            d_tokens = set(re.findall(r"[a-z']+", e["def"].lower()))
            base = 3 * _hits(q_tokens, t_tokens) + _hits(q_tokens, d_tokens)
            if base == 0:
                return 0                      # attestation breaks ties, never qualifies
            if cat and e["cat"] == cat:
                base += 2
            if e.get("attested"):
                base += 1
            return base

        sem_scores, sem_why = ({}, None)
        if semantic:
            sem_scores, sem_why = self._semantic_scores(query)
            sem_scores = sem_scores or {}

        def combined(e):
            lex = score(e)
            cos = sem_scores.get(e["term"], 0.0)
            return lex + max(0.0, (cos - SEM_FLOOR) * 10)   # 0.30→0, 0.75→4.5 — int-scale parity

        pool = [e for e in entries
                if (cat is None or e["cat"] == cat) and (tier is None or e["tier"] == tier)]
        ranked = sorted(pool, key=lambda e: -combined(e))
        rows = []
        for e in ranked[:max(limit, 1)]:
            lex, cos = score(e), sem_scores.get(e["term"], 0.0)
            if lex <= 0 and cos < SEM_INCLUDE:              # semantic-only needs the floor
                continue
            rows.append(self._entry_view(e)
                        | {"match": {"lexical": lex, "semantic": round(cos, 4)}})
        out = {"query": query, "cat": cat, "tier": tier, "terms": rows,
               "categories": sorted({e["cat"] for e in entries}),
               "store": self._store_note(comp)}
        if semantic and sem_why:
            out["semantic"] = {"enabled": False, "why": sem_why}
        return out

    def examples(self, register: str | None = None, term: str | None = None,
                 speaker: str | None = None, limit: int = 8) -> dict:
        if register is not None and register not in REGISTERS:
            raise ValueError(f"register must be one of {REGISTERS}")
        lines = self.voice_lines()
        if term:
            e = self.lookup(term)
            want = e["term"] if e else term
            lines = [ln for ln in lines if want in ln.get("terms", [])]
        if register:
            lines = [ln for ln in lines if ln.get("register") == register]
        if speaker:
            s = speaker.lower()
            lines = [ln for ln in lines
                     if s in (ln.get("speaker_name") or "").lower() or s in (ln.get("speaker") or "")]
        lines = sorted(lines, key=lambda ln: -(ln.get("confidence") or 0))[:limit]
        return {"register": register, "term": term, "speaker": speaker,
                "lines": lines, "store": self._store_note(self.compiled())}

    def info(self) -> dict:
        comp = self.compiled()
        lex = self.lexicon()
        rw = self.rewrites()
        tiers: dict[str, int] = {}
        for e in lex["terms"]:
            tiers[e["tier"]] = tiers.get(e["tier"], 0) + 1
        out = {
            "engine_version": ENGINE_VERSION,
            "lexicon": {"path": str(LEXICON_PATH), "terms": len(lex["terms"]), "tiers": tiers,
                        "sources": lex["_meta"]["sources"]},
            "rewrites": {"path": str(REWRITES_PATH),
                         "templates": len(rw["templates"]),
                         "substitutions": len(rw["substitutions"]),
                         "seasoning": len(rw["seasoning"])},
            "compiled": self._store_note(comp),
            "model_door": {"enabled": bool(self._api_key()),
                           "model": os.environ.get("CANT_MODEL", MODEL_DEFAULT),
                           "enable_via": f"set one of {API_KEY_ENVS}"},
            "semantic": self.semantic_status(),
            "registers": list(REGISTERS),
            "densities": list(DENSITY),
        }
        if comp:
            m = comp["_meta"]
            out["compiled"] |= {"built": m["built"], "dialog_lines": m["dialog_lines"],
                                "terms_attested": m["terms_attested"],
                                "candidates_for_review": len(comp.get("candidates", []))}
        return out

    def _store_note(self, comp) -> dict:
        if comp is None:
            return {"state": "LEXICON-ONLY", "why": f"no compiled store at {COMPILED_PATH}",
                    "fix": "py -3.13 pipeline/cant/harvest.py"}
        stale = False
        try:
            stale = HANDBOOK_DB.stat().st_mtime > COMPILED_PATH.stat().st_mtime
        except OSError:
            pass
        note = {"state": "COMPILED", "built": comp["_meta"]["built"]}
        if stale:
            note["state"] = "STALE"
            note["why"] = "handbook.db is newer than cant.json — a pour landed since the harvest"
            note["fix"] = "py -3.13 pipeline/cant/harvest.py"
        return note

    # ------------------------------------------------------------------ the model door (Haiku)
    @staticmethod
    def _api_key() -> str | None:
        for env in API_KEY_ENVS:
            if os.environ.get(env):
                return os.environ[env]
        return None

    def _model_door(self, text, density, attitude, register, rule_result) -> dict:
        key = self._api_key()
        if not key:
            rule_result["model_door"] = {
                "refused": "no API key in environment — the Haiku door stays shut",
                "how_to_enable": f"set one of {API_KEY_ENVS} (key never logged)",
                "note": "rule candidates above are the deterministic fallback",
            }
            return rule_result

        palette = []
        for s in rule_result["suggestions"][:14]:
            opts = ", ".join(o["cant"] for o in s["options"][:3])
            palette.append(f"- '{s['span']}' → {opts}")
        exemplars = [f"- ({ln.get('register')}) {ln['text']}"
                     for ln in rule_result["corpus_examples"][:3]]
        prompt = (
            "Rewrite the sentence in Planescape's Sigil cant. Keep the MEANING; restructure "
            "as a Cager would speak. Use the palette where it fits; never cipher-substitute "
            "every word. Proper nouns stay. Density: "
            f"{density} (light=1-2 terms, street=natural, heavy=thick patter). Attitude toward "
            f"listener: {attitude}." + (f" Register: {register}." if register else "") + "\n\n"
            "Palette (English span → cant options):\n" + "\n".join(palette or ["- (none matched)"]) +
            ("\n\nCorpus exemplars (match this voice):\n" + "\n".join(exemplars) if exemplars else "") +
            f"\n\nSentence: {text}\n\nReturn EXACTLY 3 numbered cant renderings, nothing else."
        )
        body = json.dumps({
            "model": os.environ.get("CANT_MODEL", MODEL_DEFAULT),
            "max_tokens": 400,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "content-type": "application/json",
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            raw = "".join(b.get("text", "") for b in payload.get("content", []))
            renders = [re.sub(r"^\s*\d+[.)]\s*", "", ln).strip()
                       for ln in raw.splitlines() if re.match(r"^\s*\d+[.)]", ln)]
            rule_result["method"] = "model"
            rule_result["model_door"] = {
                "model": payload.get("model"),
                "candidates": renders or [raw.strip()],
                "usage": payload.get("usage"),
                "note": "model output is non-deterministic — rule candidates remain the reproducible witness",
            }
        except Exception as e:                                # net/key/quota — refuse honestly
            rule_result["model_door"] = {"refused": f"model call failed: {type(e).__name__}: {e}",
                                         "note": "rule candidates above still stand"}
        return rule_result


# module-level singleton for the server
_ENGINE: Engine | None = None


def engine() -> Engine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = Engine()
    return _ENGINE
