#!/usr/bin/env python
"""gate.py — Mimir's blocking admission gate + the `npc` dimension (v1 registry).

The gate is the ONLY write path into the Handbook (VALIDATION.md). It runs:
  L1 schema   — per-dimension field/range checks (the registry declares them)
  L2 invariant— dimension-agnostic (provenance, confidence, garbage detector)
  L3 independent — confirmation from a channel DISJOINT from the extractor:
       • consistency: derivable 2e math (HP∈HD-range, AC/THAC0 range, damage parses)
         — this is the **Mechanus `is_lawful`** + **Modron dice-lawfulness** channel,
         implemented locally as a placeholder until those siblings are importable.
       • held-out wiki witness — the entity attested in a source the extractor never read.

Decision (Ryan 2026-06-05: auto-admit): all hard checks pass AND confidence ≥ θ → ADMIT;
else QUARANTINE with a reason bucket. Every outcome writes a docket.

The npc dimension lives here for v1; `registry.py` factors the registry out once we add
faction/plane/etc. — the gate itself has no per-dimension logic, only `REGISTRY[type]`.
"""
import sys, json, re, hashlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import store as S
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parse"))
import normalize as N
import hooks as H                                   # the mechanical plot-hook tagger (pure gear-house)
import dialog as D                                  # the NPC voice-vector extractor (pure gear-house)
import cage as C                                    # In the Cage: establishments + portal sweep + Places gazetteer
import planes as P                                  # the three Planes boxes: curated cards, text-validated
import boxset as B                                  # box-section harvest: proxy/sect/settlement/saying/adventure/timeline
import monstrous as MC                              # 2e Monstrous Compendium parser (creature dim)
import pwh as PW                                    # The Planewalker's Handbook: races + kits (cards) + spells (parsed)

# Mechanus is the gate's L3 lawfulness channel (VALIDATION §2). Import her judge as a LIBRARY —
# the same seam store.py is for the siblings, no MCP-over-MCP. Guarded: if she isn't importable
# the gate degrades to local 2e math, and a sibling exception never blocks an admission.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mechanus"))
try:
    from mechanus.lawful import is_lawful as _mech_is_lawful
    from mechanus import tables as _mech_tables
    LAW_VERSION = _mech_tables.law_version()
except Exception:                                  # sibling absent / not yet built
    _mech_is_lawful = None
    LAW_VERSION = None

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = S.ROOT
THETA = 0.70                                       # auto-admit floor; tune as answer-key earns it
STAT_FIELDS = ["ac", "mv", "hp", "thac0", "num_attacks", "damage", "special_attacks",
               "special_defenses", "magic_resistance", "size", "morale", "intelligence", "xp"]
DICE_RE = re.compile(r"^\s*\d*d\d", re.I)
FRAGMENT_RE = re.compile(r"\d|;|/|\bAC\b|\bMV\b|\bhp\b")


# ---- npc dimension (v1 registry) -------------------------------------------
def npc_envelope(v2: dict) -> dict:
    sb = v2.get("statblock", {}) or {}
    d = v2.get("descriptor", {}) or {}
    content = " ".join(filter(None, [
        v2.get("name"), d.get("race"), d.get("faction"), sb.get("special_attacks"),
        v2.get("body", ""),
        " ".join(f"{k}: {v}" for k, v in (v2.get("sections") or {}).items())]))
    return {
        "type": "npc", "id": f"npc:uncaged:{S.slug(v2['name'])}", "name": v2["name"],
        "edition": "2e",
        "fields": {"descriptor": d, "statblock": sb, "sections": v2.get("sections"),
                   "body": v2.get("body"), "tier": v2.get("tier", "full")},
        "content": content,
        "provenance": {"value_sources": [{"src": "official-2e",
                        "loc": f"uncaged:p{(v2.get('pages') or [None])[0]}"}], "method": "extraction"},
        "confidence": v2.get("confidence"),
        "curated": {},
        "source_sha": (v2.get("provenance") or {}).get("source_sha256"),
    }


def npc_edges(env: dict):
    f = env["fields"]; d = f.get("descriptor") or {}
    out = []
    if d.get("faction"):
        out.append(("member_of", env["id"], "npc", f"faction:{S.slug(d['faction'])}", "faction", None))
    for s in (f.get("sections") or {}).get("__see_also__", []):
        pass  # see_also lives on the v2 node, threaded in ingest
    return out


# ---- checks: each returns {layer,name,sev,result,detail} -------------------
def chk(layer, name, sev, ok, detail=""):
    return {"layer": layer, "name": name, "sev": sev,
            "result": ("pass" if ok else "fail") if ok is not None else "skip", "detail": detail}


def l1_npc(env):
    sb = env["fields"]["statblock"] or {}
    d = env["fields"]["descriptor"] or {}
    nm = env["name"] or ""
    name_ok = bool(nm) and not FRAGMENT_RE.search(nm) and len(re.sub(r"[^A-Za-z]", "", nm)) >= 3
    if env["fields"].get("tier") == "minor":
        # MINOR tier: the appendix's "further smattering" has no Quick Chant statblock by design.
        # Require a COMPLETE descriptor (race + alignment) and a clean name instead; confidence is
        # lower (set by the extractor from how fully the descriptor parsed), but it's a real node.
        yield chk("L1", "minor_descriptor", "hard", bool(d.get("race")) and bool(d.get("alignment")),
                  f"race={d.get('race')!r} align={d.get('alignment')!r}")
        yield chk("L1", "name_not_fragment", "hard", name_ok, repr(nm))
        return
    nfound = sum(1 for k in STAT_FIELDS if sb.get(k))
    # type-aware floor: monsters carry the full set (SA/SD/MR/HD…); class-based humanoids
    # legitimately lack several (no MR, usually no SA) — a complete humanoid block is ~7 core fields.
    floor = 7 if d.get("char_class") else 10
    kind = "humanoid" if d.get("char_class") else "monster"
    yield chk("L1", "statblock_fields", "hard", nfound >= floor, f"{nfound}/13 (≥{floor}, {kind})")
    yield chk("L1", "name_not_fragment", "hard", name_ok, repr(nm))
    yield chk("L1", "descriptor_parses", "soft", bool(d.get("race")) and bool(d.get("alignment")),
              f"race={d.get('race')!r} align={d.get('alignment')!r}")


def l2_invariants(env):
    p = env.get("provenance") or {}
    yield chk("L2", "provenance_present", "hard", bool(p.get("value_sources")), "")
    yield chk("L2", "confidence_present", "hard", env.get("confidence") is not None, str(env.get("confidence")))


def _hd_range(level_hd: str):
    m = re.fullmatch(r"(\d+)(?:\+(\d+))?", (level_hd or "").strip())
    if not m:
        return None
    n, plus = int(m.group(1)), int(m.group(2) or 0)
    return (n + plus, n * 8 + plus)                # d8 monster HD


def _coerce_2e(env):
    """Reconcile Mimir's envelope with Mechanus's CURRENT contract. She now coerces string
    numerics herself (`_int_coerce`) and reads `level_hd` from the descriptor as a fallback
    (her gap-G1 envelope fix, 2026-06-05) — so the only thing left for Mimir to do at the seam
    is WITHHOLD Hit Dice where its OWN scope skips the d8-monster-HD math: class humanoids (hp
    isn't d8-bounded — Tarholt's 76 on 9 HD) and non-bracket HD ('pack … 1 each', 'see below').
    Strip `level_hd` from BOTH statblock and descriptor (she reads either) so her hp_in_hd_range
    / thac0_vs_hd skip exactly as Mimir's local check did. Clean monster HD is left intact for
    her to judge. Verified 29/29 lawful against the live law tables."""
    f = env["fields"]; d = dict(f.get("descriptor") or {}); sb = dict(f.get("statblock") or {})
    hd = (d.get("level_hd") or "").strip()
    if d.get("char_class") or not re.fullmatch(r"\d+(?:\+\d+)?", hd):
        d.pop("level_hd", None)
        sb.pop("level_hd", None)
    return {**env, "fields": {**f, "descriptor": d, "statblock": sb}}


def _fmt_law(c):
    bits = [f"{k}={c[k]}" for k in ("expected", "actual") if c.get(k) is not None]
    if c.get("detail"):
        bits.append(c["detail"])
    return " ".join(str(b) for b in bits)


def _l3_local_2e(env):
    """Fallback only — used when Mechanus isn't importable: the one derivable hard check she
    would run that Mimir's coarse bounds don't, hp within the monster's d8 HD range."""
    sb = env["fields"]["statblock"] or {}; d = env["fields"]["descriptor"] or {}
    hd = (d.get("level_hd") or "").strip()
    if sb.get("hp") and not d.get("char_class") and re.fullmatch(r"\d+(?:\+\d+)?", hd):
        rng = _hd_range(hd); m = re.search(r"-?\d+", str(sb.get("hp")))
        if rng and m:
            hp = int(m.group())
            yield chk("L3", "hp_in_hd_range", "hard", rng[0] <= hp <= rng[1],
                      f"hp {hp} ∈ [{rng[0]},{rng[1]}] for {hd}d8 (local fallback)")


def l3_lawful(env):
    """L3 independent verification. LAWFULNESS (derivable rules-math) is Mechanus's by design
    (VALIDATION §2): the gate calls her `is_lawful`, adopts her hard/soft verdict, and stamps
    `law_version`. Mimir keeps only what is its OWN extraction-QA duty, not rules-of-the-game —
    coarse garbage bounds on AC/THAC0 (catch OCR junk like 99/50, looser than the lawful range
    so Mechanus still gets to flag deviation softly) and damage-reads-as-dice (Modron's grammar)."""
    sb = env["fields"]["statblock"] or {}
    def num(x):
        m = re.search(r"-?\d+", str(x or "")); return int(m.group()) if m else None
    ac = num(sb.get("ac"))
    if ac is not None:                              # Mimir garbage bound, NOT lawfulness
        yield chk("L3", "ac_sane", "hard", -10 <= ac <= 12, f"AC {ac}")
    th = num(sb.get("thac0"))
    if th is not None:
        yield chk("L3", "thac0_sane", "hard", 1 <= th <= 20, f"THAC0 {th}")
    if sb.get("damage"):                            # dice grammar (Modron/extraction), not law
        first = re.split(r"[ /(]", str(sb["damage"]).strip())[0]
        yield chk("L3", "damage_parses", "hard", bool(DICE_RE.match(first)), repr(first))
    verdict = None
    if _mech_is_lawful is not None:
        try:
            verdict = _mech_is_lawful(_coerce_2e(env), view="2e")
        except Exception:
            verdict = None                          # never let the sibling crash an admission
    if verdict is None:
        yield from _l3_local_2e(env)                # graceful degradation
        return
    for c in verdict["checks"]:
        if c["result"] == "skip":
            continue
        ok = c["result"] in ("pass", "waived")
        yield chk("L3", f"law:{c['name']}", c["sev"], ok,
                  (_fmt_law(c) + f"  [{verdict['law_version']}]").strip())


def l3_wiki(env, wikiblob):
    """Held-out witness: attested in a CC wiki the extractor never read. Bonus, non-hard."""
    present = (env["name"] or "").lower() in wikiblob
    return chk("L3", "held_out_wiki", "soft", present, "in CC wiki" if present else "absent")


# ---- adjudication (vision/human curations; survive every rebuild) ----------
CUR_PATH = ROOT / "build/mimir/curations.json"


def load_curations():
    return json.loads(CUR_PATH.read_text(encoding="utf-8")) if CUR_PATH.exists() else {}


def apply_curation(env, cur):
    for path, val in (cur.get("set") or {}).items():
        d = env
        keys = path.split(".")
        for k in keys[:-1]:
            d = d.setdefault(k, {})
        d[keys[-1]] = val
        env.setdefault("curated", {})[path] = {"value": val, "adjudication": cur.get("adjudication")}
    # witnessed waivers: a vision/human ruling that a named HARD check legitimately doesn't apply
    # to this entity (e.g. a stationary plant lacks MR/morale). Recorded in `curated` (audit trail)
    # and carried transiently for the gate. Mirrors Mechanus's lawful_waivers.
    if cur.get("waivers"):
        env["_waivers"] = cur["waivers"]
        env.setdefault("curated", {})["_waivers"] = {"value": cur["waivers"],
                                                      "adjudication": cur.get("adjudication")}


# Module-level curation registry for the SEEDED pours (_admit_seed). The npc gate path
# receives curations as an argument; seeds read this global, set once in main(). Tests
# monkeypatch it. Empty dict = no curations (the safe default for library importers).
_CURATIONS: dict = {}


# ---- the gate --------------------------------------------------------------
def _apply_waivers(checks, waivers):
    """Downgrade a named HARD-fail to result='waived' when a curation carries a WITNESSED waiver
    for it — disclosed in the docket with its witness, never silently passed. A waiver without a
    witness is ignored (it's a blindfold, not a waiver). Mirrors Mechanus.is_lawful's waivers."""
    by = {w["check"]: w for w in (waivers or []) if w.get("witness")}
    for c in checks:
        if c["result"] == "fail" and c["sev"] == "hard" and c["name"] in by:
            w = by[c["name"]]
            c["result"] = "waived"
            c["waiver"] = {"witness": w["witness"], "reason": w.get("reason", "")}


def gate(v2, store, wikiblob, curations):
    env = npc_envelope(v2)
    cur = curations.get(env["id"])
    if cur:
        apply_curation(env, cur)
    checks = list(l1_npc(env)) + list(l2_invariants(env)) + list(l3_lawful(env))
    checks.append(l3_wiki(env, wikiblob))
    _apply_waivers(checks, env.get("_waivers"))
    hard_fail = [c for c in checks if c["sev"] == "hard" and c["result"] == "fail"]
    conf = env.get("confidence") or 0.0
    confirmed = [c for c in checks if c["layer"] == "L3" and c["result"] == "pass"]
    docket = {"entity_id": env["id"], "checks": checks,
              "independent": {"channel": "mechanus.is_lawful+wiki", "law_version": LAW_VERSION,
                              "confirmations": len(confirmed)},
              "confidence_final": conf,
              "adjudicator": "human-vision" if env.get("curated") else "auto"}
    if hard_fail:
        layer = hard_fail[0]["layer"]
        reason = {"L1": "schema-fail", "L2": "invariant-fail", "L3": "conflict"}[layer]
        docket["decision"] = "QUARANTINE"
        store.quarantine(env, docket, reason)
        return "QUARANTINE", reason, env, docket
    if conf < THETA and not env.get("curated"):        # a human-vision adjudication overrides the auto-θ floor
        docket["decision"] = "QUARANTINE"
        store.quarantine(env, docket, "low-confidence")
        return "QUARANTINE", "low-confidence", env, docket
    docket["decision"] = "ADMIT"
    store.admit(env, docket)
    # edge synthesis (admitted entities only)
    d = env["fields"]["descriptor"] or {}
    if d.get("faction"):
        store.add_edge("member_of", env["id"], f"faction:{S.slug(d['faction'])}",
                       src_type="npc", tgt_type="faction", edition="2e")
    for ref in v2.get("see_also", []):
        store.add_edge("references", env["id"], f"npc:uncaged:{S.slug(ref['name'])}",
                       src_type="npc", tgt_type="npc", edition="2e",
                       provenance={"loc": f"see_also p{ref.get('page')}"})
    return "ADMIT", None, env, docket


def _admit_seed(store, env, channel, confirmations):
    """Admit a seeded (non-extracted) entity through the gate's write path with a docket.
    Curations apply here too (the universal lane-3 rail, Great Audit Phase 0): a
    curations.json entry keyed by this id gets its dot-path sets + witnessed waivers
    BEFORE the write — fix a berk once, survive every re-pour, ANY dimension."""
    adjudicator = "auto"
    cur = (_CURATIONS or {}).get(env["id"])
    if cur:
        apply_curation(env, cur)
        adjudicator = "human-vision"
    docket = {"decision": "ADMIT", "adjudicator": adjudicator,
              "checks": [{"layer": "L1", "name": "name_present", "sev": "hard",
                          "result": "pass" if env.get("name") else "fail"}],
              "independent": {"channel": channel, "confirmations": confirmations},
              "confidence_final": env.get("confidence")}
    store.admit(env, docket)


def pour_factions(store, nodes):
    """Pour the factions our NPCs claim membership in — closes the member_of edges."""
    from collections import defaultdict
    members = defaultdict(list)
    for v2 in nodes:
        fac = (v2.get("descriptor") or {}).get("faction")
        if fac:
            members[fac].append(v2["name"])
    for fac, mem in sorted(members.items()):
        mem = sorted(set(mem))
        env = {"type": "faction", "id": f"faction:{S.slug(fac)}", "name": fac, "edition": "2e",
               "fields": {"members": mem}, "content": f"{fac} faction Sigil " + " ".join(mem),
               "provenance": {"value_sources": [{"src": "npc-descriptor-aggregation"}], "method": "seed"},
               "confidence": 1.0, "curated": {}, "source_sha": None}
        _admit_seed(store, env, "member-attestation", len(mem))
    return len(members)


def pour_source(store, nodes):
    """Pour the book itself as a first-class node; attest every NPC to it."""
    env = {"type": "source", "id": "source:uncaged", "name": "Uncaged: Faces of Sigil",
           "edition": "2e", "fields": {"code": "2624", "year": 1996, "kind": "accessory", "line": "Planescape"},
           "content": "Uncaged Faces of Sigil Planescape 2e accessory TSR 2624",
           "provenance": {"value_sources": [{"src": "catalog"}], "method": "seed"},
           "confidence": 1.0, "curated": {}, "source_sha": None}
    _admit_seed(store, env, "catalog", 1)
    for v2 in nodes:
        store.add_edge("attested_in", f"npc:uncaged:{S.slug(v2['name'])}", "source:uncaged",
                       src_type="npc", tgt_type="source", edition="2e")


# Cross-attestation: the OTHER Planescape products each Uncaged cutter also appears in (the
# "Sources" page, p130). Pouring these as source nodes + attested_in edges is the multi-book
# on-ramp — when In the Cage / Factol's Manifesto / etc. are poured, the cutters already link.
XREF_SOURCES = [
    ("source:dragon-213", "DRAGON Magazine #213", {"kind": "magazine article", "line": "DRAGON"},
     ["A'kin", "Estavan", "Kylie", "Lissandra the Gate-seeker"]),
    ("source:harbinger-house", "Harbinger House", {"kind": "adventure", "line": "Planescape"},
     ["A'kin", "Kesto Brighteyes"]),
    ("source:in-the-cage", "In the Cage: A Guide to Sigil", {"kind": "accessory", "line": "Planescape"},
     ["Autochon the Bellringer", "Black Marian", "Harys Hatchis", "Rule-of-Three",
      "Shemeshka the Marauder", "Tarholt"]),
    ("source:something-wild", "Something Wild", {"kind": "adventure", "line": "Planescape"},
     ["Estavan", "Seamusxanthuszenus"]),
    ("source:factols-manifesto", "The Factol's Manifesto", {"kind": "accessory", "line": "Planescape",
     "note": "faction intrigues — Darkwood's coup, the Signers' Aoskar scheme"}, []),
]


