"""dabus unit pack — pure stdlib (no torch, no model): pack law, register
splitting, cache-key canon, ledger discipline, Mimir-seam normalization.
Run from pipeline/dabus/:
    py -3.13 -m pytest tests/ -q
"""

import wave

import pytest

from dabus import engine, mimir_seam, packs, store


# ---------------------------------------------------------------- fixtures

@pytest.fixture
def voices_dir(tmp_path, monkeypatch):
    vd = tmp_path / "voices"
    rip = vd / "rip"
    rip.mkdir(parents=True)
    for stem, text in [("REF1", "First reference line."),
                       ("REF2", "Second reference line.")]:
        with wave.open(str(rip / f"{stem}.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(22050)
            w.writeframes(b"\x00\x00" * 22050)
        (rip / f"{stem}.txt").write_text(text + "\n", encoding="utf-8")
    (vd / "tester.toml").write_text(
        'model = "F5TTS_v1_Base"\n'
        'ref_audio = "rip/REF1.wav"\n'
        'ref_text = "First reference line."\n'
        '[voices.grim]\n'
        'ref_audio = "rip/REF2.wav"\n'
        'speed = 0.9\n',
        encoding="utf-8")
    monkeypatch.setattr(packs, "VOICES_DIR", vd)
    return vd


@pytest.fixture
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "BUILD_DIR", tmp_path / "build")
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "build" / "renders.db")
    monkeypatch.setattr(store, "RENDERS_DIR", tmp_path / "build" / "renders")
    return store


# ---------------------------------------------------------------- packs

def test_pack_loads_with_sidecar_fallback(voices_dir):
    pack = packs.load_pack("tester")
    assert sorted(pack["registers"]) == ["grim", "main"]
    # grim had no ref_text in the toml — sidecar .txt supplies it
    assert pack["registers"]["grim"]["ref_text"] == "Second reference line."
    assert pack["registers"]["grim"]["speed"] == 0.9
    assert pack["registers"]["main"]["ref_sha"]


def test_pack_missing_ref_refuses(voices_dir):
    (voices_dir / "broken.toml").write_text(
        'ref_audio = "rip/NOPE.wav"\nref_text = "x"\n', encoding="utf-8")
    with pytest.raises(packs.PackError, match="missing reference clips"):
        packs.load_pack("broken")


def test_unknown_pack_names_known(voices_dir):
    with pytest.raises(packs.PackError, match="tester"):
        packs.load_pack("nobody")


def test_folder_scan_status(voices_dir):
    folders = packs.list_folders()
    assert folders == [{"folder": "rip", "clips": 2, "transcripts": 2,
                        "status": "RAW"}]
    (voices_dir / "rip" / "_refs.md").write_text("# refs\n", encoding="utf-8")
    assert packs.list_folders()[0]["status"] == "ONBOARDED"


# ---------------------------------------------------------------- direction

REGS = {"main": {}, "grim": {}, "wry": {}}


def test_split_plain_text_is_default_register():
    segs = engine.split_registers("Hello there.", REGS)
    assert segs == [{"register": "main", "text": "Hello there."}]


def test_split_tagged_speech():
    segs = engine.split_registers(
        "[grim] Steel out. [wry] Or don't. [main] Your funeral.", REGS)
    assert [(s["register"], s["text"]) for s in segs] == [
        ("grim", "Steel out."), ("wry", "Or don't."), ("main", "Your funeral.")]


def test_split_unknown_register_refuses():
    with pytest.raises(engine.RenderError, match=r"unknown register \[shouty\]"):
        engine.split_registers("[shouty] HELLO", REGS)


def test_split_empty_refuses():
    with pytest.raises(engine.RenderError, match="no text"):
        engine.split_registers("[grim]   ", REGS)


# ---------------------------------------------------------------- cache key

SEG = [{"register": "main", "ref_sha": "abc123", "ref_text": "r", "text": "Hi."}]


