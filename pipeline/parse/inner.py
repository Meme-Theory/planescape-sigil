"""inner.py — The Inner Planes (2634): the elemental skeleton.

The joint pour the rule-effect handoff reserved (M7 parked on it): Mimir takes
the IDENTITIES — 18 inner planes (5 merge onto In-the-Cage stubs), ~38 sites,
4 double-witnessed realms (the realms-round law: realm name AND power name must
attest), 17 power/archomental stubs, 1 proxy — while the per-plane survival LAW
(conditions, hazards, school-alteration margin tables, spell keys) rides the M7
witness package in build/family/rule-effect-handoff.md for Mechanus to pour.

Everything is CURATED CARDS text-validated against the reflow (the planes.py
law): a card may claim, the booklet's own text must witness, zero-witness
claims are REFUSED and reported. The print offset DRIFTS (+2 early, +1 by
mid-book — a page slipped) so cards claim anchor-based PDF page windows, never
computed offsets.

The back-matter creature index (PDF 127-129, "name (SOURCE)" per plane) parses
into per-plane `inhabitants[]` FIELDS — statless creature stubs would corrupt
the creature dim's L1, so the roster rides the plane nodes; real creature nodes
mint when the MC appendices pour, witnessed by these same pages.

Hazard pointer-NODES deliberately do not pour: dim:hazard is handoff-pending
and its nodes carry a Mechanus law_id — the pointers mint AFTER M7 exists
(the documented close-out sequence).

Pure gear-house: no store imports, self-tested in __main__.
"""
import re
from pathlib import Path

COMPONENT = "the-inner-planes/planescape-2634-inner-planes"
BOOK = "the-inner-planes"
SOURCE = ("source:the-inner-planes", "The Inner Planes", "2634", 1998)