def pour_xref_sources(store):
    """Seed the other-book sources the cast also appears in, with attested_in edges (page-witnessed
    from p130). Resolves names to admitted nodes; a node not in this book is simply not linked."""
    resolve = _node_resolver(store)
    for sid, name, fields, npcs in XREF_SOURCES:
        env = {"type": "source", "id": sid, "name": name, "edition": "2e", "fields": fields,
               "content": f"{name} {fields.get('kind','')} Planescape — also features " + ", ".join(npcs),
               "provenance": {"value_sources": [{"src": "uncaged:p130 sources"}], "method": "seed"},
               "confidence": 0.9, "curated": {}, "source_sha": None}
        _admit_seed(store, env, "uncaged-sources", len(npcs))
        for who in npcs:
            oid = resolve(who)
            if oid:
                store.add_edge("attested_in", oid, sid, src_type="npc", tgt_type="source",
                               edition="2e", provenance={"src": "uncaged:p130"})
    return len(XREF_SOURCES)


# --- item dimension: the magic items each cutter carries (the marquee "invoke at the table") ----
_ITEM_KINDS = [
    (r"sword|blade|dagger|dirk|scimitar|naginata|whip|spear|bow|arrows?|mace|morning star|"
     r"quarterstaff|hornblade|halberd|darts?|blowgun|club|hammer", "weapon"),
    (r"armor|plate|mail|shield|bracers|gauntlets|leather", "armor"),
    (r"wand|rod|staff", "rod-staff"),
    (r"ring|amulet|necklace|periapt|cloak|boots|bracelet|earring|luckstone|gem|talisman|brooch|"
     r"cube|net|manual|deck|book|tome|log|quill|pipes|bag|scroll|figurine|horn|stone", "wondrous"),
    (r"potion|oil|philter|elixir", "potion"),
]


def _item_kind(nm):
    for pat, k in _ITEM_KINDS:
        if re.search(r"\b(" + pat + r")\b", nm, re.I):
            return k
    return "item"


def _clean_item(s):
    s = N.dehyphenate(s).strip(" .,")
    s = re.sub(r"\*(\d)", r"+\1", s)                   # OCR asterisk = enhancement plus
    s = re.sub(r"\+(\d)\s*-+", r"+\1", s)              # '+4-' OCR tail -> '+4'
    s = re.sub(r"\bof([a-z])", r"of \1", s)            # 'oflevitation' -> 'of levitation'
    s = re.sub(r"\s*\([^)]*\)", "", s)                 # drop charge/count parentheticals
    return s.strip(" .,-")


# Item curations (Great Audit docket -> Meme ADOPTED 2026-06-06), keyed
# (npc name, slug of the cleaned item phrase). drop = extraction debris (dialogue
# prose / descriptor fragments / OCR shred grabbed as equipment — the docket is the
# record); rename = de-fuse an item name from interleaved body text.
ITEM_CURATIONS = {
    ("Tripicus", "after-a-lecture"): {"action": "drop",
        "why": "dialogue prose grabbed as equipment (body-text bleed)"},
    ("The Grixitt", "even-if-the-wards-are-taken-away"): {"action": "drop",
        "why": "fragment of the planar-wards sentence, not an item"},
    ("Saure", "fnv-tude-tfiaf-awle"): {"action": "drop",
        "why": "OCR-shredded interleave, unrecoverable as an item"},
    ("Saure", "huifivtoyno-net-acid-touch-to-wvtn-the-maw"): {"action": "drop",
        "why": "OCR shred of the xaen's acid-touch ability text"},
    ("Saure", "spikes"): {"action": "drop",
        "why": "lifted from the xaen descriptor 'bony barbs, spikes, and hooks' (p92)"},
    ("Zadara", "museum-opening"): {"action": "drop",
        "why": "role-playing prose about outings, not equipment"},
    ("Zadara", "maul-of-the-titans-attend-the-odd-art-exhibit"): {"action": "rename",
        "to": "maul of the titans",
        "why": "PERSONALITY text interleaved the SPECIAL EQUIPMENT line; de-fused"},
    ("Farrow", "str-sa-strength-of-blending-3"): {"action": "rename",
        "to": "leather armor of blending +3",
        "why": "p35: OCR fused the statblock 'Str); SA' onto the armor phrase"},
    ("Ylem", "sling-stones-20"): {"action": "rename",
        "to": "sling stones (20)",
        "why": "p117: extraction cut the storage-box parenthetical mid-phrase"},
    ("Shemeshka the Marauder", "though-i-am-detection-and-location"): {"action": "rename",
        "to": "amulet of proof against detection and location",
        "why": "p100: column splice fused dialogue ('though I am…') onto the amulet name"},
    ("Shemeshka the Marauder", "amulet-of-proof-against-more-pleasant"): {"action": "drop",
        "why": "p100: fragment of the same splice — the real amulet rides the rename above"},
}


def pour_items(store, nodes):
    """Magic items from each cutter's SPECIAL EQUIPMENT → item nodes (deduped by name) + `wields`
    edges. Serves the project's marquee goal directly: the items are invokable at the table."""
    edges = 0
    for v2 in nodes:
        se = (v2.get("sections") or {}).get("SPECIAL EQUIPMENT")
        if not se or se.strip().lower().startswith("none"):
            continue
        npc_id = f"npc:uncaged:{S.slug(v2['name'])}"
        lead = re.split(r"\bSPELLS?\b|\bSPELL-LIKE\b|\bSPELL\b", se)[0]
        for raw in lead.split(","):
            it = _clean_item(raw)
            if not (3 <= len(it) <= 46 and re.search(r"[a-z]", it)) or re.match(r"^(and|or|a|the)\b", it):
                continue
            cur = ITEM_CURATIONS.get((v2["name"], S.slug(it)))
            if cur:
                if cur["action"] == "drop":
                    continue
                it = cur["to"]
            iid = f"item:{S.slug(it)}"
            enh = re.search(r"\+(\d)", it)
            env = {"type": "item", "id": iid, "name": it, "edition": "2e",
                   "fields": {"kind": _item_kind(it), "enhancement": int(enh.group(1)) if enh else None},
                   "content": f"{it} magic item Planescape 2e",
                   "provenance": {"value_sources": [{"src": f"uncaged:{v2['name']} equipment"}],
                                  "method": "extraction"},
                   "confidence": 0.85, "curated": {}, "source_sha": None}
            _admit_seed(store, env, "equipment", 1)
            store.add_edge("wields", npc_id, iid, src_type="npc", tgt_type="item", edition="2e")
            edges += 1
    return edges


# --- fiction (voice bank): the book's in-world creative pieces, authored by their speakers --------
# The named, identifiable pieces (a journal, the in-world ads). The scattered per-entry epigraph
# QUOTES are a richer voice-bank vein but OCR poorly in display fonts — a future careful pass.
FICTION = [
    ("fiction:uncaged:shemeshka-journal", "From the Journal of Shemeshka the Marauder",
     "journal", "Shemeshka the Marauder", "p35"),
    # Great Audit (Meme 2026-06-06): the ad is SIGNED "— H.H." (p50) and p47 names the
    # hiring — the author is Harys Hatchis, advertising Iarmid's spa.
    ("fiction:uncaged:other-place-ad", "Advertisement for The Other Place", "advertisement",
     "Harys Hatchis", "p50"),
]


def pour_fiction(store):
    """Seed the named in-world fiction pieces + an authored_by edge to the in-world speaker."""
    resolve = _node_resolver(store)
    for fid, name, form, author, loc in FICTION:
        env = {"type": "fiction", "id": fid, "name": name, "edition": "2e",
               "fields": {"form": form, "author": author},
               "content": f"{name} {form} by {author}",
               "provenance": {"value_sources": [{"src": f"uncaged:{loc}"}], "method": "seed"},
               "confidence": 0.85, "curated": {}, "source_sha": None}
        _admit_seed(store, env, "in-world-fiction", 1)
        aid = resolve(author)
        if aid:
            store.add_edge("authored_by", fid, aid, src_type="fiction",
                           tgt_type=aid.split(":")[0], edition="2e")
    return len(FICTION)


# ============================================================================================
# SECOND BOOK — The Factol's Manifesto (2611). The Uncaged statblock/roster extractor finds
# NOTHING here (0 statblocks); the Manifesto's value is its 15-faction structured data. This is
# the cross-book merge: real faction fields (philosophy/factol/HQ/home/allies/enemies) MERGED into
# the Uncaged-seeded faction nodes, factols promoted to NPCs, HQs resolved against existing Sigil
# locations. Hand-transcribed from the "Factions at a Glance" quick-reference (pp 5-6), column-
# reflowed and page-witnessed. Canonical names in allies/enemies so they resolve to faction ids.
FACTION_DATA = [
    # name, nickname, factol, hq, hq_ward, home_plane, philosophy, allies, enemies
    ("Athar", "Defiers / the Lost", "Terrance", "Shattered Temple", "Lower Ward", "Astral",
     "The gods are frauds; the unknowable truth lies beyond the veil.",
     ["Believers of the Source"], []),
    ("Believers of the Source", "Godsmen", "Ambar Vergrove", "Great Foundry", "Lower Ward",
     "Ethereal demiplanes",
     "All life springs from the same divine source, ascending and descending in form as the cosmos tests it.",
     ["Athar", "Doomguard"], ["Bleak Cabal", "Dustmen"]),
    # home_plane: Great Audit fix — manifesto p5 'Home Field: Pandemonium'
    ("Bleak Cabal", "Bleakers / the Cabal", "Lhar", "Gatehouse", "Hive Ward", "Pandemonium",
     "The multiverse ain't supposed to make sense; the only escape from madness is to look inside yourself.",
     ["Doomguard", "Dustmen", "Revolutionary League"], ["Fraternity of Order", "Harmonium", "Mercykillers"]),
    ("Doomguard", "Sinkers", "Pentar", "Armory", "Lady's Ward", "Each negative quasiplane",
     "Entropy is ecstasy; decay is divine. The multiverse is dying, and we are its instruments.",
     ["Bleak Cabal", "Dustmen"], ["Fraternity of Order", "Harmonium"]),
    ("Dustmen", "the Dead", "Skall", "Mortuary", "Hive Ward", "Negative Energy Plane",
     "We're all dead — some more so than others; we purge passion and ascend toward True Death.",
     ["Bleak Cabal", "Doomguard"], ["Society of Sensation", "Sign of One"]),
    ("Fated", "Takers / Heartless", "Duke Rowan Darkwood", "Hall of Records", "Clerk's Ward", "Ysgard",
     "The multiverse belongs to those who seize it; no one's to blame for a sod's fate but the sod himself.",
     ["Free League", "Mercykillers"], []),
    ("Fraternity of Order", "Guvners", "Hashkar", "City Court", "Lady's Ward", "Mechanus",
     "Everything has laws; most are dark. Learn the laws of the multiverse and you can rule it.",
     ["Mercykillers", "Harmonium"], ["Xaositects", "Revolutionary League"]),
    ("Free League", "Indeps", None, "Great Bazaar", "Market Ward", "Outlands",
     "This ain't no faction, and nobody tells us what to do; nobody's got the key to the truth.",
     ["Fated"], ["Harmonium"]),
    ("Harmonium", "Hardheads", "Sarin", "City Barracks", "Lady's Ward", "Arcadia",
     "Peace is our goal — but if it takes a little war to reach our golden harmony, so be it.",
     ["Fraternity of Order", "Mercykillers"], ["Free League", "Revolutionary League", "Xaositects"]),
    ("Mercykillers", "Red Death", "Alisohn Nilesia", "Prison", "Lady's Ward", "Acheron",
     "Justice is everything; when properly applied, punishment leads to perfection.",
     ["Harmonium", "Fraternity of Order"], []),
    ("Revolutionary League", "Anarchists", None, "Mobile", None, "Carceri",
     "The status quo is built on lies and greed. Crush the factions and rebuild with what's left.",
     ["Doomguard", "Xaositects"], ["Harmonium", "Fraternity of Order"]),
    ("Sign of One", "Signers", "Darius", "Hall of Speakers", "Clerk's Ward", "Beastlands",
     "The multiverse exists because the mind imagines it; the Signers create it through thought.",
     ["Society of Sensation"], ["Bleak Cabal", "Harmonium"]),
    ("Society of Sensation", "Sensates", "Erin Montgomery", "Civic Festhall", "Clerk's Ward", "Arborea",
     "To know the multiverse, experience it fully; the senses form the path to truth.",
     ["Sign of One", "Free League", "Fraternity of Order"], ["Doomguard", "Mercykillers", "Dustmen"]),
    ("Transcendent Order", "Ciphers", "Rhys", "Great Gymnasium", "Guildhall Ward", "Elysium",
     "Action without thought is the purest response; train body and mind to act in harmony.",
     [], ["Harmonium"]),
    ("Xaositects", "Chaosmen", "Karan", "Hive", "Hive Ward", "Limbo",
     "Chaos is truth, order delusion; embracing randomness, one learns the multiverse's secrets.",
     ["Doomguard", "Bleak Cabal"], ["Fraternity of Order", "Harmonium"]),
]


def pour_manifesto(store):
    """Merge the Factol's Manifesto faction data into Mimir (cross-book). Enriches each faction
    node's fields + provenance (Uncaged members + Manifesto philosophy/factol/HQ/…), promotes the
    factol to an npc with led_by, resolves the HQ against existing Sigil locations (or seeds it),
    and wires allied_with/opposed_to. Returns (factions, factols, hqs)."""
    src_id = "source:factols-manifesto"

    def loc_resolve(name):
        for cand in (f"location:sigil:{S.slug(name)}", f"location:sigil:the-{S.slug(name)}",
                     f"location:sigil:{S.slug('the ' + name)}"):
            if store.get(cand):
                return cand
        return None

    nfac = nfactol = nhq = 0
    for name, nick, factol, hq, ward, home, phil, allies, enemies in FACTION_DATA:
        fid = f"faction:{S.slug(name)}"
        existing = store.get(fid) or {}
        fields = dict(existing.get("fields") or {})
        fields.update({"nickname": nick, "factol": factol, "headquarters": hq, "hq_ward": ward,
                       "home_plane": home, "philosophy": phil})
        prov = existing.get("provenance") or {"value_sources": [], "method": "cross-source"}
        srcs = prov.get("value_sources") or []
        if not any(s.get("src") == "factols-manifesto" for s in srcs):
            srcs.append({"src": "factols-manifesto", "loc": "p5-6 factions-at-a-glance"})
        prov["value_sources"] = srcs
        _admit_seed(store, {"type": "faction", "id": fid, "name": name, "edition": "2e", "fields": fields,
                            "content": f"{name} {nick} {phil} factol {factol} HQ {hq} {ward or ''}",
                            "provenance": prov, "confidence": 1.0,
                            "curated": existing.get("curated") or {}, "source_sha": None},
                    "manifesto-faction-card", len(allies) + len(enemies))
        store.add_edge("attested_in", fid, src_id, src_type="faction", tgt_type="source", edition="2e")
        nfac += 1
        if factol and factol.lower() not in ("none", "-"):
            fnid = f"npc:manifesto:{S.slug(factol)}"
            _admit_seed(store, {"type": "npc", "id": fnid, "name": factol, "edition": "2e",
                                "fields": {"tier": "factol", "role": f"factol of the {name}", "faction": name},
                                "content": f"{factol} factol leader of the {name} {nick}",
                                "provenance": {"value_sources": [{"src": "factols-manifesto"}], "method": "seed"},
                                "confidence": 0.85, "curated": {}, "source_sha": None}, "factol", 1)
            store.add_edge("led_by", fid, fnid, src_type="faction", tgt_type="npc", edition="2e")
            store.add_edge("member_of", fnid, fid, src_type="npc", tgt_type="faction", edition="2e")
            store.add_edge("attested_in", fnid, src_id, src_type="npc", tgt_type="source", edition="2e")
            nfactol += 1
        if hq and hq.lower() != "mobile":
            hid = loc_resolve(hq) or f"location:sigil:{S.slug(hq)}"
            if not store.get(hid):
                _loc_seed(store, hid, hq, "faction headquarters",
                          f"{hq}, HQ of the {name}, {ward or 'Sigil'}", 0.9, "factols-manifesto",
                          ward=ward, tier="site")
                wid = f"location:sigil:{S.slug(ward)}" if ward else None
                if wid and store.get(wid):
                    store.add_edge("part_of", hid, wid, src_type="location", tgt_type="location", edition="2e")
                nhq += 1
            store.add_edge("headquartered_in", fid, hid, src_type="faction", tgt_type="location", edition="2e")
        for a in allies:
            store.add_edge("allied_with", fid, f"faction:{S.slug(a)}",
                           src_type="faction", tgt_type="faction", edition="2e")
        for e in enemies:
            store.add_edge("opposed_to", fid, f"faction:{S.slug(e)}",
                           src_type="faction", tgt_type="faction", edition="2e")
    return nfac, nfactol, nhq


def _loc_seed(store, lid, name, kind, content, conf, src, **fields):
    _admit_seed(store, {"type": "location", "id": lid, "name": name, "edition": "2e",
                        "fields": {"kind": kind, **fields}, "content": content,
                        "provenance": {"value_sources": [{"src": src}], "method": "seed"},
                        "confidence": conf, "curated": {}, "source_sha": None}, "geography", 1)