def test_cache_key_deterministic():
    k1 = store.cache_key(model="M", voice="v", segments=SEG,
                         knobs={"nfe_step": 32, "speed": 1.0}, seed=None)
    k2 = store.cache_key(model="M", voice="v", segments=SEG,
                         knobs={"speed": 1.0, "nfe_step": 32}, seed=None)
    assert k1 == k2  # knob order canonicalized


def test_cache_key_random_take_excludes_seed_explicit_joins():
    base = store.cache_key(model="M", voice="v", segments=SEG,
                           knobs={}, seed=None)
    named = store.cache_key(model="M", voice="v", segments=SEG,
                            knobs={}, seed=7)
    assert base != named
    assert store.cache_key(model="M", voice="v", segments=SEG,
                           knobs={}, seed=None) == base


def test_cache_key_ref_swap_changes_address():
    other = [dict(SEG[0], ref_sha="zzz999")]
    assert store.cache_key(model="M", voice="v", segments=SEG, knobs={},
                           seed=None) != \
        store.cache_key(model="M", voice="v", segments=other, knobs={}, seed=None)


# ---------------------------------------------------------------- ledger

def _rec(tmp_store, sha="a" * 64, retake=False, text="The knife-work's mine."):
    return tmp_store.record(
        sha=sha, kind="render", voice="annah", registers=["main"], text=text,
        params={"model": "M", "knobs": {}}, file=f"/r/{sha[:6]}.wav",
        duration_s=3.2, seeds=[42], retake=retake)


def test_record_and_lookup_roundtrip(tmp_store):
    row = _rec(tmp_store)
    assert row["render_id"] == "rnd:" + "a" * 12
    assert tmp_store.lookup(row["render_id"])["sha"] == "a" * 64
    assert tmp_store.lookup("a" * 12)["render_id"] == row["render_id"]  # sha prefix
    assert tmp_store.lookup("nope") is None


def test_duplicate_sha_without_retake_refuses(tmp_store):
    _rec(tmp_store)
    with pytest.raises(store.StoreError, match="retake"):
        _rec(tmp_store)


def test_retake_supersedes_in_place(tmp_store):
    _rec(tmp_store)
    row = _rec(tmp_store, retake=True)
    assert row["retakes"] == 1
    assert tmp_store.stats()["renders"] == 1


def test_hits_count(tmp_store):
    _rec(tmp_store)
    tmp_store.bump_hit("a" * 64)
    tmp_store.bump_hit("a" * 64)
    assert tmp_store.get_by_sha("a" * 64)["hits"] == 2


def test_fts_search_and_voice_filter(tmp_store):
    _rec(tmp_store)
    _rec(tmp_store, sha="b" * 64, text="Roll for initiative, cutters.")
    hits = tmp_store.search("initiative", None)
    assert len(hits) == 1 and hits[0]["sha"] == "b" * 64
    assert len(tmp_store.search(None, "annah")) == 2
    assert tmp_store.search("knife", "annah")[0]["text"].startswith("The knife")


def test_slug_and_render_path(tmp_store):
    assert store.slug("Ach, would ye look at this lot!?") == \
        "ach-would-ye-look-at-this-lot"
    p = tmp_store.render_path("annah", "c" * 64, "Keep yer jink close")
    assert p.name == "cccccccccccc__keep-yer-jink-close.wav"
    assert p.parent.name == "annah"


# ---------------------------------------------------------------- aliases & casting

def test_register_aliases_route_and_disclose(voices_dir):
    (voices_dir / "tester.toml").write_text(
        'ref_audio = "rip/REF1.wav"\nref_text = "x"\n'
        '[voices.menace]\nref_audio = "rip/REF2.wav"\n'
        '[register_aliases]\ngrave = "menace"\n', encoding="utf-8")
    pack = packs.load_pack("tester")
    assert packs.resolve_register(pack, "grave") == ("menace", True)
    assert packs.resolve_register(pack, "main") == ("main", False)
    with pytest.raises(packs.PackError, match="not in pack"):
        packs.resolve_register(pack, "shouty")