# ---------------------------------------------------------------- plane cards
# (id, name, kind, composition, epithet, window(PDF), gloss, hazards_note,
#  sites[], spell_key_note)  — ids extend In the Cage's established scheme
# (plane:elemental-air, plane:para-ooze ⇒ para-/quasi-/energy- prefixes).
PLANE_CARDS = [
    {"id": "plane:elemental-air", "name": "the Elemental Plane of Air",
     "kind": "elemental", "composition": None, "epithet": "the Boundless Blue",
     "window": (22, 31), "aliases": ["plane of Air"],
     "gloss": "the eternal plunge — endless open sky, the most benign and merchant-trafficked "
              "of the Inner Planes",
     "hazards_note": "wind force and velocity govern travel; 'falling' is how a body gets around",
     "sites": ["the Citadel of Ice and Steel", "Taifun, the Palace of Tempests",
               "the Palace of Unseen Contemplation"]},
    {"id": "plane:elemental-earth", "name": "the Elemental Plane of Earth",
     "kind": "elemental", "composition": None, "epithet": "the Anvil",
     "window": (30, 42), "aliases": ["plane of Earth"],
     "gloss": "endless stretch of solid stone — home of the shad, the dao, and dwarven races "
              "whose real cities hide here",
     "hazards_note": "digging or magic to move at all; suffocation and crushing pressure for "
                     "the unprepared",
     "sites": ["the Aviary", "the Caverns Under the Stars", "the Great Dismal Delve"]},
    {"id": "plane:elemental-fire", "name": "the Elemental Plane of Fire",
     "kind": "elemental", "composition": None, "epithet": "the Crematorium",
     "window": (40, 52), "aliases": ["plane of Fire"],
     "gloss": "the endless sea of fire — islands of obsidian and pumice offer footing but no "
              "respite from the heat",
     "hazards_note": "the burning scales with natural AC (6d10/round at AC 10-8 down to nil at "
                     "-8); infravision useless; smoky-quartz glasses sold in the City of Brass",
     "sites": ["the City of Brass", "the Crimson Pillar", "the Crucible",
               "the Plain of Burnt Dreams"]},
    {"id": "plane:elemental-water", "name": "the Elemental Plane of Water",
     "kind": "elemental", "composition": None, "epithet": "the Bottomless Deep",
     "window": (52, 62), "aliases": ["plane of Water"],
     "gloss": "ocean without surface or floor — currents, storm surges, and whirlpools are "
              "the weather",
     "hazards_note": "breathing, currents (strength adjustments), whirlpools, burn water",
     "sites": ["the City of Glass", "the Citadel of Ten Thousand Pearls", "the Avenger"]},
    {"id": "plane:energy-positive", "name": "the Positive Energy Plane",
     "kind": "energy", "composition": None, "epithet": "the Life Well",
     "window": (61, 66), "aliases": ["Positive Energy Plane"],
     "gloss": "the plane of life itself — vim, vigor, soul-stuff; the powers come here to "
              "fill new creations",
     "hazards_note": "life-energy overload; no native guides — nobody is indigenous",
     "sites": []},          # the chapter names no discrete sites — prose features only
    {"id": "plane:energy-negative", "name": "the Negative Energy Plane",
     "kind": "energy", "composition": None, "epithet": None,
     "window": (65, 70), "aliases": ["Negative Energy Plane"],
     "gloss": "the most terrible place there is — even the fiends won't come; entropy "
              "embodied, the home of undeath",
     "hazards_note": "constant level/life drain; keep moving — anything that stops, freezes",
     "sites": ["Deathheart (of the Void)", "the Fortress of the Soul"]},
    {"id": "plane:para-ice", "name": "the Paraelemental Plane of Ice",
     "kind": "paraelemental", "composition": "Air + Water", "epithet": "the Precipice",
     "window": (70, 76), "aliases": ["paraplane of Ice", "plane of Ice"],
     "gloss": "frozen sky-cliff between Air and Water — Cryonax schemes to raise Ice to a "
              "true element; words freeze into salable crystals at its coldest",
     "hazards_note": "cold damage; the Mountain of Ultimate Winter freezes everything from "
                     "words to concepts",
     "sites": ["Arcolantha", "the Chiseled Estate", "the Mountain of Ultimate Winter",
               "Tiera Minuut"]},
    {"id": "plane:para-magma", "name": "the Paraelemental Plane of Magma",
     "kind": "paraelemental", "composition": "Fire + Earth", "epithet": None,
     "window": (76, 82), "aliases": ["paraplane of Magma", "plane of Magma"],
     "gloss": "the molten marriage of Fire and Earth — Chilimba, master of the lava mephits, "
              "tyrannizes it",
     "hazards_note": "molten stone and searing heat throughout",
     "sites": ["the Fields of Nevermore", "the Monolith", "Oolan's Laboratory",
               "Targath's Tower"]},
    {"id": "plane:para-ooze", "name": "the Paraelemental Plane of Ooze",
     "kind": "paraelemental", "composition": "Water + Earth", "epithet": None,
     "window": (82, 88), "aliases": ["paraplane of Ooze", "plane of Ooze"],
     "gloss": "the multiverse's sump — mud, slime, and sediment without bottom; Bwimb II "
              "holds what passes for a throne",
     "hazards_note": "suffocation in the muck; everything sinks",
     "sites": ["the Cysts", "Gnome's Home", "the Trash Heap"]},
    {"id": "plane:para-smoke", "name": "the Paraelemental Plane of Smoke",
     "kind": "paraelemental", "composition": "Air + Fire", "epithet": None,
     "window": (88, 94), "aliases": ["paraplane of Smoke", "plane of Smoke"],
     "gloss": "choking gray nothing between Air and Fire — coughing's nature's way of "
              "saying you've got lung tissue",
     "hazards_note": "breathing without protection is steady damage; vision smothered",
     "sites": ["the Choking Palace", "Cinderwood", "the Hidden City",
               "Reinsong's Ashen Fortress", "the Valley of Blinding Mist"]},
    {"id": "plane:quasi-lightning", "name": "the Quasielemental Plane of Lightning",
     "kind": "quasielemental", "composition": "Air + Positive Energy", "epithet": None,
     "window": (94, 98), "aliases": ["quasiplane of Lightning", "plane of Lightning"],
     "gloss": "one stormcloud after another — travelers come to charge items and mine "
              "vividium, solid lightning",
     "hazards_note": "the storms themselves; unauthorized flyers near tower-sites eat 10d6 bolts",
     "sites": ["the Eye", "the Tower of Storms"]},
    {"id": "plane:quasi-mineral", "name": "the Quasielemental Plane of Mineral",
     "kind": "quasielemental", "composition": "Earth + Positive Energy", "epithet":
         "the Treasure Trove of the Multiverse",
     "window": (97, 102), "aliases": ["quasiplane of Mineral", "plane of Mineral"],
     "gloss": "every valuable rock a body can think of — gold, silver, mithril, diamonds — "
              "in one solid glittering mass",
     "hazards_note": "solid matter travel (minimum Strength by earth type); razor crystal",
     "sites": ["the Tower of Lead"]},
    {"id": "plane:quasi-radiance", "name": "the Quasielemental Plane of Radiance",
     "kind": "quasielemental", "composition": "Fire + Positive Energy", "epithet": None,
     "window": (101, 106), "aliases": ["quasiplane of Radiance", "plane of Radiance"],
     "gloss": "light made substance — color and brilliance that blind and burn",
     "hazards_note": "sight-destroying brilliance; the unshielded go blind",
     "sites": ["the Kingdom of the Blind", "the Refuge of Color", "the Heart of Light"]},
    {"id": "plane:quasi-steam", "name": "the Quasielemental Plane of Steam",
     "kind": "quasielemental", "composition": "Water + Positive Energy", "epithet": None,
     "window": (105, 110), "aliases": ["quasiplane of Steam", "plane of Steam"],
     "gloss": "scalding fog without end — mist that boils a berk in his armor",
     "hazards_note": "scalding vapor; breathing and vision both suffer",
     "sites": ["Adrift", "the Straits of Varrigon", "the Tower of Ice"]},
    {"id": "plane:quasi-ash", "name": "the Quasielemental Plane of Ash",
     "kind": "quasielemental", "composition": "Fire + Negative Energy", "epithet": None,
     "window": (110, 116), "aliases": ["quasiplane of Ash", "plane of Ash"],
     "gloss": "the cold remains of fire — heat-leaching gray waste where everything decays "
              "and falls apart, particularly hope",
     "hazards_note": "heat drain (the fire's opposite); choking ash",
     "sites": ["Cavitius", "the Citadel of Former Flame", "the Crumbling Citadel"]},
    {"id": "plane:quasi-dust", "name": "the Quasielemental Plane of Dust",
     "kind": "quasielemental", "composition": "Earth + Negative Energy", "epithet": None,
     "window": (116, 120), "aliases": ["quasiplane of Dust", "plane of Dust"],
     "gloss": "matter's final crumbling — the plane that disassembles whatever lingers",
     "hazards_note": "disintegration of materials and flesh; the consuming nature of the plane",
     "sites": ["Citadel Alluvius"]},
    {"id": "plane:quasi-salt", "name": "the Quasielemental Plane of Salt",
     "kind": "quasielemental", "composition": "Water + Negative Energy", "epithet": None,
     "window": (119, 124), "aliases": ["quasiplane of Salt", "plane of Salt"],
     "gloss": "a limitless block of crystal alkaline matter, insatiably thirsty — the plane "
              "of endless need",
     "hazards_note": "desiccation: the plane draws the moisture from everything",
     "sites": ["Citadel Sealt", "the Mines"]},
    {"id": "plane:quasi-vacuum", "name": "the Quasielemental Plane of Vacuum",
     "kind": "quasielemental", "composition": "Air + Negative Energy", "epithet": None,
     "window": (122, 127), "aliases": ["quasiplane of Vacuum", "plane of Vacuum"],
     "gloss": "nothing, perfected — air unmade, where even sound starves",
     "hazards_note": "no air at all: suffocation is the plane",
     "sites": ["Citadel Exhalus"]},
]

