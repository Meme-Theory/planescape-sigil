"""Mechanus audit — work-list dumper (Phase 0).

Reads the law data + integrity-report.json and writes the review chunks the
workflow agents consume: build/mechanus/review/chunks/chunk-*.json plus
manifest.json. Every audit unit lands in exactly one chunk (the manifest
asserts it); every page citation is RESOLVED to an absolute file path so no
review agent ever does offset math (the Mimir Great Audit law).

Page conventions (pinned by integrity.py's anchor probes):
- planar witness.reflow == reflow filename index (page-{N:04d}.txt) — direct
- SRD cite p.N == srd{51,52}-text/p{N:04d}.txt — zero offset
- FG&G law cite p.N == fgg-text/p{N:04d}.txt — PDF index, NEVER add +10
"""

from __future__ import annotations

import inspect
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "pipeline" / "mechanus"))

from mechanus import budget as budget_mod  # noqa: E402
from mechanus import dc as dc_mod  # noqa: E402
from mechanus import lawful, tables  # noqa: E402

BUILD = REPO / "build"
REVIEW = BUILD / "mechanus" / "review"
CHUNKS = REVIEW / "chunks"
CACHES = {"srd51": BUILD / "mechanus" / "srd51-text",
          "srd52": BUILD / "mechanus" / "srd52-text",
          "fgg": BUILD / "mechanus" / "fgg-text"}

BOOK_DIR = {
    "ddps-planesoflaw-ii": "planes-of-law",
    "ddps-planesoflaw-iii": "planes-of-law",
    "ddps-planesoflaw-iv": "planes-of-law",
    "ddps-planesoflaw-v": "planes-of-law",
    "ddps-planesoflaw-vi": "planes-of-law",
    "tsr2603-planes-of-chaos": "planes-of-chaos",
    "planes-of-conflict-2615-01-liber-benevolentiae": "planes-of-conflict",
    "planes-of-conflict-2615-02-liber-malevolentiae": "planes-of-conflict",
    "ddps-inthecage": "in-the-cage-a-guide-to-sigil",
}

PAGE_CONVENTION = ("witness.reflow == reflow filename index; SRD/FG&G cites == cache "
                   "filename index. Paths below are pre-resolved ABSOLUTE — never add offsets.")
GREP_WARNING = ("The Grep tool silently SKIPS build/ (gitignored). Read the absolute "
                "paths given here; if you must search a cache, use bash grep / rg --no-ignore. "
                "A Grep miss is NOT evidence of absence.")

CONDITIONS_GROUPS = [
    ("planar-conditions-pol-a", ["acheron", "arcadia"], False),
    ("planar-conditions-pol-b", ["baator", "mechanus", "mount-celestia"], False),
    ("planar-conditions-chaos-a", ["the-abyss", "arborea"], False),
    ("planar-conditions-chaos-b", ["limbo", "pandemonium", "ysgard"], False),
    ("planar-conditions-conflict-a", ["the-beastlands", "bytopia", "elysium"], True),  # + _general
    ("planar-conditions-conflict-b", ["carceri", "gehenna", "the-gray-waste"], False),
]
KEYS_GROUPS = [
    ("planar-keys-pol", ["acheron", "arcadia", "baator", "mechanus", "mount-celestia"]),
    ("planar-keys-chaos", ["the-abyss", "arborea", "limbo", "pandemonium", "ysgard"]),
    ("planar-keys-conflict", ["the-beastlands", "bytopia", "elysium",
                              "carceri", "gehenna", "the-gray-waste"]),
]


def witness_paths(row: dict) -> list[str]:
    out = []
    for w in row.get("witness") or []:
        comp = w.get("component")
        if comp not in BOOK_DIR:
            continue
        for pg in w.get("reflow") or []:
            p = BUILD / BOOK_DIR[comp] / comp / "reflow" / f"page-{pg:04d}.txt"
            out.append(p.as_posix())
    return out