def test_alias_to_missing_register_refuses(voices_dir):
    (voices_dir / "bad.toml").write_text(
        'ref_audio = "rip/REF1.wav"\nref_text = "x"\n'
        '[register_aliases]\ngrave = "nothing"\n', encoding="utf-8")
    with pytest.raises(packs.PackError, match="not a register"):
        packs.load_pack("bad")


def test_alias_shadowing_real_register_refuses(voices_dir):
    (voices_dir / "bad2.toml").write_text(
        'ref_audio = "rip/REF1.wav"\nref_text = "x"\n'
        '[voices.grim]\nref_audio = "rip/REF2.wav"\n'
        '[register_aliases]\ngrim = "main"\n', encoding="utf-8")
    with pytest.raises(packs.PackError, match="shadows"):
        packs.load_pack("bad2")


def test_speaker_casting_and_refusal(voices_dir):
    (voices_dir / "speakers.toml").write_text(
        '[speakers]\n"npc:uncaged:a-kin" = "tester"\n', encoding="utf-8")
    assert packs.resolve_speaker("npc:uncaged:a-kin") == "tester"
    with pytest.raises(packs.PackError, match="no voice cast"):
        packs.resolve_speaker("npc:uncaged:unsung")


# ---------------------------------------------------------------- mimir seam

GOOD_ENV = {"id": "dialog:uncaged:abc123", "type": "dialog",
            "source_sha": "feedbeef", "confidence": 0.9,
            "fields": {"text": "Come in, come in!", "register": "grave",
                       "verb": "rasp", "owner": "npc:uncaged:a-kin", "page": 9}}


def test_seam_normalizes_the_contract():
    n = mimir_seam._normalize(GOOD_ENV)
    assert n["dialog_id"] == "dialog:uncaged:abc123"
    assert n["text"] == "Come in, come in!"
    assert n["register"] == "grave" and n["register_defaulted"] is False
    assert n["owner"] == "npc:uncaged:a-kin"
    assert n["page"] == 9 and n["source_sha"] == "feedbeef"
    assert n["verb"] == "rasp"


def test_seam_defaults_missing_register_disclosed():
    env = {**GOOD_ENV, "fields": {k: v for k, v in GOOD_ENV["fields"].items()
                                  if k != "register"}}
    n = mimir_seam._normalize(env)
    assert n["register"] == "main" and n["register_defaulted"] is True


def test_seam_refuses_wrong_type_and_missing_text():
    with pytest.raises(mimir_seam.SeamError, match="not dialog"):
        mimir_seam._normalize({**GOOD_ENV, "type": "npc"})
    with pytest.raises(mimir_seam.SeamError, match="no fields.text"):
        mimir_seam._normalize({**GOOD_ENV, "fields": {"owner": "x"}})
    with pytest.raises(mimir_seam.SeamError, match="no such entity"):
        mimir_seam._normalize(None)


# ---------------------------------------------------------------- join-key rows

def test_source_ref_roundtrip_newest_wins(tmp_store):
    did = "dialog:uncaged:abc123"
    tmp_store.record(sha="d" * 64, kind="render", voice="grace", registers=["grave"],
                     text="Old text.", params={}, file="/r/old.wav", duration_s=1.0,
                     seeds=[1], source_ref=did)
    import time as _t
    _t.sleep(1.1)  # created_utc has second resolution — force ordering
    tmp_store.record(sha="e" * 64, kind="render", voice="grace", registers=["grave"],
                     text="New text after re-pour.", params={}, file="/r/new.wav",
                     duration_s=1.0, seeds=[2], source_ref=did)
    row = tmp_store.lookup(did)
    assert row["file"] == "/r/new.wav"  # newest render answers to the join-key
    assert row["source_ref"] == did
