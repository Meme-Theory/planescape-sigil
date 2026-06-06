"""The fleet audit, pinned — all 334 SRD 5.1 monsters through is_lawful.

This is the audit run on 2026-06-05, frozen as a regression net. Every number
below was adjudicated against the SRD 5.1 PDF print (known_deviations.json):
three monsters carry print-attested non-derivable skills (waivers), five carry
upstream 5e-bits transcription bugs (must STAY flagged), four carry the
halved-XP bug (soft).

Integration test: reads the full 5e-bits set from content/; skipped if absent.
"""

import json
from pathlib import Path

import pytest

from mechanus import is_lawful, known_waivers

BITS = Path(r"C:/sandbox/Planescape/content/srd/json-data/5e-database/src/2014/en/5e-SRD-Monsters.json")

EXPECTED_HARD = {
    "passive_perception_math": {"Black Bear", "Blink Dog", "Half-Red Dragon Veteran",
                                "Spider", "Swarm of Ravens"},   # upstream 5e-bits bugs
    "skill_bonuses_math": {"Lich", "Night Hag", "Priest"},      # print-attested -> waivers
}
EXPECTED_SOFT_XP = {"Dretch", "Riding Horse", "Deep Gnome (Svirfneblin)", "Brass Dragon Wyrmling"}


@pytest.mark.skipif(not BITS.exists(), reason="5e-bits corpus not on disk")
def test_fleet_audit_pinned():
    mons = json.loads(BITS.read_text(encoding="utf-8"))
    assert len(mons) == 334

    hard, soft_xp, lawful = {}, set(), 0
    for m in mons:
        v = is_lawful(m)
        lawful += v["lawful"]
        for c in v["summary"]["hard_fails"]:
            hard.setdefault(c, set()).add(m["name"])
        if "xp_matches_cr" in v["summary"]["soft_fails"]:
            soft_xp.add(m["name"])

    assert hard == EXPECTED_HARD
    assert soft_xp == EXPECTED_SOFT_XP
    assert lawful == 334 - sum(len(s) for s in EXPECTED_HARD.values())


@pytest.mark.skipif(not BITS.exists(), reason="5e-bits corpus not on disk")
def test_fleet_with_known_waivers():
    """Waivers clear exactly the three attested monsters; the bits bugs stay caught."""
    mons = json.loads(BITS.read_text(encoding="utf-8"))
    still_failing = set()
    for m in mons:
        v = is_lawful(m, waivers=known_waivers(m["index"]))
        if not v["lawful"]:
            still_failing.add(m["name"])
    assert still_failing == EXPECTED_HARD["passive_perception_math"]
