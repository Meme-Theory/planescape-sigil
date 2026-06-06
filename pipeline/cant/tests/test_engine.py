"""Engine contract tests. Run from pipeline/cant/: py -3.13 -m pytest tests/ -q

Defect-pin discipline (the family's V&V law): every defect caught live gets a
probe here — D1 double-address, D2 suggest_terms attested-bonus leak, D3 (gears)
degenerate snippet. Plus the standing contracts: determinism, lane honesty
(model door shut without a key), store notes that tell the truth.
"""
import json
import os
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from cant import ENGINE_VERSION
from cant.engine import DENSITY, Engine
from cant.gears import Matcher, candidate_compounds, needle_rx, normalize, snippet


@pytest.fixture(scope="module")
def eng():
    return Engine()


# ---------------------------------------------------------------------------- gears
def test_word_match_inflects_and_bounds():
    m = Matcher({"term": "berk"})
    assert m.hit(normalize("Pike it, berk!"))
    assert m.hit(normalize("those berks"))
    assert m.hit(normalize("a berk's jink"))
    assert not m.hit(normalize("berserker"))
    assert Matcher({"term": "barmy"}).hit(normalize("the barmies"))


def test_phrase_policy_hard_edges():
    m = Matcher({"term": "blood", "match": "phrase", "phrases": ["a blood", "real blood"]})
    assert m.hit(normalize("she's a blood"))
    assert not m.hit(normalize("a bloodbath"))
    assert not m.hit(normalize("blood on the floor"))


def test_none_policy_strict_vs_loose():
    m = Matcher({"term": "case", "match": "none"})
    assert not m.hit(normalize("in that case"))
    found, loose = m.find(normalize("a tidy case in the Ward"), loose=True)
    assert found and loose


def test_hyphen_space_equivalence_and_curly():
    assert Matcher({"term": "bone-box"}).hit(normalize("his bone box"))
    m = Matcher({"term": "give 'em the laugh", "match": "phrase",
                 "phrases": ["give 'em the laugh"]})
    assert m.hit(normalize("she'll give ’em the laugh"))


def test_candidates_only_unknown_compounds():
    known = {normalize("bone-box")}
    assert candidate_compounds("bone-box and razor-claw", known) == ["razor-claw"]


def test_snippet_degenerate_content_still_yields():        # D3 pin
    rx = needle_rx("the dark of", inflect=False)
    s = snippet("the dark of it.", rx)
    assert s and "dark of it" in s


# ---------------------------------------------------------------------------- engine: transmute
def test_transmute_substitutes_core_terms(eng):
    r = eng.transmute("The thief stole my money.", density="street")
    street = r["candidates"][0]
    assert street["density"] == "street"
    assert "jink" in street["text"]
    assert "knight of the" in street["text"]
    assert any(a["rule"] == "money" for a in street["applied"])


def test_transmute_deterministic(eng):
    a = eng.transmute("Hello! The police arrested the thief.", density="heavy", attitude="hostile")
    b = eng.transmute("Hello! The police arrested the thief.", density="heavy", attitude="hostile")
    assert a["candidates"] == b["candidates"]              # same ask, same answer — no dice here


def test_transmute_density_ladder(eng):
    r = eng.transmute("That's crazy — never trust the guards.", density="light")
    by = {c["density"]: c["text"] for c in r["candidates"]}
    assert set(by) == set(DENSITY)
    # 'never' → 'when the Lady speaks' sleeps below heavy
    assert "when the lady speaks" not in by["light"].lower()
    assert "when the lady speaks" not in by["street"].lower()


def test_single_address_law(eng):                          # D1 pin, tightened v2 (D12)
    r = eng.transmute("Hello! Tell me about the secret plan, friend — I promise the money is real.",
                      density="street", attitude="friendly")
    import re as _re
    for c in r["candidates"]:
        addrs = len(_re.findall(r"\b(?:cutter|berk|basher|cobber|sod)\b", c["text"], _re.I))
        assert addrs <= 1, c["text"]                       # the friend→cutter vocative IS the address
        assert "{addr}" not in c["text"] and "\x00" not in c["text"]


def test_transmute_validates_inputs(eng):
    with pytest.raises(ValueError):
        eng.transmute("")
    with pytest.raises(ValueError):
        eng.transmute("x", density="soaked")
    with pytest.raises(ValueError):
        eng.transmute("x", attitude="murderous")
    with pytest.raises(ValueError):
        eng.transmute("x", register="falsetto")
    with pytest.raises(ValueError):
        eng.transmute("x", method="prayer")


def test_transmute_carries_engine_version_and_store_note(eng):
    r = eng.transmute("Good day.")
    assert r["engine_version"] == ENGINE_VERSION
    assert r["store"]["state"] in ("COMPILED", "STALE", "LEXICON-ONLY")


