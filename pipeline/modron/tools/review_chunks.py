#!/usr/bin/env python
"""review_chunks.py — work-list dumper for the Modron audit (Phase 0).

Reads the data files, integrity-report.json (the mechanical pass's pending-ref
feed / used_at map / shingle hits), the fleet compiles (fleet/*.json, written
by integrity.py), handbook.db (readonly, for G-chunk entity fields), and the
law/text caches. Writes build/modron/review/chunks/<id>.json — every witness
path ABSOLUTE and existence-asserted, every page ref RESOLVED (review agents
never do offset math), pre-greps embedded as candidate witnesses.

Census law: 23 check kinds + 29 modifiers + 34 rollables + 87 fleet entities
each land in EXACTLY ONE chunk (asserted; the dumper dies loudly otherwise).

Run: py -3.13 pipeline/modron/tools/review_chunks.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
MODRON_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
sys.path.insert(0, str(MODRON_DIR))
sys.path.insert(0, str(HERE.parent))

from integrity import (FGG_DIR, KNOWN_USED_AT_DANGLERS, LAW_DIR,           # noqa: E402
                       NOTE_PRODUCT_HINTS, REFLOW_MAP, _PAGE_RE, _reflow_pages)
from modron import semantics, store as mstore                              # noqa: E402

REVIEW = ROOT / "build/modron/review"
CHUNKS = REVIEW / "chunks"
FLEET_DIR = REVIEW / "fleet"
REPORT = REVIEW / "integrity-report.json"
KNOWN_INTENTIONAL = REVIEW / "known-intentional.json"
DATA_DIR = MODRON_DIR / "data"
HANDBOOK = ROOT / "build/mimir/handbook.db"
SRD51_DIR = ROOT / "build/mechanus/srd51-text"
SRD52_DIR = ROOT / "build/mechanus/srd52-text"

_DICE_TOKEN_RE = re.compile(r"\b\d{1,3}d\d{1,4}(?:[+-]\d{1,3})?\b")
_PCT_TOKEN_RE = re.compile(r"\b\d{1,3}%")

# ---------------------------------------------------------------------------
# pre-grep helpers (candidate witnesses for quotable caches)
# ---------------------------------------------------------------------------

_CACHE: dict[str, dict[str, str]] = {}


def _cache(dirpath: Path) -> dict[str, str]:
    key = dirpath.as_posix()
    if key not in _CACHE:
        _CACHE[key] = {p.name: p.read_text(encoding="utf-8", errors="replace")
                       for p in sorted(dirpath.glob("p*.txt"))}
    return _CACHE[key]


def pregrep(dirpath: Path, keywords: list[str], top: int = 3) -> list[dict]:
    scored = []
    for fname, text in _cache(dirpath).items():
        low = text.lower()
        hits = sum(low.count(k.lower()) for k in keywords)
        if hits:
            line = next((ln.strip() for ln in text.splitlines()
                         if any(k.lower() in ln.lower() for k in keywords)), "")
            scored.append((hits, fname, line[:160]))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [{"file": (dirpath / f).as_posix(), "hits": h, "line": ln}
            for h, f, ln in scored[:top]]


FGG_KIND_KEYWORDS = {
    "attack": ["thac0"], "save": ["saving throw"], "ability": ["ability check"],
    "proficiency": ["proficiency check", "nonweapon proficiency"],
    "thief_skill": ["thieving"], "percent": ["percentile"], "morale": ["morale"],
    "reaction": ["reaction"], "surprise": ["surprise"], "initiative": ["initiative"],
}
SRD_KIND_KEYWORDS = {
    "attack": ["attack roll"], "save": ["saving throw"], "check": ["ability check"],
    "initiative": ["initiative"], "death_save": ["death saving throw"],
    "percent": ["percent"], "recharge": ["recharge"],
}
SRD_MOD_KEYWORDS = {
    "bless": ["bless"], "bane": ["bane"], "guidance": ["guidance"],
    "bardic-inspiration": ["bardic inspiration"], "advantage": ["advantage"],
    "disadvantage": ["disadvantage"], "elven-accuracy": ["elven accuracy"],
    "halfling-luck": ["lucky"], "great-weapon-fighting": ["great weapon fighting"],
    "reliable-talent": ["reliable talent"], "brutal-critical": ["brutal critical"],
    "sneak-attack": ["sneak attack"], "resistance": ["resistance to"],
    "vulnerability": ["vulnerability to"], "archery": ["archery"],
    "dueling": ["dueling"], "rage-damage": ["rage"],
}
FGG_MOD_KEYWORDS = {
    "bless-2e": ["bless"], "curse-2e": ["curse", "bless"],
    "weapon-specialization": ["specialization"],
    "rear-attack": ["rear of", "from the rear", "rear attack"],
    "higher-ground": ["higher ground"],
    "magic-weapon-plus": ["magical weapon", "magic weapon"],
}


# ---------------------------------------------------------------------------
# law-row extraction (inline candidates for the court + lane A/B reviewers)
# ---------------------------------------------------------------------------

def _law_rows() -> dict[str, dict]:
    """law_id -> the containing row dict (trimmed) + source file."""
    rows: dict[str, dict] = {}
    for law_file in sorted(LAW_DIR.glob("*.json")):
        d = json.loads(law_file.read_text(encoding="utf-8"))

        def walk(o):
            if isinstance(o, dict):
                lid = o.get("law_id")
                if isinstance(lid, str):
                    trimmed = {k: v for k, v in o.items()
                               if k in ("law_id", "rule", "general", "plane",
                                        "witness", "schools", "key", "name", "text")}
                    trimmed["_law_file"] = (law_file).as_posix()
                    rows[lid] = trimmed
                for vv in o.values():
                    walk(vv)
            elif isinstance(o, list):
                for vv in o:
                    walk(vv)
        walk(d)
    return rows


# ---------------------------------------------------------------------------
# chunk assembly
# ---------------------------------------------------------------------------

def main() -> int:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    pending = report["pending_refs"]
    used_at = report["info"]["used_at"]
    shingle_hits = {x["ref"]: x["detail"] for x in report["violations"]
                    if x["check"] == "paraphrase_shingle"}
    law_rows = _law_rows()
    CHUNKS.mkdir(parents=True, exist_ok=True)

    chunks: dict[str, dict] = {}
    census = {"kinds": [], "modifiers": [], "rollables": [], "entities": []}

    def emit(cid: str, lane: str, mandate: str, items: list, **extra):
        chunks[cid] = {"chunk": cid, "lane": lane, "mandate": mandate,
                       "known_intentional": KNOWN_INTENTIONAL.as_posix(),
                       "items": items, **extra}

    def law_candidates_for(where_prefix: str) -> list[dict]:
        out = []
        for p in pending:
            if p["where"].startswith(where_prefix):
                rec = dict(p)
                rec["law_rows"] = [law_rows[c] for c in p.get("candidates", [])
                                   if c in law_rows][:2]
                out.append(rec)
        return out

    # ---- A: convention packs -------------------------------------------------
    packs = {v: json.loads((DATA_DIR / "conventions" / f"{v}.json").read_text(encoding="utf-8"))
             for v in ("2e", "2e-planescape", "5e-2014", "5e-2024")}

    items = []
    for kind, spec in packs["2e"]["checks"].items():
        census["kinds"].append(f"2e:{kind}")
        items.append({"kind": kind, "view": "2e", "spec": spec, "quotable": True,
                      "candidate_witnesses": pregrep(FGG_DIR, FGG_KIND_KEYWORDS[kind]),
                      "cite_today": "NONE — pack sources say 'FG&G pending pour'; "
                                    "PROPOSE the exact fgg-text page cite per kind"})
    emit("A-1-2e", "A",
         "For EACH check kind: open candidate_witnesses (FG&G = QUOTABLE 2e RAW; quote "
         "evidence). Verify the PROCEDURE matches the page: dice rolled, roll-over vs "
         "roll-under, success_op direction, band edges/labels, nat-crit/fumble rules, "
         "every mechanical claim in notes. PROPOSE the exact FG&G cite to attach per "
         "kind (file + the printed page number read from the page text). The reaction "
         "bands are marked provisional — confirm or contradict against FG&G. Findings "
         "only for defects; clean kinds return no findings.", items, view="2e")

    items = []
    for kind, spec in packs["2e-planescape"]["checks"].items():
        census["kinds"].append(f"2e-planescape:{kind}")
        wfiles = []
        for note in semantics.list_wrap(spec.get("notes")):
            for hint, product in NOTE_PRODUCT_HINTS:
                if hint in note:
                    wfiles += [p.as_posix() for p in _reflow_pages(product, note)]
                    break
        items.append({"kind": kind, "view": "2e-planescape", "spec": spec,
                      "quotable": False,
                      "witness_files": sorted(set(wfiles)),
                      "law_refs": law_candidates_for(
                          f"data/conventions/2e-planescape.json#checks.{kind}")})
    emit("A-2-2e-planescape", "A",
         "For EACH check kind: open witness_files (official scans — CITE-ONLY: never "
         "quote; paraphrase + a <=6-word locator). Verify the procedure against the "
         "page: dice, roll-under vs roll-over, success_op, band edges, every notes[] "
         "mechanical claim (stage tracks, failure consequences, cadence, riders). Do "
         "NOT adjudicate law_refs (the resolution court's lane) — but DO verify the "
         "pack's mechanics agree with the law_rows text included. Findings only for "
         "defects.", items, view="2e-planescape")

    items = []
    for kind, spec in packs["5e-2014"]["checks"].items():
        census["kinds"].append(f"5e-2014:{kind}")
        items.append({"kind": kind, "view": "5e-2014", "spec": spec, "quotable": True,
                      "candidate_witnesses": pregrep(SRD51_DIR, SRD_KIND_KEYWORDS[kind])})
    emit("A-3-5e-2014", "A",
         "For EACH check kind: open candidate_witnesses (SRD 5.1 = quotable, "
         "CC-BY-4.0). Verify the procedure: d20 state machine claims "
         "(advantage/disadvantage/elven-accuracy upgrade shapes), crit law "
         "(double_dice), death_save naturals, recharge threshold semantics, "
         "initiative order. PROPOSE an SRD page cite per kind (the pack carries "
         "product but no pages). Findings only for defects.", items, view="5e-2014")

    emit("A-4-5e-2024", "A",
         "Single item: the 5e-2024 pack INHERITS everything from 5e-2014 (extends "
         "chain; defines no checks of its own). Verify: (a) the pack file's claims "
         "in notes[] — especially 'SRD 5.2.1 p.202 carries XP budget math' (open the "
         "embedded srd52 page and confirm); (b) that inheriting 2014 dice conventions "
         "for the 2024 view is sound per SRD 5.2.1 (spot the advantage/crit/death-save "
         "text in srd52-text candidates); (c) sources/labels honest. Findings only "
         "for defects.",
         [{"kind": "_pack", "view": "5e-2024", "spec": packs["5e-2024"],
           "quotable": True,
           "srd52_p202": (SRD52_DIR / "p0202.txt").as_posix(),
           "candidate_witnesses": pregrep(SRD52_DIR, ["advantage", "death saving throw",
                                                      "critical hit"], top=4)}],
         view="5e-2024")

    # ---- B: modifiers ---------------------------------------------------------
    mods = {f: json.loads((DATA_DIR / "modifiers" / f).read_text(encoding="utf-8"))
            for f in ("core-5e.json", "core-2e.json", "planescape-2e.json")}
    overlay = json.loads((DATA_DIR / "overrides" / "modifiers.local.json").read_text(encoding="utf-8"))

    items = []
    for row in mods["core-5e.json"]:
        census["modifiers"].append(row["id"])
        items.append({"modifier": row, "quotable": True,
                      "candidate_witnesses": pregrep(SRD51_DIR,
                                                     SRD_MOD_KEYWORDS.get(row["id"], [row["id"]]))})
    emit("B-1-core-5e", "B",
         "For EACH modifier: verify the effects encode the cited SRD rule — op, expr, "
         "sign, applies_to, stacking — against candidate_witnesses (SRD 5.1 quotable; "
         "quote the operative sentence). PROPOSE the SRD page to attach to the ref. "
         "elven-accuracy is intentionally non-SRD-flagged (known-intentional) — "
         "confirm its 0-hit grep PROVES the flag honest, don't flag it. Check notes' "
         "claims (sneak-attack crit composition guidance, bardic die params). "
         "Findings only for defects.", items)

    items = []
    for row in mods["core-2e.json"]:
        census["modifiers"].append(row["id"])
        fgg_pend = next((p for p in pending
                         if p["where"].endswith(f"#{row['id']}")), None)
        items.append({"modifier": row, "quotable": True,
                      "candidate_witnesses": (fgg_pend or {}).get(
                          "candidates", pregrep(FGG_DIR, FGG_MOD_KEYWORDS.get(row["id"], [])))})
    census["modifiers"].append(overlay[0]["id"])
    items.append({"modifier": overlay[0], "quotable": False,
                  "known_intentional_key": "spire-proximity-overlay",
                  "candidate_witnesses": []})
    emit("B-2-core-2e", "B",
         "For EACH modifier: verify effects encode the rule per FG&G (quotable — "
         "quote the line) using candidate_witnesses; the '(FG&G cite pending)' refs "
         "route to the resolution court (kind=ref-upgrade), NOT as value findings — "
         "but a VALUE contradiction against FG&G is a finding. weapon-specialization "
         "split-purpose (+1 attack / +2 damage), rear-attack +2, higher-ground +1, "
         "magic-weapon-plus param shape. The spire-proximity overlay row is a V&V "
         "demo (known-intentional) — verify shape only. Findings only for defects.",
         items)

    items = []
    for row in mods["planescape-2e.json"]:
        census["modifiers"].append(row["id"])
        stated = str(row.get("source", {}).get("ref", ""))
        wfiles = []
        for hint, product in NOTE_PRODUCT_HINTS:
            if hint in stated:
                wfiles = [p.as_posix() for p in _reflow_pages(product, stated)]
                break
        recs = law_candidates_for(f"data/modifiers/planescape-2e.json#{row['id']}")
        items.append({"modifier": row, "quotable": False, "witness_files": wfiles,
                      "law_refs": recs})
    emit("B-3-planescape-2e", "B",
         "For EACH modifier: open witness_files (CITE-ONLY scans) and verify the "
         "encoded effect against the page: sign and size of the delta, the "
         "roll-under +1 == score-1 equivalence claims, applies_to split, the "
         "despair +1 attack/damage reading, initiative low-wins penalty reading. "
         "Verify the law_rows included actually GOVERN the modifier (the exact "
         "ref upgrade is the court's). Findings only for defects.", items)

    # ---- C: rollables by product ------------------------------------------------
    reg_rows = json.loads((DATA_DIR / "rollables" / "planescape-2e.json").read_text(encoding="utf-8"))
    by_product: dict[str, list[dict]] = {}
    for row in reg_rows:
        by_product.setdefault(row["source"]["product"], []).append(row)

    def c_item(row: dict) -> dict:
        src = row["source"]
        pages = _reflow_pages(src["product"], str(src.get("page", "")))
        payload = json.dumps(row, ensure_ascii=False)
        token = None
        m = _DICE_TOKEN_RE.search(payload) or _PCT_TOKEN_RE.search(payload)
        if m:
            token = m.group(0)
        probe = None
        if token and pages:
            probe = any(token.lower() in p.read_text(encoding="utf-8", errors="replace").lower()
                        for p in pages if p.exists())
        item = {"entry": row,
                "witness_files": [p.as_posix() for p in pages],
                "used_at_status": {u: used_at.get(u, None) for u in row.get("used_at", [])},
                "probe_token": token, "probe_hit": probe,
                "shingle_status": shingle_hits.get(row["id"], "clean")}
        if row.get("requires_confirmation"):
            item["adjudication_ask"] = (
                "REQUIRES_CONFIRMATION entry: read the witness page context around the "
                "OCR fragment (the notes name it) and propose: confirm the transcribed "
                "value (with the evidence locator), OR a different reading (with "
                "evidence), OR 'unconfirmable from reflow — flag stands pending a "
                "print check'.")
        return item

    C_MANDATE = (
        "For EACH rollable: open witness_files (official scans — CITE-ONLY: paraphrase "
        "+ <=6-word locator, never quote). Verify every die expression, percentage, "
        "range, band and terse outcome label attests on the cited page (OCR-loose; "
        "probe_hit=false is a hint, not a verdict); verify table coverage matches the "
        "print's bands; verify the notes' riders are on the page; judge paraphrase "
        "distance (shingle_status='clean' still deserves an eye; a pre-confirmed hit "
        "carries the shared shingle). used_at_status false on Inner-Planes ids + the "
        "mancatcher is known-intentional. lookups are diceless BY LAW. Findings only "
        "for defects.")

    chaos = by_product.get("Planes of Chaos (TSR 2603)", [])
    law = by_product.get("Planes of Law (TSR 2607), Acheron booklet", [])
    cage = by_product.get("In the Cage: A Guide to Sigil (TSR 2609)", [])
    inner = by_product.get("The Inner Planes (TSR 2634)", [])
    for row in reg_rows:
        census["rollables"].append(row["id"])
    emit("C-1-chaos-law", "C", C_MANDATE, [c_item(r) for r in chaos + law],
         products=["Planes of Chaos (TSR 2603)", "Planes of Law (TSR 2607), Acheron booklet"])
    emit("C-2-cage", "C", C_MANDATE, [c_item(r) for r in cage],
         products=["In the Cage: A Guide to Sigil (TSR 2609)"])
    emit("C-3-inner-a", "C", C_MANDATE, [c_item(r) for r in inner[:9]],
         products=["The Inner Planes (TSR 2634)"])
    emit("C-4-inner-b", "C", C_MANDATE, [c_item(r) for r in inner[9:]],
         products=["The Inner Planes (TSR 2634)"])

    # ---- F: doc-truth ----------------------------------------------------------
    mechanical = {k: report["info"].get(k) for k in
                  ("tools", "tests_collected", "rollables", "modifiers", "check_kinds",
                   "minted_law_ids")}
    f1_items = [
        {"claim_area": "MODRON.md §3 — engine v1 derivation pin",
         "doc": (MODRON_DIR / "MODRON.md").as_posix(),
         "evidence": (MODRON_DIR / "modron/engine.py").as_posix(),
         "ask": "Does the §3 derivation text (sha256(seed‖u64(counter)‖u64(draw)‖"
                "u32(chunk)) → first 8 bytes → rejection-sampled) match "
                "DiceStream.draw exactly? Commitment/reveal/ephemeral claims too."},
        {"claim_area": "MODRON.md §4 — grammar guards + postfix pipeline order",
         "doc": (MODRON_DIR / "MODRON.md").as_posix(),
         "evidence": (MODRON_DIR / "modron/grammar.py").as_posix(),
         "evidence2": (MODRON_DIR / "modron/engine.py").as_posix(),
         "ask": "Do the documented guards (<=1000 dice, <=10000 sides, explode depth "
                "<=100) and the pipeline order (reroll → explode → clamp → keep/drop "
                "→ count-successes) match the code? NOTE the pre-confirmed integrity "
                "finding: engine counts successes on kept NATURALS while analysis "
                "counts post-clamp VALUES, and §4's order implies value-counting — "
                "classify doc-wrong vs code-wrong vs analysis-wrong."},
        {"claim_area": "MODRON.md §7 — the 17-tool surface",
         "doc": (MODRON_DIR / "MODRON.md").as_posix(),
         "evidence": (MODRON_DIR / "server.py").as_posix(),
         "ask": "Does §7's tool table match server.py's actual tool list (names, "
                "count=17, described behavior)?"},
        {"claim_area": "README.md — layout/claims",
         "doc": (MODRON_DIR / "README.md").as_posix(),
         "evidence": MODRON_DIR.as_posix(),
         "ask": "Do the README's layout, counts and claims match the tree today?"},
    ]
    emit("F-1-design-docs", "F",
         "For EACH claim area: open the doc and the evidence file(s); judge whether "
         "the claim is still TRUE of the code. Mechanical counts are pre-verified "
         "(see mechanical_counts) — your job is the PROSE around them. Classify "
         "drift: doc-wrong → L5 with the exact corrected sentence; code-wrong → L4. "
         "Findings only for defects.", f1_items, mechanical_counts=mechanical)

    f2_items = [
        {"claim_area": "VERIFICATION.md header counts",
         "doc": (MODRON_DIR / "VERIFICATION.md").as_posix(),
         "ask": "Header says suite '140 passed' (current collect: 171) and '~50 live "
                "checks' (count the verdict table rows yourself). Confirm staleness; "
                "propose the L5 sentence fix."},
        {"claim_area": "VERIFICATION.md witnessed boundaries still true",
         "doc": (MODRON_DIR / "VERIFICATION.md").as_posix(),
         "evidence": (MODRON_DIR / "modron/modifiers.py").as_posix(),
         "evidence2": (MODRON_DIR / "modron/rollables.py").as_posix(),
         "ask": "The documented boundaries (GWF rerolls ALL non-d20 dice; "
                "sneak-attack-as-modifier doesn't double under crit; Black Marian "
                "first-expr-only; prose sweep context requirement) — still true of "
                "the code? These are known-intentional; flag only if the CODE moved."},
        {"claim_area": "CLAUDE.md §Modron block",
         "doc": (ROOT / "CLAUDE.md").as_posix(),
         "ask": "Read the Modron section: '~54 live probes' vs VERIFICATION.md's "
                "actual count; '171 tests'; tool surface (17); composition order "
                "claim; session ceremony claims; rollables registry claims (34 "
                "entries). Confirm each or propose the L5 fix."},
        {"claim_area": "MODRON.md §9 D1-D9 acceptances vs data reality",
         "doc": (MODRON_DIR / "MODRON.md").as_posix(),
         "evidence": (DATA_DIR / "rollables/planescape-2e.json").as_posix(),
         "evidence2": (DATA_DIR / "conventions/2e-planescape.json").as_posix(),
         "ask": "Does the §9 verdict table match what the data implements? (D1 "
                "limbo kinds + lookups; D4 slags/ooze; D5 wasting; D6 madness mods; "
                "D7 18 inner entries; D8 acheron landing-only; D9 harmonium accepted "
                "+ Yscoppel DECLINED — confirm no Yscoppel entry exists.)"},
    ]
    emit("F-2-verification-claims", "F",
         "For EACH claim area: open the doc; judge each claim against the evidence. "
         "doc-wrong → L5 with the exact corrected sentence; code-wrong → L4. "
         "Pre-spotted staleness (the 140/171 header) should land as a confirmed L5 "
         "finding, not be re-litigated. Findings only for defects.",
         f2_items, mechanical_counts=mechanical)

    # ---- G: fleet ---------------------------------------------------------------
    fleet_files = {p.stem: p for p in sorted(FLEET_DIR.glob("*.json"))}
    fleet = {}
    for slug, p in fleet_files.items():
        d = json.loads(p.read_text(encoding="utf-8"))
        fleet[d["id"]] = {"file": p, "data": d}

    hb = mstore._mimir_store().HandbookStore(HANDBOOK, readonly=True)
    envs: dict[str, dict] = {}
    try:
        for eid in fleet:
            envs[eid] = hb.get(eid) or {}
    finally:
        hb.close()

    def flags_of(specs: list[dict]) -> list[dict]:
        out = []
        for s in specs:
            cc = s.get("crosscheck") or {}
            if (s.get("unparsed") or s.get("requires_confirmation")
                    or s.get("ambiguous") or s.get("suspect")
                    or cc.get("verdict") in ("MISMATCH", "OUT_OF_RANGE")):
                out.append(s)
        return out

    def g_item(eid: str, extra_fields: tuple = ("statblock", "descriptor")) -> dict:
        d = fleet[eid]["data"]
        env = envs.get(eid, {})
        fields = env.get("fields") if isinstance(env.get("fields"), dict) else env
        flagged = flags_of(d["specs"])
        item = {"id": eid, "name": d.get("name"), "view": d.get("view"),
                "fleet_file": fleet[eid]["file"].as_posix(),
                "n_specs": len(d["specs"]), "flagged_specs": flagged,
                "fields": {k: fields.get(k) for k in extra_fields if fields.get(k) is not None},
                "provenance": env.get("provenance")}
        return item

    creatures = sorted(eid for eid, f in fleet.items() if f["data"]["type"] == "creature")
    npcs = sorted(eid for eid, f in fleet.items() if f["data"]["type"] == "npc")

    MC_FLAT_FIELDS = ("thac0", "hit_dice", "damage_attack", "no_of_attacks", "morale",
                      "magic_resistance", "armor_class", "no_appearing", "mc_component",
                      "page", "size", "special_attacks", "special_defenses")
    items = []
    for eid in creatures:
        it = g_item(eid, MC_FLAT_FIELDS)
        env = envs.get(eid, {})
        fields = env.get("fields") if isinstance(env.get("fields"), dict) else {}
        prov = (env.get("provenance") or {}).get("value_sources", [])
        src = prov[0].get("src") if prov else None
        mc = (fields or {}).get("mc_component")
        page = (fields or {}).get("page")
        if src and mc and page:
            p = ROOT / "build" / src / mc / "reflow" / f"page-{int(page):04d}.txt"
            it["reflow_files"] = [p.as_posix()] if p.exists() else []
        items.append(it)
    emit("G-1-creatures", "G",
         "SYSTEMIC pre-confirmed gap (integrity fleet_creature_shape_gap): all 16 "
         "creatures carry MC-style FLAT fields (thac0/hit_dice/damage_attack/morale/"
         "magic_resistance at top level — no statblock sub-object) and statblock_2e "
         "reads only entity['statblock'], so they compile to <=1 non-prose spec — "
         "THAC0, damage, HP, morale, MR all silently invisible. Your job: (a) CONFIRM "
         "the mechanism in pipeline/modron/modron/rollables.py statblock_2e; (b) "
         "propose the L4 fix shape (a field-alias adapter mapping MC flat fields into "
         "the statblock shape, plus damage_attack parsing) with its regression test; "
         "(c) for FOUR creatures with reflow_files, hand-derive the expected specs "
         "(attack from thac0, damage modes, hp from hit_dice, morale, MR) and verify "
         "the handbook fields against the MC page (scan pages, cite-only); (d) ONE "
         "systemic finding + per-sample expected-spec payloads, not 16 copies.",
         items)

    hp_info_ids = sorted(eid for eid in npcs
                         if any(s.get("key") == "hp" and s.get("purpose") == "info"
                                for s in fleet[eid]["data"]["specs"]))
    parakk = [eid for eid in npcs if "parakk" in eid]
    g4_ids = sorted(set(hp_info_ids) | set(parakk))
    clean_pool = [eid for eid in npcs if eid not in g4_ids]
    clean_ids = sorted(eid for eid in clean_pool if not flags_of(fleet[eid]["data"]["specs"])
                       and any(s.get("key") == "hp" and s.get("expr")
                               for s in fleet[eid]["data"]["specs"]))[:5]
    rest = [eid for eid in clean_pool if eid not in clean_ids]
    half = (len(rest) + 1) // 2

    emit("G-4-hp-roster", "G",
         "The hp-not-derivable roster. KNOWN (G11, integration-tests.md): Black "
         "Marian, Estavan, Farrow, Iarmid, Ly'kritch, Parakk, Saure, The Us, Verden. "
         "Fleet reality: the hp-info set is the 13 items here MINUS Parakk — Parakk "
         "now DERIVES (handbook envelope parses where the pre-pour build JSON "
         "didn't): confirm Parakk's hp spec is sound and record the roster DELTA as "
         "a finding (kind=other, lane L6 — the integration doc's roster line is "
         "stale). For the 5 NEW members (Koe, Omott, Patch, The Grixitt, Ylem): read "
         "fields.descriptor/statblock and adjudicate WHY hp doesn't derive — honest "
         "(no HD printed, e.g. Patch the razorvine plant) vs extractor miss "
         "(class-code present but unparsed → L6 to Mimir) vs compiler miss (parseable "
         "shape statblock_2e should handle → L4). The visible info-spec itself is "
         "CORRECT behavior — never propose inventing dice.",
         [g_item(e) for e in g4_ids])

    emit("G-5-clean-sample", "G",
         "False-negative probe over 5 clean compiles: for EACH entity, hand-derive "
         "from fields what the compiler SHOULD emit — attack (THAC0), each damage "
         "mode (split on '/', ' or ', xN), hp (class HD per descriptor.char_class "
         "F/M/T/C codes: d10/d4/d6/d8, or monster HD d8), morale, MR percent — then "
         "diff against the fleet file's specs. Report anything MISSING or extra. "
         "Naturals: no flags exist on these; your derivation is the check.",
         [g_item(e) for e in clean_ids])

    emit("G-2-npc-a", "G",
         "Per entity: compare compiled specs (fleet_file) against fields.statblock/"
         "descriptor — is every parseable value compiled (THAC0, damage modes, MR, "
         "morale, HD/class-HP)? Adjudicate each flagged_specs item: prose-sweep "
         "requires_confirmation specs carry their context — judge real-mechanic "
         "(confirm) vs OCR noise/false positive (deny, with why); unparsed specs "
         "(Saure mode-2 is known-intentional OCR garbage) — transcription wound → "
         "L6-to-Mimir vs compiler misread → L4. Findings only for defects.",
         [g_item(e) for e in rest[:half]])
    emit("G-3-npc-b", "G",
         "Per entity: compare compiled specs (fleet_file) against fields.statblock/"
         "descriptor — is every parseable value compiled (THAC0, damage modes, MR, "
         "morale, HD/class-HP)? Adjudicate each flagged_specs item: prose-sweep "
         "requires_confirmation specs carry their context — judge real-mechanic "
         "(confirm) vs OCR noise/false positive (deny, with why). Findings only for "
         "defects.",
         [g_item(e) for e in rest[half:]])

    for eid in creatures + npcs:
        census["entities"].append(eid)

    # ---- census + write ----------------------------------------------------------
    assert len(census["kinds"]) == 23, f"kinds census {len(census['kinds'])}"
    assert len(set(census["kinds"])) == 23
    assert len(census["modifiers"]) == 29, f"modifiers census {len(census['modifiers'])}"
    assert len(set(census["modifiers"])) == 29
    assert len(census["rollables"]) == 34, f"rollables census {len(census['rollables'])}"
    assert len(set(census["rollables"])) == 34
    assert len(census["entities"]) == 87, f"entities census {len(census['entities'])}"
    assert len(set(census["entities"])) == 87
    g_counts = sum(len(chunks[c]["items"]) for c in chunks if c.startswith("G-"))
    assert g_counts == 87, f"G items {g_counts} != 87"

    # every witness/evidence path in every chunk must exist
    missing: list[str] = []

    def assert_paths(o):
        if isinstance(o, dict):
            for k, vv in o.items():
                if k in ("witness_files", "reflow_files", "candidate_witnesses"):
                    for w in vv:
                        f = w["file"] if isinstance(w, dict) else w
                        if not Path(f).exists():
                            missing.append(f)
                elif k in ("doc", "evidence", "evidence2", "fleet_file", "srd52_p202",
                           "known_intentional"):
                    if isinstance(vv, str) and not Path(vv).exists():
                        missing.append(vv)
                else:
                    assert_paths(vv)
        elif isinstance(o, list):
            for vv in o:
                assert_paths(vv)

    for cid, chunk in sorted(chunks.items()):
        assert_paths(chunk)
    assert not missing, f"missing witness paths: {missing[:8]}"

    manifest = {"chunks": {}, "census": {k: len(vv) for k, vv in census.items()}}
    for cid, chunk in sorted(chunks.items()):
        path = CHUNKS / f"{cid}.json"
        path.write_text(json.dumps(chunk, indent=1, ensure_ascii=False, default=str),
                        encoding="utf-8")
        manifest["chunks"][cid] = {"file": path.as_posix(), "lane": chunk["lane"],
                                   "items": len(chunk["items"])}
    (REVIEW / "chunks-manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"chunks: {len(chunks)} -> {CHUNKS}")
    for cid, meta in sorted(manifest["chunks"].items()):
        print(f"  {cid:24} {meta['lane']}  {meta['items']:3} items")
    print(f"census: {manifest['census']}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
