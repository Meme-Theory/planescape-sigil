"""V&V — the seven-dim round: boxset (proxy/sect/settlement/saying/adventure),
creature (MC parser), timeline (Hellbound chronology)."""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "parse"))
import boxset as B
import monstrous as MC
import store as S
import gate as G

BUILD = HERE.parents[2] / "build"
needs_corpus = pytest.mark.skipif(
    not (BUILD / "planes-of-law/ddps-planesoflaw-i/reflow").exists(),
    reason="boxes not on disk")


# ---------------------------------------------------------------- unit law
def test_proxy_sweep_requires_named_binding():
    ok = B.sweep_proxies("There's the Sphinx, a shared proxy of Ra and Osiris; brave.",
                         page=1, component="x")
    assert ok[0]["name"] == "Sphinx" and ok[0]["powers"] == ["Ra", "Osiris"]
    assert B.sweep_proxies("lesser proxies of the chaotic powers wander", page=1,
                           component="x") == []


def test_saying_letterspace_soup_queues():
    text = "x\n+ H E C H A N + ,\nR 0 + G U +\n— BARMY SOD\n"
    ss = B.sweep_sayings(text, page=1, component="x")
    assert ss and ss[0]["confidence"] < B._THETA_SAYING


def test_saying_prose_attribution_rejected():
    text = "GOOD QUOTE LINE\n— an excerpt from the journal of someone\n"
    assert B.sweep_sayings(text, page=1, component="x") == []


def test_mc_parser_formats():
    # format C: label / value alternation with a wrapped label
    fc = ("BURAQ\n\nCLIMATE/TERRAIN: Elysium (Upper Planes)\nFREQUENCY:\nUncommon (rare)\n"
          "ORGANIZATION:\nHerd or solitary\nACTIVITY\nCYCLE:\nDay\nDIET:\nHerbivore\n"
          "INTELLIGENCE:\nHigh (13-14)\nTREASURE:\nNil\nALIG MENT:\nNeutral good\n"
          "ARMOR CLASS:\n4\nMOVEMENT:\n18\nHIT DICE:\n5+5\nTHAC0:\n15\nXP VALUE:\n2,000\n")
    r = MC.parse_page(fc, page=6, component="x")
    assert r["ok"], r["problems"]
    assert r["fields"]["alignment"] == "Neutral good"
    assert r["fields"]["hit_dice"] == "5+5" and r["fields"]["armor_class"] == "4"
    assert r["name"] == "Buraq"


def test_timeline_cards_sequenced_and_phrased():
    seqs = [c[2] for c in B.TIMELINE_CARDS]
    assert seqs == sorted(seqs)
    assert B.attest_phrase("ships of chaos", {16: "the Ships of Chaos wait"}) == [16]


# ---------------------------------------------------------------- integration
@pytest.fixture(scope="module")
def seven_store(tmp_path_factory):
    db = tmp_path_factory.mktemp("seven") / "scratch.db"
    st = S.HandbookStore(db)
    # substrate: planes/layers for located_in, the Blood War for part_of, a faction
    import cage as C
    for gid in ("plane:mount-celestia", "plane:mechanus", "plane:ysgard",
                "plane:pandemonium", "plane:the-beastlands", "plane:limbo"):
        _, name, _, sub, _, al = C.GAZ_BY_ID[gid]
        G._loc_seed(st, gid.replace("plane:", "location:x-"), name, "x", name, 1.0, "t") \
            if False else None
        G._admit_seed(st, {"type": "plane", "id": gid, "name": name, "edition": "2e",
                           "fields": {}, "content": name,
                           "provenance": {"value_sources": [{"src": "t"}], "method": "seed"},
                           "confidence": 0.9, "curated": {}, "source_sha": None}, "t", 1)
    for lid, nm, parent in (("layer:ocanthus", "Ocanthus", "plane:acheron"),
                            ("layer:avalas", "Avalas", "plane:acheron"),
                            ("layer:thuldanin", "Thuldanin", "plane:acheron"),
                            ("layer:avernus", "Avernus", "plane:baator"),
                            ("layer:minauros", "Minauros", "plane:baator"),
                            ("layer:phlegethon", "Phlegethon", "plane:pandemonium"),
                            ("layer:cocytus", "Cocytus", "plane:pandemonium")):
        G._admit_seed(st, {"type": "layer", "id": lid, "name": nm, "edition": "2e",
                           "fields": {"parent": parent}, "content": nm,
                           "provenance": {"value_sources": [{"src": "t"}], "method": "seed"},
                           "confidence": 0.9, "curated": {}, "source_sha": None}, "t", 1)
    G._admit_seed(st, {"type": "event", "id": "event:the-blood-war", "name": "The Blood War",
                       "edition": "2e", "fields": {}, "content": "the Blood War",
                       "provenance": {"value_sources": [{"src": "t"}], "method": "seed"},
                       "confidence": 1.0, "curated": {}, "source_sha": None}, "t", 1)
    bx = G.pour_boxset(st)
    ncre, ncre_q = G.pour_creatures(st)
    ntl = G.pour_timeline(st)
    return st, bx, (ncre, ncre_q), ntl


