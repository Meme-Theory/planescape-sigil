"""The rulings ledger — guarded writes, docket law, supersedes chains."""

import pytest

from mechanus.ledger import Ledger, DocketError, validate_docket


def docket(**over):
    d = {
        "ruling_id": "rul:tofw:grapple-while-invisible:001",
        "question": "Does Invisible impose disadvantage on the grapple escape check?",
        "view": "5e-2014",
        "scope": "campaign:tofw",
        "ladder_path": ["house:none", "raw:srd5.1:grappled+invisible", "interp"],
        "raw_quotes": [{"text": "…an invisible creature…", "loc": "SRD 5.1 Appendix PH-A", "sha": "abc"}],
        "candidates": [
            {"position": "yes — attack-roll-only reading", "fate": "rejected",
             "why": "escape is a check, not an attack"},
            {"position": "no — checks unaffected by Invisible", "fate": "ADOPTED"},
        ],
        "confidence": 0.9,
        "adjudicator": "auto",
    }
    d.update(over)
    return d


@pytest.fixture()
def ledger(tmp_path):
    return Ledger(tmp_path / "rulings.db")


def test_record_and_get(ledger):
    out = ledger.record_ruling(docket())
    assert out["sha"] and out["ts"] and out["law_version"]
    got = ledger.get("rul:tofw:grapple-while-invisible:001")
    assert got["question"].startswith("Does Invisible")


def test_identical_docket_rejected_by_sha(ledger):
    ledger.record_ruling(docket())
    with pytest.raises(DocketError, match="identical docket"):
        ledger.record_ruling(docket(ruling_id="rul:tofw:grapple-while-invisible:002"))


def test_same_id_rejected(ledger):
    ledger.record_ruling(docket())
    with pytest.raises(DocketError, match="overrule"):
        ledger.record_ruling(docket(confidence=0.8))


def test_overrule_chains_and_resolves_to_head(ledger):
    ledger.record_ruling(docket())
    new = docket(ruling_id="rul:tofw:grapple-while-invisible:002",
                 candidates=[
                     {"position": "yes — attack-roll-only reading", "fate": "ADOPTED"},
                     {"position": "no — checks unaffected", "fate": "rejected",
                      "why": "table prefers the stricter reading after session 3"}],
                 adjudicator="human:ryan", confidence=0.95)
    ledger.overrule("rul:tofw:grapple-while-invisible:001", new)

    head = ledger.get("rul:tofw:grapple-while-invisible:001")  # follows the chain
    assert head["ruling_id"].endswith(":002")
    assert head["adjudicator"] == "human:ryan"
    raw = ledger.get("rul:tofw:grapple-while-invisible:001", follow=False)
    assert raw["adjudicator"] == "auto"  # history preserved
    assert ledger.chain("rul:tofw:grapple-while-invisible:002") == [
        "rul:tofw:grapple-while-invisible:001", "rul:tofw:grapple-while-invisible:002"]


def test_cannot_supersede_twice(ledger):
    ledger.record_ruling(docket())
    ledger.overrule("rul:tofw:grapple-while-invisible:001",
                    docket(ruling_id="rul:tofw:grapple-while-invisible:002", confidence=0.95))
    with pytest.raises(DocketError, match="already superseded"):
        ledger.overrule("rul:tofw:grapple-while-invisible:001",
                        docket(ruling_id="rul:tofw:grapple-while-invisible:003", confidence=0.5))


def test_precedents_fts_and_scope(ledger):
    ledger.record_ruling(docket())
    ledger.record_ruling(docket(
        ruling_id="rul:global:flanking:001", scope="global", view="5e-2014",
        question="Does flanking grant advantage?", confidence=0.7,
        candidates=[{"position": "optional rule, off by default", "fate": "ADOPTED"},
                    {"position": "always on", "fate": "rejected", "why": "variant not adopted"}]))
    hits = ledger.precedents("invisible", scope="campaign:tofw")
    assert len(hits) == 1 and "Invisible" in hits[0]["question"]
    hits = ledger.precedents("flanking", scope="campaign:tofw")  # global rulings reach every scope
    assert len(hits) == 1
    assert ledger.precedents("druids") == []