# ---------------------------------------------------------------- site cards
# (name, plane_id, window, gloss, used_by_faction_or_None, aliases)
SITE_CARDS = [
    ("the Citadel of Ice and Steel", "plane:elemental-air", (27, 30),
     "the djinn caliph's seat in the Boundless Blue", None, ["Citadel of Ice and Steel"]),
    ("Taifun, the Palace of Tempests", "plane:elemental-air", (28, 31),
     "storm-palace ringed by lightning towers — unauthorized flyers eat 10d6 bolts "
     "within 1,000 yards", None, ["Taifun"]),
    ("the Aviary", "plane:elemental-earth", (38, 41),
     "a 15-mile air pocket holding the avariel's open city — wings for rent, "
     "gravity effectively nil", None, []),
    ("the Great Dismal Delve", "plane:elemental-earth", (37, 41),
     "the dao caste-empire; at its heart the Sevenfold Mazework surrounds the palace "
     "of the Great Khan of All Dao", None, ["Dismal Delve", "Sevenfold Mazework"]),
    ("the City of Brass", "plane:elemental-fire", (47, 51),
     "the efreet's fabled brass metropolis on the sea of fire", None, ["City of Brass"]),
    ("the Crucible", "plane:elemental-fire", (49, 52),
     "a site of the Crematorium", None, []),
    ("the Plain of Burnt Dreams", "plane:elemental-fire", (49, 53),
     "temple-plain patrolled against intruders; Imix and Zaaman Rul lately fought their "
     "great battle here, and the chant says an artifact of untold good sank in the "
     "Blazing Sea", None, ["Plain of Burnt Dreams"]),
    ("the City of Glass", "plane:elemental-water", (57, 62),
     "the Bottomless Deep's famous glass-walled trade city", None, ["City of Glass"]),
    ("the Citadel of Ten Thousand Pearls", "plane:elemental-water", (57, 62),
     "the marid padishah's opulent court", None, ["Ten Thousand Pearls"]),
    ("the Avenger", "plane:elemental-water", (57, 62),
     "a site of the Bottomless Deep", None, []),
    ("Deathheart (of the Void)", "plane:energy-negative", (66, 70),
     "a dark heart of the entropy plane", None, ["Deathheart"]),
    ("the Fortress of the Soul", "plane:energy-negative", (66, 70),
     "a bastion against (or of) the draining dark", None, ["Fortress of the Soul"]),
    ("Arcolantha", "plane:para-ice", (72, 76),
     "a polished air-sphere deep in the ice whose walls hold countless frozen-but-living "
     "beasts — museum or zoo, hard to say", None, []),
    ("the Chiseled Estate", "plane:para-ice", (71, 76),
     "a carved holding of the Precipice", None, ["Chiseled Estate"]),
    ("the Mountain of Ultimate Winter", "plane:para-ice", (71, 76),
     "true cold: freezes everything from words to concepts into crystals worth 100-5,000 gp; "
     "immoths store frozen explorers in the Caves of Folly", None,
     ["Mountain of Ultimate Winter", "Caves of Folly"]),
    ("Tiera Minuut", "plane:para-ice", (72, 76),
     "a bubble-shielded city built by priests of a forgotten wind goddess that slipped "
     "from Air to Ice — now the paraplane's rest stop", None, []),
    ("the Fields of Nevermore", "plane:para-magma", (77, 82),
     "a site of the molten paraplane", None, ["Fields of Nevermore"]),
    ("the Monolith", "plane:para-magma", (78, 82),
     "a great standing mass over the magma", None, []),
    ("Oolan's Laboratory", "plane:para-magma", (78, 82),
     "a researcher's hold amid the melt", None, ["Oolan"]),
    ("Targath's Tower", "plane:para-magma", (78, 82),
     "a tower standing against the molten tide", None, ["Targath"]),
    ("the Cysts", "plane:para-ooze", (83, 88),
     "pockets in the muck of the sump", None, []),
    ("Gnome's Home", "plane:para-ooze", (83, 88),
     "forty gnomes' sheltered hold in the ooze, led by Hundais Jeweleye", None,
     ["Hundais Jeweleye"]),   # head is display-font; the leader's name witnesses
    ("the Trash Heap", "plane:para-ooze", (83, 88),
     "where the multiverse's refuse settles", None, ["Trash Heap"]),
    ("the Choking Palace", "plane:para-smoke", (89, 94),
     "a court within the smother", None, ["Choking Palace"]),
    ("Cinderwood", "plane:para-smoke", (89, 94),
     "a forest of cinders in the gray", None, []),
    ("the Hidden City", "plane:para-smoke", (89, 94),
     "a burg the smoke keeps secret", None, ["Hidden City"]),
    ("Reinsong's Ashen Fortress", "plane:para-smoke", (89, 94),
     "a stronghold in the smoke", None, ["Reinsong"]),
    ("the Valley of Blinding Mist", "plane:para-smoke", (89, 94),
     "a vale where the smoke turns white and sight dies", None, ["Valley of Blinding Mist"]),
    ("the Eye", "plane:quasi-lightning", (95, 98),
     "the storm-free core, likely enchanted (it radiates 4.35 on the Derithrex scale); "
     "a towed pocket of elemental Earth floats within", None, []),
    ("the Tower of Storms", "plane:quasi-lightning", (95, 98),
     "an electric-blue tower of unknown element projecting from the Positive-Energy "
     "border wall; no way in, and the mephits are sure something dwells there", None,
     ["Tower of Storms", "TE9WER •f s+eRms"]),   # the page's own display-font form
    ("the Tower of Lead", "plane:quasi-mineral", (98, 102),
     "the quasiplane's lone named hold", None, ["Tower of Lead"]),
    ("the Kingdom of the Blind", "plane:quasi-radiance", (102, 106),
     "where the brilliance has taken every eye", None, ["Kingdom of the Blind"]),
    ("the Refuge of Color", "plane:quasi-radiance", (102, 106),
     "shelter in the searing light", None, ["Refuge of Color"]),
    ("the Heart of Light", "plane:quasi-radiance", (102, 106),
     "the radiance at its purest", None, ["Heart of Light"]),
    ("Adrift", "plane:quasi-steam", (105, 110),
     "a drifting hold in the scald", None, []),
    ("the Straits of Varrigon", "plane:quasi-steam", (105, 110),
     "a passage through the boiling fog", None, ["Straits of Varrigon", "Varrigon"]),
    ("the Tower of Ice", "plane:quasi-steam", (105, 110),
     "frozen defiance amid the steam", None, ["Tower of Ice", "T&WER &f ICE"]),         # the page's own display-font form
    ("Cavitius", "plane:quasi-ash", (111, 116),
     "a dread citadel in the heat-leached waste", None, []),
    ("the Citadel of Former Flame", "plane:quasi-ash", (111, 116),
     "monument to fire that was", None, ["Citadel of Former Flame", "Former Flame"]),
    ("the Crumbling Citadel", "plane:quasi-ash", (112, 116),
     "a Doomguard hold of about four hundred souls — fair relations with paraelementals "
     "and even the undead; Cagers arrive by portal to join their faction brothers",
     "faction:doomguard", ["Crumbling Citadel"]),
    ("Citadel Alluvius", "plane:quasi-dust", (116, 120),
     "the most populous Doomguard citadel in the Inner Planes, insulated by a continual "
     "wall of force; the Doomlord Pereid welcomes visitors of all kinds",
     "faction:doomguard", ["Alluvius"]),
    ("Citadel Sealt", "plane:quasi-salt", (120, 124),
     "Doomguard refuge for those who'd accelerate the multiverse's entropic death — "
     "welcomes lower-planar visitors, sells weapons and information to both sides",
     "faction:doomguard", ["Sealt"]),
    ("the Mines", "plane:quasi-salt", (120, 124),
     "where the salt is cut", None, ["Mines"]),
    ("Citadel Exhalus", "plane:quasi-vacuum", (123, 127),
     "the Doomguard's hold in the airless dark; even the Dustmen come to revere the "
     "Negative Energy Plane from its safety", "faction:doomguard", ["Exhalus"]),
]