# The real establishments, hand-transcribed from the "Locations by Ward" index (p130) via the
# column-aware reflow — (name, kind, ward, [occupants]). The garbled NPCs-&-Establishments list
# (p126) and the per-NPC LOCATION lines corroborate the kinds. Market & Guildhall are merged in
# the book; we file their shops under Market Ward.
ESTABLISHMENTS = [
    ("The Azure Iris", "gallery-inn", "Lady's Ward", ["Verden"]),
    ("City Court", "courthouse", "Lady's Ward", ["Sly Nye"]),
    ("The Dusty Wig", "tavern", "Lady's Ward", ["Black Marian", "Sly Nye"]),
    ("Fortune's Wheel", "gambling tavern", "Lady's Ward",
     ["Shemeshka the Marauder", "Jemorille the Exile", "P. Cad Peadle"]),
    ("The Palace of the Jester", "landmark", "Lady's Ward", ["Autochon the Bellringer"]),
    ("Petitioner's Square", "square", "Lady's Ward", ["Kunk"]),
    ("The Singing Fountain", "landmark", "Lady's Ward", ["Black Marian"]),
    ("Traban's Forge", "forge", "Lady's Ward", ["Tarholt"]),
    ("Tripicus's study", "study", "Lady's Ward", ["Tripicus"]),
    ("Tussa's greenhouse", "greenhouse", "Lady's Ward", ["Tussa"]),
    ("The Civic Festhall", "festhall", "Clerk's Ward", ["Ly'kritch", "Tripicus"]),
    ("The Hall of Information", "civic hall", "Clerk's Ward", ["Brot the Mad"]),
    ("The Hall of Speakers", "government hall", "Clerk's Ward", ["Cirily", "The Will of the One"]),
    ("Milori's translation shop", "shop", "Clerk's Ward", ["Milori"]),
    ("O'pok's museum", "museum", "Clerk's Ward", ["O'pok the Fawning"]),
    ("Planar Trade Consortium office", "office", "Clerk's Ward", ["Estavan", "Koe"]),
    ("The Trianym", "landmark", "Clerk's Ward", ["Cirily"]),
    ("Chinzpeter's clothing shop", "shop", "Market Ward", ["Chinzpeter", "Morvun and Phineas"]),
    ("The Fat Candle", "tavern", "Market Ward", ["Adamok Ebon"]),
    ("The Feathernest Inn", "inn", "Market Ward", ["Adamok Ebon"]),
    ("Fell's tattoo shop", "shop", "Market Ward", ["Fell"]),
    ("The Great Bazaar", "bazaar", "Market Ward", ["Koe"]),
    ("Harys Hatchis's shop", "shop", "Market Ward", ["Harys Hatchis"]),
    ("The Other Place", "spa", "Market Ward", ["Iarmid", "Autochon the Bellringer", "Koe"]),
    ("Parts and Pieces", "animal-parts shop", "Market Ward", ["Seamusxanthuszenus"]),
    ("Tiwum's Antiquities", "antiquities shop", "Market Ward", ["Alluvius Ruskin"]),
    ("Wooly Cupgrass's laboratory", "laboratory", "Market Ward", ["Wooly Cupgrass"]),
    ("The Face of Gith", "pub", "Lower Ward", ["Fhas'kir"]),
    ("The Friendly Fiend", "magic shop", "Lower Ward", ["A'kin"]),
    ("The Parted Veil", "bookshop", "Lower Ward", ["Kesto Brighteyes"]),
    ("The Court of Woe", "courthouse", "Lower Ward", ["Judge Gabberslug", "Sly Nye"]),
    ("The Shattered Temple", "temple", "Lower Ward", ["Saure"]),
    ("The Speckled Rat", "tavern", "Lower Ward", ["The Grixitt", "Qaida"]),
    ("The Styx Oarsman", "tavern", "Lower Ward", ["Rule-of-Three"]),
    ("Thelinagra's studio", "studio", "Lower Ward", ["Thelinagra"]),
    ("The White Casket", "Dustmen front", "Lower Ward", ["Qaida"]),
    ("Allesha's Pantry", "shop", "Hive Ward", ["Unity-of-Rings"]),
    ("Elia Remi's kip", "kip", "Hive Ward", ["Elia Remi"]),
    ("The Gatehouse", "asylum", "Hive Ward", ["Morvun and Phineas", "Xideous"]),
    ("The Mortuary", "mortuary", "Hive Ward", ["Ly'kritch", "Qaida"]),
    ("Parakk's kip", "kip", "Hive Ward", ["Parakk the Ratcatcher"]),
    ("Sister Cade's church", "church", "Hive Ward", ["Sister Cade"]),
    ("The Slags", "district", "Hive Ward", ["The Us"]),
    ("Stone & Cog company", "building company", "Hive Ward", ["Tcha", "Phyton", "Sken Leafwood"]),
    ("The Weary Head Pub", "pub", "Hive Ward", ["Morvun and Phineas"]),
    ("Ylem's tower", "tower", "Hive Ward", ["Ylem", "Patch"]),
]


def pour_locations(store, nodes):
    """Sigil + its six wards + the REAL establishments (kind + occupants) from the back-matter
    index, with each cutter threaded into the kip/shop/tavern it frequents and that site filed
    under its ward. Plus a ward-level placement for every NPC whose LOCATION line names a ward."""
    resolve = _node_resolver(store)
    _loc_seed(store, "location:sigil", "Sigil", "city",
              "Sigil the Cage City of Doors hub of the planes Lady of Pain", 1.0, "setting",
              epithet="the Cage, City of Doors")
    for w in N.SIGIL_WARDS:
        wid = f"location:sigil:{S.slug(w)}"
        _loc_seed(store, wid, w, "ward", f"{w} a ward of Sigil", 1.0, "setting", parent="Sigil")
        store.add_edge("part_of", wid, "location:sigil", src_type="location", tgt_type="location", edition="2e")
    n = 1 + len(N.SIGIL_WARDS)
    for name, kind, ward, occupants in ESTABLISHMENTS:
        sid = f"location:sigil:{S.slug(name)}"
        wid = f"location:sigil:{S.slug(ward)}"
        _loc_seed(store, sid, name, kind, f"{name} {kind} in the {ward}, Sigil — " + ", ".join(occupants),
                  0.9, "uncaged:locations-by-ward", ward=ward, tier="site")
        store.add_edge("part_of", sid, wid, src_type="location", tgt_type="location", edition="2e")
        for occ in occupants:
            oid = resolve(occ)
            if oid:
                store.add_edge("located_in", oid, sid, src_type=oid.split(":")[0],
                               tgt_type="location", edition="2e")
        n += 1
    for v2 in nodes:                                   # ward-level placement (covers siteless NPCs)
        p = N.parse_location((v2.get("sections") or {}).get("LOCATION") or "")
        wid = f"location:sigil:{S.slug(p['ward'])}" if p["ward"] else ("location:sigil" if p["in_sigil"] else None)
        if wid:
            store.add_edge("located_in", f"npc:uncaged:{S.slug(v2['name'])}", wid,
                           src_type="npc", tgt_type="location", edition="2e")
    return n


# Uncaged's named non-faction groups, sourced from the back-matter plot statements. Thin by
# design (the book is NPC-focused) — seeded with provenance, members linked where they're nodes.
ORGS = [
    {"id": "organization:will-of-the-one", "name": "The Will of the One",
     "fields": {"kind": "sect (Sign of One splinter)", "purpose": "resurrect Aoskar, the dead god of portals",
                "leader": "Prisine", "figurehead": "Terwolfe"},
     "members": ["Terwolfe"], "led_by": "Prisine", "parent_faction": "sign-of-one"},
    {"id": "organization:stone-and-cog", "name": "Stone & Cog",
     "fields": {"kind": "guild (builders)", "purpose": "designs, constructs, and renovates buildings in the Cage"},
     "members": ["Tcha", "Phyton", "Sken Leafwood"]},
    {"id": "organization:rrakkma-bands", "name": "Rrakkma Bands",
     "fields": {"kind": "gith hunting parties", "purpose": "hunt illithids across the planes"},
     "members": ["Fhas'kir"]},
]


def pour_organizations(store, nodes):
    """Seed the named crews/sects the cast belongs to, and link the cutters the book places in
    them (member_of), the one it names a leader (led_by), and a sect's parent faction (part_of).
    A member edge to a not-yet-promoted companion (Prisine) dangles honestly until promotion."""
    for org in ORGS:
        mem = org["members"]
        env = {"type": "organization", "id": org["id"], "name": org["name"], "edition": "2e",
               "fields": org["fields"],
               "content": f"{org['name']} {org['fields'].get('kind','')} {org['fields'].get('purpose','')} "
                          + " ".join(mem),
               "provenance": {"value_sources": [{"src": "uncaged:back-matter"}], "method": "seed"},
               "confidence": 0.85, "curated": {}, "source_sha": None}
        _admit_seed(store, env, "back-matter", len(mem))
        for m in mem:
            store.add_edge("member_of", f"npc:uncaged:{S.slug(m)}", org["id"],
                           src_type="npc", tgt_type="organization", edition="2e")
        if org.get("led_by"):
            store.add_edge("led_by", org["id"], f"npc:uncaged:{S.slug(org['led_by'])}",
                           src_type="organization", tgt_type="npc", edition="2e")
        if org.get("parent_faction"):
            store.add_edge("part_of", org["id"], f"faction:{org['parent_faction']}",
                           src_type="organization", tgt_type="faction", edition="2e")
    return len(ORGS)


# --- plot/hook dimension: the back-matter relationship webs (the book's marquee feature) ------
# The named plot threads, with the cutters each one involves. Hand-read off pp 125-126 because the
# display-font + dense layout OCR too poorly for reliable auto-parsing (Mimir V&V plot finding).
PLOT_HOOKS = [
    {"id": "hook:uncaged:blood-war", "name": "The Blood War Plot",
     "premise": "Cutters fuel — or smother — the eternal fiend war for profit and for balance.",
     "involves": ["Cirily", "Koe", "Tripicus", "Estavan", "Zadara", "Black Marian",
                  "Rule-of-Three", "Jemorille the Exile"]},
    {"id": "hook:uncaged:dead-gods", "name": "The Dead Gods Plot",
     "premise": "The Will of the One schemes to resurrect Aoskar, the dead god of portals.",
     "involves": ["The Will of the One", "Omott", "Fell", "Prisine", "Adamok Ebon", "Terwolfe",
                  "Kesto Brighteyes", "Saure", "Farrow", "Shemeshka the Marauder"]},
    {"id": "hook:uncaged:dustmen-contract", "name": "The Dustmen Contract Plot",
     "premise": "Verden cheated her Dustmen death-contract by becoming a Prolonger; the Dead collect.",
     "involves": ["Verden", "Qaida", "Judge Gabberslug", "Sly Nye", "Saure"]},
    {"id": "hook:uncaged:mind-trappers", "name": "The Mind Trappers Plot",
     "premise": "A gem-smuggling ring traps living souls in stones and trades them across the planes.",
     "involves": ["Tarholt", "Qaida", "Ly'kritch", "Alluvius Ruskin"]},
    {"id": "hook:uncaged:shemeshkas-web", "name": "Shemeshka's Web",
     "premise": "The arcanaloth King of the Cross-Trade spies, employs, and feuds across Sigil.",
     "involves": ["Shemeshka the Marauder", "Farrow", "Adamok Ebon", "Autochon the Bellringer",
                  "Kylie", "The Will of the One"]},
]

# Typed relationship edges, HAND-TRANSCRIBED from the back matter (page-witnessed, not auto-parsed —
# the section's OCR garbles names and the subject persists ambiguously across verbs). (subject, rel, targets)
PLOT_EDGES = [
    # "Bigwigs with Jink" (p126)
    ("Zadara", "funds", ["Djhek'nlarr", "Koe", "Lissandra the Gate-seeker", "Xideous", "Ylem"]),
    ("Zadara", "opposes", ["Estavan", "Shemeshka the Marauder"]),
    ("Estavan", "supplies", ["A'kin", "Kesto Brighteyes", "Koe", "Alluvius Ruskin",
                             "The Will of the One", "Xideous"]),
    ("Estavan", "opposes", ["Shemeshka the Marauder", "Tarholt", "Zadara"]),
    ("Shemeshka the Marauder", "employs", ["Autochon the Bellringer", "Adamok Ebon", "Farrow",
                                           "Jemorille the Exile"]),
    ("Shemeshka the Marauder", "protects", ["Kylie"]),
    ("Shemeshka the Marauder", "opposes", ["A'kin", "Estavan", "Xideous", "Zadara"]),
    ("Shemeshka the Marauder", "spied_on_by", ["Rule-of-Three", "Xideous"]),
    # narrative chains from the named plots
    ("Tarholt", "supplies", ["Qaida"]), ("Qaida", "supplies", ["Ly'kritch"]),
    ("Ly'kritch", "supplies", ["Alluvius Ruskin"]),
    ("Prisine", "employs", ["Adamok Ebon"]), ("Kesto Brighteyes", "summoned", ["Saure"]),
    ("Farrow", "spies_on", ["The Will of the One"]),
    ("Qaida", "opposes", ["Verden"]), ("Sly Nye", "defends", ["Verden"]),
    ("Shemeshka the Marauder", "spies_on", ["The Will of the One"]),
]


def _node_resolver(store):
    """Map a name (incl. short/leading-'the' variants) to an admitted npc/organization id."""
    pool = {}
    for r in store.conn.execute("SELECT id, name FROM entities WHERE type IN ('npc','organization')"):
        base = re.sub(r"^the ", "", (r["name"] or "").lower())
        for k in {S.slug(r["name"]), S.slug(base), (base.split() or [""])[0]}:
            if k and len(k) >= 3:
                pool.setdefault(k, r["id"])
    def resolve(name):
        b = re.sub(r"^the ", "", name.lower().strip())
        for k in (S.slug(name), S.slug(b), (b.split() or [""])[0]):
            if k in pool:
                return pool[k]
        return None
    return resolve


def pour_plots(store):
    """Seed the named plot hooks + their involves edges, and the hand-transcribed typed edges.
    Every typed edge carries its page witness in provenance — verified, not guessed."""
    resolve = _node_resolver(store)
    for h in PLOT_HOOKS:
        env = {"type": "hook", "id": h["id"], "name": h["name"], "edition": "2e",
               "fields": {"grain": "plot", "premise": h["premise"]},   # named arcs; seeds nest part_of these
               "content": f"{h['name']} {h['premise']} " + " ".join(h["involves"]),
               "provenance": {"value_sources": [{"src": "uncaged:p125-126 plots"}], "method": "seed"},
               "confidence": 0.9, "curated": {}, "source_sha": None}
        _admit_seed(store, env, "back-matter-plot", len(h["involves"]))
        for who in h["involves"]:
            tid = resolve(who)
            if tid:
                store.add_edge("involves", h["id"], tid, src_type="hook",
                               tgt_type=tid.split(":")[0], edition="2e")
    poured, unresolved = 0, []
    for subj, rel, targets in PLOT_EDGES:
        sid = resolve(subj)
        if not sid:
            unresolved.append(subj); continue
        for tg in targets:
            tid = resolve(tg)
            if tid and tid != sid:
                store.add_edge(rel, sid, tid, src_type=sid.split(":")[0], tgt_type=tid.split(":")[0],
                               edition="2e", provenance={"src": "uncaged:bigwigs-with-jink",
                                                         "method": "hand-transcribed (page-witnessed)"})
                poured += 1
            elif not tid:
                unresolved.append(tg)
    return len(PLOT_HOOKS), poured, unresolved


# --- subject dimension: the cross-book pivot STAGING lane (now EMPTY — all three folded) -------
# A subject is a STAGING node (fork ruling 2026-06-05): a cross-book MacGuffin carrying aliases so
# oblique refs resolve and the pivot is graph-walkable, UNTIL its home dimension pours and ABSORBS it.
# ALL THREE folded 2026-06-05 (Ryan): Aoskar → `deity:aoskar`, the Lady of Pain → `sigil:the-lady-of-pain`,
# the Blood War → `event:the-blood-war`. The lane stays OPEN for the next book's cross-book MacGuffin
# (it stages here until ITS home dim pours); SUBJECTS is empty until then.
SUBJECTS = []


def pour_subjects(store):
    """Admit the cross-book plot pivots as `subject` nodes (with aliases), and link each to the
    curated plot(s) it is the MacGuffin of (a `concerns` edge). Schema floor: name + >=1 alias + gloss."""
    for s in SUBJECTS:
        assert s["name"] and s["aliases"] and s["gloss"], s["id"]          # schema floor (witnessed)
        env = {"type": "subject", "id": s["id"], "name": s["name"], "edition": "2e",
               "fields": {"kind": s["kind"], "gloss": s["gloss"], "aliases": s["aliases"]},
               "content": f"{s['name']} {s['kind']} {s['gloss']} " + " ".join(s["aliases"]),
               "provenance": {"value_sources": [{"src": w} for w in s["witness"]],
                              "method": "hand-defined (page-witnessed)"},
               "confidence": 0.9, "curated": {}, "source_sha": None}
        docket = {"decision": "ADMIT", "adjudicator": "auto",
                  "checks": [{"layer": "L1", "name": "name_present", "sev": "hard",
                              "result": "pass" if env["name"] else "fail"},
                             {"layer": "L1", "name": "aliases_present", "sev": "hard",
                              "result": "pass" if s["aliases"] else "fail"},
                             {"layer": "L1", "name": "gloss_present", "sev": "soft",
                              "result": "pass" if s["gloss"] else "fail"}],
                  "independent": {"channel": "cross-book-pivot", "confirmations": len(s["witness"])},
                  "confidence_final": env["confidence"]}
        store.admit(env, docket)
        for pid in s["plots"]:
            if store.exists(pid):
                store.add_edge("concerns", pid, s["id"], src_type="hook", tgt_type="subject", edition="2e")
    return len(SUBJECTS)


# --- deity dimension: powers attested in the POURED corpus (Aoskar; fills out w/ On Hallowed Ground) ---
# Aoskar ABSORBS subject:aoskar (the fold): a real `deity` node carrying the portfolio epithets as
# aliases + the Dead Gods Plot (concerns). Poseidon/Arawn et al. live in un-poured books — out of scope
# until those pour. Page-witnessed; aliases stay Aoskar-SPECIFIC (never the generic "fraudulent god").
DEITIES = [
    {"id": "deity:aoskar", "name": "Aoskar", "portfolio": "portals", "status": "dead",
     "pantheon": "dead / Sigil", "alignment": "N",
     "gloss": "The dead god of portals; his church once rivaled the Lady's rule of Sigil until she "
              "destroyed him and forbade his worship. His remnant divinity is chanted a gate-key.",
     "aliases": ["god of portals", "dead god of portals", "the dead god of portals"],
     "witness": ["uncaged:p8", "uncaged:p24", "uncaged:p26", "manifesto:p9", "manifesto:p11", "manifesto:p124"],
     "plots": ["hook:uncaged:dead-gods"]},
]


def pour_deities(store):
    """Pour the powers attested in the poured corpus. Aoskar absorbs `subject:aoskar` (fold ruling) —
    a `deity` node carrying the portfolio epithets as aliases + the Dead Gods Plot (`concerns`)."""
    for d in DEITIES:
        env = {"type": "deity", "id": d["id"], "name": d["name"], "edition": "2e",
               "fields": {"portfolio": d["portfolio"], "status": d["status"], "pantheon": d["pantheon"],
                          "alignment": d.get("alignment"), "gloss": d["gloss"], "aliases": d["aliases"]},
               "content": f"{d['name']} {d['portfolio']} {d['status']} power {d['gloss']} " + " ".join(d["aliases"]),
               "provenance": {"value_sources": [{"src": w} for w in d["witness"]],
                              "method": "hand-defined (page-witnessed)"},
               "confidence": 0.9, "curated": {}, "source_sha": None}
        _admit_seed(store, env, "deity-attestation", len(d["witness"]))
        for pid in d["plots"]:
            if store.exists(pid):
                store.add_edge("concerns", pid, d["id"], src_type="hook", tgt_type="deity", edition="2e")
    return len(DEITIES)


