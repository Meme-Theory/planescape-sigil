"""planes.py — the three Planes boxes (Law 2607 / Chaos 2603 / Conflict 2615):
plane structure as CURATED CARDS, every claim VALIDATED against the reflow text.

The law: a card may CLAIM a layer or gate-town, but the pour gets only what the
booklet's own text ATTESTS — `attest_card` searches the component's pages for each
claimed name and returns witnesses; a zero-witness claim is REFUSED (reported,
never poured). "Verified or absent," enforced in code, same as the Cage roster.

Deliberately deferred (see DIMENSIONS ledger): realms (the "realm of X" sweep
returns OCR fragments — needs the Travelogue's structured lists), per-plane
alignment/trait strings (not freelanced without page witnesses).

Pure gear-house: no store imports, self-tested in __main__.
"""
import re
from pathlib import Path

# (plane_id, component_path, book_slug, layers[(name, ordinal, aliases, id_override)],
#  gate_town_name_or_None, layer_note_or_None, gloss)
# Layer names use the BOX'S OWN spelling (Cania not Caina; Olympus/Ossa/Pelion for
# Arborea — Pelion id-overrides onto layer:amun-thys, In the Cage's name for the
# same layer, so the Ditch portal keeps pointing at one identity).
PLANE_CARDS = [
    {"id": "plane:acheron", "component": "planes-of-law/ddps-planesoflaw-ii",
     "book": "planes-of-law",
     "layers": [("Avalas", 1, [], None), ("Thuldanin", 2, [], None),
                ("Tintibulus", 3, [], None), ("Ocanthus", 4, [], None)],
     "gate_town": "Rigus", "layer_note": None,
     "gloss": "endless war on drifting iron cubes; the armies of order grind each other to filings"},
    {"id": "plane:arcadia", "component": "planes-of-law/ddps-planesoflaw-iii",
     "book": "planes-of-law",
     "layers": [("Abellio", 1, [], None), ("Buxenus", 2, [], None),
                ("Nemausus", 3, [], None)],
     "gate_town": "Fortitude", "layer_note": "the third layer is said to be lost to Mechanus",
     "gloss": "perfect orchards and orderly harmony; even the trees grow in rows"},
    {"id": "plane:baator", "component": "planes-of-law/ddps-planesoflaw-iv",
     "book": "planes-of-law",
     "layers": [("Avernus", 1, [], None), ("Dis", 2, [], None), ("Minauros", 3, [], None),
                ("Phlegethos", 4, [], None), ("Stygia", 5, [], None), ("Malbolge", 6, [], None),
                ("Maladomini", 7, [], None), ("Cania", 8, [], None), ("Nessus", 9, [], None)],
     "gate_town": "Ribcage", "layer_note": None,
     "gloss": "the Nine Hells: nine layers of calculated cruelty under the baatezu"},
    {"id": "plane:mechanus", "component": "planes-of-law/ddps-planesoflaw-v",
     "book": "planes-of-law",
     "layers": [], "gate_town": "Automata",
     "layer_note": "a single infinite plane of interlocking cogs",
     "gloss": "the clockwork plane of absolute law; modrons and the gears of cause and effect"},
    {"id": "plane:mount-celestia", "component": "planes-of-law/ddps-planesoflaw-vi",
     "book": "planes-of-law",
     "layers": [("Lunia", 1, [], None), ("Mercuria", 2, [], None), ("Venya", 3, [], None),
                ("Solania", 4, [], None), ("Mertion", 5, [], None), ("Jovar", 6, [], None),
                ("Chronias", 7, [], None)],
     "gate_town": "Excelsior", "layer_note": None,
     "gloss": "the Seven Heavens: one holy mountain rising from a sea of holy water"},
    {"id": "plane:limbo", "component": "planes-of-chaos/tsr2603-planes-of-chaos",
     "book": "planes-of-chaos",
     "layers": [], "gate_town": "Xaos",
     "layer_note": "undifferentiated chaos-stuff; no distinct layers named",
     "gloss": "raw chaos shaped by will; githzerai monasteries and Anarchs' islands of order"},
    {"id": "plane:ysgard", "component": "planes-of-chaos/tsr2603-planes-of-chaos",
     "book": "planes-of-chaos",
     "layers": [("Ysgard", 1, [], None), ("Muspelheim", 2, [], None),
                ("Nidavellir", 3, [], None)],
     "gate_town": "Glorium", "layer_note": None,
     "gloss": "rivers of earth over seas of fire; the heroes' plane of eternal battle reborn each dawn"},
    {"id": "plane:arborea", "component": "planes-of-chaos/tsr2603-planes-of-chaos",
     "book": "planes-of-chaos",
     "layers": [("Olympus", 1, [], None), ("Ossa", 2, [], None),
                ("Pelion", 3, ["amun-thys", "mithardir"], "layer:amun-thys")],
     "gate_town": "Sylvania", "layer_note": None,
     "gloss": "passion writ large: Olympus of the Greek powers, Ossa's seas, Pelion's white wastes"},
    {"id": "plane:pandemonium", "component": "planes-of-chaos/tsr2603-planes-of-chaos",
     "book": "planes-of-chaos",
     "layers": [("Pandesmos", 1, [], None), ("Cocytus", 2, [], None),
                ("Phlegethon", 3, [], None), ("Agathion", 4, [], None)],
     "gate_town": "Bedlam", "layer_note": None,
     "gloss": "howling wind-tunnels in infinite rock; the madhouse of the planes"},
    {"id": "plane:the-abyss", "component": "planes-of-chaos/tsr2603-planes-of-chaos",
     "book": "planes-of-chaos",
     "layers": [("the Plain of Infinite Portals", 1, ["pazunia"], None)],
     "gate_town": "Plague-Mort", "layer_note": "infinite layers; only the first is reliably mapped",
     "gloss": "infinite layers of evil without order; the tanar'ri's bottomless home"},
    {"id": "plane:the-beastlands", "component": "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae",
     "book": "planes-of-conflict",
     "layers": [("Krigala", 1, [], None), ("Brux", 2, [], None), ("Karasuthra", 3, [], None)],
     "gate_town": "Faunel", "layer_note": "eternal noon, twilight, and night",
     "gloss": "the wilderness of pure nature; beasts hold court and the hunt is holy"},
    {"id": "plane:bytopia", "component": "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae",
     "book": "planes-of-conflict",
     "layers": [("Dothion", 1, [], None), ("Shurrock", 2, [], None)],
     "gate_town": "Tradegate", "layer_note": "two layers facing each other, sky-to-sky",
     "gloss": "the twin paradises of honest industry; gnomes and good work"},
    {"id": "plane:elysium", "component": "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae",
     "book": "planes-of-conflict",
     "layers": [("Amoria", 1, [], None), ("Eronia", 2, [], None),
                ("Belierin", 3, [], None), ("Thalasia", 4, [], None)],
     "gate_town": "Ecstasy", "layer_note": None,
     "gloss": "the plane of untroubled good along the River Oceanus; rest that can trap a body"},
    {"id": "plane:carceri", "component": "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae",
     "book": "planes-of-conflict",
     "layers": [("Othrys", 1, [], None), ("Cathrys", 2, [], None), ("Minethys", 3, [], None),
                ("Colothys", 4, [], None), ("Porphatys", 5, [], None), ("Agathys", 6, [], None)],
     "gate_town": "Curst", "layer_note": "nested orbs, each inside the last",
     "gloss": "the Red Prison: exiles, traitors, and the titans in their nested cells"},
    {"id": "plane:gehenna", "component": "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae",
     "book": "planes-of-conflict",
     "layers": [("Khalas", 1, [], None), ("Chamada", 2, [], None),
                ("Mungoth", 3, [], None), ("Krangath", 4, [], None)],
     "gate_town": "Torch", "layer_note": "four furnace-mounts with no level ground",
     "gloss": "the Fourfold Furnaces: volcanic slopes where mercy is a commodity"},
    {"id": "plane:the-gray-waste", "component": "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae",
     "book": "planes-of-conflict",
     "layers": [("Oinos", 1, [], None), ("Niflheim", 2, [], None), ("Pluton", 3, [], None)],
     "gate_town": "Hopeless", "layer_note": None,
     "gloss": "the three glooms that bleach hope itself; the yugoloths' mercenary heart"},
]