def test_precedents_hyphenated_topic_quote_fallback(ledger):
    """F4 (build/family/integration-tests.md): a hyphenated topic (`spell-like`)
    hits FTS5 column-filter syntax and crashed precedents with OperationalError.
    The fix is Mimir's quote-fallback (store.py search): raw MATCH first, on
    OperationalError retry with each term quoted + OR-joined."""
    ledger.record_ruling(docket(
        ruling_id="rul:global:spell-like-abilities:001", scope="global",
        question="Do spell-like abilities require components?", confidence=0.8,
        candidates=[{"position": "no components — innate", "fate": "ADOPTED"},
                    {"position": "as the written spell", "fate": "rejected",
                     "why": "innate reading holds for 2e"}]))
    hits = ledger.precedents("spell-like")  # raw MATCH raises; the fallback must serve
    assert len(hits) == 1 and hits[0]["ruling_id"] == "rul:global:spell-like-abilities:001"
    assert ledger.precedents("nonsense-topic") == []  # fallback path, clean miss


def test_precedents_resolve_overrules(ledger):
    ledger.record_ruling(docket())
    ledger.overrule("rul:tofw:grapple-while-invisible:001",
                    docket(ruling_id="rul:tofw:grapple-while-invisible:002", confidence=0.95))
    hits = ledger.precedents("invisible")
    assert len(hits) == 1 and hits[0]["ruling_id"].endswith(":002")


def test_house_rules_kind(ledger):
    ledger.record_ruling(docket(
        ruling_id="rul:tofw:house:max-hp-first-level:001", kind="house-rule",
        question="Max HP at first level?", confidence=1.0, adjudicator="human:ryan",
        ladder_path=["house:declared"],
        candidates=[{"position": "yes, table standard", "fate": "ADOPTED"},
                    {"position": "roll it", "fate": "rejected", "why": "table voted"}]))
    hr = ledger.house_rules(scope="campaign:tofw")
    assert len(hr) == 1 and hr[0]["kind"] == "house-rule"
    assert ledger.house_rules(scope="campaign:other") == []


def test_rolls_cite_modron_ids(ledger):
    out = ledger.record_ruling(docket(
        ruling_id="rul:tofw:loot-split:001", question="Random loot recipient?",
        rolls=["roll:tofw-s3:000042"], confidence=1.0,
        ladder_path=["house:none", "raw:none", "fiat:randomized"],
        candidates=[{"position": "d4 among the party", "fate": "ADOPTED"},
                    {"position": "DM picks", "fate": "rejected", "why": "table prefers dice"}]))
    assert out["rolls"] == ["roll:tofw-s3:000042"]


# --- docket law, enforced ---

@pytest.mark.parametrize("breaker,msg", [
    (dict(ruling_id="grapple"), "ruling_id"),
    (dict(question="  "), "question"),
    (dict(scope="party"), "scope"),
    (dict(ladder_path=[]), "ladder_path"),
    (dict(candidates=[]), "candidates"),
    (dict(confidence=1.5), "confidence"),
    (dict(adjudicator=""), "adjudicator"),
    (dict(rolls=[42]), "rolls"),
    (dict(raw_quotes=[{"text": "words"}]), "loc"),
])
def test_docket_schema_forced(breaker, msg):
    with pytest.raises(DocketError, match=msg):
        validate_docket(docket(**breaker))


def test_no_adopted_candidate_rejected():
    d = docket(candidates=[{"position": "a", "fate": "rejected", "why": "b"}])
    with pytest.raises(DocketError, match="ADOPTED"):
        validate_docket(d)


def test_two_adopted_rejected():
    d = docket(candidates=[{"position": "a", "fate": "ADOPTED"},
                           {"position": "b", "fate": "ADOPTED"}])
    with pytest.raises(DocketError, match="exactly one"):
        validate_docket(d)


def test_rejected_without_why_rejected():
    d = docket(candidates=[{"position": "a", "fate": "ADOPTED"},
                           {"position": "b", "fate": "rejected"}])
    with pytest.raises(DocketError, match="loser preservation"):
        validate_docket(d)

def test_kindless_docket_sha_reproducible_as_stored(ledger):
    """Correction docket C5 (2026-06-06): kind defaults BEFORE the content-address,
    so a docket submitted WITHOUT kind is sha-reproducible from its stored row.
    Pre-fix rows (rul:vnv:akin-mr-vs-spell-like:*) recompute with kind removed —
    that historical derivation stays valid; this pins the post-fix law."""
    import json
    import sqlite3
    from mechanus.ledger import _canonical_sha
    d = docket()
    assert "kind" not in d  # the fixture exercises the kind-less path
    out = ledger.record_ruling(d)
    cx = sqlite3.connect(ledger.db_path)
    row = cx.execute("SELECT docket, sha, kind FROM rulings WHERE ruling_id = ?",
                     (out["ruling_id"],)).fetchone()
    cx.close()
    stored = json.loads(row[0])
    assert stored["kind"] == "ruling" == row[2]
    assert _canonical_sha(stored) == row[1]  # as-stored recompute, no key surgery
