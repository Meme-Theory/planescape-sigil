"""Planar law pack (rule-effect handoff §M) — schema law, resolution, honesty.

Two corpus-backed tests (witness pages exist; no verbatim leak) run only when
the distilled build/ tree is present — they enforce the cite-only lane in code,
not vibes: every row must point at a real page, and no row may carry a long
verbatim run of the scan's text.
"""

import re
from pathlib import Path

import pytest

from mechanus import tables

REPO = Path(__file__).resolve().parents[3]
BUILD = REPO / "build"

# component slug -> distilled book dir under build/
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
    "planescape-2634-inner-planes": "the-inner-planes",
}

INNER_PLANES = {
    "elemental-air", "elemental-earth", "elemental-fire", "elemental-water",
    "energy-positive", "energy-negative",
    "para-ice", "para-magma", "para-ooze", "para-smoke",
    "quasi-lightning", "quasi-mineral", "quasi-radiance", "quasi-steam",
    "quasi-ash", "quasi-dust", "quasi-salt", "quasi-vacuum",
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


def _all_rows():
    for fam in tables.PLANAR_LAW_FILES:
        for row in tables._planar_rows(fam):
            yield fam, row


def _rule_text(row) -> str:
    """A row's governing prose, ALL of it — conditions plane rows carry
    `general`, keys plane rows the two key fields, inner-survival plane rows
    `conditions`, the pockets row a `per_type` map; everything else
    `rule`/`effect`. Concatenated so the shingle test sweeps every field."""
    extra = " ".join(str(v) for v in (row.get("per_type") or {}).values())
    return " ".join(filter(None, (
        row.get("rule"), row.get("effect"), row.get("general"),
        row.get("conditions"), row.get("spell_keys"), row.get("power_keys"),
        extra)))


# --- schema law -------------------------------------------------------------

def test_ids_unique_and_family_prefixed():
    seen = set()
    for fam, row in _all_rows():
        law_id = row["law_id"]
        assert law_id.startswith(fam + ":"), law_id
        assert law_id not in seen, f"duplicate law_id: {law_id}"
        seen.add(law_id)
    assert len(seen) == sum(len(ids) for ids in tables.planar_law_index().values())


def test_every_row_ruled_and_witnessed():
    for fam, row in _all_rows():
        law_id = row["law_id"]
        assert _rule_text(row).strip(), f"{law_id} has no rule/effect text"
        witnesses = row.get("witness")
        assert witnesses, f"{law_id} has no witness — an answer without a citation doesn't ship"
        for w in witnesses:
            assert w["component"] in BOOK_DIR, f"{law_id}: unknown component {w['component']}"
            assert w["reflow"] and all(isinstance(p, int) and p > 0 for p in w["reflow"]), \
                f"{law_id}: bad reflow pages {w}"


def test_resolution_round_trip():
    for fam, ids in tables.planar_law_index().items():
        for law_id in ids:
            row = tables.planar_law(law_id)
            assert row["family"] == fam and row["law_id"] == law_id
    with pytest.raises(KeyError):
        tables.planar_law("law:planar-conditions:krynn:phlogiston")
    with pytest.raises(KeyError):
        tables.planar_law("law:no-such-family:x")


# --- coverage law -----------------------------------------------------------

def test_great_ring_conditions_coverage():
    doc = tables._load("planar_conditions.json")
    assert set(doc["planes"].keys()) == GREAT_RING
    for slug, row in doc["planes"].items():
        assert row["plane"] == f"plane:{slug}"
        assert row["law_id"] == f"law:planar-conditions:{slug}"
        assert len(row["schools"]) >= 4, f"{slug}: suspiciously thin school law"
        assert set(row["schools"]) <= SCHOOLS, \
            f"{slug}: non-canonical school keys {set(row['schools']) - SCHOOLS}"


def test_keys_sub_ids_for_every_plane():
    for slug in GREAT_RING:
        for kind in ("spell", "power"):
            row = tables.planar_law(f"law:planar-keys:{slug}:{kind}")
            assert row["rule"].strip()


def test_plane_lookup():
    for slug in GREAT_RING:
        ids = {r["law_id"] for r in tables.planar_law_for_plane(f"plane:{slug}")}
        assert f"law:planar-conditions:{slug}" in ids, slug
        assert f"law:planar-keys:{slug}" in ids, slug
        assert not any(":spell" in i or i.endswith(":power") for i in ids
                       if i.startswith("law:planar-keys:")), "sub-rows leaked into plane lookup"
    sigil = {r["law_id"] for r in tables.planar_law_for_plane("sigil")}
    assert {"law:cage:execution", "law:cage:harmonium-patrol",
            "law:cage:plane-shift-ban", "law:cage:garnish",
            "law:seals-wards:sigil-portal-law", "law:seals-wards:surelock"} <= sigil
    assert tables.planar_law_for_plane("plane:the-outlands") == []  # not in these boxes
    assert tables.planar_law_for_plane("krynn") == []


def test_environment_rows_carry_their_plane_in_id():
    for row in tables._planar_rows("law:plane-environment"):
        slug = row["law_id"].split(":")[2]
        assert slug in GREAT_RING | {"sigil", "lower-planes"}, row["law_id"]


def test_spells_keyed_to_planes():
    for row in tables._planar_rows("law:planar-spell"):
        assert row["keyed_to"].startswith("plane:"), row["law_id"]
        assert row["keyed_to"].split(":", 1)[1] in GREAT_RING, row["law_id"]
        assert row.get("stats"), f"{row['law_id']} lacks a stat block"
        assert row.get("level"), row["law_id"]


def test_inner_survival_coverage():
    """M7 (handoff §M7-UNPARK, Q6): all 18 inner planes profiled, general
    topics present, hazard sub-ids resolve, witnessed prohibitions carried."""
    doc = tables._load("inner_survival.json")
    assert set(doc["planes"].keys()) == INNER_PLANES
    for slug, row in doc["planes"].items():
        assert row["plane"] == f"plane:{slug}"
        assert row["law_id"] == f"law:inner-survival:{slug}"
        assert row.get("hazards"), f"{slug}: no hazards distilled"
    gen = {r["law_id"] for r in doc["general"]}
    assert {"law:inner-survival:general:elemental-pockets",
            "law:inner-survival:general:elemental-guides",
            "law:inner-survival:general:magic-use",
            "law:inner-survival:general:school-alterations-legend",
            "law:inner-survival:general:priest-level-loss",
            "law:inner-survival:general:item-plus-loss"} <= gen
    # hazard sub-id grain (the XR-3 join): exact rows resolve with their dice
    heat = tables.planar_law("law:inner-survival:elemental-fire:heat")
    assert heat["_sub"] and "6d10" in heat["rule"]
    veins = tables.planar_law("law:inner-survival:quasi-salt:crystal-veins")
    assert "2d10" in veins["rule"]
    # plane lookup reaches survival rows (sub-rows stay folded)
    ids = {r["law_id"] for r in tables.planar_law_for_plane("plane:quasi-vacuum")}
    assert "law:inner-survival:quasi-vacuum" in ids
    assert "law:inner-survival:general:elemental-pockets" in ids
    assert not any(i.count(":") == 3 and i.startswith("law:inner-survival:quasi-")
                   for i in ids), "hazard sub-rows leaked into plane lookup"
    # chapter-head absolute prohibitions, witnessed
    assert tables.planar_law("law:inner-survival:elemental-water")["prohibition"] == "fire"
    assert tables.planar_law("law:inner-survival:quasi-vacuum")["prohibition"] == "air"
    # Great Ring untouched by this pour
    assert tables.planar_law_for_plane("plane:the-outlands") == []


def test_law_version_includes_planar_files():
    files = {p.name for p in tables.LAW_DIR.glob("*.json")}
    assert set(tables.PLANAR_LAW_FILES.values()) <= files
    assert re.fullmatch(r"[0-9a-f]{16}", tables.law_version())


# --- corpus-backed honesty (cite-only lane, enforced) ------------------------

corpus = pytest.mark.skipif(not BUILD.exists(),
                            reason="distilled corpus (build/) not present")


def _page_path(component: str, page: int) -> Path:
    return BUILD / BOOK_DIR[component] / component / "reflow" / f"page-{page:04d}.txt"


@corpus
def test_witness_pages_exist_on_disk():
    missing = []
    for fam, row in _all_rows():
        for w in row.get("witness", []):
            for page in w["reflow"]:
                if not _page_path(w["component"], page).exists():
                    missing.append((row["law_id"], w["component"], page))
    assert not missing, f"witnessed pages missing from corpus: {missing}"


def _norm_tokens(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).split()


SHINGLE = 10  # tokens — long enough that organic overlap (spell names, dice) stays under it


@corpus
def test_no_verbatim_leak():
    """No 10-token run of any rule may appear verbatim in its witnessed pages.

    The official scans are cite-only (R4 / CLAUDE.md data law): rows must be
    paraphrase. Mechanical facts (names, numbers, dice) survive normalization
    as short runs; a 10-token verbatim shingle means prose was copied.
    """
    leaks = []
    page_cache: dict[Path, str] = {}
    for fam, row in _all_rows():
        # sub-rows are checked too — conditions sub-rows carry the per-school
        # prose that the parent's `general` text does not.
        tokens = _norm_tokens(_rule_text(row))
        if len(tokens) < SHINGLE:
            continue
        shingles = {" ".join(tokens[i:i + SHINGLE]) for i in range(len(tokens) - SHINGLE + 1)}
        for w in row.get("witness", []):
            for page in w["reflow"]:
                path = _page_path(w["component"], page)
                if path not in page_cache:
                    page_cache[path] = " ".join(_norm_tokens(path.read_text(encoding="utf-8")))
                hay = page_cache[path]
                for sh in shingles:
                    if sh in hay:
                        leaks.append((row["law_id"], str(path.name), sh))
                        break
    assert not leaks, "verbatim runs found (reword these rows): " + repr(leaks)
