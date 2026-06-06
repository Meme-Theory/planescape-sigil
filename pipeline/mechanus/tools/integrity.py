"""Mechanus audit — deterministic mechanical integrity checker (Phase 0).

Runs BEFORE the review workflow (build/mechanus/review/PLAN.md): every check
here is pure arithmetic / file-existence / schema law over the law data, the
rulings ledger, the text caches, and the cross-engine seam files. Hard
violations are BUGS to fix before any agent reviews anything; advisories ride
into the chunks as review hints. Agents never re-derive what this script can
compute.

Output: build/mechanus/review/integrity-report.json
Exit:   nonzero iff any hard violation.

Read-only everywhere: DBs via sqlite file:?mode=ro URIs, no store writes, no
MCP calls. (Windows: the live servers open-close per call, so a readonly open
here never collides — never touch rulings.lock.)
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "pipeline" / "mechanus"))

from mechanus import ledger, tables  # noqa: E402
from mechanus.lawful import ABILITIES, SKILL_ABILITY, _checks_5e  # noqa: E402

BUILD = REPO / "build"
REVIEW = BUILD / "mechanus" / "review"
CACHES = {"srd51": BUILD / "mechanus" / "srd51-text",
          "srd52": BUILD / "mechanus" / "srd52-text",
          "fgg": BUILD / "mechanus" / "fgg-text"}

# component slug -> distilled book dir (mirror of tests/test_planar_law.py BOOK_DIR)
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

GREAT_RING = {
    "acheron", "arcadia", "baator", "mechanus", "mount-celestia",
    "the-abyss", "arborea", "limbo", "pandemonium", "ysgard",
    "the-beastlands", "bytopia", "elysium", "carceri", "gehenna",
    "the-gray-waste",
}
SCHOOLS = {
    "abjuration", "alteration", "conjuration-summoning", "divination",
    "enchantment-charm", "illusion-phantasm", "invocation-evocation",
    "necromancy", "wild-magic", "elemental",
}
EXPECTED_FAMILY_COUNTS = {
    "law:planar-conditions": 109, "law:planar-keys": 48, "law:seals-wards": 5,
    "law:planar-priest": 3, "law:plane-environment": 18, "law:planar-spell": 12,
    "law:cage": 4,
}
SHINGLE = 10  # the cite-only law's verbatim threshold (test_planar_law.py)

MODRON_SEAM_FILES = [
    REPO / "pipeline" / "modron" / "data" / "modifiers" / "planescape-2e.json",
    REPO / "pipeline" / "modron" / "data" / "conventions" / "2e-planescape.json",
    REPO / "pipeline" / "modron" / "data" / "rollables" / "planescape-2e.json",
]

violations: list[dict] = []
stats: dict = {}


def flag(check: str, unit_id: str, sev: str, detail: str) -> None:
    violations.append({"check": check, "unit_id": unit_id, "sev": sev, "detail": detail})


def page_path(component: str, page: int) -> Path:
    return BUILD / BOOK_DIR[component] / component / "reflow" / f"page-{page:04d}.txt"


def _norm_tokens(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


def _rule_text(row: dict) -> str:
    return (row.get("rule") or row.get("effect") or row.get("general")
            or " ".join(filter(None, (row.get("spell_keys"), row.get("power_keys"))))
            or "")


# ---------------------------------------------------------------------------
# U1 — planar law rows
# ---------------------------------------------------------------------------

def check_u1() -> dict:
    idx = tables.planar_law_index()
    fam_counts = {fam: len(ids) for fam, ids in idx.items()}
    total = sum(fam_counts.values())
    if fam_counts != EXPECTED_FAMILY_COUNTS:
        flag("u1.family_counts", "law:*", "hard",
             f"expected {EXPECTED_FAMILY_COUNTS}, got {fam_counts}")
    if total != 199:
        flag("u1.total_199", "law:*", "hard", f"planar total {total} != 199")

    seen: set[str] = set()
    ocr_rows: list[str] = []
    near_misses: list[dict] = []
    page_cache: dict[Path, str] = {}
    deltas: dict[str, Counter] = {}
    rows_by_id: dict[str, dict] = {}

    for fam in tables.PLANAR_LAW_FILES:
        for row in tables._planar_rows(fam):
            law_id = row["law_id"]
            rows_by_id[law_id] = row
            if not law_id.startswith(fam + ":"):
                flag("u1.family_prefix", law_id, "hard", f"id not under {fam}")
            if law_id in seen:
                flag("u1.id_unique", law_id, "hard", "duplicate law_id")
            seen.add(law_id)
            if not _rule_text(row).strip():
                flag("u1.rule_text", law_id, "hard", "no rule/effect text")
            wits = row.get("witness") or []
            if not wits:
                flag("u1.witness_present", law_id, "hard", "no witness")
            for w in wits:
                comp = w.get("component")
                if comp not in BOOK_DIR:
                    flag("u1.witness_component", law_id, "hard", f"unknown component {comp!r}")
                    continue
                for pg in w.get("reflow") or []:
                    if not page_path(comp, pg).exists():
                        flag("u1.witness_page_exists", law_id, "hard",
                             f"{comp} reflow p{pg}: file missing")
                printed = w.get("printed") or []
                for rf, pr in zip(w.get("reflow") or [], printed):
                    deltas.setdefault(comp, Counter())[rf - pr] += 1
            if "ocr_note" in row:
                ocr_rows.append(law_id)

    # sub-id <-> parent integrity (every :sub has a resolvable parent row)
    for law_id, row in rows_by_id.items():
        if row.get("_sub"):
            parent = law_id.rsplit(":", 1)[0]
            if parent not in rows_by_id:
                flag("u1.sub_parent", law_id, "hard", f"parent {parent} not a row")

    # plane-slug enums
    cond = tables._load("planar_conditions.json")
    if set(cond["planes"].keys()) != GREAT_RING:
        flag("u1.great_ring", "law:planar-conditions", "hard",
             f"plane set != Great Ring: {set(cond['planes']) ^ GREAT_RING}")
    for slug, row in cond["planes"].items():
        if row.get("plane") != f"plane:{slug}":
            flag("u1.plane_field", row["law_id"], "hard", f"plane field {row.get('plane')!r}")
        extra = set(row.get("schools", {})) - SCHOOLS
        if extra:
            flag("u1.school_enum", row["law_id"], "hard", f"non-canonical schools {extra}")
    for row in tables._planar_rows("law:plane-environment"):
        slug = row["law_id"].split(":")[2]
        if slug not in GREAT_RING | {"sigil", "lower-planes"}:
            flag("u1.env_slug", row["law_id"], "hard", f"bad plane slug {slug!r}")
    for row in tables._planar_rows("law:planar-spell"):
        if row.get("_sub"):
            continue
        keyed = row.get("keyed_to", "")
        if not (keyed.startswith("plane:") and keyed.split(":", 1)[1] in GREAT_RING):
            flag("u1.spell_keyed_to", row["law_id"], "hard", f"keyed_to {keyed!r}")
        for field in ("stats", "level", "class"):
            if not row.get(field):
                flag("u1.spell_fields", row["law_id"], "hard", f"missing {field}")

    # shingle law: >=10-token verbatim run = hard; 7-9 = advisory near-miss
    for law_id, row in rows_by_id.items():
        tokens = _norm_tokens(_rule_text(row))
        if len(tokens) < 7:
            continue
        for w in row.get("witness") or []:
            comp = w.get("component")
            if comp not in BOOK_DIR:
                continue
            for pg in w.get("reflow") or []:
                path = page_path(comp, pg)
                if not path.exists():
                    continue
                if path not in page_cache:
                    page_cache[path] = " ".join(_norm_tokens(path.read_text(encoding="utf-8")))
                hay = page_cache[path]
                hit_n = 0
                for n in (SHINGLE, 9, 8, 7):
                    if len(tokens) < n:
                        continue
                    if any(" ".join(tokens[i:i + n]) in hay
                           for i in range(len(tokens) - n + 1)):
                        hit_n = n
                        break
                if hit_n >= SHINGLE:
                    flag("u1.verbatim_leak", law_id, "hard",
                         f"{hit_n}-token verbatim run vs {path.name} ({comp})")
                elif hit_n:
                    near_misses.append({"unit_id": law_id, "run": hit_n,
                                        "page": f"{comp}/{path.name}"})

    mode_deltas = {comp: c.most_common(1)[0][0] for comp, c in deltas.items()}
    for comp, c in deltas.items():
        for delta, n in c.items():
            if delta != mode_deltas[comp]:
                flag("u1.page_delta_outlier", comp, "advisory",
                     f"reflow-printed delta {delta} x{n} (component mode {mode_deltas[comp]}) — transposed-cite candidates")

    stats["u1"] = {"family_counts": fam_counts, "total": total,
                   "ocr_note_rows": ocr_rows, "near_misses": near_misses}
    return {"component_page_deltas": mode_deltas, "ocr_note_rows": ocr_rows,
            "near_misses": near_misses}


# ---------------------------------------------------------------------------
# U2 — SRD-cited tables
# ---------------------------------------------------------------------------

def check_u2() -> None:
    xp = tables._load("xp_by_cr.json")["xp"]
    want_keys = {str(c) if c.denominator == 1 else str(c) for c in
                 (Fraction(k) if "/" not in k else Fraction(*map(int, k.split("/")))
                  for k in xp)}
    valid_keys = {("%d" % c.numerator) if c.denominator == 1 else f"{c.numerator}/{c.denominator}"
                  for c in tables.VALID_CRS}
    if set(xp.keys()) != valid_keys:
        flag("u2.xp_keys", "srd:xp_by_cr", "hard",
             f"keys != VALID_CRS: {set(xp) ^ valid_keys}")
    if xp.get("0") != [0, 10]:
        flag("u2.cr0_dual", "srd:xp_by_cr:cr-0", "hard", f"CR0 {xp.get('0')!r} != [0, 10]")
    ordered = sorted(xp.items(), key=lambda kv: Fraction(*map(int, kv[0].split("/"))) if "/" in kv[0] else Fraction(kv[0]))
    prev = -1
    for k, v in ordered:
        hi = max(v) if isinstance(v, list) else v
        if hi < prev:
            flag("u2.xp_monotonic", f"srd:xp_by_cr:cr-{k}", "advisory", f"XP {hi} < prior {prev}")
        prev = hi

    pb = tables._load("pb_by_cr.json")
    brackets = pb["brackets"]
    if brackets[0][0] != 0 or brackets[-1][1] != 30:
        flag("u2.pb_cover", "srd:pb_by_cr", "hard", "brackets don't cover 0..30")
    for i, (lo, hi, val) in enumerate(brackets):
        if i and lo != brackets[i - 1][1] + 1:
            flag("u2.pb_contiguous", f"srd:pb_by_cr:{lo}-{hi}", "hard", "gap/overlap with prior bracket")
        for cr in (lo, hi):
            formula = max(2, math.ceil(Fraction(cr) / 4) + 1)
            if val != formula:
                flag("u2.pb_formula", f"srd:pb_by_cr:{lo}-{hi}", "hard",
                     f"bracket pb {val} != formula {formula} at CR {cr}")

    ladder = tables.dc_ladder()
    if [r["dc"] for r in ladder] != [5, 10, 15, 20, 25, 30]:
        flag("u2.dc_ladder", "srd:dc_ladder", "hard", f"rungs {[r['dc'] for r in ladder]}")
    for view in tables.VIEWS_5E:
        if not tables.dc_source(view):
            flag("u2.dc_source", "srd:dc_ladder", "hard", f"no _source for {view}")

    bud = tables._load("xp_budget_2024.json")
    bpc = bud["budget_per_character"]
    if set(bpc.keys()) != {str(n) for n in range(1, 21)}:
        flag("u2.budget_levels", "srd:xp_budget", "hard", "levels != 1..20")
    prev_row = [0, 0, 0]
    for lvl in range(1, 21):
        row = bpc[str(lvl)]
        if len(row) != 3 or row != sorted(row):
            flag("u2.budget_row", f"srd:xp_budget:L{lvl}", "hard", f"row {row} not low<=mod<=high")
        if any(row[i] < prev_row[i] for i in range(3)):
            flag("u2.budget_monotonic", f"srd:xp_budget:L{lvl}", "advisory",
                 f"decreases vs L{lvl - 1}: {prev_row} -> {row}")
        prev_row = row

    cond = tables._load("conditions.json")
    for view in tables.VIEWS_5E:
        if len(cond["conditions"][view]) != 15:
            flag("u2.conditions_count", f"srd:conditions:{view}", "hard",
                 f"{len(cond['conditions'][view])} != 15")
    if len(cond["senses"]) != 4:
        flag("u2.senses_count", "srd:conditions:senses", "hard", f"{cond['senses']}")

    attr = tables._load("attribution.json")
    for view in tables.VIEWS_5E:
        block = attr.get(view, "")
        if "System Reference Document" not in block or \
           "creativecommons.org/licenses/by/4.0/legalcode" not in block:
            flag("u2.attribution", f"srd:attribution:{view}", "hard", "block malformed")


# ---------------------------------------------------------------------------
# U2b — RAW anchor probes + page pinning
# ---------------------------------------------------------------------------

def _cache_page(cache: str, n: int) -> str:
    p = CACHES[cache] / f"p{n:04d}.txt"
    if not p.exists():
        return ""
    return re.sub(r"\s+", " ", p.read_text(encoding="utf-8"))


ANCHORS = [
    ("srd52", 256, ["Experience Points by Challenge", "Proficiency Bonus by Challenge"]),
    ("srd51", 258, ["Experience Points by Challenge"]),
    ("srd51", 77, ["Typical Difficulty Classes"]),
    ("srd52", 6, ["Typical Difficulty Classes"]),
    ("srd52", 202, ["XP Budget"]),
    ("srd51", 325, ["Arcana +18"]),
    ("srd51", 319, ["Deception +7"]),
    ("srd51", 401, ["Religion +4"]),
    ("fgg", 27, ["Table 3.3"]),
]

PIN_PROBES = {
    # needles must pin the DEFINITION pages, not the first spell-text page that
    # happens to name three conditions (docket C4: old needles hit p0137/p0055)
    "srd51_conditions_appendix": ("srd51", ["Appendix PH-A", "Blinded", "Charmed", "Deafened"]),
    "srd52_conditions": ("srd52", ["Blinded [Condition]"]),
    "srd51_ability_mods": ("srd51", ["Ability Scores and Modifiers"]),
    "srd52_ability_mods": ("srd52", ["Ability Scores and Modifiers"]),
    "srd51_skills_list": ("srd51", ["Acrobatics", "Sleight of Hand", "Survival"]),
    "srd52_skills_list": ("srd52", ["Acrobatics", "Sleight of Hand", "Survival"]),
    "fgg_morale": ("fgg", ["Morale", "2-20"]),
    "fgg_armor_class": ("fgg", ["Armor Class", "descending"]),
}


def check_anchors() -> tuple[list[dict], dict]:
    probes = []
    for cache, page, needles in ANCHORS:
        hay = _cache_page(cache, page)
        found = all(n.lower() in hay.lower() for n in needles)
        probes.append({"anchor": " + ".join(needles),
                       "file": (CACHES[cache] / f"p{page:04d}.txt").as_posix(),
                       "found": found})
        if not found:
            flag("u2.anchor_probe", f"{cache}:p{page:04d}", "hard",
                 f"heading(s) {needles} not on cited page — citation bug")

    pinned: dict[str, str | None] = {}
    page_texts: dict[str, list[tuple[int, str]]] = {}
    for cache in CACHES:
        pages = sorted(CACHES[cache].glob("p*.txt"))
        page_texts[cache] = [(int(p.stem[1:]), re.sub(r"\s+", " ", p.read_text(encoding="utf-8")).lower())
                             for p in pages]
    for key, (cache, needles) in PIN_PROBES.items():
        hit = next((f"p{n:04d}" for n, txt in page_texts[cache]
                    if all(nd.lower() in txt for nd in needles)), None)
        pinned[key] = hit
        if hit is None:
            flag("u2.pin_probe", key, "advisory",
                 f"no {cache} page holds all of {needles} — chunk falls back to bash-grep instructions")
    return probes, pinned


# ---------------------------------------------------------------------------
# U3 — FG&G THAC0 brackets
# ---------------------------------------------------------------------------

def check_u3() -> None:
    data = tables._load("thac0_2e.json")
    br = data["brackets"]
    if br[0][:2] != [0, 0.99] or br[-1][1] != 99:
        flag("u3.bracket_cover", "fgg:thac0", "hard", f"coverage {br[0]}..{br[-1]}")
    for i in range(1, len(br)):
        if br[i][0] != math.floor(br[i - 1][1]) + 1:
            flag("u3.bracket_contiguous", f"fgg:thac0:{br[i][0]}", "hard",
                 f"{br[i - 1]} -> {br[i]}")
        if br[i][2] >= br[i - 1][2]:
            flag("u3.thac0_descending", f"fgg:thac0:{br[i][0]}", "hard",
                 f"THAC0 {br[i][2]} !< {br[i - 1][2]}")
    spot = {"1-1": 20, "1/2": 20, "1": 19, "6+3": 13, "8+8": 11, "13": 7, "17": 3}
    for hd, want in spot.items():
        got = tables.thac0_expected_2e(hd)
        if got != want:
            flag("u3.spot_vector", f"fgg:thac0:{hd}", "hard", f"{hd} -> {got}, expected {want}")


# ---------------------------------------------------------------------------
# U4 — known_deviations
# ---------------------------------------------------------------------------

def check_u4() -> None:
    dev = json.loads((tables.LAW_DIR / "known_deviations.json").read_text(encoding="utf-8"))
    for name, entries in dev["attested_deviations"].items():
        for e in entries:
            for field in ("check", "printed", "witness", "reason"):
                if field not in e:
                    flag("u4.waiver_fields", f"dev:{name}", "hard", f"missing {field}")
            m = re.search(r"SRD 5\.1 p\.(\d+)", e.get("witness", ""))
            if not m:
                flag("u4.waiver_witness", f"dev:{name}", "hard",
                     f"witness not SRD 5.1 page-cited: {e.get('witness')!r}")
            elif not (CACHES["srd51"] / f"p{int(m.group(1)):04d}.txt").exists():
                flag("u4.waiver_page", f"dev:{name}", "hard", f"page file p{m.group(1)} missing")
    if set(dev["upstream_5e_bits_bugs"]["halved_xp"]) != \
       {"dretch", "riding-horse", "deep-gnome-svirfneblin", "brass-dragon-wyrmling"}:
        flag("u4.halved_xp", "dev:halved_xp", "hard", "halved-XP set drifted")
    if not dev.get("policy"):
        flag("u4.policy", "dev:policy", "hard", "policy line missing")


# ---------------------------------------------------------------------------
# U5 — code-as-law cross-consistency
# ---------------------------------------------------------------------------

def check_u5() -> None:
    if len(SKILL_ABILITY) != 18 or not set(SKILL_ABILITY.values()) <= set(ABILITIES):
        flag("u5.skill_ability", "code:lawful:SKILL_ABILITY", "hard",
             f"{len(SKILL_ABILITY)} keys, values {set(SKILL_ABILITY.values())}")
    # conditions enum round-trip through the check's normalization
    for view in tables.VIEWS_5E:
        known = tables.conditions(view)
        for name in known:
            idx = name.lower().replace(" ", "-")
            stat = {"abilities": {a: 10 for a in ABILITIES}, "cr": None, "pb": None,
                    "xp": None, "hp": None, "hp_roll": None, "ac": None, "speeds": {},
                    "passive_perception": None, "saves": {}, "skills": {},
                    "condition_immunities": [idx], "special_senses": {}}
            checks = {c["name"]: c for c in _checks_5e(stat, view)}
            if checks["conditions_known"]["result"] != "pass":
                flag("u5.condition_roundtrip", f"srd:conditions:{view}:{idx}", "hard",
                     f"{name!r} fails its own enum check as index {idx!r}")
    # law_version recompute (independent of tables' lru_cache)
    import hashlib
    h = hashlib.sha256()
    for p in sorted(tables.LAW_DIR.glob("*.json")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    if h.hexdigest()[:16] != tables.law_version():
        flag("u5.law_version", "code:tables:law_version", "hard", "recompute mismatch")


# ---------------------------------------------------------------------------
# U6 — rulings ledger
# ---------------------------------------------------------------------------

def check_u6() -> dict:
    import sqlite3
    db = BUILD / "mechanus" / "rulings.db"
    cx = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    cx.row_factory = sqlite3.Row
    rows = cx.execute("SELECT * FROM rulings").fetchall()
    n_fts = cx.execute("SELECT count(*) FROM rulings_fts").fetchone()[0]
    roll_ids_needed = set()
    by_id = {r["ruling_id"]: r for r in rows}
    if len(rows) != 6:
        flag("u6.count", "ledger:*", "advisory", f"{len(rows)} rulings (expected 6 at plan time)")
    if n_fts != len(rows):
        flag("u6.fts_sync", "ledger:*", "hard", f"fts {n_fts} != rulings {len(rows)}")
    for r in rows:
        d = json.loads(r["docket"])
        uid = f"ledger:{r['ruling_id']}"
        try:
            ledger.validate_docket(d)
        except ledger.DocketError as e:
            flag("u6.docket_law", uid, "hard", str(e))
        # sha law: record_ruling computes the content-address BEFORE
        # setdefault("kind") — a docket submitted without explicit kind hashes
        # without the key. Verify the submission-time sha; the as-stored
        # non-reproducibility is a real wart, recorded for the ledger court.
        as_stored = ledger._canonical_sha(d)
        minus_default_kind = (ledger._canonical_sha({k: v for k, v in d.items() if k != "kind"})
                              if d.get("kind") == "ruling" else None)
        if as_stored != r["sha"] and minus_default_kind != r["sha"]:
            flag("u6.sha", uid, "hard", "stored sha != content-address under either kind form")
        elif as_stored != r["sha"]:
            flag("u6.sha_kind_wart", uid, "advisory",
                 "sha only recomputable with kind removed — record_ruling hashes before "
                 "setdefault('kind'); stored docket is not sha-reproducible as-stored "
                 "(ledger.py:151-154 ordering; code-fix lane candidate)")
        if r["supersedes"]:
            tgt = by_id.get(r["supersedes"])
            if tgt is None:
                flag("u6.chain", uid, "hard", f"supersedes {r['supersedes']} missing")
            elif tgt["superseded_by"] != r["ruling_id"]:
                flag("u6.chain_symmetric", uid, "hard",
                     f"{r['supersedes']}.superseded_by = {tgt['superseded_by']!r}")
        if not re.fullmatch(r"[0-9a-f]{16}", r["law_version"] or ""):
            flag("u6.law_version_stamp", uid, "hard", f"stamp {r['law_version']!r}")
        roll_ids_needed.update(d.get("rolls") or [])
    # acyclic: walk every chain
    for rid in by_id:
        seen = set()
        cur = rid
        while cur and by_id.get(cur) and by_id[cur]["superseded_by"]:
            if cur in seen:
                flag("u6.chain_cycle", f"ledger:{rid}", "hard", "supersedes cycle")
                break
            seen.add(cur)
            cur = by_id[cur]["superseded_by"]
    cx.close()

    rolls_db = BUILD / "modron" / "rolls.db"
    cx = sqlite3.connect(f"file:{rolls_db.as_posix()}?mode=ro", uri=True)
    have = {r[0] for r in cx.execute("SELECT roll_id FROM rolls")}
    cx.close()
    missing = roll_ids_needed - have
    for rid in missing:
        flag("u6.roll_exists", f"roll:{rid}", "hard", "docket-cited roll_id absent from rolls.db")
    return {"rulings": len(rows), "cited_rolls": sorted(roll_ids_needed),
            "law_version_stamps": sorted({r["law_version"] for r in rows})}


# ---------------------------------------------------------------------------
# U7 — cross-engine seams (truth table; never hard)
# ---------------------------------------------------------------------------

LAW_REF = re.compile(r"law:[a-z0-9:*\-]+[a-z0-9*]")


def check_u7() -> list[dict]:
    table = []
    for f in MODRON_SEAM_FILES:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for raw in LAW_REF.findall(line):
                entry = {"file": f.relative_to(REPO).as_posix(), "line": i, "raw_ref": raw,
                         "wildcard": "*" in raw, "resolves": False, "candidate_targets": []}
                if not entry["wildcard"]:
                    try:
                        tables.planar_law(raw)
                        entry["resolves"] = True
                    except KeyError:
                        pass
                table.append(entry)

    # candidate re-bind targets, substance-known (for the seam court)
    known_targets = {
        "law:planar-conditions:*": ["law:planar-conditions:general:school-alteration-legend"],
        "law:planar-conditions:*:spell-keys": [
            "law:planar-conditions:general:school-alteration-legend"],
        "law:planar-conditions:limbo:*": ["law:planar-conditions:limbo"],
        "law:plane-env:pandemonium:madness": [
            "law:plane-environment:pandemonium:wind-madness"],
        "law:plane-env:gray-waste:wasting": [
            "law:plane-environment:the-gray-waste:wasting-sickness"],
    }
    for entry in table:
        for pat, cands in known_targets.items():
            if entry["raw_ref"] == pat or entry["raw_ref"].startswith(pat):
                live = [c for c in cands if _resolvable(c)]
                entry["candidate_targets"] = live
                for c in cands:
                    if not _resolvable(c):
                        flag("u7.candidate_missing", c, "advisory",
                             f"planned re-bind target does not resolve (for {entry['raw_ref']})")

    import sqlite3
    cx = sqlite3.connect(f"file:{(BUILD / 'mimir' / 'handbook.db').as_posix()}?mode=ro", uri=True)
    have = {r[0] for r in cx.execute("SELECT id FROM entities WHERE type='plane'")}
    cx.close()
    missing = {f"plane:{s}" for s in GREAT_RING} - have
    for p in missing:
        flag("u7.mimir_plane_node", p, "advisory", "Great Ring plane node absent from handbook.db")
    stats["u7"] = {"refs": len(table), "unresolved": sum(1 for e in table if not e["resolves"])}
    return table


def _resolvable(law_id: str) -> bool:
    try:
        tables.planar_law(law_id)
        return True
    except KeyError:
        return False


# ---------------------------------------------------------------------------
# U8 — doc claims vs mechanical actuals (informational; feeds the doc court)
# ---------------------------------------------------------------------------

def check_u8() -> list[dict]:
    claims = []

    def claim(doc: str, what: str, stated, actual) -> None:
        claims.append({"doc": doc, "claim": what, "stated": stated, "actual": actual,
                       "matches": stated == actual})

    mech_md = (REPO / "pipeline" / "mechanus" / "MECHANUS.md").read_text(encoding="utf-8")
    lv = tables.law_version()
    m = re.search(r"law_version ([0-9a-f]{16})", mech_md)
    claim("MECHANUS.md", "header law_version literal", m.group(1) if m else None, lv)
    claim("MECHANUS.md", "199 law ids across 7 families",
          bool(re.search(r"199 law ids across 7 families", mech_md)),
          sum(len(v) for v in tables.planar_law_index().values()) == 199)
    m = re.search(r"(\d+) tests \+ 20-check stdio smoke", mech_md)
    try:
        out = subprocess.run(
            ["py", "-3.13", "-m", "pytest", "tests/", "--collect-only", "-q"],
            cwd=REPO / "pipeline" / "mechanus", capture_output=True, text=True, timeout=120)
        collected = re.search(r"(\d+) tests? collected", out.stdout)
        n_tests = int(collected.group(1)) if collected else None
    except Exception:
        n_tests = None
    claim("MECHANUS.md", "test count", int(m.group(1)) if m else None, n_tests)
    s10 = mech_md.split("## 10.", 1)[-1].split("## 11", 1)[0]
    n_rows = len(re.findall(r"^\| 20\d\d-", s10, re.M))
    claims.append({"doc": "MECHANUS.md", "claim": "§10 decision rows (measured, no stated claim)",
                   "stated": None, "actual": n_rows, "matches": True})

    vnv = (BUILD / "mechanus" / "vnv-report.md").read_text(encoding="utf-8")
    m = re.search(r"law_version ([0-9a-f]{16})", vnv)
    claim("vnv-report.md", "law_version (historical — addendum business, not a rewrite)",
          m.group(1) if m else None, lv)
    m = re.search(r"\*\*(\d+) passed\*\*", vnv)
    claim("vnv-report.md", "suite count at V&V time", int(m.group(1)) if m else None, n_tests)
    claim("vnv-report.md", "47/47 probes claim present", bool(re.search(r"47/47", vnv)), True)

    claude_md = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    claim("CLAUDE.md", "47/47 live probes cited", "47/47" in claude_md, True)
    claim("CLAUDE.md", "334-monster fleet audit cited", "334-monster" in claude_md, True)
    claim("CLAUDE.md", "planar law: 7 families/199 ids cited",
          bool(re.search(r"7 page-cited law families \(199 ids\)", claude_md)), True)
    return claims


# ---------------------------------------------------------------------------

def main() -> int:
    u1_extra = check_u1()
    check_u2()
    anchor_probes, pinned = check_anchors()
    check_u3()
    check_u4()
    check_u5()
    u6_stats = check_u6()
    seam_table = check_u7()
    doc_claims = check_u8()

    hard = [v for v in violations if v["sev"] == "hard"]
    report = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "law_version": tables.law_version(),
        "counts": {"planar_by_family": stats["u1"]["family_counts"],
                   "planar_total": stats["u1"]["total"]},
        "violations": violations,
        "anchor_probes": anchor_probes,
        "pinned_pages": pinned,
        "component_page_deltas": u1_extra["component_page_deltas"],
        "ocr_note_rows": u1_extra["ocr_note_rows"],
        "near_misses": u1_extra["near_misses"],
        "ledger": u6_stats,
        "seam_truth_table": seam_table,
        "doc_claims": doc_claims,
        "stats": {"hard": len(hard), "advisory": len(violations) - len(hard)},
    }
    REVIEW.mkdir(parents=True, exist_ok=True)
    out = REVIEW / "integrity-report.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"integrity: {len(hard)} hard, {len(violations) - len(hard)} advisory -> {out}")
    for v in hard:
        print(f"  HARD {v['check']} {v['unit_id']}: {v['detail']}")
    return 1 if hard else 0


if __name__ == "__main__":
    sys.exit(main())