# --- sigil dimension: the singleton hub's irreducible ruler-being --------------------------------
# The Lady of Pain ABSORBS subject:the-lady-of-pain (the fold). She's a `sigil`-type being (sui generis —
# no statblock, no power); the hub PLACE stays `location:sigil`, now ruled_by her, seating the factions
# and holding the six wards. trace_entity("The Lady of Pain") → one node spanning both books' hooks.
LADY = {"id": "sigil:the-lady-of-pain", "name": "The Lady of Pain", "kind": "ruler",
        "gloss": "Sigil's silent, dreaded ruler; she suffers no worship and mazes or flays any who would "
                 "seize the city or set themselves up as her equal. Sui generis — no statblock, no power.",
        "aliases": ["lady of pain", "the lady of pain", "her serenity"],
        "witness": ["uncaged:passim", "manifesto:fated"]}


def pour_sigil(store):
    """Pour the Lady of Pain as the sigil singleton's ruler-being (absorbs subject:the-lady-of-pain), and
    enrich the existing `location:sigil` hub: ruled_by → the Lady, has_ward → the six wards, seats → every
    faction. Returns (lady, ward_edges, faction_seats)."""
    env = {"type": "sigil", "id": LADY["id"], "name": LADY["name"], "edition": "2e",
           "fields": {"kind": LADY["kind"], "gloss": LADY["gloss"], "aliases": LADY["aliases"]},
           "content": f"{LADY['name']} ruler of Sigil {LADY['gloss']} " + " ".join(LADY["aliases"]),
           "provenance": {"value_sources": [{"src": w} for w in LADY["witness"]],
                          "method": "hand-defined (page-witnessed)"},
           "confidence": 0.9, "curated": {}, "source_sha": None}
    _admit_seed(store, env, "sigil-ruler", len(LADY["witness"]))
    hub, wards, seats = "location:sigil", 0, 0
    if store.exists(hub):
        store.add_edge("ruled_by", hub, LADY["id"], src_type="location", tgt_type="sigil", edition="2e")
        for w in store.list("location", limit=999):
            if "ward" in (w["name"] or "").lower():
                store.add_edge("has_ward", hub, w["id"], src_type="location", tgt_type="location", edition="2e")
                wards += 1
        for f in store.list("faction", limit=99):
            store.add_edge("seats", hub, f["id"], src_type="location", tgt_type="faction", edition="2e")
            seats += 1
    return 1, wards, seats


# --- event dimension: historical / setting events attested in the poured corpus -----------------
# The Blood War ABSORBS subject:the-blood-war (the LAST fold). The Great Upheaval (~630y ago) is the
# founding event of the modern Cage — the Lady destroyed Aoskar, razed his Great Temple of Doors (now
# the Shattered Temple), forbade worship, chartered the factions; deity:aoskar + sigil:the-lady-of-pain
# `participated_in` it (the cross-dimension capstone). Page-witnessed.
EVENTS = [
    {"id": "event:the-blood-war", "name": "The Blood War", "kind": "war", "era": "ongoing (eternal)",
     "when": "since the dawn of the planes",
     "gloss": "The eternal, multiverse-spanning war between the tanar'ri and the baatezu — chaos against "
              "law among the fiends. Neither side can win; cutters profit by fueling or smothering it, and "
              "whole factions quietly take sides.",
     "aliases": ["blood war", "the blood war", "the eternal war"],
     "participants": [], "occurred_at": None,
     "witness": ["uncaged:p125", "manifesto:doomguard"], "plots": ["hook:uncaged:blood-war"]},
    {"id": "event:the-great-upheaval", "name": "The Great Upheaval", "kind": "cataclysm",
     "era": "~630 years ago", "when": "c. 630 years before the 2e present",
     "gloss": "The founding event of the modern Cage: the Lady of Pain destroyed the god Aoskar, razed his "
              "Great Temple of Doors (now the Shattered Temple), forbade the worship of any power within "
              "Sigil, and set the terms under which the factions hold their charter.",
     "aliases": ["great upheaval", "the great upheaval"],
     "participants": ["sigil:the-lady-of-pain", "deity:aoskar"],
     "occurred_at": "location:sigil:the-shattered-temple",
     "witness": ["manifesto:p4", "manifesto:p11", "manifesto:p41", "manifesto:p103"], "plots": []},
]


def pour_events(store):
    """Pour the historical events attested in the poured corpus. The Blood War absorbs
    `subject:the-blood-war` (the last fold) — aliases + the Blood War Plot (`concerns`). The Great
    Upheaval ties the capstone: deity:aoskar + sigil:the-lady-of-pain `participated_in` it, and it
    `occurred_at` the Shattered Temple. Returns len(EVENTS)."""
    for ev in EVENTS:
        env = {"type": "event", "id": ev["id"], "name": ev["name"], "edition": "2e",
               "fields": {"kind": ev["kind"], "era": ev["era"], "when": ev["when"], "gloss": ev["gloss"],
                          "aliases": ev["aliases"], "participants": ev["participants"]},
               "content": f"{ev['name']} {ev['kind']} {ev['era']} {ev['gloss']} " + " ".join(ev["aliases"]),
               "provenance": {"value_sources": [{"src": w} for w in ev["witness"]],
                              "method": "hand-defined (page-witnessed)"},
               "confidence": 0.9, "curated": {}, "source_sha": None}
        _admit_seed(store, env, "event-attestation", len(ev["witness"]))
        for pid in ev["plots"]:
            if store.exists(pid):
                store.add_edge("concerns", pid, ev["id"], src_type="hook", tgt_type="event", edition="2e")
        for part in ev["participants"]:
            if store.exists(part):
                store.add_edge("participated_in", part, ev["id"],
                               src_type=part.split(":")[0], tgt_type="event", edition="2e")
        if ev.get("occurred_at") and store.exists(ev["occurred_at"]):
            store.add_edge("occurred_at", ev["id"], ev["occurred_at"],
                           src_type="event", tgt_type="location", edition="2e")
    return len(EVENTS)


# --- THIRD BOOK: In the Cage — A Guide to Sigil (2609) + the Places dimensions ---------------
# parse/cage.py is the gear-house (roster-driven establishment split + the portal sweep +
# the curated Places gazetteer); this section is the pour. The book is the city's geography
# vector: ~50 ward establishments (heavy dual-source merge with Uncaged's location nodes),
# the portal catalog, and the first plane/layer/realm/gate-town/pathway/cosmology nodes —
# every Places node ships ONLY with page witnesses from the attestation sweep.
CAGE_SRC = "source:in-the-cage"
CAGE_REFLOW = ROOT / "build/in-the-cage-a-guide-to-sigil/ddps-inthecage/reflow"


def _cage_loc_resolver(store):
    """name → existing location id (Uncaged pour), tolerant of 'the-' prefix and
    suffix drift ('Golden Bariaur Inn' vs the text's 'Golden Bariaur')."""
    pool = {}
    for r in store.conn.execute("SELECT id, name FROM entities WHERE type='location'"):
        base = re.sub(r"^the ", "", (r["name"] or "").lower()).strip()
        for k in {S.slug(r["name"]), S.slug(base), S.slug(re.sub(r"\s+inn$", "", base))}:
            if k and len(k) >= 3:
                pool.setdefault(k, r["id"])
    def resolve(name):
        b = re.sub(r"^the ", "", (name or "").lower()).strip()
        for k in (S.slug(name), S.slug(b), S.slug(re.sub(r"\s+inn$", "", b))):
            if k in pool:
                return pool[k]
        return None
    return resolve


def _cage_entries():
    """Segment the book once: (entries incl. minors, missing-but-explained, pages)."""
    pages = C.load_pages(CAGE_REFLOW)
    entries, missing = C.segment(pages)
    minors, mmissing = C.segment_minors(pages)
    C.trim_entries(pages, entries, minors)
    return entries + minors, missing + mmissing, pages


def pour_cage(store):
    """Pour In the Cage: source node, establishments (merge-or-seed), Places nodes
    (gazetteer attestation), portal nodes (sentence-witnessed sweep), and the named
    expected-absent entries into quarantine for the v1b re-OCR pass.
    Returns a counts dict for the report."""
    srcjson = CAGE_REFLOW.parent / "source.json"
    sha = None
    if srcjson.exists():
        sha = (json.loads(srcjson.read_text(encoding="utf-8")) or {}).get("sha256")
    _admit_seed(store, {"type": "source", "id": CAGE_SRC, "name": "In the Cage: A Guide to Sigil",
                        "edition": "2e", "fields": {"tsr": "2609", "year": 1995,
                        "authors": "Wolfgang Baur & Rick Swan", "pages": 128},
                        "content": "In the Cage A Guide to Sigil TSR 2609 wards establishments portals",
                        "provenance": {"value_sources": [{"src": "ddps-inthecage"}], "method": "seed"},
                        "confidence": 1.0, "curated": {}, "source_sha": sha}, "book", 1)

    entries, missing, pages = _cage_entries()
    resolve = _cage_loc_resolver(store)
    nmerged = nnew = 0
    for e in entries:
        if e["rtype"] not in ("site", "minor"):
            continue
        body = e["body"][:6000]
        eid = e.get("hint") or resolve(e["name"])
        wid = f"location:sigil:{S.slug(e['ward'])}" if e.get("ward") else None
        old = store.get(eid) if eid else None
        if old:                                          # dual-source MERGE (the Manifesto pattern)
            fields = dict(old.get("fields") or {})
            fields.setdefault("kind", e["kind"])
            fields["cage_page"] = e["page"]
            fields.setdefault("ward", e.get("ward"))
            prov = old.get("provenance") or {"value_sources": [], "method": "cross-source"}
            srcs = prov.get("value_sources") or []
            if not any(s.get("src") == "in-the-cage" for s in srcs):
                srcs.append({"src": "in-the-cage", "loc": f"p{e['page']}"})
            prov["value_sources"] = srcs
            content = (old.get("content") or "") + f"\n\n[In the Cage p{e['page']}] " + body
            _admit_seed(store, {"type": "location", "id": eid, "name": old["name"], "edition": "2e",
                                "fields": fields, "content": content, "provenance": prov,
                                "confidence": max(old.get("confidence") or 0, 0.9),
                                "curated": old.get("curated") or {}, "source_sha": old.get("source_sha")},
                        "cage-establishment-merge", 2)
            nmerged += 1
        else:                                            # fresh node, roster-verified
            eid = f"location:sigil:{S.slug(e['name'])}"
            _admit_seed(store, {"type": "location", "id": eid, "name": e["name"], "edition": "2e",
                                "fields": {"kind": e["kind"], "ward": e.get("ward"),
                                           "tier": e["rtype"], "cage_page": e["page"],
                                           "head_score": e["score"]},
                                "content": f"{e['name']} {e['kind']} in the {e.get('ward') or 'Cage'}, "
                                           f"Sigil.\n{body}",
                                "provenance": {"value_sources": [{"src": "in-the-cage",
                                                                  "loc": f"p{e['page']}"}],
                                               "method": "roster-extraction"},
                                "confidence": 0.9, "curated": {}, "source_sha": sha},
                        "cage-establishment", 1)
            if wid and store.exists(wid):
                store.add_edge("part_of", eid, wid, src_type="location", tgt_type="location",
                               edition="2e")
            nnew += 1
        e["loc_id"] = eid
        store.add_edge("attested_in", eid, CAGE_SRC, src_type="location", tgt_type="source",
                       edition="2e")

    # the named losses — review queue, never guesses (v1b re-OCR is the upgrade path).
    # Entries RECOVERED by a witnessed ENTRY_CURATIONS span (Great Audit, Meme-adopted
    # 2026-06-06) poured above and skip the queue; if a curation's anchors ever fail,
    # the name lands back here automatically — verified or absent, both directions.
    recovered = {e["name"] for e in entries if e.get("cured")}
    nabsent = 0
    for name, why in C.EXPECTED_ABSENT.items():
        if name in recovered:
            continue
        qid = f"location:sigil:{S.slug(name)}#cage-entry"
        store.quarantine({"type": "location", "id": qid, "name": name, "edition": "2e",
                          "fields": {"book": "in-the-cage"}, "content": why,
                          "provenance": {"value_sources": [{"src": "in-the-cage"}],
                                         "method": "roster-extraction"},
                          "confidence": 0.0, "curated": {}, "source_sha": sha},
                         {"entity_id": qid, "decision": "QUARANTINE", "adjudicator": "auto",
                          "checks": [{"layer": "L1", "name": "entry_recovered", "sev": "hard",
                                      "result": "fail", "detail": why}]},
                         "cage-head-lost")
        nabsent += 1

    nplaces, nplace_edges = pour_places(store, C.attest_places(pages, offset=2), sha)
    nportal, nportal_q = pour_portals(store, entries, sha)
    return {"merged": nmerged, "new": nnew, "absent": nabsent, "places": nplaces,
            "place_edges": nplace_edges, "portals": nportal, "portals_queued": nportal_q}


def pour_places(store, wit, sha):
    """The Places dimensions: every gazetteer node the book ATTESTS (page witnesses
    required), plus the structural edges — layer_of, located_in, gate_to, part_of
    ring/inner-planes groupings. Curated geometry, witnessed admission."""
    order = {"cosmology": 0, "plane": 1, "layer": 2, "realm": 3, "pathway": 4, "gate-town": 5}
    npl = nedge = 0
    poured = set()
    for gid in sorted(wit, key=lambda g: order.get(g.split(":")[0], 9)):
        gtype = gid.split(":")[0]
        _, name, _, subtype, parent, aliases = C.GAZ_BY_ID[gid]
        pp = wit[gid]
        _admit_seed(store, {"type": gtype, "id": gid, "name": name, "edition": "2e",
                            "fields": {"subtype": subtype, "parent": parent, "aliases": aliases,
                                       "pages": pp},
                            "content": f"{name} {subtype or gtype} " + " ".join(aliases),
                            "provenance": {"value_sources": [{"src": "in-the-cage",
                                                              "loc": f"pp{pp[0]}-{pp[-1]}"}],
                                           "method": "gazetteer-attestation"},
                            "confidence": 0.95, "curated": {}, "source_sha": sha},
                    "places-gazetteer", len(pp))
        store.add_edge("attested_in", gid, CAGE_SRC, src_type=gtype, tgt_type="source", edition="2e")
        poured.add(gid)
        npl += 1
    for gid in poured:
        gtype = gid.split(":")[0]
        _, name, _, subtype, parent, _ = C.GAZ_BY_ID[gid]
        if parent and parent in poured:
            rel = {"layer": "layer_of", "realm": "located_in", "gate-town": "gate_to"}.get(gtype)
            if rel:
                store.add_edge(rel, gid, parent, src_type=gtype,
                               tgt_type=parent.split(":")[0], edition="2e")
                nedge += 1
        if gtype == "gate-town" and "plane:the-outlands" in poured:
            store.add_edge("located_in", gid, "plane:the-outlands", src_type=gtype,
                           tgt_type="plane", edition="2e")
            nedge += 1
        if gtype == "plane" and subtype == "outer" and "cosmology:the-great-ring" in poured \
                and gid != "plane:the-outlands":          # the Outlands sits INSIDE the Ring
            store.add_edge("part_of", gid, "cosmology:the-great-ring", src_type="plane",
                           tgt_type="cosmology", edition="2e")
            nedge += 1
        if gtype == "plane" and subtype in ("inner", "paraelemental") \
                and "cosmology:the-inner-planes" in poured:
            store.add_edge("part_of", gid, "cosmology:the-inner-planes", src_type="plane",
                           tgt_type="cosmology", edition="2e")
            nedge += 1
    # Sigil touches everything: the city of doors sits at the Ring's hub (book passim)
    if "cosmology:the-great-ring" in poured and store.exists("location:sigil"):
        store.add_edge("hub_of", "location:sigil", "cosmology:the-great-ring",
                       src_type="location", tgt_type="cosmology", edition="2e")
        nedge += 1
    return npl, nedge


def pour_portals(store, entries, sha):
    """The portal dimension: sweep every segmented body (owned regime for sites/minors,
    sentence-resolved src for features/chapters; the Index never sweeps). Candidates
    ≥θ with a bound src and a poured dest become portal nodes with opens_from /
    connects_to edges; the rest quarantine for review — unbound is honest, not silent."""
    pool = {}
    for r in store.conn.execute("SELECT id, name FROM entities WHERE type='location'"):
        nm = (r["name"] or "").lower().strip()
        if not nm:
            continue
        pool[nm] = r["id"]
        b = re.sub(r"^the ", "", nm)
        pool.setdefault(b, r["id"])
        pool.setdefault("the " + b, r["id"])
        short = re.sub(r"\s+inn$", "", b)
        if short != b:
            pool.setdefault(short, r["id"])
            pool.setdefault("the " + short, r["id"])
    pool["the hive"] = pool.get("hive ward", "location:sigil:hive-ward")
    pool["the cage"] = pool["sigil"] = "location:sigil"

    cands = []
    for e in entries:
        if e["name"] == "Index":
            continue
        owned = e["rtype"] in ("site", "minor")
        cands += C.sweep_portals(e["body"], page=e["page"],
                                 src_id=e.get("loc_id") if owned else None,
                                 src_name=e["name"] if owned else None,
                                 src_pool=None if owned else pool)
    groups, queued = {}, {}
    for c in cands:
        cure = C.PORTAL_CURATIONS.get((c["src"], c["dest"]))
        if cure and store.exists(cure):                # witnessed re-bind (reflow scramble)
            c = {**c, "src": cure, "src_name": (store.get(cure) or {}).get("name"),
                 "cured": True}
        adj = C.PORTAL_ADJUDICATIONS.get((c["dest"], c["page"]))
        if adj and adj["ruling"] == "promote" and store.exists(adj["src"]):
            # human override of the θ floor / a curated binding (the vision-over-θ law)
            c = {**c, "src": adj["src"], "src_name": (store.get(adj["src"]) or {}).get("name"),
                 "adjudicated": adj["why"], "src_class": adj.get("src_class")}
        elif adj and adj["ruling"] == "reject":
            c = {**c, "rejected": adj["why"]}
        ok = (not c.get("rejected")
              and (c["confidence"] >= C.THETA_PORTAL or c.get("adjudicated"))
              and c["src"] and store.exists(c["src"]) and store.exists(c["dest"]))
        bucket = groups if ok else queued
        k = (c["src"] or c["src_name"], c["dest"])
        g = bucket.setdefault(k, {"best": c, "pages": set(), "forms": set()})
        g["pages"].add(c["page"])
        if c["form"]:
            g["forms"].add(c["form"])
        if c["confidence"] > g["best"]["confidence"]:
            g["best"] = c

    nport = 0
    for (src, dest), g in sorted(groups.items(), key=lambda kv: -kv[1]["best"]["confidence"]):
        b = g["best"]
        src_short = src.split(":", 2)[-1]
        pid = f"portal:sigil:{src_short}--{dest.split(':', 1)[1]}"
        name = f"Portal: {b['src_name'] or src_short} to {b['dest_name']}"
        pp = sorted(g["pages"])
        fields = {"form": sorted(g["forms"]) or ["unspecified"],
                  "sigil_side": src, "far_side": dest, "pages": pp,
                  "trigger": b["trigger"], "witness": b["sentence"]}
        if b.get("src_class"):
            fields["src_class"] = b["src_class"]       # class-portals bind city-level, disclosed
        method = "portal-sweep" + ("+curation" if b.get("cured") else "") \
                                + ("+adjudication" if b.get("adjudicated") else "")
        curated = {}
        if b.get("cured"):
            curated["src_rebind"] = "reflow scramble; witness names the true owner"
        if b.get("adjudicated"):
            curated["adjudication"] = b["adjudicated"]
        _admit_seed(store, {"type": "portal", "id": pid, "name": name, "edition": "2e",
                            "fields": fields,
                            "content": f"{name}. {b['sentence']}",
                            "provenance": {"value_sources": [{"src": "in-the-cage",
                                                              "loc": f"p{pp[0]}"}],
                                           "method": method},
                            "confidence": b["confidence"],
                            "curated": curated, "source_sha": sha},
                    "portal-sweep", len(pp))
        store.add_edge("opens_from", pid, src, src_type="portal", tgt_type="location",
                       role="sigil-side", edition="2e")
        store.add_edge("connects_to", pid, dest, src_type="portal",
                       tgt_type=dest.split(":")[0], role="far-side", edition="2e")
        nport += 1
    nq = 0
    for (srck, dest), g in queued.items():
        b = g["best"]
        qid = f"portal:sigil:review-{S.slug(str(srck or 'unbound'))[:24]}--{dest.split(':', 1)[1]}"
        if b.get("rejected"):
            why, reason, adjor = b["rejected"], "portal-rejected", "Meme (2026-06-06 review pass)"
        elif not b["src"]:
            why, reason, adjor = "unbound sigil-side", "portal-review", "auto"
        else:
            why, reason, adjor = f"confidence {b['confidence']} < θ {C.THETA_PORTAL}", "portal-review", "auto"
        store.quarantine({"type": "portal", "id": qid, "name": f"Portal candidate → {b['dest_name']}",
                          "edition": "2e", "fields": {"far_side": dest, "page": b["page"],
                                                      "witness": b["sentence"]},
                          "content": b["sentence"],
                          "provenance": {"value_sources": [{"src": "in-the-cage",
                                                            "loc": f"p{b['page']}"}],
                                         "method": "portal-sweep"},
                          "confidence": b["confidence"], "curated": {}, "source_sha": sha},
                         {"entity_id": qid, "decision": "QUARANTINE", "adjudicator": adjor,
                          "checks": [{"layer": "L2", "name": "portal_bound", "sev": "hard",
                                      "result": "fail", "detail": why}]},
                         reason)
        nq += 1
    return nport, nq