def cache_page(cache: str, n: int) -> str:
    return (CACHES[cache] / f"p{n:04d}.txt").as_posix()


def find_page(cache: str, needles: list[str], lo: int = 1, hi: int = 9999) -> int | None:
    """First cache page (within [lo, hi]) containing every needle, case-folded."""
    for p in sorted(CACHES[cache].glob("p*.txt")):
        n = int(p.stem[1:])
        if not (lo <= n <= hi):
            continue
        txt = re.sub(r"\s+", " ", p.read_text(encoding="utf-8")).lower()
        if all(nd.lower() in txt for nd in needles):
            return n
    return None


def src(obj) -> str:
    return inspect.getsource(obj)


def main() -> int:
    report = json.loads((REVIEW / "integrity-report.json").read_text(encoding="utf-8"))
    pinned = report["pinned_pages"]
    near_by_unit: dict[str, list[str]] = {}
    for nm in report["near_misses"]:
        near_by_unit.setdefault(nm["unit_id"], []).append(
            f"longest verbatim run {nm['run']} tokens vs {nm['page']} (advisory near-miss)")
    ocr_rows = set(report["ocr_note_rows"])

    chunks: list[dict] = []
    manifest: dict[str, str] = {}  # unit_id -> chunk slug

    def add_chunk(slug: str, unit_class: str, units: list[dict], book: str | None = None,
                  shared: dict | None = None) -> None:
        for u in units:
            for uid in [u["unit_id"], *u.get("sub_ids", [])]:
                if uid in manifest:
                    raise SystemExit(f"unit {uid} already in {manifest[uid]} (re-added by {slug})")
                manifest[uid] = slug
        chunks.append({"chunk": slug, "unit_class": unit_class,
                       **({"book": book} if book else {}),
                       **({"shared": shared} if shared else {}),
                       "page_convention": PAGE_CONVENTION,
                       "grep_warning": GREP_WARNING,
                       "rules_of_engagement_ref": (REVIEW / "PLAN.md").as_posix(),
                       "known_intentional": (REVIEW / "known-intentional.json").as_posix(),
                       "units": units})

    def advisories_for(law_id: str, subs: list[str] = ()) -> list[str]:
        out = []
        for uid in [law_id, *subs]:
            out.extend(near_by_unit.get(uid, []))
            if uid in ocr_rows:
                out.append(f"{uid} carries ocr_note — confidence cap 0.5, verdict "
                           "needs-print-check (known-intentional KI-16)")
        return out

    # ---------------- U1: planar-conditions (6 chunks) -----------------------
    cond_doc = tables._load("planar_conditions.json")
    cond_rows = {r["law_id"]: r for r in tables._planar_rows("law:planar-conditions")}

    def plane_unit(family: str, parent: dict) -> dict:
        law_id = parent["law_id"]
        subs = sorted(i for i in cond_rows if i.startswith(law_id + ":")) \
            if family == "law:planar-conditions" else \
            [f"{law_id}:spell", f"{law_id}:power"]
        ev = set(witness_paths(parent))
        for s in subs:
            row = tables.planar_law(s)
            ev.update(witness_paths(row))
        return {"unit_id": law_id, "kind": "plane-row",
                "payload": parent, "sub_ids": subs,
                "evidence_files": sorted(ev),
                "advisories": advisories_for(law_id, subs)}

    for slug, planes, with_general in CONDITIONS_GROUPS:
        units = []
        if with_general:
            for g in cond_doc["_general"]:
                units.append({"unit_id": g["law_id"], "kind": "general-row", "payload": g,
                              "evidence_files": sorted(set(witness_paths(g))),
                              "advisories": advisories_for(g["law_id"])})
        for p in planes:
            units.append(plane_unit("law:planar-conditions", cond_doc["planes"][p]))
        book = BOOK_DIR[cond_doc["planes"][planes[0]]["witness"][0]["component"]]
        add_chunk(slug, "planar-conditions", units, book=book)

    # ---------------- U1: planar-keys (3 chunks) -----------------------------
    keys_doc = tables._load("planar_keys.json")
    for slug, planes in KEYS_GROUPS:
        units = [plane_unit("law:planar-keys", keys_doc["planes"][p]) for p in planes]
        book = BOOK_DIR[keys_doc["planes"][planes[0]]["witness"][0]["component"]]
        add_chunk(slug, "planar-keys", units, book=book)

    # ---------------- U1: environment (2 chunks, split by witnessing book) ---
    env_rows = tables._planar_rows("law:plane-environment")
    env_pol = [r for r in env_rows if r["witness"][0]["component"].startswith("ddps-planesoflaw")]
    env_rest = [r for r in env_rows if r not in env_pol]
    for slug, rows in (("plane-environment-pol", env_pol), ("plane-environment-rest", env_rest)):
        units = [{"unit_id": r["law_id"], "kind": "rule-row", "payload": r,
                  "evidence_files": sorted(set(witness_paths(r))),
                  "advisories": advisories_for(r["law_id"])} for r in rows]
        add_chunk(slug, "plane-environment", units)

    # ---------------- U1: spells (1) · seals+priest+cage (1) -----------------
    spell_units = [{"unit_id": r["law_id"], "kind": "spell-row", "payload": r,
                    "evidence_files": sorted(set(witness_paths(r))),
                    "advisories": advisories_for(r["law_id"])}
                   for r in tables._planar_rows("law:planar-spell")]
    add_chunk("planar-spells", "planar-spell", spell_units)

    spc_units = []
    for fam in ("law:seals-wards", "law:planar-priest", "law:cage"):
        for r in tables._planar_rows(fam):
            spc_units.append({"unit_id": r["law_id"], "kind": "rule-row", "payload": r,
                              "evidence_files": sorted(set(witness_paths(r))),
                              "advisories": advisories_for(r["law_id"])})
    add_chunk("seals-priest-cage", "seals-priest-cage", spc_units)

    # ---------------- U2: SRD tables (3 chunks) ------------------------------
    xp_doc = tables._load("xp_by_cr.json")
    pb_doc = tables._load("pb_by_cr.json")
    xp_ev = [cache_page("srd52", 256), cache_page("srd51", 258)]
    units = [{"unit_id": f"srd:xp_by_cr:cr-{k.replace('/', '-')}", "kind": "table-row",
              "payload": {"cr": k, "xp": v, "_source": xp_doc["_source"]},
              "evidence_files": xp_ev, "advisories": []}
             for k, v in xp_doc["xp"].items()]
    units += [{"unit_id": f"srd:pb_by_cr:{lo}-{hi}", "kind": "table-row",
               "payload": {"bracket": [lo, hi, pb], "_source": pb_doc["_source"]},
               "evidence_files": [cache_page("srd52", 256)], "advisories": []}
              for lo, hi, pb in pb_doc["brackets"]]
    units.append({"unit_id": "srd:pb_by_cr:formula", "kind": "formula",
                  "payload": {"formula": pb_doc["formula"], "_source": pb_doc["_source"]},
                  "evidence_files": [cache_page("srd52", 256)], "advisories": []})
    add_chunk("srd-xp-pb", "srd-tables", units)

    dc_doc = tables._load("dc_ladder.json")
    cond_json = tables._load("conditions.json")
    attr = tables._load("attribution.json")
    units = [{"unit_id": f"srd:dc_ladder:{r['task'].lower().replace(' ', '-')}",
              "kind": "table-row", "payload": {**r, "_source": dc_doc["_source"]},
              "evidence_files": [cache_page("srd51", 77), cache_page("srd52", 6)],
              "advisories": []} for r in dc_doc["ladder"]]
    # srd51: Appendix PH-A spans two pages; srd52: conditions live as
    # '[Condition]' entries across the Rules Glossary span (docket B2/C4)
    _c51 = int(pinned["srd51_conditions_appendix"][1:])
    cond_ev = ([cache_page("srd51", _c51), cache_page("srd51", _c51 + 1)]
               + [cache_page("srd52", p) for p in (177, 178, 181, 182, 184, 186, 187, 189, 191)])
    for view in tables.VIEWS_5E:
        units.append({"unit_id": f"srd:conditions:{view}", "kind": "enum-list",
                      "payload": {"conditions": cond_json["conditions"][view],
                                  "_source": cond_json["_source"]},
                      "evidence_files": cond_ev,
                      "advisories": ["enum sourced from 5e-bits; the SRD appendix pages "
                                     "verify the NAMES exist as conditions (KI-8)"]})
    units.append({"unit_id": "srd:conditions:senses", "kind": "enum-list",
                  "payload": {"senses": cond_json["senses"]},
                  # srd51 p0257 covers all four senses; srd52 glossary pages
                  # carry blindsight/darkvision (177), tremorsense (180),
                  # truesight (190) — docket B5
                  "evidence_files": [cache_page("srd51", 257), cache_page("srd52", 177),
                                     cache_page("srd52", 180), cache_page("srd52", 190)],
                  "advisories": []})
    for view in tables.VIEWS_5E:
        units.append({"unit_id": f"srd:attribution:{view}", "kind": "legal-block",
                      "payload": {"block": attr[view], "_note": attr.get("_note")},
                      "evidence_files": [cache_page("srd51" if view == "5e-2014" else "srd52", 1)],
                      "advisories": ["VERBATIM is correct here — CC-BY legal text (KI-4)"]})
    add_chunk("srd-dc-conditions-attribution", "srd-tables", units)

    bud = tables._load("xp_budget_2024.json")
    units = [{"unit_id": f"srd:xp_budget:L{lvl}", "kind": "table-row",
              "payload": {"level": lvl, "low_moderate_high": bud["budget_per_character"][str(lvl)],
                          "_source": bud["_source"]},
              "evidence_files": [cache_page("srd52", 202)],
              "advisories": (["OCR note: print reads '11,70 0' — double-read the High cell (L17)"]
                             if lvl == 17 else [])}
             for lvl in range(1, 21)]
    add_chunk("srd-xp-budget", "srd-tables", units)

    # ---------------- U3: FG&G THAC0 (1 chunk) -------------------------------
    th = tables._load("thac0_2e.json")
    spot_pages = []
    for p in sorted(CACHES["fgg"].glob("p*.txt")):
        n = int(p.stem[1:])
        # FG&G prints 'THACO' (letter O), never 'THAC0'; Appendix C bestiary
        # begins at p0309 — pp.301-308 are Appendix B treasure (docket C6).
        if 309 <= n <= 384 and "thaco" in p.read_text(encoding="utf-8").lower():
            spot_pages.append(n)
    spot_pages = spot_pages[:: max(1, len(spot_pages) // 9)][:9]
    fgg_ev = [cache_page("fgg", 27)] + [cache_page("fgg", n) for n in spot_pages]
    units = [{"unit_id": f"fgg:thac0:bracket-{lo}-{hi}", "kind": "table-row",
              "payload": {"bracket": [lo, hi, t], "_source": th["_source"]},
              "evidence_files": fgg_ev, "advisories": []}
             for lo, hi, t in th["brackets"]]
    units.append({"unit_id": "fgg:thac0:plus-bump", "kind": "rule",
                  "payload": th["plus_bump"], "evidence_files": fgg_ev, "advisories": []})
    units.append({"unit_id": "fgg:thac0:fit-disclosure", "kind": "disclosure",
                  "payload": th["_evidence"], "evidence_files": fgg_ev,
                  "advisories": ["disclosed empirical fit — outliers are disclosures, "
                                 "not defects (KI-12)"]})
    add_chunk("fgg-thac0", "fgg-tables", units,
              shared={"bestiary_spot_pages": spot_pages,
                      "task": "verify brackets against Table 3.3 AND spot-check the "
                              "bestiary pages' (HD, THAC0) pairs against the brackets"})

    # ---------------- U4: known_deviations (1 chunk) -------------------------
    dev = json.loads((tables.LAW_DIR / "known_deviations.json").read_text(encoding="utf-8"))
    units = []
    for name, entries in dev["attested_deviations"].items():
        pages = [int(m.group(1)) for e in entries
                 if (m := re.search(r"SRD 5\.1 p\.(\d+)", e.get("witness", "")))]
        units.append({"unit_id": f"dev:waiver:{name}", "kind": "waiver",
                      "payload": entries,
                      "evidence_files": [cache_page("srd51", p) for p in pages],
                      "advisories": []})
    bug_pages = {"spider": 389, "blink-dog": 368, "black-bear": 367, "swarm-of-ravens": 391,
                 "half-red-dragon-veteran": 321}
    for slug, note in dev["upstream_5e_bits_bugs"].items():
        if slug == "halved_xp":
            continue
        ev = [cache_page("srd51", bug_pages[slug])] if slug in bug_pages else []
        units.append({"unit_id": f"dev:bug:{slug}", "kind": "upstream-bug-note",
                      "payload": {"note": note}, "evidence_files": ev,
                      "advisories": ([] if ev else ["print verification pending per the note "
                                                    "itself — confirm or keep pending"])})
    for slug in dev["upstream_5e_bits_bugs"]["halved_xp"]:
        # exact statblock headings (first-word needles matched the wrong
        # monsters — docket C1-C3; verified unique in srd51-text)
        heading = {"dretch": "Dretch", "riding-horse": "Riding Horse",
                   "deep-gnome-svirfneblin": "Svirfneblin",
                   "brass-dragon-wyrmling": "Brass Dragon Wyrmling"}[slug]
        pg = find_page("srd51", [heading], lo=260, hi=404)
        # statblocks span page breaks (Dretch 270->271, Brass Dragon Wyrmling
        # 292->293) — include the next page so the Challenge line is in evidence
        ev = [cache_page("srd51", p) for p in ((pg, pg + 1) if pg else ())]
        units.append({"unit_id": f"dev:halved-xp:{slug}", "kind": "upstream-bug-xp",
                      "payload": {"monster": slug,
                                  "claim": "5e-bits XP is exactly half the printed value"},
                      "evidence_files": ev,
                      "advisories": [] if pg else ["page not auto-located — bash-grep "
                                                   "srd51-text for the monster heading"]})
    add_chunk("known-deviations", "known-deviations", units)

    # ---------------- U5: code-as-law (3 chunks) -----------------------------
    checks_5e_src = src(lawful._checks_5e)
    checks_2e_src = src(lawful._checks_2e)
    five_e_meta = {
        "abilities_present_in_range": ("hard", "engineering-bound + SRD ability range",
                                       [cache_page("srd51", 76), cache_page("srd52", 21)]),
        "cr_valid": ("hard", "CR enum from XP table keys",
                     [cache_page("srd52", 256), cache_page("srd51", 258)]),
        "pb_matches_cr": ("hard", "pb_by_cr.json brackets + formula",
                          [cache_page("srd52", 256)]),
        "xp_matches_cr": ("soft", "xp_by_cr.json",
                          [cache_page("srd52", 256), cache_page("srd51", 258)]),
        "hp_matches_roll": ("hard", "floor(mean(NdS±K)) ±1 — statblock convention; verify "
                                    "against any printed statblock's HP line",
                            [cache_page("srd51", 325)]),
        "ac_in_range": ("hard", "engineering-bound 5..25 (SRD extremes)", []),
        "speeds_multiple_of_5": ("hard", "engineering-bound (all SRD speeds are 5-multiples)", []),
        "passive_perception_math": ("hard", "10 + perception skill bonus (or WIS mod)",
                                    [cache_page("srd51", int(pinned["srd51_skills_list"][1:])),
                                     cache_page("srd52", int(pinned["srd52_skills_list"][1:]))]),
        "save_bonuses_math": ("hard", "ability mod + PB",
                              [cache_page("srd51", 76), cache_page("srd52", 21)]),
        "skill_bonuses_math": ("hard", "mod + PB or mod + 2·PB (expertise)",
                               [cache_page("srd51", int(pinned["srd51_skills_list"][1:]))]),
        "conditions_known": ("hard", "conditions.json enum", cond_ev),
        "senses_known": ("hard", "senses enum", cond_ev),
    }
    units = [{"unit_id": f"code:lawful:{name}", "kind": "check",
              "payload": {"sev": sev, "law_basis": basis,
                          "law_tables": {"pb_by_cr": pb_doc, "xp_by_cr": xp_doc["xp"]}
                          if name in ("pb_matches_cr", "xp_matches_cr", "cr_valid") else None},
              "evidence_files": ev, "advisories": []}
             for name, (sev, basis, ev) in five_e_meta.items()]
    add_chunk("code-checks-5e", "code-as-law", units,
              shared={"source": checks_5e_src,
                      "helpers": src(lawful.ability_mod) + src(lawful.mean_hp),
                      "instruction": "verify each check implements its law_basis exactly: "
                                     "ranges, formulas, enum normalization, hard/soft per "
                                     "MECHANUS.md print-deviation policy, skip-vs-fail honesty"})

    fgg_idx = (CACHES["fgg"] / "INDEX.md").as_posix()
    fgg_hd = find_page("fgg", ["hit dice", "hit points"], hi=60)
    fgg_mr = find_page("fgg", ["magic resistance"], hi=300)
    two_e_meta = {
        "thac0_vs_hd": ("soft", "thac0_2e.json brackets + plus-bump",
                        [cache_page("fgg", 27)]),
        "hp_in_hd_range": ("hard", "monster HD are d8; HP in [floor(dice+plus), ceil(8·dice+plus)], min 1",
                           [cache_page("fgg", fgg_hd)] if fgg_hd else [fgg_idx]),
        "ac_2e_range": ("soft", "2e descending AC -10..10",
                        [cache_page("fgg", int(pinned["fgg_armor_class"][1:])), fgg_idx]),
        "morale_in_range": ("soft", "2e morale 2..20",
                            [cache_page("fgg", int(pinned["fgg_morale"][1:])), fgg_idx]),
        "magic_resistance_pct": ("soft", "MR as percentage 0..100",
                                 [cache_page("fgg", fgg_mr)] if fgg_mr else [fgg_idx]),
    }
    units = [{"unit_id": f"code:lawful:{name}", "kind": "check",
              "payload": {"sev": sev, "law_basis": basis},
              "evidence_files": ev, "advisories": []}
             for name, (sev, basis, ev) in two_e_meta.items()]
    for fn, basis in ((lawful._adapt_5e_bits, "5e-bits monster JSON shape"),
                      (lawful._adapt_envelope_5e, "Mimir envelope fields.statblock (5e)"),
                      (lawful._adapt_2e, "2e statblock / envelope; G1 descriptor fallback; "
                                         "_int_coerce never guesses"),
                      (lawful.detect_shape, "shape routing; unknown shape raises")):
        units.append({"unit_id": f"code:lawful:{fn.__name__}", "kind": "adapter",
                      "payload": {"law_basis": basis, "source": src(fn)},
                      "evidence_files": [], "advisories": []})
    units.append({"unit_id": "code:tables:parse_hd_2e+thac0_expected_2e", "kind": "parser",
                  "payload": {"law_basis": "HD grammar ('12+24', '1/2', '1-1') + bracket "
                                           "walk + plus-bump + V&V F1/F2 boundary law",
                              "source": src(tables.parse_hd_2e) + src(tables.thac0_expected_2e),
                              "law_tables": {"thac0_2e": th}},
                  "evidence_files": [cache_page("fgg", 27)], "advisories": []})
    add_chunk("code-checks-2e", "code-as-law", units,
              shared={"source": checks_2e_src, "fgg_index": fgg_idx,
                      "instruction": "FG&G page hints are PROBED (may be imprecise) — "
                                     "verify via the INDEX.md chapter map + bash grep when a "
                                     "hint page looks wrong; cite the page you actually used"})

    units = [
        {"unit_id": "code:lawful:SKILL_ABILITY", "kind": "constant",
         "payload": {"law_basis": "18 skills -> abilities, identical both 5e views",
                     "value": lawful.SKILL_ABILITY},
         "evidence_files": [cache_page("srd51", int(pinned["srd51_skills_list"][1:])),
                            cache_page("srd52", int(pinned["srd52_skills_list"][1:]))],
         "advisories": []},
        {"unit_id": "code:lawful:ability_mod+mean_hp", "kind": "helper",
         "payload": {"law_basis": "(score-10)//2; exact mean of NdS±K",
                     "source": src(lawful.ability_mod) + src(lawful.mean_hp)},
         "evidence_files": [cache_page("srd51", 76), cache_page("srd52", 21)],
         "advisories": []},
        {"unit_id": "code:tables:parse_cr+VALID_CRS+cr_to_xp+cr_to_pb", "kind": "accessor",
         "payload": {"law_basis": "CR enum; XP tuple (CR0 dual); PB bracket==formula assert",
                     "source": src(tables.parse_cr) + src(tables.cr_to_xp) + src(tables.cr_to_pb)},
         "evidence_files": [cache_page("srd52", 256), cache_page("srd51", 258)],
         "advisories": []},
        {"unit_id": "code:dc+budget", "kind": "tool-law",
         "payload": {"law_basis": "DC ladder per-view citation; 2e refusal; 2024-only "
                                  "budget with LawUnavailable refusal for 2014 (KI-2)",
                     "source": src(dc_mod) + src(budget_mod)},
         "evidence_files": [cache_page("srd51", 77), cache_page("srd52", 6),
                            cache_page("srd52", 202)],
         "advisories": []},
    ]
    add_chunk("code-accessors", "code-as-law", units)

    # ---------------- Court inputs (3 files, consumed in P3) -----------------
    import sqlite3
    cx = sqlite3.connect(f"file:{(BUILD / 'mechanus' / 'rulings.db').as_posix()}?mode=ro", uri=True)
    cx.row_factory = sqlite3.Row
    led_units = []
    for r in cx.execute("SELECT * FROM rulings ORDER BY ts"):
        uid = f"ledger:{r['ruling_id']}"
        warts = [v["detail"] for v in report["violations"] if v["unit_id"] == uid]
        led_units.append({"unit_id": uid, "kind": "ruling",
                          "payload": {"docket": json.loads(r["docket"]),
                                      "row": {k: r[k] for k in ("sha", "supersedes",
                                                                "superseded_by", "law_version", "ts")}},
                          "evidence_files": [],
                          "advisories": warts + ["all cited roll_ids verified present in "
                                                 "rolls.db by integrity.py"]})
    cx.close()
    add_chunk("court-ledger", "ledger-court", led_units,
              shared={"mechanical_precheck": report["ledger"],
                      "instruction": "schema is mechanically green — judge SUBSTANCE: adopted "
                                     "candidate defensible, rejection whys real, scope/confidence/"
                                     "adjudicator sane, raw_quotes loc resolves, chains coherent. "
                                     "Historical law_version stamps are LAW (KI-10)."})

    seam_units = []
    seen_seam = {}
    for e in report["seam_truth_table"]:
        key = f"seam:{Path(e['file']).stem}:{e['line']}"
        if key in seen_seam:  # one line can match twice only if two refs share a line
            key += "b"
        seen_seam[key] = True
        cands = []
        for c in e.get("candidate_targets", []):
            row = tables.planar_law(c)
            cands.append({"law_id": c, "rule": row.get("rule") or row.get("general"),
                          "witness": row.get("witness")})
        ctx_lines = (REPO / e["file"]).read_text(encoding="utf-8").splitlines()
        lo, hi = max(0, e["line"] - 6), min(len(ctx_lines), e["line"] + 4)
        seam_units.append({"unit_id": key, "kind": "seam-ref",
                           "payload": {**e, "context": ctx_lines[lo:hi],
                                       "candidates_with_substance": cands},
                           "evidence_files": [(REPO / e["file"]).as_posix()],
                           "advisories": []})
    seam_units.append({"unit_id": "seam:mimir-plane-join", "kind": "join-check",
                       "payload": {"claim": "all 16 Great Ring plane:* nodes exist in handbook.db",
                                   "verified_by": "integrity.py u7 (no advisories emitted)"},
                       "evidence_files": [], "advisories": []})
    add_chunk("court-seam", "seam-court", seam_units,
              shared={"instruction": "Per stale/wildcard ref propose the exact re-bind, "
                                     "substance-matched to the candidate rows given (or a better "
                                     "row you find via tables. The planar-keys:* alternates must "
                                     "be REJECTED with why if the legend row wins). ALL output "
                                     "lane=sibling-proposal — Modron/Mimir files are NEVER edited "
                                     "by this audit (sibling etiquette)."})

    doc_units = []
    slug_map = {"MECHANUS.md": "mechanus-md", "vnv-report.md": "vnv", "CLAUDE.md": "claude-md"}
    for i, c in enumerate(report["doc_claims"]):
        key = re.sub(r"[^a-z0-9]+", "-", c["claim"].lower())[:40].strip("-")
        doc_units.append({"unit_id": f"doc:{slug_map[c['doc']]}:{key}", "kind": "doc-claim",
                          "payload": c,
                          "evidence_files": [(REPO / ("pipeline/mechanus/MECHANUS.md"
                                                      if c["doc"] == "MECHANUS.md"
                                                      else "build/mechanus/vnv-report.md"
                                                      if c["doc"] == "vnv-report.md"
                                                      else "CLAUDE.md")).as_posix()],
                          "advisories": []})
    add_chunk("court-doc", "doc-court", doc_units,
              shared={"instruction": "vnv-report is a HISTORICAL record — propose a dated "
                                     "ADDENDUM, never a rewrite. MECHANUS.md §7 tool table vs "
                                     "server.py live/parked sets is in scope: read "
                                     + (REPO / "pipeline/mechanus/mechanus/server.py").as_posix()})

    # ---------------- write ---------------------------------------------------
    CHUNKS.mkdir(parents=True, exist_ok=True)
    for old in CHUNKS.glob("chunk-*.json"):
        old.unlink()
    index = []
    for i, ch in enumerate(chunks, 1):
        name = f"chunk-{i:03d}-{ch['chunk']}.json"
        (CHUNKS / name).write_text(json.dumps(ch, indent=1, ensure_ascii=False),
                                   encoding="utf-8")
        n_units = sum(1 + len(u.get("sub_ids", [])) for u in ch["units"])
        index.append({"file": (CHUNKS / name).as_posix(), "slug": ch["chunk"],
                      "unit_class": ch["unit_class"], "units": n_units})

    total = len(manifest)
    (REVIEW / "manifest.json").write_text(json.dumps(
        {"total_units": total, "chunks": index, "unit_to_chunk": manifest},
        indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(chunks)} chunks, {total} units")
    for row in index:
        print(f"  {row['slug']:38s} {row['units']:4d} units  ({row['unit_class']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