# ---------------------------------------------------------------- realms
# The realms-round double-witness law: realm name AND power name must both
# attest within the window. (realm, power, plane_id, window, gloss, aliases)
REALM_CARDS = [
    ("the Crimson Pillar", "Kossuth", "plane:elemental-fire", (48, 53),
     "the Tyrant-King of Elementals holds court within the Pillar — its rays burn by "
     "distance (1d4/round at 100 miles up to 1d20 at one mile, doubled for the "
     "unprotected)", ["Crimson Pillar", "Pillar of Kossuth"]),
    ("the Caverns Under the Stars", "Geb", "plane:elemental-earth", (36, 41),
     "Geb's labyrinthine realm at the heart of the Anvil — a hidden portal to Elysium "
     "(and Nut) is said to stand at its center", ["Caverns Under the Stars"]),
    ("Stonemire", "Ogremoch", "plane:elemental-earth", (37, 41),
     "the Stone Tyrant's fortress on a plateau near the Magma border, decorated with "
     "molten fountains and the entombed bodies of those who crossed him", []),
    ("the Palace of Unseen Contemplation", "Chan", "plane:elemental-air", (26, 30),
     "the Silent One's floating stronghold of purest glass", ["Palace of Unseen Contemplation"]),
]

# ---------------------------------------------------------------- power stubs
# (name, kind, plane_id, window, gloss, aliases) — every name text-verified in
# its chapter; kinds typed honestly per the realms-round precedent.
POWER_STUBS = [
    ("Akadi", "elemental lord", "plane:elemental-air", (24, 30),
     "Queen of Air — the Azure Guard, her twelve devoted warriors, wear armor forged "
     "from the wind itself", []),
    ("Chan", "archomental (good)", "plane:elemental-air", (26, 30),
     "the Silent One — rules by reputation, watching Yan-C-Bin", []),
    ("Yan-C-Bin", "archomental (evil)", "plane:elemental-air", (26, 30),
     "the evil Prince of Air, watched and opposed by Chan", []),
    ("Grumbar", "elemental lord", "plane:elemental-earth", (36, 41),
     "the Earthlord — his presence is suspected at the plane's junctures, never visible", []),
    ("Geb", "power", "plane:elemental-earth", (36, 41),
     "Egyptian earth-god dwelling outside Heliopolis, in the Caverns Under the Stars", []),
    ("Sunnis", "archomental (good)", "plane:elemental-earth", (37, 41),
     "Princess of Good Earth — travels the Anvil hunting exotic treasures; a unique gift "
     "wins a mysterious boon", []),
    ("Ogremoch", "archomental (evil)", "plane:elemental-earth", (37, 41),
     "the Stone Tyrant, Prince of Elemental Evil — ten feet of rock with obsidian eyes", []),
    ("Kossuth", "elemental lord", "plane:elemental-fire", (48, 53),
     "the Tyrant-King of Elementals — serves his own needs as master of Fire; holds court "
     "in the Crimson Pillar", []),
    ("Imix", "archomental (evil)", "plane:elemental-fire", (48, 53),
     "Prince of Evil Fire — lately battled Zaaman Rul on the Plain of Burnt Dreams", []),
    ("Zaaman Rul", "archomental (good)", "plane:elemental-fire", (48, 53),
     "Prince of Good Fire — lost his great battle (and perhaps an artifact) to Imix", []),
    ("Istishia", "elemental lord", "plane:elemental-water", (56, 61),
     "the Water Lord of the Bottomless Deep", []),
    ("Persana", "power", "plane:elemental-water", (56, 61),
     "power of the tritons in the Bottomless Deep", []),
    ("Olhydra", "archomental (evil)", "plane:elemental-water", (56, 61),
     "Princess of Evil Water Creatures — chant says she absorbs her own petitioners", []),
    ("Cryonax", "archomental (evil)", "plane:para-ice", (71, 76),
     "Prince of Ice — schemes to raise Ice to a true element, in cold war with the wyrm "
     "Albrathanilar", []),
    ("Chilimba", "archomental (evil)", "plane:para-magma", (77, 82),
     "Master of the lava mephits — a tyrant who studied torture under a pit fiend", []),
    ("Bwimb II", "archomental (evil)", "plane:para-ooze", (83, 88),
     "the closest thing to a Paraelemental Princess of Ooze — an archomental in the "
     "loosest sense, and among the weakest; she inherited the post", ["Bwimb"]),
    ("Hastsezini", "power", "plane:para-smoke", (89, 94),
     "fire god served in Smoke through his proxy Jay Burning-Hand", []),
]