# --- BOOKS 4-6: the Planes boxes (Law 2607 / Chaos 2603 / Conflict 2615) ---------------------
# parse/planes.py holds the curated PLANE_CARDS; every layer/gate-town claim is text-validated
# against the box's own reflow (attest_card) — a zero-witness claim is REFUSED and reported.
def pour_planes(store):
    """Enrich the plane stubs with their attested layer structure, pour layer nodes
    (layer_of edges), and backfill gate-towns the boxes attest. Realms + alignment
    strings are DEFERRED (ledger) — the realm sweep returns OCR fragments.
    Returns (planes_enriched, layers, gate_towns_new, refused: [(plane, name)])."""
    shas = {}
    for book, (sid, name, tsr, year) in P.BOX_SOURCES.items():
        srcjson = ROOT / "build" / book
        sha = None
        for sj in srcjson.glob("*/source.json"):
            sha = (json.loads(sj.read_text(encoding="utf-8")) or {}).get("sha256")
            break
        shas[book] = sha
        _admit_seed(store, {"type": "source", "id": sid, "name": name, "edition": "2e",
                            "fields": {"tsr": tsr, "year": year, "box": True},
                            "content": f"{name} TSR {tsr} Planescape boxed set planes layers",
                            "provenance": {"value_sources": [{"src": book}], "method": "seed"},
                            "confidence": 1.0, "curated": {}, "source_sha": sha}, "book", 1)

    comp_cache = {}
    nplane = nlayer = ngt = 0
    refused_all = []
    for card in P.PLANE_CARDS:
        comp = card["component"]
        if comp not in comp_cache:
            comp_cache[comp] = P.load_component(ROOT / "build", comp)
        pages = comp_cache[comp]
        rep = P.attest_card(card, pages)
        refused_all += [(card["id"], n) for n in rep["refused"]]
        sid = P.BOX_SOURCES[card["book"]][0]
        sha = shas[card["book"]]

        old = store.get(card["id"]) or {}
        fields = dict(old.get("fields") or {})
        attested = [n for n, _, _, _ in card["layers"] if n in rep["layers"]]
        if attested:
            fields["layers"] = attested
            fields["layer_count"] = len(attested)
        if card.get("layer_note"):
            fields["layer_note"] = card["layer_note"]
        # verified-or-absent (Great Audit): the gate_town FIELD ships only when the
        # box itself attests the town — an unattested claim stays off the node.
        if card.get("gate_town") and rep["gate_town_pages"]:
            fields["gate_town"] = card["gate_town"]
        fields["book"] = card["book"]
        prov = old.get("provenance") or {"value_sources": [], "method": "cross-source"}
        srcs = prov.get("value_sources") or []
        if not any(s.get("src") == card["book"] for s in srcs):
            srcs.append({"src": card["book"], "loc": comp.split("/")[-1]})
        prov["value_sources"] = srcs
        content = (old.get("content") or "") + f"\n\n[{card['book']}] " + card["gloss"]
        _admit_seed(store, {"type": "plane", "id": card["id"], "name": old.get("name") or card["id"],
                            "edition": "2e", "fields": fields, "content": content,
                            "provenance": prov,
                            "confidence": max(old.get("confidence") or 0, 0.95),
                            "curated": old.get("curated") or {},
                            "source_sha": old.get("source_sha") or sha},
                    "plane-card", len(rep["layers"]) + 1)
        store.add_edge("attested_in", card["id"], sid, src_type="plane", tgt_type="source",
                       edition="2e")
        nplane += 1

        for name, ordinal, aliases, override in card["layers"]:
            if name not in rep["layers"]:
                continue                                # refused — never poured
            lid = override or f"layer:{S.slug(name)}"
            lold = store.get(lid) or {}
            lf = dict(lold.get("fields") or {})
            lf.update({"ordinal": ordinal, "parent": card["id"], "pages": rep["layers"][name]})
            if aliases:
                lf["aliases"] = sorted(set((lf.get("aliases") or []) + aliases))
            lprov = lold.get("provenance") or {"value_sources": [], "method": "plane-card"}
            lsrcs = lprov.get("value_sources") or []
            if not any(s.get("src") == card["book"] for s in lsrcs):
                lsrcs.append({"src": card["book"],
                              "loc": f"pp{rep['layers'][name][0]}-{rep['layers'][name][-1]}"})
            lprov["value_sources"] = lsrcs
            _admit_seed(store, {"type": "layer", "id": lid, "name": name, "edition": "2e",
                                "fields": lf,
                                "content": f"{name} layer {ordinal} of {card['id'].split(':')[1]} "
                                           + " ".join(aliases),
                                "provenance": lprov,
                                "confidence": max(lold.get("confidence") or 0, 0.95),
                                "curated": lold.get("curated") or {}, "source_sha": sha},
                        "plane-card-layer", len(rep["layers"][name]))
            store.add_edge("layer_of", lid, card["id"], src_type="layer", tgt_type="plane",
                           edition="2e")
            store.add_edge("attested_in", lid, sid, src_type="layer", tgt_type="source",
                           edition="2e")
            nlayer += 1

        gt = card.get("gate_town")
        if gt and rep["gate_town_pages"]:
            gid = f"gate-town:{S.slug(gt)}"
            if gid in C.GAZ_BY_ID and not store.exists(gid):
                _, gname, _, _, gparent, galiases = C.GAZ_BY_ID[gid]
                _admit_seed(store, {"type": "gate-town", "id": gid, "name": gname, "edition": "2e",
                                    "fields": {"parent": gparent, "aliases": galiases,
                                               "pages": rep["gate_town_pages"], "book": card["book"]},
                                    "content": f"{gname} gate-town of the Outlands gate to "
                                               + card["id"].split(":")[1],
                                    "provenance": {"value_sources": [{"src": card["book"]}],
                                                   "method": "gazetteer-attestation"},
                                    "confidence": 0.95, "curated": {}, "source_sha": sha},
                            "places-gazetteer", len(rep["gate_town_pages"]))
                store.add_edge("gate_to", gid, card["id"], src_type="gate-town", tgt_type="plane",
                               edition="2e")
                if store.exists("plane:the-outlands"):
                    store.add_edge("located_in", gid, "plane:the-outlands",
                                   src_type="gate-town", tgt_type="plane", edition="2e")
                ngt += 1
            store.add_edge("attested_in", gid, sid, src_type="gate-town", tgt_type="source",
                           edition="2e")
    return nplane, nlayer, ngt, refused_all


def pour_realms(store):
    """The realms round: every REALM_CARD whose realm name AND power both attest in
    the box's own reflow pours as a realm node; its power pours as a deity stub
    (merge-safe — Aoskar's pattern); refusals are reported, never poured.
    Edges: realm_of (realm→deity), located_in (realm→layer if bound else plane),
    attested_in (both→box source). Returns (realms, deities, refused)."""
    comp_cache = {}
    nrealm = ndeity = 0
    refused = []
    seen_powers = {}
    for card in P.REALM_CARDS:
        (name, power, plane, layer, comp, book, raliases, paliases, note) = card
        if comp not in comp_cache:
            comp_cache[comp] = P.load_component(ROOT / "build", comp)
        rep = P.attest_realm(card, comp_cache[comp])
        if not rep["ok"]:
            refused.append((name, rep["why"]))
            qid = f"realm:{S.slug(name)}#refused"
            store.quarantine({"type": "realm", "id": qid, "name": name, "edition": "2e",
                              "fields": {"power": power, "plane": plane, "book": book},
                              "content": rep["why"],
                              "provenance": {"value_sources": [{"src": book}],
                                             "method": "realm-card"},
                              "confidence": 0.0, "curated": {}, "source_sha": None},
                             {"entity_id": qid, "decision": "QUARANTINE", "adjudicator": "auto",
                              "checks": [{"layer": "L1", "name": "realm_attested", "sev": "hard",
                                          "result": "fail", "detail": rep["why"]}]},
                             "realm-unattested")
            continue
        sid = P.BOX_SOURCES[book][0]
        rid = f"realm:{S.slug(name)}"
        rpp = rep["realm_pages"]
        fields = {"power": power, "plane": plane, "pages": rpp}
        if layer and store.exists(layer):
            fields["layer"] = layer
        if note:
            fields["note"] = note
        _admit_seed(store, {"type": "realm", "id": rid, "name": name, "edition": "2e",
                            "fields": fields,
                            "content": f"{name} realm of {power or 'no power'} in "
                                       f"{plane.split(':')[1]}. {note or ''}",
                            "provenance": {"value_sources": [{"src": book,
                                                              "loc": f"pp{rpp[0]}-{rpp[-1]}"}],
                                           "method": "realm-card"},
                            "confidence": 0.95, "curated": {}, "source_sha": None},
                    "realm-card", len(rpp))
        target = fields.get("layer") or plane
        store.add_edge("located_in", rid, target, src_type="realm",
                       tgt_type=target.split(":")[0], edition="2e")
        store.add_edge("attested_in", rid, sid, src_type="realm", tgt_type="source", edition="2e")
        nrealm += 1

        if power:
            did = f"deity:{S.slug(power)}"
            kind = ("pantheon-group" if power.startswith("The ") and power not in
                    ("The Queen of Air and Darkness",) else
                    "abyssal lord (quasi-power)" if plane == "plane:the-abyss"
                    and power not in ("Beshaba", "Kiaransalee") else "power")
            old = store.get(did) or {}
            f = dict(old.get("fields") or {})
            f.setdefault("kind", kind)
            f.setdefault("realms", [])
            if rid not in f["realms"]:
                f["realms"] = sorted(set(f["realms"] + [rid]))
            f["home_plane"] = f.get("home_plane") or plane
            prov = old.get("provenance") or {"value_sources": [], "method": "realm-card"}
            srcs = prov.get("value_sources") or []
            if not any(s.get("src") == book for s in srcs):
                srcs.append({"src": book, "loc": f"pp{rep['power_pages'][0]}-{rep['power_pages'][-1]}"})
            prov["value_sources"] = srcs
            _admit_seed(store, {"type": "deity", "id": did, "name": old.get("name") or power,
                                "edition": "2e", "fields": f,
                                "content": (old.get("content") or f"{power} {kind}")
                                           + f" — holds {name}",
                                "provenance": prov,
                                "confidence": max(old.get("confidence") or 0, 0.9),
                                "curated": old.get("curated") or {}, "source_sha": None},
                        "realm-card-power", len(rep["power_pages"]))
            store.add_edge("realm_of", rid, did, src_type="realm", tgt_type="deity", edition="2e")
            store.add_edge("attested_in", did, sid, src_type="deity", tgt_type="source", edition="2e")
            if did not in seen_powers:
                seen_powers[did] = True
                ndeity += 1
    return nrealm, ndeity, refused


# --- the seven-dim round: proxy/sect/settlement/saying/adventure (boxset), creature, timeline -
def _box_pages(component):
    d = ROOT / "build" / component / "reflow"
    return {int(p.stem.split("-")[1]): p.read_text(encoding="utf-8")
            for p in d.glob("page-*.txt")}


def _box_source(component):
    return {"planes-of-law": "source:planes-of-law", "planes-of-chaos": "source:planes-of-chaos",
            "planes-of-conflict": "source:planes-of-conflict",
            "in-the-cage": CAGE_SRC}.get(B.BOOK_OF.get(component), "source:planes-of-law")


def pour_boxset(store):
    """proxy · sect · settlement · saying · adventure from the distilled boxes.
    Mechanical sweeps where the books give anchors; curated cards attested in text.
    Returns a counts dict."""
    n = {"proxy": 0, "deity_stub": 0, "sect": 0, "settlement": 0,
         "saying": 0, "saying_q": 0, "adventure": 0}
    resolve = _node_resolver(store)
    cache = {}
    def pages(comp):
        if comp not in cache:
            cache[comp] = _box_pages(comp)
        return cache[comp]

    # — proxies (+ deity stubs for unseen powers) —
    for comp in B.SWEEP_COMPONENTS:
        for pg, txt in pages(comp).items():
            for p in B.sweep_proxies(txt, page=pg, component=comp):
                pid = f"proxy:{S.slug(p['name'])}"
                if store.exists(pid):
                    continue
                _admit_seed(store, {"type": "proxy", "id": pid, "name": p["name"],
                                    "edition": "2e",
                                    "fields": {"powers": p["powers"], "descriptor": p["descriptor"],
                                               "page": p["page"], "witness": p["witness"]},
                                    "content": f"{p['name']} proxy of {', '.join(p['powers'])}. "
                                               + p["witness"],
                                    "provenance": {"value_sources": [{"src": B.BOOK_OF[comp],
                                                                      "loc": f"p{p['page']}"}],
                                                   "method": "proxy-sweep"},
                                    "confidence": p["confidence"], "curated": {},
                                    "source_sha": None}, "proxy-sweep", 1)
                store.add_edge("attested_in", pid, _box_source(comp), src_type="proxy",
                               tgt_type="source", edition="2e")
                n["proxy"] += 1
                for power in p["powers"]:
                    did = f"deity:{S.slug(power)}"
                    if not store.exists(did):
                        _admit_seed(store, {"type": "deity", "id": did, "name": power,
                                            "edition": "2e",
                                            "fields": {"kind": "power", "via": "proxy-sweep"},
                                            "content": f"{power} power (named as a proxy's patron)",
                                            "provenance": {"value_sources": [{"src": B.BOOK_OF[comp],
                                                                              "loc": f"p{p['page']}"}],
                                                           "method": "proxy-sweep"},
                                            "confidence": 0.8, "curated": {}, "source_sha": None},
                                    "proxy-sweep-power", 1)
                        n["deity_stub"] += 1
                    store.add_edge("serves", pid, did, src_type="proxy", tgt_type="deity",
                                   edition="2e")

    # — sects (curated cards, attested) —
    for card in B.SECT_CARDS:
        name, comp, hint, plane, aliases, gloss = card
        pp = B.attest_sect(card, pages(comp))
        if not pp:
            continue
        sid = f"sect:{S.slug(name)}"
        _admit_seed(store, {"type": "sect", "id": sid, "name": name, "edition": "2e",
                            "fields": {"plane": plane, "aliases": aliases, "pages": pp},
                            "content": f"{name} sect. {gloss}",
                            "provenance": {"value_sources": [{"src": B.BOOK_OF[comp],
                                                              "loc": f"pp{pp[0]}-{pp[-1]}"}],
                                           "method": "sect-card"},
                            "confidence": 0.9, "curated": {}, "source_sha": None}, "sect-card",
                    len(pp))
        if plane and store.exists(plane):
            store.add_edge("located_in", sid, plane, src_type="sect", tgt_type="plane",
                           edition="2e")
        store.add_edge("attested_in", sid, _box_source(comp), src_type="sect",
                       tgt_type="source", edition="2e")
        n["sect"] += 1

    # — settlements (curated cards, attested) —
    for card in B.SETTLEMENT_CARDS:
        name, kind, parent, comp, aliases, gloss = card
        pp = B.attest_settlement(card, pages(comp))
        if not pp:
            continue
        sid = f"settlement:{S.slug(name)}"
        _admit_seed(store, {"type": "settlement", "id": sid, "name": name, "edition": "2e",
                            "fields": {"kind": kind, "parent": parent, "aliases": aliases,
                                       "pages": pp},
                            "content": f"{name} {kind}. {gloss}",
                            "provenance": {"value_sources": [{"src": B.BOOK_OF[comp],
                                                              "loc": f"pp{pp[0]}-{pp[-1]}"}],
                                           "method": "settlement-card"},
                            "confidence": 0.9, "curated": {}, "source_sha": None},
                    "settlement-card", len(pp))
        if parent and store.exists(parent):
            store.add_edge("located_in", sid, parent, src_type="settlement",
                           tgt_type=parent.split(":")[0], edition="2e")
        store.add_edge("attested_in", sid, _box_source(comp), src_type="settlement",
                       tgt_type="source", edition="2e")
        n["settlement"] += 1

    # — sayings (mechanical, θ-gated; speaker resolved when known) —
    for comp in B.SWEEP_COMPONENTS + [B.CAGE]:
        for pg, txt in pages(comp).items():
            for s in B.sweep_sayings(txt, page=pg, component=comp):
                sid = ("saying:" + B.BOOK_OF[comp] + ":"
                       + hashlib.sha256(s["text"].encode("utf-8")).hexdigest()[:10])
                if s["confidence"] < B._THETA_SAYING:
                    n["saying_q"] += 1
                    continue
                if store.exists(sid):
                    continue
                _admit_seed(store, {"type": "saying", "id": sid, "name": s["text"][:60],
                                    "edition": "2e",
                                    "fields": {"text": s["text"], "attribution": s["speaker"],
                                               "page": s["page"]},
                                    "content": f"{s['text']} — {s['speaker']}",
                                    "provenance": {"value_sources": [{"src": B.BOOK_OF[comp],
                                                                      "loc": f"p{s['page']}"}],
                                                   "method": "saying-sweep"},
                                    "confidence": s["confidence"], "curated": {},
                                    "source_sha": None}, "saying-sweep", 1)
                spk = resolve(re.sub(r"^(?:FACTOL|FACTOR|A|AN|THE)\s+", "", s["speaker"],
                                     flags=re.I))
                if spk:
                    store.add_edge("spoken_by", sid, spk, src_type="saying",
                                   tgt_type=spk.split(":")[0], edition="2e")
                store.add_edge("attested_in", sid, _box_source(comp), src_type="saying",
                               tgt_type="source", edition="2e")
                n["saying"] += 1

    # — adventures (mechanical cards) —
    adv_comps = [B.LAW + x for x in ("ii", "iii", "iv", "v", "vi")] + [B.ADV4, B.CHAOS]
    seq = {}
    for comp in adv_comps:
        for a in B.sweep_adventures(pages(comp), component=comp):
            seq[comp] = seq.get(comp, 0) + 1
            slug = S.slug(a["title"]) if a.get("title") else f"p{a['page']}-{seq[comp]}"
            aid = f"adventure:{B.BOOK_OF[comp]}:{slug}"
            if store.exists(aid):
                continue
            plane = B.COMPONENT_PLANE.get(comp)
            fields = {k: v for k, v in a.items() if k in ("levels", "n_pcs", "factions",
                                                          "synopsis", "page")}
            _admit_seed(store, {"type": "adventure", "id": aid,
                                "name": a.get("title") or f"Adventure ({comp.split('/')[-1]} p{a['page']})",
                                "edition": "2e", "fields": fields,
                                "content": (a.get("title") or "") + " " + a["synopsis"],
                                "provenance": {"value_sources": [{"src": B.BOOK_OF[comp],
                                                                  "loc": f"p{a['page']}"}],
                                               "method": "adventure-card"},
                                "confidence": 0.85, "curated": {}, "source_sha": None},
                        "adventure-card", 1)
            if plane and store.exists(plane):
                store.add_edge("set_in", aid, plane, src_type="adventure",
                               tgt_type=plane.split(":")[0], edition="2e")
            for fac in re.split(r"[,;/]| and ", a.get("factions", "") or ""):
                fid = resolve(fac.strip())
                if fid and fid.startswith("faction:"):
                    store.add_edge("involves", aid, fid, src_type="adventure",
                                   tgt_type="faction", edition="2e")
            store.add_edge("attested_in", aid, _box_source(comp), src_type="adventure",
                           tgt_type="source", edition="2e")
            n["adventure"] += 1
    return n


