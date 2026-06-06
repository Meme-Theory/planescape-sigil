"""V&V — the Planes boxes pour (parse/planes.py + gate.pour_planes).

The law under test: curated cards, text-validated — a claim pours ONLY with page
witnesses from the box's own reflow; refusals are reported, never silent. Plus the
Pelion/Amun-Thys identity merge (one layer, two books, two names, ONE node)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "parse"))
import planes as P
import store as S
import gate as G

BUILD = HERE.parents[2] / "build"
needs_corpus = pytest.mark.skipif(
    not (BUILD / "planes-of-law/ddps-planesoflaw-ii/reflow").exists(),
    reason="planes boxes not on disk")


# ---------------------------------------------------------------- card law (unit)
def test_cards_cover_the_great_ring_minus_outlands():
    ids = {c["id"] for c in P.PLANE_CARDS}
    assert len(ids) == 16 and "plane:the-outlands" not in ids   # Player's Primer not in corpus


def test_attest_refuses_unwitnessed_claims():
    card = {"id": "plane:x", "component": "x", "book": "planes-of-law",
            "layers": [("Avalas", 1, [], None), ("Nowhereland", 2, [], None)],
            "gate_town": None, "layer_note": None, "gloss": ""}
    rep = P.attest_card(card, {1: "the cubes of Avalas drift"})
    assert rep["refused"] == ["Nowhereland"] and "Avalas" in rep["layers"]


def test_short_names_are_case_sensitive():
    card = {"id": "plane:x", "component": "x", "book": "planes-of-law",
            "layers": [("Dis", 2, [], None)], "gate_town": None,
            "layer_note": None, "gloss": ""}
    assert P.attest_card(card, {1: "this dismal distraction"})["refused"] == ["Dis"]
    assert P.attest_card(card, {1: "the iron city of Dis"})["layers"] == {"Dis": [1]}


# ---------------------------------------------------------------- integration (real boxes)
@pytest.fixture(scope="module")
def planes_store(tmp_path_factory):
    db = tmp_path_factory.mktemp("planes") / "scratch.db"
    st = S.HandbookStore(db)
    # substrate: the Places nodes the cage pour would have made
    for gid in ("plane:acheron", "plane:arcadia", "plane:baator", "plane:mechanus",
                "plane:mount-celestia", "plane:limbo", "plane:ysgard", "plane:arborea",
                "plane:pandemonium", "plane:the-abyss", "plane:the-beastlands", "plane:bytopia",
                "plane:elysium", "plane:carceri", "plane:gehenna", "plane:the-gray-waste",
                "plane:the-outlands"):
        _, name, _, sub, _, al = __import__("cage").GAZ_BY_ID[gid]
        G._admit_seed(st, {"type": "plane", "id": gid, "name": name, "edition": "2e",
                           "fields": {"subtype": sub, "aliases": al, "pages": [1]},
                           "content": name, "provenance": {"value_sources": [{"src": "in-the-cage"}],
                                                           "method": "gazetteer-attestation"},
                           "confidence": 0.95, "curated": {}, "source_sha": None}, "t", 1)
    # the In the Cage layer that Pelion must merge ONTO (the identity test)
    G._admit_seed(st, {"type": "layer", "id": "layer:amun-thys", "name": "Amun-Thys",
                       "edition": "2e", "fields": {"parent": "plane:arborea"},
                       "content": "Amun-Thys dry wastes third layer of Arborea",
                       "provenance": {"value_sources": [{"src": "in-the-cage"}],
                                      "method": "gazetteer-attestation"},
                       "confidence": 0.95, "curated": {}, "source_sha": None}, "t", 1)
    counts = G.pour_planes(st)
    return st, counts


@needs_corpus
def test_all_claims_attest_zero_refused(planes_store):
    st, (npl, nly, ngt, refused) = planes_store
    assert npl == 16 and refused == []
    assert nly == 56                       # every claimed layer found its witness


@needs_corpus
def test_baator_carries_its_nine(planes_store):
    st, _ = planes_store
    b = st.get("plane:baator")
    assert b["fields"]["layers"] == ["Avernus", "Dis", "Minauros", "Phlegethos", "Stygia",
                                     "Malbolge", "Maladomini", "Cania", "Nessus"]
    srcs = [s["src"] for s in b["provenance"]["value_sources"]]
    assert "in-the-cage" in srcs and "planes-of-law" in srcs       # dual-source enrich
    rels = {r["src_id"] for r in st.conn.execute(
        "SELECT src_id FROM edges WHERE rel='layer_of' AND tgt_id='plane:baator'")}
    assert len(rels) == 9 and "layer:cania" in rels


@needs_corpus
def test_pelion_amun_thys_is_one_identity(planes_store):
    """In the Cage named it Amun-Thys; Planes of Chaos names it Pelion. One node:
    the existing id keeps any portal edges pointing at the same identity."""
    st, _ = planes_store
    assert not st.exists("layer:pelion")
    n = st.get("layer:amun-thys")
    assert n["name"] == "Pelion" and n["fields"]["ordinal"] == 3
    assert "amun-thys" in n["fields"]["aliases"]
    srcs = [s["src"] for s in n["provenance"]["value_sources"]]
    assert "in-the-cage" in srcs and "planes-of-chaos" in srcs


@needs_corpus
def test_gate_town_backfill_is_attested_only(planes_store):
    st, (_, _, ngt, _) = planes_store
    # 11 here (no cage substrate): the 7 the real pour backfills + rigus/ribcage/
    # automata/hopeless, which In the Cage normally pours first. Torch gets ZERO
    # mentions in liber malevolentiae — absent like the Primer-only towns.
    assert ngt == 11
    assert st.exists("gate-town:xaos") and st.exists("gate-town:plague-mort")
    # their booklets never name these — they stay absent (Player's Primer isn't poured)
    assert not st.exists("gate-town:fortitude")
    assert not st.exists("gate-town:ecstasy")
    assert not st.exists("gate-town:curst")
    assert not st.exists("gate-town:glorium")
    assert not st.exists("gate-town:torch")
    x = st.get("gate-town:xaos")
    assert x["fields"]["pages"], "gate-town backfill ships with page witnesses"
    rels = {(r["rel"], r["tgt_id"]) for r in st.conn.execute(
        "SELECT rel, tgt_id FROM edges WHERE src_id='gate-town:xaos'")}
    assert ("gate_to", "plane:limbo") in rels
    assert ("located_in", "plane:the-outlands") in rels


@pytest.fixture(scope="module")
def realms_store(planes_store):
    st, _ = planes_store
    counts = G.pour_realms(st)
    return st, counts


@needs_corpus
def test_realms_attest_both_names_or_refuse(realms_store):
    st, (nrealm, ndeity, refused) = realms_store
    # 47/47 post-docket: Blood Tor attests (_name_rx whitespace-tolerant join),
    # Noctos' Domain REMOVED (the moon is a layer epithet, not a power's realm),
    # Glass Tarn -> Goldfire and Centerspire -> Windwrath renamed per witnesses
    # (Great Audit, Meme ADOPTED 2026-06-06)
    assert nrealm == 47 and ndeity >= 40
    assert refused == []
    assert st.exists("realm:blood-tor")
    assert st.exists("realm:goldfire") and st.exists("realm:windwrath")
    assert not st.exists("realm:noctos-domain") and not st.exists("deity:noctos")


@needs_corpus
def test_realm_chain_walks_power_to_layer(realms_store):
    """The marquee chain: Erackinor → realm_of → Moradin; located_in → Solania."""
    st, _ = realms_store
    r = st.get("realm:erackinor")
    assert r and r["fields"]["power"] == "Moradin"
    rels = {(x["rel"], x["tgt_id"]) for x in st.conn.execute(
        "SELECT rel, tgt_id FROM edges WHERE src_id='realm:erackinor'")}
    assert ("realm_of", "deity:moradin") in rels
    assert ("located_in", "layer:solania") in rels
    d = st.get("deity:moradin")
    assert d["fields"]["kind"] == "power" and "realm:erackinor" in d["fields"]["realms"]


@needs_corpus
def test_powerless_realms_carry_their_note(realms_store):
    st, _ = realms_store
    s = st.get("realm:the-spawning-stone")
    assert s and s["fields"]["power"] is None and "slaad lords" in s["fields"]["note"]
    rels = [x for x in st.conn.execute(
        "SELECT rel FROM edges WHERE src_id='realm:the-spawning-stone' AND rel='realm_of'")]
    assert rels == []                       # no power → no realm_of edge, ever
    still = st.get("realm:stillsong")
    assert still and "mysteries" in still["fields"]["note"]


@needs_corpus
def test_abyssal_lords_are_typed_honestly(realms_store):
    st, _ = realms_store
    g = st.get("deity:graz-zt")
    assert g and "quasi-power" in g["fields"]["kind"]
    k = st.get("deity:kiaransalee")
    assert k and k["fields"]["kind"] == "power"          # a true power holding Thanatos


@needs_corpus
def test_renamed_realms_use_the_texts_own_words(realms_store):
    """Cavern of Azuth + The Slime Pits pour under their ATTESTED names; the
    canonical-but-unrecoverable spellings ride as aliases only."""
    st, _ = realms_store
    assert st.exists("realm:cavern-of-azuth") and not st.exists("realm:azuth-s-cavern")
    sp = st.get("realm:the-slime-pits")
    assert sp and "shedaklah" in (sp["fields"].get("note") or "").lower() + str(sp["fields"])


@needs_corpus
def test_unlayered_planes_claim_nothing(planes_store):
    st, _ = planes_store
    mech = st.get("plane:mechanus")
    assert "layers" not in mech["fields"] and "single infinite" in mech["fields"]["layer_note"]
    limbo = st.get("plane:limbo")
    assert "layers" not in limbo["fields"]
    rows = st.conn.execute("SELECT COUNT(*) c FROM edges WHERE rel='layer_of' "
                           "AND tgt_id IN ('plane:mechanus','plane:limbo')").fetchone()
    assert rows["c"] == 0