# sources for the three boxes (poured once each)
BOX_SOURCES = {
    "planes-of-law": ("source:planes-of-law", "Planes of Law", "2607", 1995),
    "planes-of-chaos": ("source:planes-of-chaos", "Planes of Chaos", "2603", 1994),
    "planes-of-conflict": ("source:planes-of-conflict", "Planes of Conflict", "2615", 1995),
}


# ---------------------------------------------------------------- realms (round 2)
# Curated from the boxes' own realm sections (the Law/Conflict books carry literal
# "POWER. <name>" stat lines; the Chaos Travelogue heads each realm with its name).
# attest_realms enforces: the REALM name must witness in the component, and the
# POWER name must witness too — or the card must declare power=None WITH a note
# (Stillsong's power is "one of the few great mysteries of the plane"; the
# Spawning Stone has slaad lords, not a power). Refusals are reported, never poured.
# (realm_name, power_or_None, plane_id, layer_id_or_None, component, book,
#  realm_aliases, power_aliases, note)
REALM_CARDS = [
    # — Planes of Law —
    ("Clangor", "Maglubiyet", "plane:acheron", "layer:avalas",
     "planes-of-law/ddps-planesoflaw-ii", "planes-of-law", [], [], "realm of the goblin pantheon"),
    ("Nishrek", "Gruumsh", "plane:acheron", "layer:avalas",
     "planes-of-law/ddps-planesoflaw-ii", "planes-of-law", [], [], "realm of the orc pantheon"),
    ("Marduk", "Marduk", "plane:arcadia", None,
     "planes-of-law/ddps-planesoflaw-iii", "planes-of-law", [], [],
     "eponymous realm of the Babylonian Binder of Dragons"),
    ("Mount Clangeddin", "Clangeddin Silverbeard", "plane:arcadia", None,
     "planes-of-law/ddps-planesoflaw-iii", "planes-of-law", [], ["clangeddin"], None),
    ("Cavern of Azuth", "Azuth", "plane:arcadia", "layer:buxenus",
     "planes-of-law/ddps-planesoflaw-iii", "planes-of-law", ["azuth's cavern"], [],
     "realm of Toril's god of mages"),
    ("Ankhwugaht", "Set", "plane:baator", "layer:stygia",
     "planes-of-law/ddps-planesoflaw-iv", "planes-of-law", [], [], "Set's desert of snow and ice"),
    ("Sheyruushk", "Sekolah", "plane:baator", "layer:stygia",
     "planes-of-law/ddps-planesoflaw-iv", "planes-of-law", [], [], "the sahuagin shark-god's hunting waters"),
    ("Draukari", "Kurtulmak", "plane:baator", "layer:avernus",
     "planes-of-law/ddps-planesoflaw-iv", "planes-of-law", [], [], "the kobold god's warrens"),
    ("Regulus", "Primus", "plane:mechanus", None,
     "planes-of-law/ddps-planesoflaw-v", "planes-of-law", [], [],
     "the modron realm of 64 sectors"),
    ("Bahamut's Palace", "Bahamut", "plane:mount-celestia", None,
     "planes-of-law/ddps-planesoflaw-vi", "planes-of-law", [], [],
     "wanders the layers — the Platinum Dragon's court"),
    ("Green Fields", "Yondalla", "plane:mount-celestia", "layer:venya",
     "planes-of-law/ddps-planesoflaw-vi", "planes-of-law", [], [], "realm of the halfling pantheon"),
    ("Erackinor", "Moradin", "plane:mount-celestia", "layer:solania",
     "planes-of-law/ddps-planesoflaw-vi", "planes-of-law", [], [],
     "the Soul Forges of the dwarf-father (with Berronar)"),
    ("The Glass Tarn", "Mitra", "plane:mount-celestia", "layer:mercuria",
     "planes-of-law/ddps-planesoflaw-vi", "planes-of-law", ["glass tarn"], [],
     "shared by Mitra and Surya of the Vedic pantheon"),
    # — Planes of Chaos (Travelogue) —
    ("Azzagrat", "Graz'zt", "plane:the-abyss", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [],
     "the Triple Realm, three layers under one lord"),
    ("Thanatos", "Kiaransalee", "plane:the-abyss", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [],
     "the Belly of Death — the drow banshee-queen holds the dead god Orcus's realm"),
    ("The Slime Pits", "Zuggtmoy", "plane:the-abyss", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos",
     ["slime pits", "shedaklah"], [],
     "canonically Shedaklah (that name OCR-shredded here) — Zuggtmoy above, Juiblex below"),
    # Blood Tor (Beshaba) stays REFUSED: only the shredded layer-list header
    # 'BL OOIJ ToR' survives the grade-C scan — v1b re-OCR is its door in.
    ("Blood Tor", "Beshaba", "plane:the-abyss", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [],
     "the Maid of Misfortune's tor (an Arborea face too)"),
    ("Gaping Maw", "Demogorgon", "plane:the-abyss", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [], None),
    ("Iron Wastes", "Kostchtchie", "plane:the-abyss", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [], None),
    ("Torremor", "Pazrael", "plane:the-abyss", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], ["pazrael"], None),
    ("Arvandor", "Corellon Larethian", "plane:arborea", "layer:olympus",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], ["corellon"],
     "realm of the Seldarine"),
    ("Evergold", "Hanali Celanil", "plane:arborea", "layer:olympus",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], ["hanali"],
     "the shared pool of beauty (Hanali with Sune's faithful)"),
    ("Brightwater", "Sune", "plane:arborea", "layer:olympus",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [], None),
    ("Fennimar", "Fenmarel Mestarine", "plane:limbo", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], ["fenmarel"],
     "the lone-elf god's realm in the chaos-soup"),
    ("The Spawning Stone", None, "plane:limbo", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", ["spawning stone"], [],
     "the slaadi's eternal spawning ground — ruled by the slaad lords Ssendam and Ygorl, not a power"),
    ("Winter's Hall", "Loki", "plane:pandemonium", "layer:pandesmos",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [], None),
    ("The Unseelie Court", "The Queen of Air and Darkness", "plane:pandemonium", None,
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", ["unseelie court"],
     ["queen of air"], "a wandering court of fallen faerie"),
    ("Asgard", "Odin", "plane:ysgard", "layer:ysgard",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [],
     "hall-realm of the Norse pantheon"),
    ("Alfheim", "Freya", "plane:ysgard", "layer:ysgard",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [], "the elf-home of the Norse"),
    ("Himinborg", "Heimdall", "plane:ysgard", "layer:ysgard",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [],
     "the watchtower at Bifrost's foot"),
    ("Jotunheim", "Thrym", "plane:ysgard", "layer:ysgard",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [], "the giants' realm"),
    ("Gates of the Moon", "Selune", "plane:ysgard", "layer:ysgard",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], ["selune", "selûne"], None),
    ("Merratet", "Bast", "plane:ysgard", "layer:ysgard",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], [], "the cat goddess's pleasure-realm"),
    ("Vanaheim", "The Vanir", "plane:ysgard", "layer:ysgard",
     "planes-of-chaos/tsr2603-planes-of-chaos", "planes-of-chaos", [], ["vanir"],
     "the elder Norse pantheon's hidden realm"),
    # — Planes of Conflict —
    ("Skerrit's Glade", "Skerrit", "plane:the-beastlands", "layer:brux",
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     ["skerrit's"], [], "the centaur god's forest court"),
    ("Ursis", "Balador", "plane:the-beastlands", "layer:brux",
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     [], [], "Father Bear's realm"),
    ("Noctos' Domain", "Noctos", "plane:the-beastlands", None,
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     ["noctos"], [], "the owl power's night demesne"),
    ("Stormhold", "Stronmaus", "plane:the-beastlands", None,
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     [], [], "the giants' sky-father storms here"),
    ("Centerspire", "Tefnut", "plane:bytopia", None,
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     [], [], "the mountain between Bytopia's facing layers"),
    ("Stillsong", None, "plane:elysium", None,
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     [], [], "'one of the few great mysteries of the plane' — a realm that is a song; no power named"),
    ("Quietude", "Isis", "plane:elysium", None,
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     [], [], None),
    ("Selkies' Grotto", "Surminare", "plane:elysium", "layer:thalasia",
     "planes-of-conflict/planes-of-conflict-2615-01-liber-benevolentiae", "planes-of-conflict",
     ["selkies"], [], None),
    ("Mount Othrys", "The Titans", "plane:carceri", "layer:othrys",
     "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae", "planes-of-conflict",
     ["othrys"], ["titans"], "home of the imprisoned Greek titans"),
    ("Land of the Hunt", "Malar", "plane:carceri", "layer:colothys",
     "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae", "planes-of-conflict",
     [], [], "the Beastlord's cliff-hunting grounds"),
    ("The Glitterhell", "Abbathor", "plane:the-gray-waste", "layer:oinos",
     "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae", "planes-of-conflict",
     ["glitterhell"], [], "the dwarf god of greed counts his hoard"),
    ("Annwn", "Arawn", "plane:the-gray-waste", "layer:niflheim",
     "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae", "planes-of-conflict",
     [], [], "the Celtic death-realm in the mists"),
    ("Aeaea", "Hecate", "plane:the-gray-waste", "layer:pluton",
     "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae", "planes-of-conflict",
     [], [], "the mistress of magic's isle"),
    ("The Underworld", "Hades", "plane:the-gray-waste", "layer:pluton",
     "planes-of-conflict/planes-of-conflict-2615-02-liber-malevolentiae", "planes-of-conflict",
     ["underworld"], [], "the Lord of the Dead's gray kingdom"),
]