def pour_creatures(store):
    """The creature dimension from the MC supplements: clean parses admit; problem
    pages QUARANTINE by name with their reasons (never guessed). Returns (ok, queued)."""
    nok = nq = 0
    for comp in MC.MC_COMPONENTS:
        book = MC.MC_BOOK[comp]
        for r in MC.parse_component(_box_pages(comp), component=comp):
            if not r["name"]:
                continue                                # page fragment, not a creature
            # witnessed creature curations (Great Audit, Meme-adopted 2026-06-06):
            # keyed by RAW extracted name — renames re-slug the id, field re-reads
            # override the scramble, court recoveries flip ok and admit.
            cur = MC.CREATURE_CURATIONS.get((book, r["page"], r["name"]))
            curated = {}
            if cur:
                r = dict(r)
                if cur.get("name"):
                    r["name"] = cur["name"]
                if cur.get("fields"):
                    r["fields"] = {**r["fields"], **cur["fields"]}
                    r["ok"] = True
                curated["creature_curation"] = {
                    "value": cur.get("why", ""),
                    "adjudication": "Meme (Great Audit docket, 2026-06-06)"}
            cid = f"creature:{book}:{S.slug(r['name'])[:40]}"
            if r["ok"]:
                if store.exists(cid):
                    continue
                _admit_seed(store, {"type": "creature", "id": cid, "name": r["name"],
                                    "edition": "2e",
                                    "fields": {**r["fields"], "page": r["page"],
                                               "mc_component": comp.split("/")[-1]},
                                    "content": r["name"] + " " + " ".join(
                                        f"{k}:{v}" for k, v in r["fields"].items()),
                                    "provenance": {"value_sources": [{"src": book,
                                                                      "loc": f"p{r['page']}"}],
                                                   "method": "mc-parse"
                                                             + ("+curation" if cur else "")},
                                    "confidence": 0.85, "curated": curated, "source_sha": None},
                        "mc-parse", len(r["fields"]))
                # source derives from the MC component's PARENT BOOK (audit misbind fix:
                # _box_source lacks the MC comps and defaulted Conflict to planes-of-law)
                store.add_edge("attested_in", cid, f"source:{book}", src_type="creature",
                               tgt_type="source", edition="2e")
                nok += 1
            else:
                store.quarantine({"type": "creature", "id": cid + "#mc", "name": r["name"],
                                  "edition": "2e",
                                  "fields": {**r["fields"], "page": r["page"]},
                                  "content": "; ".join(r["problems"]),
                                  "provenance": {"value_sources": [{"src": book,
                                                                    "loc": f"p{r['page']}"}],
                                                 "method": "mc-parse"},
                                  "confidence": 0.3, "curated": {}, "source_sha": None},
                                 {"entity_id": cid + "#mc", "decision": "QUARANTINE",
                                  "adjudicator": "auto",
                                  "checks": [{"layer": "L1", "name": "mc_fields", "sev": "hard",
                                              "result": "fail",
                                              "detail": "; ".join(r["problems"])[:200]}]},
                                 "mc-parse")
                nq += 1
    return nok, nq


def pour_timeline(store):
    """The Blood War chronology (Hellbound: The Dark of the War) — phrase-witnessed
    sequence events, before/after edges, nested part_of event:the-blood-war."""
    pages = _box_pages(B.HELLBOUND)
    sha = None
    sj = (ROOT / "build" / B.HELLBOUND).parent / "ddps-hellboundbloodwar-ii/source.json"
    if sj.exists():
        sha = (json.loads(sj.read_text(encoding="utf-8")) or {}).get("sha256")
    _admit_seed(store, {"type": "source", "id": "source:hellbound", "edition": "2e",
                        "name": "Hellbound: The Blood War",
                        "fields": {"tsr": "2621", "year": 1996, "box": True},
                        "content": "Hellbound the Blood War boxed set Dark of the War chronology",
                        "provenance": {"value_sources": [{"src": "hellbound"}], "method": "seed"},
                        "confidence": 1.0, "curated": {}, "source_sha": sha}, "book", 1)
    poured = []
    for eid, name, seqn, phrase, hint, gloss in B.TIMELINE_CARDS:
        pp = B.attest_phrase(phrase, pages)
        if not pp:
            continue                                    # verified or absent
        _admit_seed(store, {"type": "event", "id": eid, "name": name, "edition": "2e",
                            "fields": {"sequence": seqn, "witness_phrase": phrase, "pages": pp,
                                       "era": "Blood War chronology"},
                            "content": f"{name}. {gloss}",
                            "provenance": {"value_sources": [{"src": "hellbound",
                                                              "loc": f"p{pp[0]}"}],
                                           "method": "timeline-card"},
                            "confidence": 0.9, "curated": {}, "source_sha": sha},
                    "timeline-card", len(pp))
        store.add_edge("attested_in", eid, "source:hellbound", src_type="event",
                       tgt_type="source", edition="2e")
        if store.exists("event:the-blood-war"):
            store.add_edge("part_of", eid, "event:the-blood-war", src_type="event",
                           tgt_type="event", edition="2e")
        poured.append(eid)
    for a, b in zip(poured, poured[1:]):
        store.add_edge("before", a, b, src_type="event", tgt_type="event", edition="2e")
    return len(poured)


# --- plothook dimension: mechanically-tagged adventure seeds (grain='seed') ------------------
THETA_HOOK = 0.55                                  # adventure seeds are softer than facts; tune w/ review

# Hook adjudications (Great Audit correction docket → Meme ADOPTED 2026-06-06). Seed ids
# RENUMBER across pours, so rulings key on the tag's STABLE coordinates:
#   (book, object_id, flavor, page-as-tagged) → ruling
# rulings: {"reject": why}                        — not a seed (DM-mechanics box, mis-paired
#                                                   subject); quarantined `hook-rejected`,
#                                                   never silently dropped
#          {"fix": {...}, "why": ...}             — rebind owner (reflow scramble), correct
#                                                   the witnessed page, replace a spliced
#                                                   premise, re-point the object, or raise
#                                                   confidence (vision-over-θ promotes)
# The cage entry re-splits (ENTRY_CURATIONS) fix most cage misbinds at the ROOT — only
# residue that re-tagging cannot self-correct is ruled here.
HOOK_ADJUDICATIONS = {
    # — In the Cage: reflow scrambles the re-split can't reach —
    ("in-the-cage", "plane:ysgard", "goal", 41): {
        "fix": {"owner": "location:sigil:the-palace-of-the-jester"},
        "why": "Jeremo's Ysgard-portal paragraph reflowed into the Prison span (the PORTAL_CURATIONS precedent, same page)"},
    ("in-the-cage", "location:sigil:fortune-s-wheel", "goal", 39): {
        "fix": {"owner": None},
        "why": "Fortune's Wheel tail wrapped under the Golden Bariaur head; premise is about the Wheel itself — ownerless, object carries it"},
    ("in-the-cage", "location:sigil:lady-s-ward", "quest", 55): {
        "fix": {"owner": None},
        "why": "'soft whispers' premise is ward lore about Lady's Ward knights, not an establishment's own hook"},
    ("in-the-cage", "faction:free-league", "goal", 79): {
        "fix": {"owner": None, "page": 80},
        "why": "Market/Guildhall ward chatter following the nic'Epona entry, not nic'Epona content"},
    ("in-the-cage", "location:sigil:the-great-bazaar", "goal", 79): {
        "fix": {"owner": None, "page": 80}, "why": "ward chatter, as above"},
    ("in-the-cage", "location:sigil:great-gymnasium", "goal", 79): {
        "fix": {"owner": None, "page": 80}, "why": "ward chatter, as above"},
    ("in-the-cage", "location:sigil:imel-s-happy-tongue", "goal", 79): {
        "fix": {"owner": None, "page": 80}, "why": "ward chatter, as above"},
    # — In the Cage: witnessed-page corrections (premise sits later in the entry) —
    ("in-the-cage", "faction:fraternity-of-order", "goal", 19): {
        "fix": {"page": 21}, "why": "Wyrm-execution premise prints on p21 (reflow page-0023); p19 is Harmonium Patrols"},
    ("in-the-cage", "location:sigil:the-great-bazaar", "goal", 84): {
        "fix": {"page": 86}, "why": "premise attested on p86 (reflow page-0088)"},
    ("in-the-cage", "location:sigil:market-ward", "goal", 101): {
        "fix": {"page": 103}, "why": "premise attested on p103 (reflow page-0105)"},
    ("in-the-cage", "faction:harmonium", "goal", 74): {
        "fix": {"page": 75}, "why": "sweeper-boys premise prints on p75; p74 ends mid-sentence at the footer"},
    ("in-the-cage", "faction:free-league", "quest", 106): {
        "fix": {"page": 107}, "why": "tout/bounty-hunter premise prints on p107"},
    ("in-the-cage", "faction:free-league", "scheme", 43): {
        "fix": {"page": 44, "premise": "He also commands a set of cambion twins who constantly maneuver to take Noshteroth's post for themselves (and whose schemes are transparent enough for even the rutterkin to see through — the chant is the brain intended for one was split between the two when they became twins)."},
        "why": "premise witnessed complete on p44; cited p43 lacks it"},
    ("in-the-cage", "faction:fraternity-of-order", "goal", 90): {
        "fix": {"premise": "Before he'll make a loan, F. Moskin Faz (Pl/male human/F3/Fraternity of Order/LG) requires borrowers to provide a letter of recommendation from any reputable Cager and a statement of purpose explaining how the applicant intends to use the money."},
        "why": "splitter broke at the 'F.' abbreviation; full sentence restored from the witnessed page (p90)"},
    # — Uncaged: the p119 Zadara-entry bleed (appendix pp125-126 text in her span) —
    ("uncaged", "npc:uncaged:rule-of-three", "scheme", 119): {
        "fix": {"page": 125}, "why": "premise is the p125 plot-appendix line, not Zadara-entry prose"},
    ("uncaged", "npc:uncaged:jemorille-the-exile", "scheme", 119): {
        "fix": {"owner": "npc:uncaged:shemeshka-the-marauder", "page": 126},
        "why": "SHEMESHKA'S WEB appendix: the schemer is Shemeshka ('her most seeming-loyal groomer guard')"},
    ("uncaged", "npc:uncaged:xideous", "scheme", 119): {
        "fix": {"owner": "npc:uncaged:jemorille-the-exile", "page": 126},
        "why": "the appendix line's subject is Jemorille (the seeming-loyal groomer guard himself)"},
    ("uncaged", "npc:uncaged:estavan", "conflict", 119): {
        "fix": {"owner": "npc:uncaged:shemeshka-the-marauder", "page": 126},
        "why": "'Her main business rivals are ESTAVAN and ZADARA' — 'her' is Shemeshka (her Web, p126)"},
    ("uncaged", "npc:uncaged:xideous", "conflict", 119): {
        "fix": {"owner": "npc:uncaged:shemeshka-the-marauder", "page": 126},
        "why": "same Web line: Shemeshka 'holds a great enmity toward… XIDEOUS'"},
    ("uncaged", "npc:uncaged:adamok-ebon", "quest", 119): {
        "fix": {"owner": "organization:will-of-the-one", "page": 125},
        "why": "'PRISINE, leader of the Will of the One, hires ADAMOK EBON' — the hirer is the sect (p125)"},
    ("uncaged", "npc:uncaged:terwolfe", "quest", 119): {
        "fix": {"owner": "organization:will-of-the-one", "page": 125},
        "why": "same p125 statement; Terwolfe is the figurehead being maneuvered"},
    ("uncaged", "organization:will-of-the-one", "quest", 119): {
        "fix": {"page": 125}, "why": "premise witnessed on p125, not in the Zadara entry"},
    ("uncaged", "npc:uncaged:black-marian", "goal", 119): {
        "fix": {"page": 125}, "why": "Koe/Estavan delivery premise is the p125 appendix"},
    ("uncaged", "npc:uncaged:tripicus", "goal", 119): {
        "fix": {"page": 125}, "why": "same p125 appendix statement"},
    # — Uncaged: other witnessed corrections —
    ("uncaged", "deity:aoskar", "goal", 112): {
        "fix": {"owner": "organization:will-of-the-one"},
        "why": "the Omott-as-gate-key goal belongs to the Will of the One (Prisine), not Terwolfe personally"},
    ("uncaged", "faction:dustmen", "goal", 23): {
        "fix": {"object": "deity:aoskar"},
        "why": "'blood of [the dead god]' premise's object is Aoskar; the Dustmen tag was a proximity false-positive (p23 witness)"},
    ("uncaged", "npc:uncaged:ly-kritch", "scheme", 87): {
        "fix": {"premise": "But while she gathers every spell and magical item she can get her hands on (often trading them for gate keys), she's got a scheme in the works that might quicken her rise to power. She trades raw evil magic to the shadow fiend Ly'kritch in exchange for gems that contain trapped intellects."},
        "why": "extracted premise was a segmentation splice that INVERTED the meaning (she HAS the scheme); restored from p87"},
    ("uncaged", "faction:dustmen", "quest", 39): {
        "fix": {"page": 41}, "why": "Contract premise witnessed on p41"},
    ("uncaged", "npc:uncaged:black-marian", "quest", 69): {
        "fix": {"page": 71}, "why": "Phineas's pass-music proposal witnessed on p71"},
    # — Manifesto —
    ("manifesto", "sigil:the-lady-of-pain", "goal", 68): {
        "fix": {"premise": "It's no dark that the Duke hopes to take over all of Sigil, though how he intends to take control of the Hall of Speakers, get the city's ruling class behind him, and avoid being trapped in one of the Lady of Pain's Mazes is any hasher's guess."},
        "why": "premise truncated mid-word by the tagger cap; completed from manifesto p67 (reflow page-0068)"},
    # — Rejects: rules-text and mis-paired subjects, recorded never dropped —
    ("in-the-cage", "item:notes", "scheme", 110): {
        "reject": "premise is the mount-IMPAIRMENTS DM box ('The DM notes the impairment in secret'), rules-text not a seed"},
    ("in-the-cage", "plane:the-prime", "scheme", 115): {
        "reject": "premise is the Slags vortex DM mechanic ('the DM should secretly roll 1d4'), rules-text not a seed"},
    ("uncaged", "plane:the-abyss", "goal", 69): {
        "reject": "'Non-Bleakniks dragged to the pub' has no Abyss goal — the Abyss mention is the neighboring Temple ad"},
    ("uncaged", "npc:uncaged:jemorille-the-exile", "goal", 119): {
        "reject": "Zadara↔Jemorille is not asserted by the premise; per BIGWIGS Zadara funds others, Shemeshka employs Jemorille"},
    ("uncaged", "npc:uncaged:alluvius-ruskin", "goal", 119): {
        "reject": "the Alluvius gem tie belongs to Ly'kritch's trade (Mind Trappers), not Zadara's goals"},
    ("uncaged", "faction:incantifier", "goal", 87): {
        "reject": "'wicker baskets for shoppers' — proximity false-positive on a shopping aside, no Incantifier goal"},
    # — Vision-over-θ promotes (quarantine court) —
    ("in-the-cage", "location:sigil", "goal", 41): {
        "fix": {"owner": "location:sigil:the-palace-of-the-jester", "confidence": 0.7,
                "premise": "Jeremo hopes to become the factol of the Ring-Givers when the sect finally moves into Sigil to begin its part in the kriegstanz, the undeclared war for control of Sigil, in earnest."},
        "why": "vision-over-θ: real seed (the kriegstanz), owner re-bound off the Prison-span scramble; witnessed p41"},
    ("in-the-cage", "location:sigil", "goal", 66): {
        "fix": {"confidence": 0.7},
        "why": "vision-over-θ: 'she' = Bordon Mok, chief of the Hall of Information; blackmail-evidence premise witnessed verbatim p66"},
    ("uncaged", "location:sigil", "goal", 87): {
        "fix": {"confidence": 0.7,
                "premise": "See, Lu's ultimate goal is to drain Sigil itself of magic, and she's looking for a magical item (or perhaps a one-of-a-kind wild magic surge) that'll let her do it."},
        "why": "vision-over-θ: real seed, premise de-interleaved from the Cania gate-key sales pitch; witnessed p87"},
    ("uncaged", "location:sigil", "goal", 119): {
        "fix": {"confidence": 0.7},
        "why": "vision-over-θ: Zadara backs Darkwood's takeover of Sigil — playable as written, witnessed p119"},
}
PIVOT_TYPES = ("subject", "deity", "sigil", "event")   # cross-book MacGuffin anchors (boosted; get pivot edge)
FLAVOR_REL = {"goal": "seeks", "scheme": "schemes_around", "conflict": "opposes", "quest": "hires"}
FVERB = {"goal": "seeks", "scheme": "schemes around", "conflict": "opposes", "quest": "hires toward"}