# (proxy name, power, plane_id, window, gloss)
PROXY_CARDS = [
    ("Jay Burning-Hand", "Hastsezini", "plane:para-smoke", (89, 94),
     "fire genasi proxy of Hastsezini — hawk-headed, coal-skinned, a gaze that sets "
     "objects aflame"),
]

# ------------------------------------------------------- creature index parse
INDEX_PAGES = (127, 128, 129)
# index headers are clean-font: "Elemental Plane of Fire", "Quasielemental
# Plane of Salt", "Positive Energy Plane"…
_HDR_RX = re.compile(
    r"^\s*((?:Elemental|Paraelemental|Quasielemental)\s+Plane\s+of\s+[A-Za-z]+"
    r"|(?:Positive|Negative)\s+Energy\s+Plane)\s*$")
_ENTRY_RX = re.compile(r"^\s*([a-z][a-z'\- ]{2,32}?)\s*\(([A-Za-z0-9, \"'\.]+)\)\s*$")

HDR_TO_PLANE = {
    "Elemental Plane of Air": "plane:elemental-air",
    "Elemental Plane of Earth": "plane:elemental-earth",
    "Elemental Plane of Fire": "plane:elemental-fire",
    "Elemental Plane of Water": "plane:elemental-water",
    "Positive Energy Plane": "plane:energy-positive",
    "Negative Energy Plane": "plane:energy-negative",
    "Paraelemental Plane of Ice": "plane:para-ice",
    "Paraelemental Plane of ke": "plane:para-ice",   # the scan's own form (dropped I)
    "Paraelemental Plane of Magma": "plane:para-magma",
    "Paraelemental Plane of Ooze": "plane:para-ooze",
    "Paraelemental Plane of Smoke": "plane:para-smoke",
    "Quasielemental Plane of Lightning": "plane:quasi-lightning",
    "Quasielemental Plane of Mineral": "plane:quasi-mineral",
    "Quasielemental Plane of Radiance": "plane:quasi-radiance",
    "Quasielemental Plane of Steam": "plane:quasi-steam",
    "Quasielemental Plane of Ash": "plane:quasi-ash",
    "Quasielemental Plane of Dust": "plane:quasi-dust",
    "Quasielemental Plane of Salt": "plane:quasi-salt",
    "Quasielemental Plane of Vacuum": "plane:quasi-vacuum",
}