@needs_corpus
def test_boxset_counts(seven_store):
    st, bx, _, _ = seven_store
    assert bx["proxy"] >= 4 and bx["sect"] == 6 and bx["settlement"] == 11
    assert bx["saying"] >= 25 and bx["adventure"] >= 28


@needs_corpus
def test_proxy_serves_power(seven_store):
    st, _, _, _ = seven_store
    sphinx = st.get("proxy:sphinx")
    assert sphinx and sphinx["fields"]["powers"] == ["Ra", "Osiris"]
    rels = {r["tgt_id"] for r in st.conn.execute(
        "SELECT tgt_id FROM edges WHERE src_id='proxy:sphinx' AND rel='serves'")}
    assert rels == {"deity:ra", "deity:osiris"}
    assert st.get("deity:ra")["fields"]["via"] == "proxy-sweep"


@needs_corpus
def test_settlement_binds_layer(seven_store):
    st, _, _, _ = seven_store
    z = st.get("settlement:zoronor")
    assert z and z["fields"]["pages"]
    rels = {(r["rel"], r["tgt_id"]) for r in st.conn.execute(
        "SELECT rel, tgt_id FROM edges WHERE src_id='settlement:zoronor'")}
    assert ("located_in", "layer:ocanthus") in rels


@needs_corpus
def test_creatures_admit_or_queue_by_name(seven_store):
    st, _, (ncre, ncre_q), _ = seven_store
    # 22 admitted / 3 queued: the Great Audit court recovered 6 mc-parse creatures
    # via CREATURE_CURATIONS (Delphon, Ethyk, Warden Beast, Baernaloth, Achaierai,
    # Bladeling); the 3 confirm-rejects stay honestly queued (Meme-adopted 2026-06-06)
    assert ncre >= 20 and ncre_q == 3
    assert st.exists("creature:planes-of-law:bladeling")          # recovered + renamed
    assert st.exists("creature:planes-of-conflict:delphon")
    kyton = st.get("creature:planes-of-law:kyton")                # renamed off 'Kytedn'
    assert kyton and kyton["fields"]["special_attacks"] == "Chain snag"
    rows = st.conn.execute("SELECT COUNT(*) c FROM quarantine WHERE reason='mc-parse'").fetchone()
    assert rows["c"] == ncre_q
    # a clean creature carries the MC fields
    rows = st.conn.execute("SELECT id FROM entities WHERE type='creature' LIMIT 1").fetchone()
    c = st.get(rows["id"])
    assert "armor_class" in c["fields"] and "alignment" in c["fields"]


@needs_corpus
def test_timeline_sequence_edges(seven_store):
    st, _, _, ntl = seven_store
    assert ntl == 4
    rels = [(r["src_id"], r["tgt_id"]) for r in st.conn.execute(
        "SELECT src_id, tgt_id FROM edges WHERE rel='before' ORDER BY src_id")]
    assert ("event:the-coming-of-the-baernaloths",
            "event:the-spawning-of-the-yugoloths") in rels
    part = {r["src_id"] for r in st.conn.execute(
        "SELECT src_id FROM edges WHERE rel='part_of' AND tgt_id='event:the-blood-war'")}
    assert "event:the-ships-of-chaos" in part