def _anchor_records(store):
    """All admitted entities as (id, type, name, aliases) for the hook index — subjects/factions
    bring their alias lists so oblique and nicknamed references resolve."""
    recs = []
    for t in ("npc", "faction", "location", "organization", "item", "subject", "deity", "sigil",
              "event", "source", "plane", "layer", "realm", "gate-town", "pathway", "cosmology"):
        for n in store.list(t, limit=10000):
            f = n.get("fields") or {}
            aliases = []
            for k in ("aliases", "nickname", "aka", "also_known_as", "short"):
                v = f.get(k)
                if isinstance(v, str):
                    aliases.append(v)
                elif isinstance(v, list):
                    aliases += [x for x in v if isinstance(x, str)]
            recs.append((n["id"], t, n.get("name") or "", aliases))
    return recs


def _uncaged_scopes(store):
    """One scope per ADMITTED Uncaged npc: its entry body, owned by that npc (EXACT subject)."""
    admitted = {n["id"] for n in store.list("npc", limit=10000)}
    npcdir = ROOT / "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/npc"
    for p in sorted(npcdir.glob("*.json")):
        if p.name == "graph.json":
            continue
        node = json.loads(p.read_text(encoding="utf-8"))
        oid = f"npc:uncaged:{S.slug(node['name'])}"
        if oid not in admitted or not node.get("body"):
            continue
        yield {"text": node["body"], "owner": oid, "owner_type": "npc",
               "page": (node.get("pages") or [None])[0], "book": "uncaged", "subject_known": 1.0}


def _cage_scopes(store):
    """One scope per In the Cage establishment (owner = its location node, prose regime —
    tags freely like Uncaged) plus the front-matter features (owner-less: the tout's
    narration holds schemes — Shifter's Log forgers — that belong to no single site)."""
    entries, _, _ = _cage_entries()
    resolve = _cage_loc_resolver(store)
    for e in entries:
        if e["name"] == "Index" or not e.get("body"):
            continue
        if e["rtype"] in ("site", "minor"):
            oid = e.get("loc_id") or resolve(e["name"])
            if oid and store.exists(oid):
                yield {"text": e["body"], "owner": oid, "owner_type": "location",
                       "page": e["page"], "book": "in-the-cage", "subject_known": 1.0}
        else:
            yield {"text": e["body"], "owner": None, "owner_type": None,
                   "page": e["page"], "book": "in-the-cage", "subject_known": 0.8}


def _manifesto_scopes(store, idx):
    """One scope per Manifesto reflow page that has a faction chapter, owned by the page's DOMINANT
    faction (inferred chapter subject; subject_known=0.8). Faction-less pages (intro/appendix) skip."""
    reflow = ROOT / "build/the-factol-s-manifesto/planescape-2611-the-factols-manifesto/reflow"
    fac_keys = {k: v for k, v in idx.items() if v[1] == "faction"}
    for p in sorted(reflow.glob("page-*.txt")):
        text = p.read_text(encoding="utf-8")
        low = text.lower()
        tally = {}
        for name, (eid, typ, spec) in fac_keys.items():
            c = low.count(name)
            if c:
                tally[eid] = tally.get(eid, 0) + c
        if not tally:
            continue
        owner = max(tally, key=tally.get)
        yield {"text": text, "owner": owner, "owner_type": "faction",
               "page": int(p.stem.split("-")[1]), "book": "manifesto", "subject_known": 0.8}


def pour_plothooks(store):
    """Tag adventure-seed hooks mechanically from BOTH books (parse/hooks.py grammar), pour the ones
    that clear THETA_HOOK as grain='seed' hook nodes, and wire them into the plot graph. The same
    SUBJECT node anchors seeds from both books — trace_entity(subject) IS the cross-book bridge.
    Returns (admitted, queued, n_partof, n_crossbook_pivots)."""
    idx = H.build_index(_anchor_records(store))
    scopes = (list(_uncaged_scopes(store)) + list(_manifesto_scopes(store, idx))
              + list(_cage_scopes(store)))

    raw = []
    for sc in scopes:
        raw += H.tag_text(sc["text"], idx, owner_id=sc["owner"], owner_type=sc["owner_type"],
                          page=sc["page"], book=sc["book"], subject_known=sc["subject_known"])
    # field-structured book: a faction's geography/allies/enemies are ALREADY poured as fields+edges,
    # so prose-tagging the Manifesto mostly re-surfaces structured data ("Athar schemes around its own
    # HQ"). Restrict it to SUBJECT anchors — the narrative MacGuffins the cards DON'T hold, which are
    # exactly the cross-book bridges (Doomguard→Blood War, Fated→the Lady). Uncaged (prose) tags freely.
    raw = [r for r in raw if r["book"] != "manifesto" or r["object_type"] in PIVOT_TYPES]
    for r in raw:                                          # pivot bonus: cross-book MacGuffins are hook-worthy
        if r["object_type"] in PIVOT_TYPES:
            r["confidence"] = round(min(0.98, r["confidence"] * 1.15), 2)

    # Great Audit adjudications, applied at the RAW-tag level (stable coordinates,
    # never seed ids). Rejects quarantine `hook-rejected` — recorded, never dropped.
    kept, rejected = [], {}
    for r in raw:
        adj = HOOK_ADJUDICATIONS.get((r["book"], r["object_id"], r["flavor"], r["page"]))
        if not adj:
            kept.append(r)
            continue
        if "reject" in adj:
            rejected.setdefault((r["book"], r["object_id"], r["flavor"], r["page"]), (r, adj["reject"]))
            continue
        fix = adj.get("fix") or {}
        if "owner" in fix:
            r["owner"] = fix["owner"]
            r["owner_type"] = fix["owner"].split(":")[0] if fix["owner"] else None
        if "object" in fix:
            r["object_id"] = fix["object"]
            r["object_type"] = fix["object"].split(":")[0]
        if "page" in fix:
            r["page"] = fix["page"]
        if "premise" in fix:
            r["sentence"] = fix["premise"]
        if "confidence" in fix:
            r["confidence"] = max(r["confidence"], fix["confidence"])
        r["adjudicated"] = adj["why"]
        kept.append(r)
    raw = kept
    nrej = 0
    for (book, obj, flavor, page), (r, why) in rejected.items():
        qid = f"hook:{book}:rejected-{S.slug(obj.split(':')[-1])[:20]}-{flavor}-p{page}"
        store.quarantine(
            {"type": "hook", "id": qid, "name": f"Rejected seed: {flavor} {obj}", "edition": "2e",
             "fields": {"grain": "seed", "flavor": flavor, "premise": r["sentence"],
                        "object": obj, "book": book, "pages": [page]},
             "content": r["sentence"],
             "provenance": {"value_sources": [{"src": f"{book}:p{page}"}],
                            "method": "mechanical-tag (hooks.py)"},
             "confidence": r["confidence"], "curated": {}, "source_sha": None},
            {"entity_id": qid, "decision": "QUARANTINE",
             "adjudicator": "Meme (Great Audit docket, 2026-06-06)",
             "checks": [{"layer": "L3", "name": "hook_adjudication", "sev": "hard",
                         "result": "fail", "detail": why}]},
            "hook-rejected")
        nrej += 1

    groups = {}                                            # (owner,object,flavor) -> best seed + all pages
    for r in raw:
        g = groups.setdefault((r["owner"], r["object_id"], r["flavor"]),
                              {"best": r, "pages": set()})
        g["pages"].add(r["page"])
        if r["confidence"] > g["best"]["confidence"]:
            g["best"] = r

    resolve = _node_resolver(store)                        # involved-id -> curated plot(s) for part_of
    plot_of = {}
    for h in PLOT_HOOKS:
        for who in h["involves"]:
            tid = resolve(who)
            if tid:
                plot_of.setdefault(tid, []).append(h["id"])
    for e in store.conn.execute("SELECT src_id, tgt_id FROM edges WHERE rel='concerns'"):
        plot_of.setdefault(e["tgt_id"], []).append(e["src_id"])   # any pivot (deity/sigil/subject) → its plot(s)

    admitted = queued = n_partof = 0
    seed_n = {}
    subj_books = {}                                        # subject_id -> {books} (cross-book pivot count)
    for (owner, obj, flavor), g in sorted(groups.items(), key=lambda kv: -kv[1]["best"]["confidence"]):
        best = g["best"]
        owner_node = store.get(owner) if owner and store.exists(owner) else None
        owner_name = owner_node.get("name") if owner_node else None
        obj_node = store.get(obj)
        obj_name = obj_node.get("name") if obj_node else best["object_name"]
        pages = sorted(x for x in g["pages"] if x is not None)
        seed_n[best["book"]] = seed_n.get(best["book"], 0) + 1
        hid = f"hook:{best['book']}:seed-{seed_n[best['book']]:04d}"
        name = f"{owner_name or 'A cutter'} {FVERB[flavor]} {obj_name}"
        env = {"type": "hook", "id": hid, "name": name, "edition": "2e",
               "fields": {"grain": "seed", "flavor": flavor, "premise": best["sentence"],
                          "trigger": best["trigger"], "owner": owner, "object": obj,
                          "object_type": best["object_type"], "book": best["book"], "pages": pages},
               "content": f"{name} — {best['sentence']}",
               "provenance": {"value_sources": [{"src": f"{best['book']}:p{p}"} for p in pages],
                              "method": "mechanical-tag (hooks.py)"},
               "confidence": best["confidence"],
               "curated": ({"hook_adjudication": {"value": best["adjudicated"],
                            "adjudication": "Meme (Great Audit docket, 2026-06-06)"}}
                           if best.get("adjudicated") else {}),
               "source_sha": None}
        if best["confidence"] < THETA_HOOK:
            docket = {"decision": "QUARANTINE", "adjudicator": "auto",
                      "checks": [{"layer": "L3", "name": "confidence_floor", "sev": "hard", "result": "fail",
                                  "detail": f"conf {best['confidence']} < theta {THETA_HOOK}"}],
                      "independent": {"channel": "lexical-tagger", "confirmations": len(pages)},
                      "confidence_final": best["confidence"]}
            store.quarantine(env, docket, "low-confidence-hook")
            queued += 1
            continue
        docket = {"decision": "ADMIT", "adjudicator": "auto",
                  "checks": [{"layer": "L1", "name": "name_present", "sev": "hard", "result": "pass"},
                             {"layer": "L1", "name": "anchor_resolved", "sev": "hard",
                              "result": "pass" if obj_node else "fail"},
                             {"layer": "L3", "name": "trigger+anchor+proximity", "sev": "soft",
                              "result": "pass", "detail": f"{flavor}:{best['trigger']}"}],
                  "independent": {"channel": "lexical-tagger", "confirmations": len(pages)},
                  "confidence_final": best["confidence"]}
        store.admit(env, docket)
        admitted += 1
        if owner_node:
            store.add_edge("involves", hid, owner, src_type="hook",
                           tgt_type=owner.split(":")[0], role="subject", edition="2e")
        store.add_edge("involves", hid, obj, src_type="hook",
                       tgt_type=best["object_type"], role="object", edition="2e")
        if best["object_type"] in PIVOT_TYPES and owner_node:       # the cross-book pivot graph
            store.add_edge(FLAVOR_REL[flavor], owner, obj, src_type=owner.split(":")[0],
                           tgt_type=best["object_type"], edition="2e",
                           provenance={"src": f"{best['book']}:p{best['page']}", "method": "mechanical-tag"})
            subj_books.setdefault(obj, set()).add(best["book"])
        for pid in set(plot_of.get(obj, []) + plot_of.get(owner, [])):
            if store.exists(pid):
                store.add_edge("part_of", hid, pid, src_type="hook", tgt_type="hook", edition="2e")
                n_partof += 1
    n_cross = sum(1 for b in subj_books.values() if len(b) >= 2)
    return admitted, queued + nrej, n_partof, n_cross


# --- dialog dimension: the NPC voice vector (bound speech, register-tagged) ------------------
def pour_dialog(store, nodes=None):
    """Bind each admitted Uncaged npc's spoken lines as `dialog` nodes + `spoken_by` edges
    (`parse/dialog.py`). Register comes from the speech verb → render-ready vs grace.toml. The
    voice stack (tools/, out-of-band) pulls a character's lines via the edge; Mimir owns the text.
    Returns (admitted, queued)."""
    npcs = {n["id"]: n["name"] for n in store.list("npc", limit=10000)}
    names = set(npcs.values())
    if nodes is None:
        npcdir = ROOT / "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/npc"
        nodes = [json.loads(p.read_text(encoding="utf-8"))
                 for p in sorted(npcdir.glob("*.json")) if p.name != "graph.json"]
    admitted = queued = 0
    seen_ids = set()
    for node in nodes:
        oid = f"npc:uncaged:{S.slug(node['name'])}"
        if oid not in npcs or not node.get("body"):
            continue
        text = (node.get("body") or "") + "\n" + " ".join(str(v) for v in (node.get("sections") or {}).values())
        page = (node.get("pages") or [None])[0]
        for u in D.extract(text, owner_id=oid, owner_name=node["name"], page=page,
                           book="uncaged", others=names - {node["name"]}):
            # content-addressed id (owner+text) → STABLE across re-pours, so a rendered WAV stays
            # joined to its line. The Dabus voice MCP keys audio to this id (sequential ids renumber).
            did = "dialog:uncaged:" + hashlib.sha256(f"{oid}|{u['text']}".encode("utf-8")).hexdigest()[:12]
            # Great Audit dialog adjudications (Meme ADOPTED 2026-06-06): reject = the
            # span is not this npc speaking (anonymous narrator / mimir voice / splice)
            # — quarantined, never dropped; rebind = real speech of ANOTHER npc.
            adj = D.DIALOG_ADJUDICATIONS.get(did)
            if adj and adj["action"] == "reject":
                store.quarantine(
                    {"type": "dialog", "id": did, "name": u["text"][:60], "edition": "2e",
                     "fields": {"text": u["text"], "register": u["register"], "verb": u["verb"],
                                "owner": oid, "attribution": u["attribution"], "page": u["page"]},
                     "content": u["text"],
                     "provenance": {"value_sources": [{"src": f"uncaged:p{u['page']}"}],
                                    "method": "dialog-extract (dialog.py)"},
                     "confidence": u["confidence"], "curated": {}, "source_sha": None},
                    {"entity_id": did, "decision": "QUARANTINE",
                     "adjudicator": "Meme (Great Audit docket, 2026-06-06)",
                     "checks": [{"layer": "L3", "name": "dialog_adjudication", "sev": "hard",
                                 "result": "fail", "detail": adj["why"]}]},
                    "dialog-rejected")
                queued += 1
                continue
            owner_id = oid                              # a rebind is per-UTTERANCE — never
            if adj and adj["action"] == "rebind":       # clobber the node's own oid
                owner_id = adj["owner"]
                u = {**u, "verb": adj.get("verb", u["verb"]),
                     "register": adj.get("register", u["register"])}
                did = "dialog:uncaged:" + hashlib.sha256(
                    f"{owner_id}|{u['text']}".encode("utf-8")).hexdigest()[:12]
            if did in seen_ids:
                continue
            seen_ids.add(did)
            env = {"type": "dialog", "id": did, "name": u["text"][:60], "edition": "2e",
                   "fields": {"text": u["text"], "register": u["register"], "verb": u["verb"],
                              "owner": owner_id, "attribution": u["attribution"], "page": u["page"]},
                   "content": u["text"],
                   "provenance": {"value_sources": [{"src": f"uncaged:p{u['page']}"}],
                                  "method": "dialog-extract (dialog.py)"},
                   "confidence": u["confidence"], "curated": {}, "source_sha": None}
            # vision-over-θ (the gate() pattern, Great Audit court promotes): a curation
            # on this content-addressed id applies BEFORE the θ check — an adjudicated
            # line admits below the floor, with the curated stamp disclosing it.
            cur = (_CURATIONS or {}).get(did)
            if cur:
                apply_curation(env, cur)
                env["name"] = (env["fields"].get("text") or env["name"])[:60]
            if u["confidence"] >= D.THETA_DIALOG or env.get("curated"):
                store.admit(env, {"decision": "ADMIT", "adjudicator": "auto",
                    "checks": [{"layer": "L1", "name": "speech_span", "sev": "hard", "result": "pass"},
                               {"layer": "L1", "name": "attributed", "sev": "hard", "result": "pass",
                                "detail": u["attribution"]}],
                    "independent": {"channel": "speech-verb", "confirmations": 1},
                    "confidence_final": u["confidence"]})
                store.add_edge("spoken_by", did, owner_id, src_type="dialog", tgt_type="npc", edition="2e")
                admitted += 1
            else:
                store.quarantine(env, {"decision": "QUARANTINE", "adjudicator": "auto",
                    "checks": [{"layer": "L3", "name": "cleanliness", "sev": "hard", "result": "fail",
                                "detail": f"conf {u['confidence']} < theta {D.THETA_DIALOG}"}],
                    "independent": {"channel": "speech-verb", "confirmations": 1},
                    "confidence_final": u["confidence"]}, "low-confidence-dialog")
                queued += 1
    return admitted, queued