def parse_creature_index(pages):
    """The back-matter per-plane inhabitant roster: 'name (SOURCE[, "Entry"])'
    lines under clean-font plane headers. Returns {plane_id: [(name, src), …]}
    plus the pages each plane's list witnessed on."""
    out, current, witness = {}, None, {}
    for pg in INDEX_PAGES:
        txt = pages.get(pg)
        if not txt:
            continue
        # de-wrap: an entry's source-paren may wrap to the next line
        lines, buf = [], ""
        for raw in txt.splitlines():
            s = raw.strip()
            if buf:
                s = (buf + " " + s).strip()
                buf = ""
            if s and "(" in s and ")" not in s.split("(")[-1] and not _HDR_RX.match(s):
                buf = s
                continue
            lines.append(s)
        for s in lines:
            hm = _HDR_RX.match(s)
            if hm:
                current = HDR_TO_PLANE.get(re.sub(r"\s+", " ", hm.group(1)))
                continue
            em = _ENTRY_RX.match(s)
            if em and current:
                out.setdefault(current, []).append(
                    (em.group(1).strip(), em.group(2).strip()))
                witness.setdefault(current, set()).add(pg)
    return out, {k: sorted(v) for k, v in witness.items()}


# ---------------------------------------------------------------- attestation
def load_component(build_root):
    d = Path(build_root) / COMPONENT / "reflow"
    return {int(p.stem.split("-")[1]): p.read_text(encoding="utf-8")
            for p in d.glob("page-*.txt")}