def attest_realm(card, pages):
    """Witnesses for one realm card: the realm name AND its power must both attest
    (a power=None card needs its note). Returns {realm_pages, power_pages, ok, why}."""
    name, power, _, _, _, _, raliases, paliases, note = card
    rxs = [_name_rx(name)] + [_name_rx(a) for a in raliases]
    rpp = sorted(pg for pg, txt in pages.items() if any(rx.search(txt) for rx in rxs))
    if not rpp:
        return {"realm_pages": [], "power_pages": [], "ok": False, "why": "realm name unattested"}
    if power is None:
        if not note:
            return {"realm_pages": rpp, "power_pages": [], "ok": False,
                    "why": "power=None requires a note"}
        return {"realm_pages": rpp, "power_pages": [], "ok": True, "why": None}
    prxs = [_name_rx(power)] + [_name_rx(a) for a in paliases]
    ppp = sorted(pg for pg, txt in pages.items() if any(rx.search(txt) for rx in prxs))
    if not ppp:
        return {"realm_pages": rpp, "power_pages": [], "ok": False, "why": f"power '{power}' unattested"}
    return {"realm_pages": rpp, "power_pages": ppp, "ok": True, "why": None}


def load_component(build_root, component):
    d = Path(build_root) / component / "reflow"
    return {int(p.stem.split("-")[1]): p.read_text(encoding="utf-8")
            for p in d.glob("page-*.txt")}


