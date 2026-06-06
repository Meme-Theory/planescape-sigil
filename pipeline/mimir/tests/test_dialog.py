"""V&V — the NPC dialog extractor (pipeline/parse/dialog.py).

A bound utterance must be SPEECH, attributed to THIS NPC, with a register from the speech verb.
These probes pin each guard the corpus forced: emphasis-quotes, foreign speakers, and OCR
column-bleed (the Seamus entry's narration leaking into quote spans).
"""
import dialog as D

OTHERS = {"Ensin", "Shemeshka the Marauder", "Yllgarra"}


def test_named_subject_and_register_from_verb():
    a = D.extract('A friendly sort, A\'kin beams, "Come in, come in! I won\'t bite." His shop is warm.',
                  owner_id="npc:uncaged:a-kin", owner_name="A'kin", page=12, book="uncaged", others=OTHERS)
    assert len(a) == 1
    assert a[0]["register"] == "amused" and a[0]["confidence"] >= 0.85
    assert a[0]["owner"] == "npc:uncaged:a-kin"


def test_register_axis_maps_grace_toml():
    stern = D.extract('He snarled, "You\'ll get nothing, berk!"', owner_id="x", owner_name="X", others=OTHERS)
    grave = D.extract('She whispered, "They are listening, always listening."',
                      owner_id="y", owner_name="Y", others=OTHERS)
    assert stern[0]["register"] == "stern" and grave[0]["register"] == "grave"


def test_emphasis_quote_is_not_speech():
    assert D.extract('They call them the "silent couriers" of the Cage.',
                     owner_id="z", owner_name="Z", others=OTHERS) == []


def test_foreign_named_speaker_does_not_bind():
    f = D.extract('Then Ensin says, "Mind the portal, friend." A\'kin only nodded.',
                  owner_id="npc:uncaged:a-kin", owner_name="A'kin", others=OTHERS)
    assert f == []


def test_ocr_narration_bleed_drops_below_theta():
    # the Seamus failure: narration ("the mephit proclaimed", "leapt") leaked into the quote span.
    nb = D.extract('He says, "Service! the mephit proclaimed, and ever after I leapt to the counter."',
                   owner_id="npc:uncaged:seamus", owner_name="Seamus", others=OTHERS)
    assert nb and nb[0]["confidence"] < D.THETA_DIALOG


def test_word_fusion_bleed_drops_below_theta():
    fz = D.extract('He says, "I am SeamusxanFact is the hedgehoglike thuszenus, Slayer."',
                   owner_id="npc:uncaged:seamus", owner_name="Seamus", others=OTHERS)
    assert fz and fz[0]["confidence"] < D.THETA_DIALOG


def test_hyphen_split_is_joined():
    h = D.extract('He says, "I am a humble shop- keep, friend."',
                  owner_id="npc:uncaged:a-kin", owner_name="A'kin", others=OTHERS)
    assert h and "shopkeep" in h[0]["text"]


def test_clean_short_line_admits():
    c = D.extract('"I never barter!" the mephit insisted to Adamok.',
                  owner_id="npc:uncaged:seamus", owner_name="Seamus", others=OTHERS)
    assert c and c[0]["confidence"] >= D.THETA_DIALOG