def _name_rx(name):
    pat = r"\s+".join(re.escape(w) for w in name.split())
    if len(name) <= 4:
        return re.compile(rf"\b{pat}\b")
    return re.compile(rf"\b{pat}\b", re.IGNORECASE)


def attest_window(name, aliases, pages, window):
    lo, hi = window
    rxs = [_name_rx(name)] + [_name_rx(a) for a in aliases]
    return sorted(pg for pg, txt in pages.items()
                  if lo <= pg <= hi and any(rx.search(txt) for rx in rxs))


def attest_plane_card(card, pages):
    names = [card["name"]] + card.get("aliases", [])
    if card.get("epithet"):
        names.append(card["epithet"])
    pp = sorted(set().union(*[attest_window(n, [], pages, card["window"]) for n in names]))
    return {"pages": pp, "refused": not pp}


def attest_site(name, aliases, pages, window):
    # strip leading article for the witness search ('the Aviary' → 'Aviary')
    base = re.sub(r"^the\s+", "", name, flags=re.I)
    pp = attest_window(base, aliases, pages, window)
    return {"pages": pp, "refused": not pp}


def attest_realm(card, pages):
    realm, power, plane, window, gloss, aliases = card
    base = re.sub(r"^the\s+", "", realm, flags=re.I)
    rp = attest_window(base, aliases, pages, window)
    pp = attest_window(power, [], pages, window)
    ok = bool(rp and pp)
    return {"ok": ok, "realm_pages": rp, "power_pages": pp,
            "why": None if ok else
            f"unattested: {'realm' if not rp else 'power'} name not witnessed in window"}