def _name_rx(name):
    """Word-boundary, case-insensitive — EXCEPT short common-word names ('Dis',
    'Ossa'): case-sensitive exact word so prose 'dis' never counts."""
    if len(name) <= 4:
        return re.compile(rf"\b{re.escape(name)}\b")
    return re.compile(rf"\b{re.escape(name)}\b", re.IGNORECASE)


def attest_card(card, pages):
    """Witness search for every claim on the card. Returns
    {layers: {name: [pages]}, refused: [names], gate_town_pages: [pages]}."""
    layers, refused = {}, []
    for name, ordinal, aliases, _ in card["layers"]:
        rxs = [_name_rx(name)] + [_name_rx(a) for a in aliases]
        pp = sorted(pg for pg, txt in pages.items() if any(rx.search(txt) for rx in rxs))
        if pp:
            layers[name] = pp
        else:
            refused.append(name)
    gt = card.get("gate_town")
    gpp = sorted(pg for pg, txt in pages.items()
                 if gt and _name_rx(gt).search(txt)) if gt else []
    return {"layers": layers, "refused": refused, "gate_town_pages": gpp}


if __name__ == "__main__":
    import sys

    # cards are well-formed
    seen = set()
    for c in PLANE_CARDS:
        assert c["id"].startswith("plane:") and c["id"] not in seen
        seen.add(c["id"])
        assert c["book"] in BOX_SOURCES
        ordinals = [o for _, o, _, _ in c["layers"]]
        assert ordinals == sorted(ordinals), c["id"]

    # attestation refuses what the text lacks
    fake = {"id": "plane:test", "component": "x", "book": "planes-of-law",
            "layers": [("Avalas", 1, [], None), ("Nowhereland", 2, [], None)],
            "gate_town": "Rigus", "layer_note": None, "gloss": ""}
    rep = attest_card(fake, {1: "the cubes of Avalas drift near Rigus."})
    assert rep["layers"] == {"Avalas": [1]} and rep["refused"] == ["Nowhereland"]
    assert rep["gate_town_pages"] == [1]

    # short names are case-sensitive: prose 'dis' is not the layer Dis
    rep2 = attest_card({"id": "plane:x", "component": "x", "book": "planes-of-law",
                        "layers": [("Dis", 2, [], None)], "gate_town": None,
                        "layer_note": None, "gloss": ""},
                       {1: "this dismal place distracts everyone"})
    assert rep2["refused"] == ["Dis"]
    rep3 = attest_card({"id": "plane:x", "component": "x", "book": "planes-of-law",
                        "layers": [("Dis", 2, [], None)], "gate_town": None,
                        "layer_note": None, "gloss": ""},
                       {1: "the iron city of Dis rises forever"})
    assert rep3["layers"] == {"Dis": [1]}

    # alias rescues an alt spelling (Pelion via amun-thys)
    rep4 = attest_card({"id": "plane:x", "component": "x", "book": "planes-of-chaos",
                        "layers": [("Pelion", 3, ["amun-thys"], None)], "gate_town": None,
                        "layer_note": None, "gloss": ""},
                       {9: "the dry wastes of Amun-Thys stretch white"})
    assert rep4["layers"] == {"Pelion": [9]}

    # realm cards well-formed: plane ids real, both names present or None+note
    plane_ids = {c["id"] for c in PLANE_CARDS} | {"plane:the-outlands"}
    for rc in REALM_CARDS:
        nm, power, plane, layer, comp, book, ra, pa, note = rc
        assert plane in plane_ids, nm
        assert book in BOX_SOURCES
        assert power is not None or note, nm
    # realm attestation: both names must witness; power=None needs its note
    card = ("Clangor", "Maglubiyet", "plane:acheron", None, "x", "planes-of-law", [], [], None)
    ok = attest_realm(card, {1: "the goblin realm of Clangor", 2: "Maglubiyet rules here"})
    assert ok["ok"] and ok["realm_pages"] == [1] and ok["power_pages"] == [2]
    bad = attest_realm(card, {1: "the goblin realm of Clangor"})
    assert not bad["ok"] and "unattested" in bad["why"]
    mystery = ("Stillsong", None, "plane:elysium", None, "x", "planes-of-conflict", [], [], "a mystery")
    assert attest_realm(mystery, {1: "the Stillsong rises"})["ok"]

    print("planes.py self-test: all green")
    sys.exit(0)
