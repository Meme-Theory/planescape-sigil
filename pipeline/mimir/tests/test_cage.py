"""V&V — In the Cage extraction (parse/cage.py) + the gate's cage/Places/portal pours.

The unit probes pin the OCR-decode law the book forced (smallcaps carnage, wrap joins,
fallback boundaries, the negation guard). The integration probes run the REAL reflow
through a scratch store and pin the pour invariants: dual-source merge, verified-or-
absent quarantine, witnessed portals, attested-only Places.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                 # store / gate
sys.path.insert(0, str(HERE.parents[1] / "parse"))   # cage gear-house
import cage as C
import store as S
import gate as G

REFLOW = HERE.parents[2] / "build/in-the-cage-a-guide-to-sigil/ddps-inthecage/reflow"


# ---------------------------------------------------------------- decode law
def test_decode_smallcaps_carnage():
    assert C.head_score("• SCRA+CH WAtt •", "Scratch Wall") > 0.7        # tt = LL
    assert C.head_score("StAGS •", "Slags") > 0.62                       # t = l
    assert C.head_score("DALY'S • cempeuND •", "Ealy's Compound") > 0.62  # e = O
    assert C.head_score("THE UBIQUI + 8US WAYFARER", "Ubiquitous Wayfarer") > 0.62
    assert C.head_score("F0R+UNE'S • WHEEL •", "Fortune's Wheel") > 0.62
    assert C.head_score("B0++LE 8t JUG", "Bottle & Jug") > 0.55          # 8t = &


def test_em_digraphs_decode_to_M():
    assert "MARK" in C.decode_heading("NIGH+ IIIARKJ+").upper().replace(" ", "")[5:]
    assert C.decode_heading("fflAXim").upper().startswith("MAXI")


def test_prose_line_is_not_a_heading():
    assert C.head_score("he walked into Fortune's Wheel carrying a purse", "Fortune's Wheel") == 0.0
    assert not C.is_headingish("The common room is called the Dragon Bar, a chamber.")


def test_bullet_line_is_heading_regardless_of_case():
    assert C.is_headingish("• cempeuND •")


# ---------------------------------------------------------------- segmentation law
FIX = {
    12: "intro\nF0R+UNE'S\n• WHEEL •\nThe tavern where high-ups duel.\nMeme (Order #1)\n",
    13: "GOLDEN BARIAUR INN\nA fine inn with a shifting portal.\n",
    14: "prose continues here for the lost entry's page\nmore\n",
}
ROSTER3 = [("Fortune's Wheel", 10, "Lady's Ward", "tavern", "site"),
           ("Golden Bariaur Inn", 11, "Lady's Ward", "inn", "site"),
           ("Lost Entry", 12, "Lady's Ward", "shop", "site")]


def test_fallback_boundary_caps_at_page_end_never_zeroes_neighbors():
    entries, missing = C.segment(FIX, ROSTER3, offset=2)
    assert missing == ["Lost Entry"]
    gb = next(e for e in entries if e["name"] == "Golden Bariaur Inn")
    assert "fine inn" in gb["body"]
    # the lost entry's page may bleed into the neighbor (≤1 page), but is bounded
    assert gb["end"][0] == 14


def test_watermark_variants_are_furniture():
    assert C._FURNITURE.match("Meme (Order #52159161)")
    assert C._FURNITURE.match("Ryan Berry (Order #52159161)")
    assert not C._FURNITURE.match("Jeremo keeps a great secret (Order of the Planes)")


# ---------------------------------------------------------------- sweep law
def test_negation_guard_holds_the_wayfarer():
    neg = C.sweep_portals("Its portals lead to the planes of the Great Ring, not to the "
                          "gate-towns of the Outlands.", page=57, src_id="x", src_name="X")
    dests = {c["dest"] for c in neg}
    assert "cosmology:the-great-ring" in dests and "plane:the-outlands" not in dests


def test_clause_pairing_binds_nearest_src():
    pool = {"golden bariaur": "loc:gb", "the ditch": "loc:ditch"}
    fm = C.sweep_portals("A shifting portal to the Abyss has been known to appear in the "
                         "Golden Bariaur, and the Ditch is said to lead to the dry wastes "
                         "of Amun-Thys in the third layer of Arborea.", page=9, src_pool=pool)
    by = {c["dest"]: c["src"] for c in fm}
    assert by["plane:the-abyss"] == "loc:gb" and by["layer:amun-thys"] == "loc:ditch"


def test_layer_suppresses_parent_plane_in_same_clause():
    hits = [c["dest"] for c in C.sweep_portals(
        "a portal leading to Amun-Thys in the third layer of Arborea.", page=1,
        src_id="x", src_name="X")]
    assert hits == ["layer:amun-thys"]


def test_one_way_ooze_form():
    oz = C.sweep_portals("It's a one-way portal from the Hive to the Paraelemental Plane "
                         "of Ooze.", page=8, src_pool={"the hive": "loc:hive-ward"})
    c = next(x for x in oz if x["dest"] == "plane:para-ooze")
    assert c["form"] == "one-way" and c["src"] == "loc:hive-ward"


def test_portal_curations_shape():
    for (src, dest), cure in C.PORTAL_CURATIONS.items():
        assert src.startswith("location:") and cure.startswith("location:")
        assert ":" in dest


# ---------------------------------------------------------------- integration (real reflow)
needs_corpus = pytest.mark.skipif(not REFLOW.exists(), reason="reflow corpus not on disk")


@pytest.fixture(scope="module")
def cage_store(tmp_path_factory):
    db = tmp_path_factory.mktemp("cage") / "scratch.db"
    st = S.HandbookStore(db)
    G._loc_seed(st, "location:sigil", "Sigil", "city", "Sigil hub", 1.0, "setting")
    for w in ("Lady's Ward", "Lower Ward", "Hive Ward", "Clerk's Ward", "Market Ward",
              "Guildhall Ward"):
        G._loc_seed(st, f"location:sigil:{S.slug(w)}", w, "ward", f"{w} ward", 1.0, "setting")
    for nm in ("Fortune's Wheel", "The Shattered Temple", "The Styx Oarsman",
               "The Civic Festhall", "The Gatehouse", "The Mortuary", "The Face of Gith",
               "The White Casket", "Great Foundry", "Hall of Records", "City Court",
               "Prison", "The Palace of the Jester", "The Slags", "Hive"):
        G._loc_seed(st, f"location:sigil:{S.slug(nm)}", nm, "site", f"{nm} site", 0.9, "uncaged")
    counts = G.pour_cage(st)
    return st, counts


@needs_corpus
def test_pour_merges_never_collide(cage_store):
    st, counts = cage_store
    # all 15 seeded merge targets merge — the Shattered Temple now RECOVERS via its
    # witnessed ENTRY_CURATIONS span (Great Audit, Meme-adopted 2026-06-06)
    assert counts["merged"] == 15 and counts["new"] >= 25
    fw = st.get("location:sigil:fortune-s-wheel")
    srcs = [s["src"] for s in fw["provenance"]["value_sources"]]
    assert "uncaged" in srcs and "in-the-cage" in srcs          # dual-source, one node
    assert "[In the Cage p36]" in fw["content"]


@needs_corpus
def test_expected_absent_is_quarantined_not_guessed(cage_store):
    st, counts = cage_store
    # every EXPECTED_ABSENT name now carries a witnessed ENTRY_CURATIONS recovery
    # (Great Audit court, all 10 promote-with-fix) — the queue drains to zero, and the
    # recovered entries POUR. If a curation's anchors ever fail, the name re-queues.
    assert counts["absent"] == 0
    assert st.conn.execute("SELECT 1 FROM quarantine WHERE reason='cage-head-lost'").fetchone() is None
    for lid in ("location:sigil:golden-bell", "location:sigil:green-mill",
                "location:sigil:bones-of-the-night", "location:sigil:tower-of-the-wyrm"):
        assert st.exists(lid), lid                               # recovered = admitted
    armory = st.get("location:sigil:armory")                     # dual-source merge target
    assert "in-the-cage" in [x["src"] for x in armory["provenance"]["value_sources"]]


@needs_corpus
def test_places_are_attested_only(cage_store):
    st, _ = cage_store
    assert st.exists("plane:the-abyss") and st.exists("cosmology:the-great-ring")
    assert not st.exists("plane:bytopia")                       # in the gazetteer, NOT in the book
    assert not st.exists("gate-town:curst")
    ab = st.get("plane:the-abyss")
    assert ab["fields"]["pages"], "a Places node ships only with page witnesses"


@needs_corpus
def test_places_structural_edges(cage_store):
    st, _ = cage_store
    rels = {(r["rel"], r["src_id"], r["tgt_id"]) for r in
            st.conn.execute("SELECT rel, src_id, tgt_id FROM edges")}
    assert ("layer_of", "layer:amun-thys", "plane:arborea") in rels
    assert ("gate_to", "gate-town:ribcage", "plane:baator") in rels
    assert ("located_in", "gate-town:ribcage", "plane:the-outlands") in rels
    assert ("part_of", "plane:the-abyss", "cosmology:the-great-ring") in rels
    assert ("hub_of", "location:sigil", "cosmology:the-great-ring") in rels
    assert ("part_of", "plane:the-outlands", "cosmology:the-great-ring") not in rels


@needs_corpus
def test_portals_carry_witness_and_edges(cage_store):
    st, counts = cage_store
    assert counts["portals"] >= 20
    p = st.get("portal:sigil:ditch--amun-thys")
    assert p["fields"]["form"] == ["shifting"] and "Amun-Thys" in p["fields"]["witness"]
    rels = {(r["rel"], r["tgt_id"]) for r in
            st.conn.execute("SELECT rel, tgt_id FROM edges WHERE src_id=?", (p["id"],))}
    assert ("opens_from", "location:sigil:ditch") in rels
    assert ("connects_to", "layer:amun-thys") in rels


@needs_corpus
def test_portal_curation_rebinds_the_jester(cage_store):
    st, _ = cage_store
    assert st.exists("portal:sigil:the-palace-of-the-jester--ysgard")
    assert not st.exists("portal:sigil:prison--ysgard")
    p = st.get("portal:sigil:the-palace-of-the-jester--ysgard")
    assert "curation" in p["provenance"]["method"]


@needs_corpus
def test_unbound_portals_queue_for_review(cage_store):
    st, counts = cage_store
    assert counts["portals_queued"] >= 5
    rows = st.conn.execute("SELECT COUNT(*) c FROM quarantine "
                           "WHERE reason IN ('portal-review','portal-rejected')").fetchone()
    assert rows["c"] == counts["portals_queued"]


@needs_corpus
def test_adjudication_promotes_with_override(cage_store):
    """The review pass (2026-06-06): promoted candidates become portal nodes even
    below θ / unbound, carrying the human ruling; class-portals disclose src_class."""
    st, _ = cage_store
    gym = st.get("portal:sigil:great-gymnasium--elysium")          # was 0.50 < θ
    assert gym and "adjudication" in gym["provenance"]["method"]
    assert gym["curated"].get("adjudication")
    mort = st.get("portal:sigil:the-mortuary--the-inner-planes")   # comma-list rescue
    assert mort and "nexus" in mort["fields"]["src_class"]
    air = st.get("portal:sigil:sigil--elemental-air")              # city-level class portal
    assert air and "air-supply" in air["fields"]["src_class"]


@needs_corpus
def test_adjudication_rejects_are_recorded_not_dropped(cage_store):
    """Rejected candidates stay in quarantine under portal-rejected with the why —
    the illustrative shifting-pattern example and the defunct Baator arch."""
    st, _ = cage_store
    row = st.conn.execute("SELECT docket, reason FROM quarantine "
                          "WHERE id LIKE '%--mount-celestia'").fetchone()
    assert row and row["reason"] == "portal-rejected"
    import json as _j
    assert "illustrative" in _j.loads(row["docket"])["checks"][0]["detail"]
    assert not st.exists("portal:sigil:unbound--plane:baator")
    baator = st.conn.execute("SELECT reason FROM quarantine WHERE id LIKE '%review-unbound--baator'").fetchone()
    assert baator and baator["reason"] == "portal-rejected"