def test_model_door_shut_without_key(eng, monkeypatch):
    for env in ("CANT_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    r = eng.transmute("Tell me the truth.", method="model")
    assert r["method"] == "rule"                           # door shut → rule witness stands
    assert "refused" in r["model_door"]
    assert "how_to_enable" in r["model_door"]


# ---------------------------------------------------------------------------- engine: decode
def test_decode_glosses_and_flags_loose(eng):
    r = eng.decode("Pike it, berk — the chant's dark and this case smells of jink.")
    terms = {h["term"]: h["loose"] for h in r["hits"]}
    assert terms.get("pike it") is False
    assert terms.get("berk") is False
    assert terms.get("jink") is False
    assert terms.get("case") is True                       # loose collision, flagged
    assert "[a fool]" in r["glossed"]


def test_decode_phrase_headword_loose(eng):                # smoke catch pin
    r = eng.decode("No jink, no chant.")
    hits = {h["term"]: h["loose"] for h in r["hits"]}
    assert hits.get("jink") is False
    assert hits.get("the chant") is True                   # bare headword, flagged ?


def test_decode_longest_match_wins(eng):
    r = eng.decode("He's a knight of the post, sure as Sigil.")
    terms = [h["term"] for h in r["hits"]]
    assert "knight of the post" in terms
    assert "sure as sigil" in terms


# ---------------------------------------------------------------------------- engine: suggest/examples/info
def test_suggest_terms_relevance_only(eng):                # D2 pin
    r = eng.suggest_terms("kill death murder")
    terms = [t["term"] for t in r["terms"]]
    assert "dead-book" in terms
    assert "addle-cove" not in terms                       # attested bonus must not qualify
    assert all(t["attested"] is not None for t in r["terms"])


def test_suggest_terms_filters(eng):
    r = eng.suggest_terms("money", tier="core")
    assert all(t["tier"] == "core" for t in r["terms"])
    assert "jink" in [t["term"] for t in r["terms"]]


def test_examples_by_register_and_term(eng):
    if not eng.voice_lines():
        pytest.skip("no compiled store — lexicon-only world")
    r = eng.examples(register="stern", limit=5)
    assert all(ln["register"] == "stern" for ln in r["lines"])
    r2 = eng.examples(term="jink")
    assert all("jink" in ln["terms"] for ln in r2["lines"])


def test_info_shape(eng):
    info = eng.info()
    assert info["engine_version"] == ENGINE_VERSION
    assert info["lexicon"]["terms"] > 300
    assert info["rewrites"]["templates"] >= 15
    assert info["model_door"]["enabled"] in (False, True)
    assert set(info["densities"]) == set(DENSITY)


def test_lexicon_data_law():
    """Every lexicon entry honors the schema the engine trusts."""
    lex = json.loads((HERE / "data" / "lexicon.json").read_text(encoding="utf-8"))
    seen = set()
    for e in lex["terms"]:
        assert e["term"] and e["def"] and e["cat"] and e["tier"] in ("core", "ext"), e
        assert e["src"], f"{e['term']} cites no source"
        assert e["term"] not in seen, f"duplicate term {e['term']}"
        seen.add(e["term"])
        if e.get("match") == "phrase":
            assert e.get("phrases") or e.get("variants"), \
                f"{e['term']}: phrase policy with nothing to match"


# ---------------------------------------------------------------------------- dabus handoff (D11)
@pytest.fixture()
def voices_dir(tmp_path):
    """A miniature dabus casting world: one pack with grave + an alias, one cast."""
    (tmp_path / "speakers.toml").write_text(
        '[speakers]\n"npc:test:akin" = "fakevoice"\n', encoding="utf-8")
    (tmp_path / "fakevoice.toml").write_text(
        'ref_audio = "x.wav"\nref_text = "y"\n'
        '[voices.grave]\nref_audio = "g.wav"\nref_text = "z"\n'
        '[register_aliases]\nstern = "grave"\n', encoding="utf-8")
    return tmp_path


def test_voiceover_explicit_voice_tags_register(voices_dir):
    e = Engine(voices_dir=voices_dir)
    r = e.voiceover("Be careful, friend.", voice="fakevoice", register="grave")
    assert r["speakable"]["tool"] == "speak"
    assert r["speakable"]["args"]["voice"] == "fakevoice"
    assert r["speakable"]["args"]["text"].startswith("[grave] ")
    assert r["line"] in r["speakable"]["args"]["text"]
    assert r["casting"]["pack_found"] is True


def test_voiceover_npc_cast_via_speakers_toml(voices_dir):
    e = Engine(voices_dir=voices_dir)
    r = e.voiceover("Hello.", npc="npc:test:akin")
    assert r["speakable"]["args"]["voice"] == "fakevoice"
    assert "speakers.toml cast" in r["casting"]["how"]


def test_voiceover_uncast_npc_refuses_speakable(voices_dir):
    e = Engine(voices_dir=voices_dir)
    r = e.voiceover("Hello.", npc="npc:test:stranger")
    assert r["speakable"] is None                          # cant never guesses a voice
    assert "UNCAST" in r["casting"]["why"]
    assert r["line"]                                       # the cant line still serves


def test_voiceover_register_alias_routes(voices_dir):
    e = Engine(voices_dir=voices_dir)
    r = e.voiceover("Watch yourself.", voice="fakevoice", register="stern")
    assert r["speakable"]["args"]["text"].startswith("[grave] ")   # stern→grave via alias
    assert "alias" in r["casting"]["register_note"]


def test_voiceover_register_falls_back_to_main(voices_dir):
    e = Engine(voices_dir=voices_dir)
    r = e.voiceover("How droll.", voice="fakevoice", register="amused")
    assert r["speakable"]["args"]["text"].startswith("[main] ")
    assert "falling back" in r["casting"]["register_note"]


def test_voiceover_unknown_pack_emits_unvalidated(voices_dir):
    e = Engine(voices_dir=voices_dir)
    r = e.voiceover("Hello.", voice="ghostpack")
    assert r["speakable"]["args"]["voice"] == "ghostpack"  # dabus's refusal stays dabus's
    assert r["casting"]["pack_found"] is False


def test_voiceover_voice_and_npc_is_ambiguous(voices_dir):
    e = Engine(voices_dir=voices_dir)
    with pytest.raises(ValueError):
        e.voiceover("Hello.", voice="fakevoice", npc="npc:test:akin")


def test_voiceover_no_voice_no_npc(voices_dir):
    e = Engine(voices_dir=voices_dir)
    r = e.voiceover("Hello.")
    assert r["speakable"] is None and "no voice given" in r["casting"]["why"]


def test_voiceover_deterministic(voices_dir):
    e = Engine(voices_dir=voices_dir)
    a = e.voiceover("The thief stole my money.", voice="fakevoice", density="heavy")
    b = e.voiceover("The thief stole my money.", voice="fakevoice", density="heavy")
    assert a["speakable"] == b["speakable"]                # same ask ⇒ same WAV upstream


@pytest.mark.skipif(not (HERE.parent.parent / "tools" / "voices" / "grace.toml").exists(),
                    reason="real dabus packs not provisioned")
def test_voiceover_live_grace_pack():
    e = Engine()
    r = e.voiceover("Be careful — someone betrayed us.", npc="npc:uncaged:a-kin",
                    register="stern", attitude="friendly")
    assert r["speakable"]["args"]["voice"] == "grace"      # the standing A'kin cast
    assert r["speakable"]["args"]["text"].startswith("[stern] ")
    assert "turned stag" in r["speakable"]["args"]["text"]
    assert "stern" in r["casting"]["registers"]


# ---------------------------------------------------------------------------- semantic lane (D9)
class _FakeEmbedder:
    model_sha = "fake-sha"

    def encode_one(self, text):
        import numpy as np
        return np.zeros(384, dtype=np.float32)


def _fake_sidecar(tmp_path, lexicon_sha, model_sha="fake-sha"):
    import numpy as np
    p = tmp_path / "vectors.npz"
    np.savez(p, vectors=np.zeros((2, 384), dtype=np.float32),
             terms=np.array(["berk", "jink"], dtype=object),
             meta=np.array(json.dumps({"model_id": "fake", "model_sha": model_sha,
                                       "dim": 384, "lexicon_sha": lexicon_sha,
                                       "built": "2026-06-06"})))
    return p


def test_semantic_disabled_without_sidecar(tmp_path):
    e = Engine(vectors_path=tmp_path / "absent.npz")
    e.enable_semantic(embedder=_FakeEmbedder())
    st = e.semantic_status()
    assert st["enabled"] is False
    assert "sidecar" in st["why"]


def test_vectors_lexicon_sha_mismatch_refused(tmp_path):    # stale-ranking law
    e = Engine(vectors_path=_fake_sidecar(tmp_path, lexicon_sha="WRONG"))
    e.enable_semantic(embedder=_FakeEmbedder())
    st = e.semantic_status()
    assert st["enabled"] is False
    assert "different lexicon" in st["why"]


def test_vectors_model_sha_mismatch_refused(tmp_path):      # ranking-drift law
    from cant.embed import file_sha256
    from cant.engine import LEXICON_PATH
    e = Engine(vectors_path=_fake_sidecar(tmp_path, lexicon_sha=file_sha256(LEXICON_PATH),
                                          model_sha="some-other-model"))
    e.enable_semantic(embedder=_FakeEmbedder())
    st = e.semantic_status()
    assert st["enabled"] is False
    assert "different model" in st["why"]


def test_semantic_off_env_hatch(tmp_path, monkeypatch):
    monkeypatch.setenv("CANT_SEMANTIC", "off")
    e = Engine()
    e.enable_semantic()
    assert e.semantic_status()["enabled"] is False
    assert "ops hatch" in e.semantic_status()["why"]


def _lane_available():
    from cant.embed import MODEL_DIR
    try:
        import numpy, onnxruntime, tokenizers  # noqa: F401
    except ImportError:
        return False
    from cant.engine import VECTORS_PATH
    return (MODEL_DIR / "model.onnx").exists() and VECTORS_PATH.exists()


semantic_live = pytest.mark.skipif(not _lane_available(),
                                   reason="semantic lane not provisioned (model/vectors absent)")


@pytest.fixture(scope="module")
def eng_sem():
    e = Engine()
    e.enable_semantic()
    if not e.semantic_status()["enabled"]:
        pytest.skip(f"lane disabled: {e.semantic_status()['why']}")
    return e


@semantic_live
def test_live_semantic_bribe_finds_garnish(eng_sem):
    r = eng_sem.suggest_terms("bribe")
    assert r["terms"][0]["term"] == "garnish"
    assert r["terms"][0]["match"]["semantic"] > 0.5


@semantic_live
def test_live_concepts_gemstone(eng_sem):                   # regex misses 'gemstone'; semantics doesn't
    r = eng_sem.transmute("I'll pay you well for that gemstone.")
    assert "sparkle" in [c["term"] for c in r["concepts"]]
    assert all(c["cosine"] >= 0.35 for c in r["concepts"])


@semantic_live
def test_live_negative_control_stays_silent(eng_sem):      # θ=0.35 holds the line
    r = eng_sem.transmute("The weather is pleasant today.")
    assert r["concepts"] == []


@semantic_live
def test_live_concepts_never_rewrite(eng_sem):              # D9: palette, not pen
    plain = Engine()                                        # lane never booted
    a = plain.transmute("I'll pay you well for that gemstone.")
    b = eng_sem.transmute("I'll pay you well for that gemstone.")
    assert a["candidates"] == b["candidates"]               # byte-identical composition


@semantic_live
def test_live_semantic_deterministic(eng_sem):
    a = eng_sem.suggest_terms("drinking establishment")
    b = eng_sem.suggest_terms("drinking establishment")
    assert a["terms"] == b["terms"]


def test_rewrites_data_law():
    """Every rewrite rule compiles and links to a real lexicon term when it claims one."""
    import re as _re
    rw = json.loads((HERE / "data" / "rewrites.json").read_text(encoding="utf-8"))
    eng_local = Engine()
    for kind in ("templates", "substitutions", "seasoning"):
        for rule in rw[kind]:
            _re.compile(rule["en"], _re.IGNORECASE)        # must compile
            assert rule["out"], rule["id"]
            if rule.get("term"):
                assert eng_local.lookup(rule["term"]) is not None, \
                    f"{rule['id']} links unknown term {rule['term']!r}"


def test_rewrites_backrefs_within_groups():                # V&V A5 guard
    """A `\\N` in out[] referencing a group `en` never captures only explodes
    when that rule FIRES — audit it at data level instead of at the table."""
    import re as _re
    rw = json.loads((HERE / "data" / "rewrites.json").read_text(encoding="utf-8"))
    for kind in ("templates", "substitutions", "seasoning"):
        for rule in rw[kind]:
            groups = _re.compile(rule["en"], _re.IGNORECASE).groups
            for opt in rule["out"]:
                refs = [int(n) for n in _re.findall(r"\\(\d+)", opt)]
                assert all(0 < n <= groups for n in refs), \
                    f"{rule['id']}: out {opt!r} references group beyond {groups}"


@semantic_live
def test_vectors_sidecar_integrity():                      # V&V A6 guard
    import numpy as np
    from cant.engine import VECTORS_PATH
    with np.load(VECTORS_PATH, allow_pickle=True) as z:
        vecs, terms = z["vectors"], list(z["terms"])
        meta = json.loads(str(z["meta"]))
    lex = json.loads((HERE / "data" / "lexicon.json").read_text(encoding="utf-8"))
    assert vecs.shape == (len(lex["terms"]), meta["dim"])
    assert terms == [e["term"] for e in lex["terms"]]      # aligned, in lexicon order
    norms = np.linalg.norm(vecs, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-4), "vectors must be L2-normalized"
    from cant.embed import file_sha256, MODEL_DIR
    assert meta["lexicon_sha"] == file_sha256(HERE / "data" / "lexicon.json")
    prov = json.loads((MODEL_DIR / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert meta["model_sha"] == prov["sha256"]["model.onnx"]