if __name__ == "__main__":
    import sys

    # cards well-formed; site planes resolve to card ids; windows sane
    plane_ids = {c["id"] for c in PLANE_CARDS}
    assert len(PLANE_CARDS) == 18 and len(plane_ids) == 18
    kinds = {}
    for c in PLANE_CARDS:
        assert c["kind"] in ("elemental", "paraelemental", "quasielemental", "energy")
        kinds[c["kind"]] = kinds.get(c["kind"], 0) + 1
        lo, hi = c["window"]
        assert 6 <= lo < hi <= 130, c["id"]
        if c["kind"] in ("paraelemental", "quasielemental"):
            assert c["composition"], c["id"]
    assert kinds == {"elemental": 4, "energy": 2, "paraelemental": 4, "quasielemental": 8}
    seen_sites = set()
    for nm, pid, win, gloss, fac, al in SITE_CARDS:
        assert pid in plane_ids, nm
        assert nm not in seen_sites, nm
        seen_sites.add(nm)
        assert fac in (None, "faction:doomguard"), nm
    # every plane-card 'sites' claim is carded (realms count as sites too)
    carded = {nm for nm, *_ in SITE_CARDS} | {r[0] for r in REALM_CARDS}
    for c in PLANE_CARDS:
        for s in c["sites"]:
            assert s in carded, (c["id"], s)
    for nm, power, pid, win, gloss, al in REALM_CARDS:
        assert pid in plane_ids, nm
    for nm, kind, pid, win, gloss, al in POWER_STUBS:
        assert pid in plane_ids, nm

    # attestation: refuses what the text lacks, accepts what it holds
    fake = {7: "The shad dwell in the Anvil near the Aviary."}
    rep = attest_site("the Aviary", [], fake, (6, 10))
    assert rep["pages"] == [7] and not rep["refused"]
    rep = attest_site("the Aviary", [], fake, (20, 30))
    assert rep["refused"]                                  # outside the window
    card = ("Stonemire", "Ogremoch", "plane:elemental-earth", (6, 10), "", [])
    ok = attest_realm(card, {7: "Ogremoch dwells in Stonemire."})
    assert ok["ok"]
    bad = attest_realm(card, {7: "Stonemire stands silent."})
    assert not bad["ok"] and "power" in bad["why"]

    # creature index parser: headers split, entries bind, wraps join
    pages = {127: "\n".join([
        "Elemental Plane of Fire",
        "azer (MAl, \"Elemental Kin, Fire\")",
        "efreeti (MM,",
        "\"Genie\")",
        "fire bat (PSJ)",
        "Quasielemental Plane of Salt",
        "facet (PS3)",
    ])}
    idx, wit = parse_creature_index(pages)
    assert ("fire bat", "PSJ") in idx["plane:elemental-fire"]
    assert idx["plane:quasi-salt"] == [("facet", "PS3")]
    assert any(n == "efreeti" for n, _ in idx["plane:elemental-fire"])
    assert wit["plane:elemental-fire"] == [127]

    print("inner.py self-test: all green")
    sys.exit(0)