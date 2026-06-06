"""V&V — extraction gear-house (regions.parse_statblock + normalize).

The gate is only as good as what it's fed. P5 source-fidelity caught two NPCs (Zadara,
Seamusxanthuszenus) whose THAC0 was OCR'd as letter-lookalikes (`THACO S`, `THACO IS`) and
dropped to None because the THAC0 capture demanded a literal digit. The fix strengthens the
RULE (apply the numeric-OCR gear + a 1..20 range guard to the THAC0 value) rather than
curating two berks — these probes pin it. (V&V D2, 2026-06-05)
"""
import regions as R


def thac0(text):
    return R.parse_statblock({"lines": [{"text": text}]})[0].get("thac0")


def test_thac0_letter_lookalikes_repaired():
    # the two real Uncaged lines that P5 surfaced
    assert thac0("AC 0; MV 36; hp 132; THACO S (-2 w/maul); #AT 2 or 1; Dmg 2d10") == "5"     # Zadara
    assert thac0("AC 3; MV 12, Fl 24 (B); hp 41; THACO IS; *AT 2; Dmg 1d4") == "15"           # Seamus


def test_thac0_clean_value_untouched():
    assert thac0("AC -8; hp 92; THAC0 7; #AT 3; Dmg 1d4/1d4/2d6") == "7"                       # A'kin
    assert thac0("AC 1; hp 88; THAC0 9; #AT 1; Dmg 1d8") == "9"                                # Autochon


def test_thac0_out_of_range_token_dropped():
    # 'SO' -> '50' is not a lawful 2e THAC0 (1..20) — the guard must reject, not admit garbage
    assert thac0("AC 5; hp 30; THAC0 SO; #AT 1; Dmg 1d6") is None