# --- BOOK 8: The Planewalker's Handbook (2620) — race · class · spell -------------------------
def pour_pwh(store):
    """The player bible: 8 races + 7 kits as curated cards (text-attested, the
    planes.py law), 4 base-class stubs, ~57 spells parsed from Magic on the
    Planes (identity certain; stats verified-or-absent, hand-curations carry
    page witnesses). psionic does NOT pour — the book has none (ledger note).
    Returns a counts dict."""
    n = {"race": 0, "kit": 0, "base_class": 0, "spell": 0, "spell_q": 0,
         "refused": [], "edges": 0}
    pages = PW.load_component(ROOT / "build")
    sid, sname, tsr, year = PW.SOURCE

    sha = None
    sj = ROOT / "build" / PW.COMPONENT / "source.json"
    if sj.exists():
        sha = (json.loads(sj.read_text(encoding="utf-8")) or {}).get("sha256")

    _admit_seed(store, {"type": "source", "id": sid, "name": sname, "edition": "2e",
                        "fields": {"tsr": tsr, "year": year, "kind": "accessory",
                                   "line": "Planescape", "designer": "Monte Cook"},
                        "content": f"{sname} TSR {tsr} Planescape player's guide planar races "
                                   "kits proficiencies magic spells cant glossary belief",
                        "provenance": {"value_sources": [{"src": PW.BOOK}], "method": "seed"},
                        "confidence": 1.0, "curated": {}, "source_sha": sha}, "book", 1)

    # — base classes (the four 2e class groups the kits + spells hang off) —
    kit_pages_blob = {pg: pages[pg] for pg in PW.KIT_CHAPTER_PAGES if pg in pages}
    for cid, cname, gloss in PW.BASE_CLASSES:
        wit = PW.attest_name(cname, [cname + "s"], kit_pages_blob)
        _admit_seed(store, {"type": "class", "id": cid, "name": cname, "edition": "2e",
                            "fields": {"is_kit": False, "pages": wit},
                            "content": f"{cname} 2e class group. {gloss}",
                            "provenance": {"value_sources": [{"src": PW.BOOK,
                                                              "loc": f"pp{wit[0]}-{wit[-1]}" if wit else "kit-chapter"}],
                                           "method": "card-attestation"},
                            "confidence": 0.95, "curated": {}, "source_sha": sha}, "pwh-card", max(len(wit), 1))
        store.add_edge("attested_in", cid, sid, src_type="class", tgt_type="source", edition="2e")
        n["base_class"] += 1

    # — races (cards, attested; variants are structured sub-records) —
    for card in PW.RACE_CARDS:
        rep = PW.attest_race_card(card, pages)
        if rep["refused"]:
            n["refused"].append((card["id"], "name-unattested"))
            continue
        fields = {k: card[k] for k in ("ability_mods", "traits", "origin_plane",
                                       "subtype", "classes", "alignment") if card.get(k)}
        fields["playable"] = True
        fields["pages"] = rep["pages"]
        if card["variants"]:
            fields["variants"] = [
                {**{k: v[k] for k in ("name", "epithet", "ability_mods", "traits",
                                      "classes", "alignment") if v.get(k)},
                 "pages": rep["variants"].get(v["name"], [])}
                for v in card["variants"]]
            unattested = [v["name"] for v in card["variants"]
                          if not rep["variants"].get(v["name"])]
            if unattested:                       # a variant the text doesn't witness stays off
                fields["variants"] = [v for v in fields["variants"]
                                      if v["name"] not in unattested]
                n["refused"] += [(card["id"], f"variant-unattested: {u}") for u in unattested]
        content = (f"{card['name']} planar PC race. {card['gloss']}. "
                   f"{card['ability_mods']}. " + " ".join(card["traits"])
                   + " " + " ".join(v["name"] for v in card.get("variants", [])))
        _admit_seed(store, {"type": "race", "id": card["id"], "name": card["name"],
                            "edition": "2e", "fields": fields, "content": content,
                            "provenance": {"value_sources": [{"src": PW.BOOK,
                                                              "loc": f"pp{rep['pages'][0]}-{rep['pages'][-1]}"}],
                                           "method": "card-attestation"},
                            "confidence": 0.95, "curated": {}, "source_sha": sha},
                    "pwh-race-card", len(rep["pages"]))
        store.add_edge("attested_in", card["id"], sid, src_type="race", tgt_type="source", edition="2e")
        if card.get("native_to") and store.exists(card["native_to"]):
            store.add_edge("native_to", card["id"], card["native_to"],
                           src_type="race", tgt_type="plane", edition="2e")
            n["edges"] += 1
        n["race"] += 1

    # — kits (class dim, is_kit=True, parent_class field; location kits get plane edges) —
    for card in PW.KIT_CARDS:
        rep = PW.attest_kit_card(card, pages)
        if rep["refused"]:
            n["refused"].append((card["id"], "name-unattested"))
            continue
        fields = {"is_kit": True, "parent_class": card["parent_class"],
                  "kind": card["kind"], "classes_allowed": card["classes_allowed"],
                  "requirements": card["requirements"], "abilities": card["benefits"],
                  "hindrances": card["hindrances"], "pages": rep["pages"]}
        content = (f"{card['name']} planewalking kit ({card['kind']}). {card['gloss']}. "
                   + " ".join(card["benefits"]) + " " + " ".join(card["hindrances"]))
        _admit_seed(store, {"type": "class", "id": card["id"], "name": card["name"],
                            "edition": "2e", "fields": fields, "content": content,
                            "provenance": {"value_sources": [{"src": PW.BOOK,
                                                              "loc": f"p{rep['pages'][0]}"}],
                                           "method": "card-attestation"},
                            "confidence": 0.95, "curated": {}, "source_sha": sha},
                    "pwh-kit-card", len(rep["pages"]))
        store.add_edge("attested_in", card["id"], sid, src_type="class", tgt_type="source", edition="2e")
        store.add_edge("kit_of", card["id"], card["parent_class"],
                       src_type="class", tgt_type="class", edition="2e")
        n["edges"] += 1
        if card.get("located_in") and store.exists(card["located_in"]):
            store.add_edge("located_in", card["id"], card["located_in"],
                           src_type="class", tgt_type="plane", edition="2e")
            n["edges"] += 1
        n["kit"] += 1

    # — faction third witness (the player-bible faction chapter, printed 54-67):
    #   an attested_in edge per faction the chapter names — provenance, not new fields
    fac_pages = {pg: pages[pg] for pg in range(56, 70) if pg in pages}
    for f in store.list("faction", limit=100):
        wit = PW.attest_name(f["name"], (f.get("fields") or {}).get("aliases") or [], fac_pages)
        if wit:
            store.add_edge("attested_in", f["id"], sid, src_type="faction", tgt_type="source",
                           edition="2e", provenance={"loc": f"pp{wit[0]}-{wit[-1]}"})
            n["faction_witness"] = n.get("faction_witness", 0) + 1

    # — spells (parsed; identity certain, stats verified-or-absent) —
    w, wrej = PW.extract_spells(pages, PW.WIZARD_PAGES, "wizard")
    p, prej = PW.extract_spells(pages, PW.PRIEST_PAGES, "priest")
    spells = PW.finalize_spells(PW.merge_spells(w, p))
    for s in spells:
        slug = PW.slugify(s["name"])
        eid = f"spell:{slug}"
        fields = {"level": s["level"], "school": s["school"], "classes": s["classes"],
                  "reversible": s["reversible"], "pages": sorted(set(s["pages"])),
                  "printed_pages": sorted({pg - PW.PAGE_OFFSET for pg in s["pages"]})}
        if s["elemental"]:
            fields["elemental"] = s["elemental"]
        fields.update({k: v for k, v in s["stats"].items()})
        if s["level_by_class"]:
            fields["level_by_class"] = s["level_by_class"]
        if s["stats_by_class"]:
            fields["stats_by_class"] = s["stats_by_class"]
        if s.get("stats_cured"):
            fields["stats_cured"] = s["stats_cured"]    # the witness rides the node
        if s["origin"]:
            fields["first_printed_in"] = s["origin"]
        conf = 0.9 if s.get("stats_cured") else 0.95
        content = (f"{s['name']} 2e spell level {s['level']} {s['school']} "
                   f"({'/'.join(s['classes'])}). "
                   + " ".join(f"{k.replace('_', ' ')}: {v}" for k, v in s["stats"].items())
                   + (" elemental " + " ".join(s["elemental"]) if s["elemental"] else ""))
        _admit_seed(store, {"type": "spell", "id": eid, "name": s["name"],
                            "edition": "2e", "fields": fields, "content": content,
                            "provenance": {"value_sources": [
                                {"src": PW.BOOK, "loc": "pp" + ",".join(str(x) for x in sorted(set(s["pages"])))}],
                                           "method": "spell-parse" + ("+stat-curation" if s.get("stats_cured") else "")},
                            "confidence": conf, "curated": {}, "source_sha": sha},
                    "pwh-spell-parse", len(set(s["pages"])))
        store.add_edge("attested_in", eid, sid, src_type="spell", tgt_type="source", edition="2e")
        for k in s["classes"]:
            store.add_edge("castable_by", eid, f"class:{k}",
                           src_type="spell", tgt_type="class", edition="2e")
            n["edges"] += 1
        if s["origin"] and store.exists(s["origin"]):
            store.add_edge("attested_in", eid, s["origin"], role="first-printed-in",
                           src_type="spell", tgt_type="source", edition="2e")
            n["edges"] += 1
        n["spell"] += 1

    # — head-lost + parse rejects → quarantine by page, never guessed —
    for h in PW.HEAD_LOST:
        env = {"type": "spell", "id": f"spell:pwh-head-lost-p{h['printed_page']}",
               "name": f"[head lost — PWH printed p{h['printed_page']}]", "edition": "2e",
               "fields": {**h["stats"], "level": h["level"], "school": h["school"],
                          "sphere": h["sphere"], "classes": [h["klass"]],
                          "pages": [h["page"]], "note": h["note"]},
               "content": h["note"],
               "provenance": {"value_sources": [{"src": PW.BOOK, "loc": f"p{h['page']}"}],
                              "method": "spell-parse"},
               "confidence": 0.5, "curated": {}, "source_sha": sha}
        store.quarantine(env, {"decision": "QUARANTINE", "adjudicator": "auto",
            "checks": [{"layer": "L1", "name": "name_present", "sev": "hard", "result": "fail",
                        "detail": "name line destroyed by OCR — promotion needs a print reading"}],
            "independent": {"channel": "spell-parse", "confirmations": 1},
            "confidence_final": 0.5}, "pwh-spell-head-lost")
        n["spell_q"] += 1
    for r in wrej + prej:
        if not r["name_raw"]:
            continue                                  # the empty pg132 echo of HEAD_LOST
        env = {"type": "spell", "id": f"spell:pwh-reject-p{r['page']}-{PW.slugify(r['name_raw'])[:24]}",
               "name": r["name_raw"], "edition": "2e",
               "fields": {"level": r["level"], "school": r["school"], "pages": [r["page"]]},
               "content": f"unparsed spell head {r['name_raw']!r} p{r['page']}",
               "provenance": {"value_sources": [{"src": PW.BOOK, "loc": f"p{r['page']}"}],
                              "method": "spell-parse"},
               "confidence": 0.5, "curated": {}, "source_sha": sha}
        store.quarantine(env, {"decision": "QUARANTINE", "adjudicator": "auto",
            "checks": [{"layer": "L1", "name": "name_plausible", "sev": "hard", "result": "fail",
                        "detail": f"OCR name {r['name_raw']!r} implausible — needs a fix-table entry"}],
            "independent": {"channel": "spell-parse", "confirmations": 1},
            "confidence_final": 0.5}, "pwh-spell-parse")
        n["spell_q"] += 1
    return n


def main():
    npcdir = ROOT / "build/uncaged-faces-of-sigil/ps-uncaged-facesofsigil/npc"
    nodes = [json.loads(p.read_text(encoding="utf-8"))
             for p in sorted(npcdir.glob("*.json")) if p.name != "graph.json"]
    # held-out witness corpus: the CC wikis the extractor never touched
    wikiblob = ""
    for x in (ROOT / "content/wikis/fandom-planescape").glob("export_*.xml"):
        wikiblob += x.read_text(encoding="utf-8", errors="ignore").lower()

    (ROOT / "build/mimir").mkdir(parents=True, exist_ok=True)
    db = ROOT / "build/mimir/handbook.db"
    if db.exists(): db.unlink()
    store = S.HandbookStore(db)

    curations = load_curations()
    global _CURATIONS
    _CURATIONS = curations                              # seeded pours consult the same registry
    seen, admitted, quarantined = set(), [], []
    for v2 in nodes:
        eid = f"npc:uncaged:{S.slug(v2['name'])}"
        if eid in seen:                                       # never overwrite silently — surface it
            env = npc_envelope(v2)
            docket = {"entity_id": eid, "decision": "QUARANTINE", "adjudicator": "auto",
                      "checks": [{"layer": "L2", "name": "unique_id", "sev": "hard", "result": "fail",
                                  "detail": f"id {eid} already admitted — merge-or-drop adjudication needed"}]}
            store.quarantine(env, docket, "id-collision")
            quarantined.append((env, "id-collision", docket))
            continue
        decision, reason, env, docket = gate(v2, store, wikiblob, curations)
        if decision == "ADMIT":
            seen.add(env["id"])
        (admitted if decision == "ADMIT" else quarantined).append((env, reason, docket))

    # pour on — the dimensions that close the NPC graph
    nfac = pour_factions(store, nodes)
    pour_source(store, nodes)
    nloc = pour_locations(store, nodes)
    norg = pour_organizations(store, nodes)
    nhook, nedge, unresolved = pour_plots(store)
    nxref = pour_xref_sources(store)
    nitem = pour_items(store, nodes)
    nfic = pour_fiction(store)
    mfac, mfactol, mhq = pour_manifesto(store)         # SECOND BOOK: The Factol's Manifesto
    ndeity = pour_deities(store)                        # powers (Aoskar absorbs subject:aoskar)
    nlady, nward, nseat = pour_sigil(store)            # the Lady absorbs subject:lady; enrich location:sigil
    nevent = pour_events(store)                         # events (the Blood War absorbs subject:the-blood-war)
    nsub = pour_subjects(store)                         # staging lane (now empty — all three pivots folded)
    cage = pour_cage(store)                             # THIRD BOOK: In the Cage (geography + portals + Places)
    npl, nly, ngt, refused = pour_planes(store)         # BOOKS 4-6: the Planes boxes (cards, text-validated)
    nrealm, ndeity, rrefused = pour_realms(store)       # realms round: realm cards + deity stubs
    bx = pour_boxset(store)                             # seven-dim round: proxy/sect/settlement/saying/adventure
    ncre, ncre_q = pour_creatures(store)                # creature dim (MC supplements)
    ntl = pour_timeline(store)                          # Blood War chronology (Hellbound)
    hadm, hqd, hpart, hcross = pour_plothooks(store)   # mechanically-tagged adventure seeds (all three books)
    dadm, dqd = pour_dialog(store)                      # the NPC voice vector (bound speech, register-tagged)
    pw = pour_pwh(store)                                # BOOK 8: The Planewalker's Handbook (race/class/spell)
    cov = store.coverage()
    adj = [e for e, r, d in admitted if e.get("curated")]
    print(f"=== MIMIR GATE — Uncaged ({len(nodes)} npc) ===")
    print(f"ADMITTED   : {len(admitted)}/{len(nodes)}"
          + (f"   ({len(adj)} via vision adjudication: {', '.join(e['name'] for e in adj)})" if adj else ""))
    print(f"QUARANTINED: {len(quarantined)}  {dict(__import__('collections').Counter(r for _,r,_ in quarantined))}")
    print(f"poured  : {nfac} factions · {1+nxref} sources · {nloc} locations · {norg} organizations · "
          f"{nhook} plot-hooks ({nedge} edges) · {nitem} item-wields · {nfic} fiction   ·   store now: {cov['admitted']}")
    print(f"manifesto: {mfac} faction cards merged · {mfactol} factols (npc) · {mhq} new HQ locations")
    print(f"powers   : {ndeity} deity (Aoskar ⊃ subject:aoskar) · sigil hub: the Lady + {nward} wards + "
          f"{nseat} faction-seats (location:sigil enriched)")
    print(f"events   : {nevent} (Blood War ⊃ subject:the-blood-war · Great Upheaval ↔ Lady+Aoskar participated_in)")
    print(f"in-the-cage: {cage['merged']} establishments merged · {cage['new']} new · "
          f"{cage['absent']} entries head-lost (review) · {cage['places']} Places nodes "
          f"({cage['place_edges']} edges) · {cage['portals']} portals · {cage['portals_queued']} portal-review")
    print(f"planes-boxes: {npl} planes enriched · {nly} layers · {ngt} gate-towns backfilled"
          + (f" · REFUSED: {refused}" if refused else " · 0 refused"))
    print(f"realms   : {nrealm} realms · {ndeity} powers (deity stubs)"
          + (f" · REFUSED: {rrefused}" if rrefused else " · 0 refused"))
    print(f"seven-dim: {bx['proxy']} proxies (+{bx['deity_stub']} powers) · {bx['sect']} sects · "
          f"{bx['settlement']} settlements · {bx['saying']} sayings ({bx['saying_q']} <θ) · "
          f"{bx['adventure']} adventures · {ncre} creatures ({ncre_q} mc-queued) · {ntl} timeline events")
    print(f"plothooks: {nsub} staging pivots · {hadm} seed-hooks tagged · {hqd} queued (<θ {THETA_HOOK}) · "
          f"{hpart} part_of links · {hcross} cross-book pivots")
    print(f"dialog   : {dadm} utterances bound (spoken_by, register-tagged) · {dqd} queued (<θ {D.THETA_DIALOG})")
    print(f"planewalker's-hbk: {pw['race']} races · {pw['kit']} kits + {pw['base_class']} base classes · "
          f"{pw['spell']} spells · {pw['spell_q']} spell-quarantine · {pw['edges']} typed edges · "
          f"{pw.get('faction_witness', 0)} faction 3rd-witnesses"
          + (f" · REFUSED: {pw['refused']}" if pw['refused'] else " · 0 refused")
          + f"   ·   total: {cov['admitted_total']} entities, {cov['edges']} edges")
    if unresolved:
        print(f"          plot edges unresolved (not poured): {sorted(set(unresolved))}")
    dang = store.dangling_edges()
    by_rel = __import__('collections').Counter(e['rel'] for e in dang)
    print(f"edges   : {cov['edges']} total · {len(dang)} dangling {dict(by_rel)}")
    print(f"          (danglers are see_also refs to cutters outside this book — e.g. "
          f"{sorted({e['tgt_id'].split(':')[-1] for e in dang if e['rel']=='references'})[:6]})")
    print("\n--- quarantine review queue (what a human/workflow adjudicates) ---")
    for env, reason, docket in quarantined:
        bad = [f"{c['name']}={c['detail']}" for c in docket["checks"]
               if c["sev"] == "hard" and c["result"] == "fail"]
        print(f"  [{reason:14}] {env['name'][:24]:24} conf={env['confidence']}  {('· '+'; '.join(bad)) if bad else ''}")
    print("\n--- sample ADMIT docket (A'kin) ---")
    ak = next((d for e, r, d in admitted if "kin" in e["id"]), None)
    if ak:
        print(json.dumps({"decision": ak["decision"], "confidence_final": ak["confidence_final"],
                          "independent": ak["independent"],
                          "checks": [f"{c['layer']}:{c['name']}={c['result']}" for c in ak["checks"]]},
                         indent=1, ensure_ascii=False))
    store.close()


if __name__ == "__main__":
    main()
