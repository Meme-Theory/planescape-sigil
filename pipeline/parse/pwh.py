"""pwh.py — The Planewalker's Handbook (2620): the player bible.

Three dims pour from this book (DIMENSIONS registry close-out 2026-06-06):
  race  — 8 planar PC races as CURATED CARDS, name-attested against the reflow
          (the planes.py/REALM_CARDS law: a card may claim, the text must witness).
  class — 4 planewalker kits + 3 location kits + the 4 base-class stubs they hang
          off, curated cards, attested the same way.
  spell — ~60 spells PARSED from the Magic-on-the-Planes chapter (printed 112-131).
          The head is rigid (NAME line + "(School[, Elemental [X]]; Level N)") so
          IDENTITY is certain; the two-column reflow scrambles head→statline
          binding for adjacent heads, so stat fields bind ONLY when exactly one
          field-group follows a head before the next head ("verified or absent").
          Ambiguous spells ship identity-only with stats_unbound=True; the
          SPELL_STAT_CURATIONS table promotes them after a human reads the page.

psionic does NOT pour: the book has no psionics section (three scattered asides,
pp. 8/92/141 printed) — re-parked in the DIMENSIONS ledger, wrong-book corrected.

Pure gear-house: no store imports, self-tested in __main__.
"""
import re
from pathlib import Path

COMPONENT = "the-planewalker-s-handbook/planescape-2620-the-planewalkers-handbook"
BOOK = "the-planewalker-s-handbook"
SOURCE = ("source:planewalkers-handbook", "The Planewalker's Handbook", "2620", 1996)

# printed page = PDF page - 2 (verified: races head printed 68 = page-0070.txt)
PAGE_OFFSET = 2

# ---------------------------------------------------------------- race cards
# Mechanics are PARAPHRASE (official scan stays cite-only); every card names its
# PDF pages and the pour attests the race name (and each variant head) there.
RACE_CARDS = [
    {"id": "race:aasimar", "name": "Aasimar", "pages": [72, 73],
     "ability_mods": "+1 Str, +1 Wis, -2 Con (option: +1 Cha in place of Str)",
     "traits": ["infravision 60 ft", "+1 to surprise checks",
                "half damage from heat and cold attacks",
                "+2 saves vs charm/fear/emotion/domination",
                "10% magic resistance (nonwizards only)"],
     "origin_plane": "the Upper Planes (celestial descent)", "native_to": None,
     "subtype": "plane-touched", "variants": [],
     "classes": "all classes; many multiclass combos (fighter/priest, fighter/mage, "
                "ranger/priest, mage/priest, priest/bard et al.)",
     "alignment": "any nonevil (most lawful/neutral/chaotic good)",
     "gloss": "scions of celestials — golden-haired, noble to a fault; the tiefling coin's other side"},
    {"id": "race:bariaur", "name": "Bariaur", "pages": [73],
     "ability_mods": "male +1 Str/+1 Con, -1 Wis/-1 Dex; female +1 Int/+1 Wis, -1 Str/-1 Dex",
     "traits": ["infravision 60 ft", "movement 15", "max level 13 in any allowed class",
                "male: horn butt 1d8 (+Str); charge ≥30 ft triples damage, "
                "save vs breath or take the same, knocks down size M- half the time",
                "female: +2 surprise rolls, +3 saves vs spell"],
     "origin_plane": "the Upper Planes — most claim Ysgard; herds in Elysium, the Beastlands, Arborea",
     "native_to": "plane:ysgard",
     "subtype": None, "variants": [],
     "classes": "male: fighter/ranger/paladin/priest; female: fighter/priest/wizard",
     "alignment": "any nonevil (most chaotic good)",
     "gloss": "goat-bodied wanderers of the Upper Planes; fussy pelts, fierce when the herd's threatened"},
    {"id": "race:genasi", "name": "Genasi", "pages": [73, 74, 75, 76, 77],
     "ability_mods": "per element (see variants)",
     "traits": ["plane-touched: human x elemental descent",
                "-2 reaction penalty from all planar races",
                "+1 save vs their element's magic per 5 levels (all variants)",
                "one elemental spell-like power 1/day at 5th-level use (per variant)"],
     "origin_plane": "the Inner Planes (elemental descent)", "native_to": None,
     "subtype": "plane-touched",
     "variants": [
         {"name": "Air Genasi", "epithet": "wind dukes", "pages": [74],
          "ability_mods": "+1 Dex, +1 Int, -1 Wis, -1 Cha",
          "traits": ["levitate 1/day (as 5th-level wizard)", "no need to breathe",
                     "+1 save vs air-based magic per 5 levels"],
          "classes": "priest/fighter/wizard; MC fighter/cleric, fighter/wizard; "
                     "specialists must take air elementalism; no druids",
          "alignment": "any nonlawful"},
         {"name": "Earth Genasi", "epithet": "stone princes", "pages": [74, 75],
          "ability_mods": "+1 Str, +1 Con, -1 Wis, -1 Cha",
          "traits": ["natural AC 8", "innate appraising (stone-lore)",
                     "pass without trace 1/day (as 5th-level priest)",
                     "+1 save vs earth-based magic per 5 levels"],
          "classes": "fighter/wizard/priest, never multiclassed; earth elementalism; "
                     "no druids (stone champions: rare paladin variant, mostly NPC)",
          "alignment": "any nonchaotic"},
         {"name": "Fire Genasi", "epithet": "flame lords", "pages": [75, 76],
          "ability_mods": "+1 Int, -1 Cha",
          "traits": ["no damage from normal flame", "infravision 60 ft",
                     "affect normal fires 1/day (as 5th-level wizard)",
                     "+1 save vs fire-based magic per 5 levels"],
          "classes": "fighter/wizard or fighter/wizard MC; fire elementalism",
          "alignment": "any"},
         {"name": "Water Genasi", "epithet": "sea kings", "pages": [76, 77],
          "ability_mods": "+1 Con, -1 Cha",
          "traits": ["amphibious (breathes water, no gills)", "swim 15",
                     "create water 1/day (as 5th-level caster)",
                     "+1 save vs water-based magic per 5 levels"],
          "classes": "fighter/wizard/priest/rogue (incl. bard); MC fighter/priest, "
                     "fighter/thief; water elementalism; no druids",
          "alignment": "any neutral (not LG/CG/LE/CE)"}],
     "classes": "per element (see variants)",
     "alignment": "per element (see variants)",
     "gloss": "the elemental plane-touched — wind dukes, stone princes, flame lords, sea kings; "
              "arrogant one and all, and each genasi dislikes every other"},
    {"id": "race:githzerai", "name": "Githzerai", "pages": [77],
     "ability_mods": "+1 Int, +1 Dex, -1 Str, -1 Wis",
     "traits": ["infravision 60 ft",
                "warriors/thieves: always-on magic resistance 5%/level (max 95%) — "
                "affects own magic items (a resisted item is useless to them forever); "
                "mages purge it to cast; fighter/wizards choose",
                "PC githzerai lose the native plane shift ability"],
     "origin_plane": "Limbo (adopted home after the gith schism)", "native_to": "plane:limbo",
     "subtype": None, "variants": [],
     "classes": "fighter, fighter/wizard, wizard, thief; no priests (they revere the wizard-king)",
     "alignment": "any nonlawful",
     "gloss": "severe ascetics of Limbo — ex-slaves of the illithids, blood-foes of the githyanki"},
    {"id": "race:planar-half-elf", "name": "Planar Half-Elf", "pages": [77],
     "ability_mods": "as Player's Handbook",
     "traits": ["created per the Player's Handbook; on the planes a half-elf "
                "barely raises an eyebrow next to the plane-touched"],
     "origin_plane": "planar human x prime elf unions", "native_to": None,
     "subtype": None, "variants": [],
     "classes": "as Player's Handbook", "alignment": "any",
     "gloss": "rarer than prime half-elves and far less remarked — pointy-eared humans to most planars"},
    {"id": "race:planar-human", "name": "Planar Human", "pages": [78],
     "ability_mods": "as Player's Handbook",
     "traits": ["created per the Player's Handbook",
                "DM option: minor abilities by place of birth"],
     "origin_plane": "everywhere — Pandemonium's caves to the plane of Fire", "native_to": None,
     "subtype": None, "variants": [],
     "classes": "as Player's Handbook", "alignment": "any",
     "gloss": "ubiquitous as their prime kin; no racial gifts, all determination — bloods, not clueless"},
    {"id": "race:rogue-modron", "name": "Rogue Modron", "pages": [78, 79, 80],
     "ability_mods": "+1 Int, +1 Con, -1 Dex, -1 Cha",
     "traits": ["6-ft cube body (quadrone-like); genderless, ageless",
                "double normal sight range (readjustable vision)",
                "secret doors 2-in-6, concealed doors 3-in-6",
                "30% resistance to illusion/energy drain/charm/sleep/fear/domination "
                "and similar mind-affecting magic",
                "+1 saves vs fire, cold, acid", "natural AC 8", "movement 15",
                "surprised for twice the normal duration", "-1 reaction vs chaotics",
                "cannot ride mounts, wear normal armor, or squeeze through narrow gaps",
                "DM options: preset actions; predetermined initiative"],
     "origin_plane": "Mechanus (exiled from the clockwork hierarchy)", "native_to": "plane:mechanus",
     "subtype": None, "variants": [],
     "classes": "fighter or wizard (specialists yes, wild mages never); no multiclass",
     "alignment": "lawful only (good/neutral/evil open)",
     "gloss": "a modron gone rogue — cast out of Mechanus with the forbidden glimmer of self"},
    {"id": "race:tiefling", "name": "Tiefling", "pages": [80, 81, 82, 83],
     "ability_mods": "+1 Int, +1 Cha, -1 Str, -1 Wis",
     "traits": ["infravision 60 ft", "darkness 15-ft radius 1/day",
                "half damage from cold", "+2 saves vs fire, electricity, poison",
                "options: roll 5x on the Tiefling Abilities table in place of the "
                "standard package; 1d4 rolls on the Appearance table (tables printed p80)"],
     "origin_plane": "an unnamed (usually lower-planar) heritage", "native_to": None,
     "subtype": "plane-touched", "variants": [],
     "classes": "fighter/ranger/wizard (and specialists)/priest/thief/bard; MC fighter/wizard, "
                "fighter/priest, fighter/thief, wizard/thief, priest/thief",
     "alignment": "any but lawful good",
     "gloss": "human and 'something else' — the mystery is the stigma; loners who out-dare the multiverse"},
]

# ---------------------------------------------------------------- class cards
BASE_CLASSES = [
    ("class:fighter", "Fighter", "the warrior group's core class"),
    ("class:wizard", "Wizard", "mages and specialists; the magic-using core class"),
    ("class:priest", "Priest", "clerics and specialty priests of the powers"),
    ("class:rogue", "Rogue", "thieves and bards; the cross-trade core class"),
]

KIT_CARDS = [
    {"id": "class:planewalker-warrior", "name": "Planewalker Warrior", "pages": [95],
     "parent_class": "class:fighter", "kind": "planewalker",
     "classes_allowed": "fighters (modifiable for rangers/paladins)",
     "requirements": "bonus: planar survival (one plane); required: planar sense",
     "benefits": ["treats weapon-enchantment requirements as one step lower "
                  "(never below +1) when striking only-hit-by-magic creatures",
                  "starts play with a simple key to a permanent portal of the player's choice"],
     "hindrances": ["starting proficiencies must serve the profession — no homebody crafts"],
     "located_in": None,
     "gloss": "professional planar muscle — caravan guard, retriever of anything from herbs to true names"},
    {"id": "class:planewalker-wizard", "name": "Planewalker Wizard", "pages": [96],
     "parent_class": "class:wizard", "kind": "planewalker",
     "classes_allowed": "mages and specialists",
     "requirements": "required: portal feel; recommended: planar survival, planology, spell recovery",
     "benefits": ["reduces a foe's magic resistance by 5% +1% per level before the roll"],
     "hindrances": ["one chosen plane (never a demiplane) where the wizard can NEVER "
                    "make spell keys function"],
     "located_in": None,
     "gloss": "knows when to fireball and when to rock-to-mud — magic's a tiefling hireling, "
              "it won't always work just 'cause you want it to"},
    {"id": "class:planewalker-priest", "name": "Planewalker Priest", "pages": [97],
     "parent_class": "class:priest", "kind": "planewalker",
     "classes_allowed": "clerics and most specialty priests",
     "requirements": "bonus: etiquette; required: local history (power's realm); "
                     "recommended: ancient history, planology, religion",
     "benefits": ["+1 attack and damage on planes where their spellcasting is diminished",
                  "three planar contacts (player picks the planes, DM the particulars)"],
     "hindrances": ["must obey the commands of their power's proxies — errands follow"],
     "located_in": None,
     "gloss": "the power's eyes and ears on the Ring; scrolls, contacts, and a well-applied cudgel"},
    {"id": "class:planewalker-rogue", "name": "Planewalker Rogue", "pages": [98],
     "parent_class": "class:rogue", "kind": "planewalker",
     "classes_allowed": "thieves (some bards)",
     "requirements": "bonus: direction sense; required: planar sense; "
                     "recommended: appraisal, disguise, planar survival, weather sense",
     "benefits": ["climb walls doubles as general get-around-nonhorizontal-environments "
                  "(Mechanus gears, Gehenna slopes, Baator glass plains)",
                  "bards may take the priest kit's planar contacts instead"],
     "hindrances": ["-10% hide in shadows / move silently against law-enforcement "
                    "(Harmonium, Mercykillers, Guvners)",
                    "planar locks are wise to them: -10% open locks in Sigil and like places"],
     "located_in": None,
     "gloss": "masters of the chant working the big ride — the cant itself half-arose to fox the law"},
    {"id": "class:abyssal-warrior", "name": "Abyssal Warrior", "pages": [99],
     "parent_class": "class:fighter", "kind": "location",
     "classes_allowed": "fighters only; humans and tieflings likeliest; chaotic, never good — mostly NPC",
     "requirements": "bonus: planar survival (Abyss); required: blind fighting",
     "benefits": ["+1 to all saving throws (Abyss-forged hardiness)",
                  "starts with a weapon and armor of choice from the Abyssal forges"],
     "hindrances": ["-3 reaction vs nontanar'ri", "baatezu treat them as tanar'ri on sight",
                    "-1 attack/ability/proficiency checks in bright sunlight"],
     "located_in": "plane:the-abyss",
     "gloss": "mortal muscle of the Blood War — useful keeps you alive in the Abyss"},
    {"id": "class:floating-sorcerer", "name": "Floating Sorcerer", "pages": [99],
     "parent_class": "class:wizard", "kind": "location",
     "classes_allowed": "any wizard raised on the plane of Air (air genasi the obvious choice); "
                        "specialists are air elementalists",
     "requirements": "weapons: thrown dagger and dart only; required: riding (airborne — winged harness)",
     "benefits": ["glider harness: 1,000 ft glide per 100 ft descent; Int check rides strong "
                  "winds upward; class E maneuverability, MV 18, dies at 6 damage",
                  "+1 saves/ability checks vs balance, climbing, falling, knockdown",
                  "boost one factor of any levitation/flight/air-moving spell by 50% at casting"],
     "hindrances": ["double encumbrance penalties",
                    "may never learn agriculture, mining, land riding, seamanship, or swimming"],
     "located_in": None,   # Elemental Plane of Air — not a poured node until 2634
     "gloss": "masters of the sky on wood-and-skin wings; at home soaring, lumbering never"},
    {"id": "class:hinterland-bandit", "name": "Hinterland Bandit", "pages": [100],
     # p100 is grade C/D: OCR shreds 'bandits' to 'band.its'/'bandi' — the alias
     # is the page's own remnant (the Blood Tor law: recover by the text's form)
     "aliases": ["Hinterland band"],
     "parent_class": "class:rogue", "kind": "location",
     "classes_allowed": "rogues of the Outlands' Hinterlands; mostly human, some half-elves/tieflings",
     "requirements": "weapons: short bow first, short sword second; bonus: riding (land); "
                     "required: animal handling",
     "benefits": ["starts with a riding horse (or like creature) and tack",
                  "no penalty for any action from the saddle",
                  "+1 attack and saves in flat open terrain (≥1,000 sq ft clear)"],
     "hindrances": ["-1 attack and saves underground or fully enclosed (Pandemonium's tunnels)"],
     "located_in": "plane:the-outlands",
     "gloss": "caravan-raiders of the open Hinterlands; not necessarily evil, and many leave the life"},
]

# kit-structure rubric pages (attest base classes here)
KIT_CHAPTER_PAGES = list(range(92, 104))

# ---------------------------------------------------------------- item cards
# Planewalking Equipment, printed 132-141 (PDF 134-143). Mechanics are
# PARAPHRASE; printed tables transcribe only legible cells ("verified or absent"
# at the cell level — a weight the reflow lost stays absent). The four embedded
# d100 tables (fiend globe / grue bottle / elemental-breathing potion /
# outer-planar-protection scroll) are TABLE substance → Modron's lane (handoff
# §PWH D13); the cards keep identity + the note. The printed-136 "What to Look
# For" survey lists EXISTING core/ToM items — cross-refs, not identities this
# book owns; recorded in the ledger, never minted.
ITEM_CARDS = [
    # — tools of the trade (nonmagical) —
    {"id": "item:baatorian-green-steel", "name": "Baatorian Green Steel",
     "pages": [134, 136], "kind": "material", "magical": False,
     "aliases": ["green steel"],
     "properties": [
         "ore of Avernus (Baator's first layer) tempered into a metal lighter than steel",
         "razor-fine edges: weapons deal more damage than standard counterparts",
         "armor sits two AC classes better than its standard counterpart",
         "NOT magical; at least 4x the standard price; rare even in Sigil markets"],
     "table": {"armor (cost gp / weight lbs / AC)": [
                   "banded mail 800 / 20 / 2", "chain mail 350 / 25 / 3",
                   "plate mail 2,500 / 30 / 1", "scale mail 500 / 25 / 4"],
               "weapons (cost gp / weight lbs / dmg S-M / L)": [
                   "dagger 8 / — / 1d4+1 / 1d4", "knife 2 / — / 1d4 / 1d3",
                   "javelin 2 / 1 / 1d8 / 1d8", "spear 4 / 3 / 1d8 / 1d10",
                   "bastard sword 100 / 5 / 1H 1d10, 2H 2d6 / 1H 1d12+1, 2H 2d10",
                   "long sword 60 / 2 / 1d10 / 1d12+1", "scimitar 60 / 2 / 1d10 / 1d10",
                   "short sword 40 / 2 / 1d8 / 1d10",
                   "two-handed sword 200 / 8 / 1d12 / 2d10"]},
     "origin": "the wastelands of Avernus, Baator",
     "gloss": "the baatezu's lighter, crueler metal — four times the jink, twice the edge"},
    {"id": "item:bariaur-armor", "name": "Bariaur Armor", "pages": [136],
     "kind": "armor", "magical": False,
     "aliases": ["8ariaur armor"],          # the scan renders the B as 8
     "properties": ["mail tailored to bariaur physiology; AC identical to humanoid armor",
                    "costs and weighs more for the extra material; most bariaur go light"],
     "table": {"cost gp / weight lbs": [
         "banded mail 250 / 50", "brigantine 150 / 45", "bronze plate mail 500 / 60",
         "chain mail 90 / 55", "field plate 2,500 / 75", "full plate 5,000-15,000 / 85",
         "leather 7 / 25", "padded 5 / 20", "plate mail 720 / 65", "ring mail 150 / 45",
         "splint mail 100 / 50", "studded leather 25 / 40"]},
     "origin": None, "gloss": "planar armorers fit the goat-bodied; barding is for primes"},
    {"id": "item:bariaur-harness", "name": "Bariaur Harness", "pages": [136],
     "kind": "equipment", "magical": False, "cost": "3 gp", "weight": "4 lbs",
     "properties": ["frame backpack for the bariaur back: 90 lbs capacity, 3.5 x 3 x 1 ft"],
     "origin": None, "gloss": "the wanderer's pack, built for four legs"},
    {"id": "item:bariaur-horned-helm", "name": "Bariaur Horned Helm", "pages": [136],
     "kind": "armor", "magical": False, "cost": "45 gp", "weight": "10 lbs",
     "aliases": ["homed helm"],     # the scan's own form
     "properties": [
         "spiked helm: charge still deals 1d8 (+Str) but a failed save vs breath "
         "costs only HALF the damage dealt (the horns absorb the shock)",
         "lets bariaur females make charging attacks",
         "tailor-made per wearer: 1d6+2 days construction"],
     "origin": None, "gloss": "horns for the hornless, shock-absorbers for the horned"},
    {"id": "item:bariaur-saddle", "name": "Bariaur Saddle", "pages": [136],
     "kind": "equipment", "magical": False, "cost": "10 gp", "weight": "10 lbs",
     "aliases": ["bariaur addle"],
     "properties": ["leather harness-saddle for carrying a two-foot when expedience demands"],
     "origin": None, "gloss": "for hauling slow-movers — dignity not included"},
    {"id": "item:bariaur-shoes", "name": "Bariaur Shoes", "pages": [136],
     "kind": "equipment", "magical": False, "cost": "5 gp (set of four)",
     "aliases": ["bariaur 110es", "bariaur hoes"],
     "properties": ["iron-shod foot protection for rough ground; negligible weight"],
     "origin": None, "gloss": "horseshoes that would offend a horse"},
    {"id": "item:celestial-etheroscope", "name": "Celestial Etheroscope", "pages": [136],
     "kind": "tool", "magical": False, "cost": "1,000 gp", "weight": "50 lbs",
     "aliases": ["etheroscope"],            # display-font head; the body witnesses
     "properties": [
         "brass-bound lenses, tubes, and colored-liquid vials, 2 x 1 x 1 ft, extremely delicate",
         "used exclusively with the planology proficiency to read a plane's tides of fortune",
         "only specially trained planar craftsmen can build one; nonmagical despite appearances"],
     "origin": None, "gloss": "fortune-telling for planologists, plumbing for everyone else"},
    {"id": "item:modron-armor", "name": "Modron Armor", "pages": [136, 137],
     "kind": "armor", "magical": False, "cost": "120 gp", "weight": "75 lbs",
     "properties": ["flat bolted/strapped metal sheets over the cube: AC 4",
                    "no tailoring — every rogue modron is the same size"],
     "origin": None, "gloss": "plate for a box; one size fits all, literally"},
    {"id": "item:modron-storage-container", "name": "Modron Storage Container",
     "pages": [137], "kind": "equipment", "magical": False, "cost": "5 gp", "weight": "10 lbs",
     "properties": ["metal-and-leather box bolted to the chassis: 100 lbs capacity, 1.5 x 3 x 1 ft"],
     "origin": None, "gloss": "luggage you bolt on"},
    {"id": "item:modron-clothing", "name": "Modron Clothing", "pages": [137],
     "kind": "equipment", "magical": False,
     "aliases": ["clotiijng"],              # MooRON CLOTIIJNG — the page's own form
     "properties": ["cloaks and (more commonly) belts cut for the cube run 3-5x normal price"],
     "origin": None, "gloss": "a human has very little need for a 12-foot-long belt"},
    {"id": "item:sickle", "name": "Sickle", "pages": [137],
     "kind": "weapon", "magical": False, "cost": "6 sp", "weight": "3 lbs",
     "properties": ["one-handed chiv: 1-ft curved blade sharp on the concave side",
                    "size S, type S, speed 4, dmg 1d4+1 (S-M) / 1d4 (L)",
                    "easily hidden in a belt; for cutting stalks, not swathes"],
     "origin": None, "gloss": "the small harvest blade — favored where it looks innocent"},
    {"id": "item:scythe", "name": "Scythe", "pages": [137],
     "kind": "weapon", "magical": False, "cost": "5 gp", "weight": "8 lbs",
     "properties": ["two-handed: 3.5-4 ft blade on a curved, pegged haft",
                    "size M, type P/S, speed 8, dmg 1d6+1 (S-M) / 1d8 (L)",
                    "takes practice to swing at a berk's head; wicked-looking"],
     "origin": None,
     "gloss": "the big harvest blade — valued as a tool topside, as a statement below"},
    # — new magical items —
    {"id": "item:bakus-trumpet", "name": "Baku's Trumpet", "pages": [139],
     "kind": "wondrous", "magical": True,
     "properties": [
         "nondescript brass horn of the Upper Planes; sounding it deals 1d8 to evil "
         "creatures within 40 ft, who also save vs paralyzation or flee as per fear",
         "3 uses/day; an evil user saves vs paralyzation or is struck mute — "
         "it never functions for them"],
     "origin": "the Upper Planes", "gloss": "the baku's bellow, bottled in brass"},
    {"id": "item:bottled-breath", "name": "Bottled Breath", "pages": [139],
     "kind": "wondrous", "magical": True,
     "aliases": ["bomed breatii"],          # BomED BREATII — tt/th fusions
     "properties": [
         "clear bottle of limitless pure air: uncork and drink a breath",
         "sustains a body indefinitely where nothing's breathable",
         "open longer than one round and the magic goes inert — recork every draught"],
     "origin": None, "gloss": "an empty-looking bottle a berk's life hangs on"},
    {"id": "item:chains-of-light", "name": "Chains of Light", "pages": [139],
     "kind": "wondrous", "magical": True,
     "aliases": ["chai s of light"],        # CHAI s OF LIGHT — dropped N
     "properties": [
         "chains forged of solid sunbeams (the chant names Reorx, or Clangeddin's halls, "
         "or plain Arcadian smithies)",
         "binding an evil creature lights them like continual light; evil/chaotic onlookers "
         "save or are blinded 1d6 rounds (-4 attacks, saves, AC); LG/NG/LN gaze freely",
         "a struggling captive takes escalating heat-or-cold: 1d2, then 1d4, 1d6… "
         "to 1d12/round, whichever hurts it more; stops when the struggle stops"],
     "origin": "Arcadia (by the chant)", "gloss": "sunlight that holds a fiend still"},
    {"id": "item:fiend-globe", "name": "Fiend Globe", "pages": [139],
     "kind": "wondrous", "magical": True,
     "properties": [
         "hollow ceramic globe under 3 inches; breaking it summons a minor fiend "
         "(d100 table, nupperibo through night hag) that serves faithfully for 1 hour, "
         "then is drawn home; single-use",
         "works even on planes where summoning is normally impossible — only an "
         "antimagic shell stops it",
         "the chant: baatezu lords mint them as rewards for faithful servants",
         "embedded d100 fiend table → Modron rollable (handoff D13)"],
     "origin": "the Lower Planes (baatezu work)", "gloss": "break glass for emergency fiend"},
    {"id": "item:grue-bottle", "name": "Grue Bottle", "pages": [139, 140],
     "kind": "wondrous", "magical": True,
     "properties": [
         "opaque bottle: shake and open for a temporary Inner-Planes gate that pours "
         "out a grue, mephit, or rarer elemental being (d100 table)",
         "the first (random) creature binds to the bottle and serves 10d10+50 rounds "
         "TOTAL across summonings, usable once per week; the count survives new owners",
         "when its term ends the creature is NOT sent home — it acts as its nature "
         "dictates, usually on the last summoner",
         "embedded d100 elemental table → Modron rollable (handoff D13)"],
     "origin": "the Inner Planes (gate-work)", "gloss": "an elemental on layaway, with a temper"},
    {"id": "item:horn-caps-of-battering", "name": "Horn Caps of Battering", "pages": [140],
     "kind": "wondrous", "magical": True,
     "properties": [
         "1-inch brass caps for a bariaur's natural horns: his charge strikes "
         "construction (walls, doors) as a battering ram",
         "natural horns only — a horned helm's spikes won't take them"],
     "origin": None, "gloss": "the bariaur as siege engine"},
    {"id": "item:net-of-crystal-capturing", "name": "Net of Crystal Capturing", "pages": [140],
     "kind": "wondrous", "magical": True,
     "aliases": ["net of cry tal capturing"],
     "properties": [
         "2 x 2 ft crystal-laced net, useless as a weapon; catches spell crystals "
         "(attack vs AC 3; a miss means save vs spell or the crystal takes effect)",
         "holds one crystal indefinitely; the obvious use is releasing it on an enemy",
         "spell crystals spill from prime wizards' castings — unbidden summonings and "
         "divination demands"],
     "origin": None, "gloss": "a butterfly net for stray prime magic"},
    {"id": "item:oil-of-stone-integration", "name": "Oil of Stone Integration", "pages": [140],
     "kind": "potion", "magical": True,
     "properties": [
         "coat a cutter and ALL possessions (1d10+10 rounds to apply; one flask does "
         "two man-sized bodies or one plus gear): pass through stone and earth as if absent",
         "stone weapons and earthen creatures (elementals included) can't harm the user — "
         "who also can't touch or handle stone",
         "a coated stone object is untouchable and immovable till the oil fades",
         "each application lasts 10d6+30 minutes"],
     "origin": None, "gloss": "swim the rock, forfeit the road"},
    {"id": "item:planar-compass", "name": "Planar Compass", "pages": [140, 141],
     "kind": "wondrous", "magical": True,
     "aliases": ["planar compa"],
     "properties": [
         "6-inch iron sphere that splits to a 4-inch cavity: seal a fragment of a plane "
         "inside and an arrow juts out pointing to the nearest portal, conduit, path, "
         "or vortex leading there",
         "keeps pointing until you arrive or the fragment comes out",
         "the Outer-Planes cousin of the Tome of Magic's elemental compass"],
     "origin": None, "gloss": "feed it a souvenir, follow the needle"},
    {"id": "item:planar-wards", "name": "Planar Wards", "pages": [141],
     "kind": "wards", "magical": True,
     "properties": [
         "sets of 4-8 carved white-stone blocks (the chant: cut from Sigil's destroyed "
         "portals), numbered for activation order; one command word fires the set",
         "emanates an invisible wall (stones up to 60 yards apart, any pattern; extends "
         "60 yards up and down) inside which portals, gates, and conduits cannot open",
         "teleport/plane-shift entry stops at the wall — a spell aimed inside delivers "
         "the body 60 yards short, unharmed",
         "deactivated by command from within; otherwise lasts 1d4 weeks, then the "
         "blocks are plain stone — never rechargeable",
         "based on the 4th-level priest spell surelock; expensive and rare"],
     "origin": "Sigil (by the chant)", "gloss": "a fence against doors themselves"},
    {"id": "item:planar-mancatcher", "name": "Planar Mancatcher", "pages": [141],
     "kind": "weapon", "magical": True,
     "used_by": "faction:harmonium",
     "properties": [
         "+2 mancatcher in rune-graven steel, built to hold what plane-shifts: "
         "githyanki, githzerai, tanar'ri, and kin",
         "catches S/M/L targets at effective AC 10 (Dex applies; armor and magic don't); "
         "damage and effects as a normal mancatcher",
         "a held shifter's plane shift or teleport FAILS and costs 1d10 damage per "
         "attempt, with a cumulative 1% per point chance of knockout",
         "Harmonium patrols carry them by preference"],
     "origin": None, "gloss": "the law's answer to 'you can't hold me'"},
    {"id": "item:portal-trap", "name": "Portal Trap", "pages": [141],
     "kind": "wondrous", "magical": True,
     "properties": [
         "half-inch lead ball; speak the command word (often etched on it) and set it "
         "in a portal's framework, active or not",
         "the next use of the portal detonates a 6d6 fireball (as a 6th-level wizard) "
         "THROUGH BOTH ENDS — half the force out each side, any portal type",
         "the portal itself survives; the framework is destroyed 1% of the time"],
     "origin": None, "gloss": "a toll nobody wants to pay"},
    {"id": "item:potion-of-elemental-breathing", "name": "Potion of Elemental Breathing",
     "pages": [141], "kind": "potion", "magical": True,
     "properties": [
         "as a potion of water breathing for some other element: variants exist for "
         "every Inner Plane without (or with marginal) breathable atmosphere",
         "d100 variant table (water incl. Steam/Ooze · fire incl. Magma · earth incl. "
         "Mineral · smoke · ash · salt · dust) → Modron rollable (handoff D13)",
         "75% chance of two doses, 25% of four; each dose lasts 1 hour + 1d10 minutes"],
     "origin": None, "gloss": "lungs by the bottle, element by the label"},
    {"id": "item:ring-of-the-bariaur-lord", "name": "Ring of the Bariaur Lord",
     "pages": [141, 142], "kind": "wondrous", "magical": True,
     "properties": [
         "ram's-head ring, active only on a bariaur",
         "foot- and leg-shaped magic items (boots, shoes, slippers, leggings…) transform "
         "to bariaur-usable forms keeping their magic (DM's discretion)",
         "the transformation holds while the bariaur wears ring and item both"],
     "origin": None, "gloss": "finally, boots of speed for four hooves"},
    {"id": "item:scourge-of-lightning", "name": "Scourge of Lightning", "pages": [142],
     "kind": "weapon", "magical": True,
     "properties": [
         "4-ft barbed whip (1 ft of handle), 1d4 per lash; shreds ordinary clothes in "
         "two rounds, leather in three",
         "+2 weapon in the Abyss",
         "electrified at will: a sparking hit adds 2d8 electrical (save vs spell for half)",
         "a tanar'ri of 5+ HD triggers the lightning freely; anyone else 5 times/day",
         "petitioner-discipline on the Lower Planes, the Abyss especially"],
     "origin": "the Abyss", "gloss": "pain with a power cord"},
    {"id": "item:scythe-of-flame", "name": "Scythe/Sickle of Flame", "pages": [142],
     "kind": "weapon", "magical": True,
     "aliases": ["scythe of flame"],
     "properties": [
         "+3 enchantment on ANY plane (Upper- or Lower-Planes work — both claim it, "
         "both field champions who swing it)",
         "command word wreathes the blade in REAL flame: torchlight, ignites flammables, "
         "+1d6 vs the flame-vulnerable",
         "flare lasts three hours or until the word is spoken again"],
     "origin": "disputed — Upper or Lower Planes", "gloss": "the harvest, lit"},
    {"id": "item:scythe-of-light", "name": "Scythe/Sickle of Light", "pages": [142],
     "kind": "weapon", "magical": True,
     "aliases": ["scythe of light", "scytiie/sickle of ugiit"],
     "properties": [
         "Mount Celestia's make: +4 weapon on its home plane",
         "command word (inscribed in the gold-tinged blade) turns undead as a "
         "7th-level cleric, 3/day",
         "the same word raises a continual-light sphere for up to an hour, 3/day; "
         "dispellable at will but every use counts"],
     "origin": "Mount Celestia", "works_on": "plane:mount-celestia",
     "gloss": "the archons' answer to the grim reaper"},
    {"id": "item:scythe-of-pain", "name": "Scythe/Sickle of Pain", "pages": [142],
     "kind": "weapon", "magical": True,
     "aliases": ["scythe of pain"],
     "properties": [
         "baatezu petitioner-discipline; only baatezu of 6+ HD carry them — any other "
         "berk seen with one is marked for death on sight",
         "+3 weapon on Baator",
         "command word: a hit forces save vs spell or an agony rush — Dexterity -3, "
         "AC two grades worse, -4 to attack and damage, for 1d6 rounds"],
     "origin": "Baator", "works_on": "plane:baator",
     "gloss": "order, enforced one shriek at a time"},
    {"id": "item:scythe-of-paralyzation", "name": "Scythe/Sickle of Paralyzation",
     "pages": [142], "kind": "weapon", "magical": True,
     "aliases": ["scythe of paralyzation"],
     "properties": [
         "Outlands work, sold to anyone with the jink: a +2 weapon",
         "speak its name (written on haft or pegs) and hits force save vs paralyzation "
         "or the victim can't move for 2d4 rounds",
         "1d10 activations a day — and the dark of it: nobody knows the count till "
         "the charges are gone"],
     "origin": "the Outlands", "works_on": "plane:the-outlands",
     "gloss": "stillness for sale, supply uncertain"},
    {"id": "item:scroll-of-outer-planar-protection",
     "name": "Scroll of Outer-Planar Protection", "pages": [142],
     "kind": "scroll", "magical": True,
     "aliases": ["scrolls of protection"],   # head shredded; the body line witnesses (page-restricted)
     "properties": [
         "reads as most protection scrolls (reading time 8): a mobile 10-ft-radius "
         "circle around the reader",
         "wards a maximum of 50 Hit Dice of creatures for 1d6+10 rounds; attacks out "
         "are possible, and creatures over the HD cap can press in",
         "never affects creatures on their home plane",
         "d100 type table (celestials · neutrals · fiends · modrons · slaadi · all "
         "outer-planar — each including the matching plane-touched and natives) → "
         "Modron rollable (handoff D13)"],
     "origin": None, "gloss": "a chalk circle against half the multiverse"},
    {"id": "item:shifters-manacles", "name": "Shifters' Manacles", "pages": [143],
     "kind": "wondrous", "magical": True,
     "used_by": "faction:mercykillers",
     "aliases": ["shifters manacles"],
     "properties": [
         "Mercykiller commission: the Prison kept losing prisoners who plane-shift "
         "at will, so their mages forged manacles no shifting magic escapes",
         "big, heavy, non-adjusting (built fast and in bulk) — but the Prison stocks "
         "sizes for almost anything",
         "the metal resists rust, magic, and (by special enchantment) psionics",
         "a shift attempt fails and costs 1d10 damage of nerve-fire, with 2% per "
         "point cumulative chance of unconsciousness for 1d3 turns"],
     "origin": "Sigil (the Prison)", "gloss": "the birdcage's birdcage"},
    {"id": "item:seeker-stones", "name": "Seeker Stones", "pages": [143],
     "kind": "wondrous", "magical": True,
     "properties": [
         "a matched pair of clear peridot balls; speak the inscribed words and a "
         "glowing arrow inside homes on the mate within 10 miles",
         "the arrow fattens and brightens with closeness, dying within 5 feet; it "
         "re-fires if the gap reopens; reversed words dispel",
         "either stone seeks independently of the other",
         "chant whispers of planar-spanning sets — no reliable blood has seen one"],
     "origin": None, "gloss": "a compass that points at your partner"},
    {"id": "item:transient-sword", "name": "Transient Sword", "pages": [143],
     "kind": "weapon", "magical": True,
     "properties": [
         "a long sword +2 by every test, tome, and sage — until the wielder changes "
         "planes and notices nothing changed",
         "its enchantment is tied to NO plane: always +2, everywhere",
         "origins unknown, possibly permanently obscured"],
     "origin": "unknown", "gloss": "the sword that never heard of plane-bleed"},
    {"id": "item:vambraces-of-evils-warding", "name": "Vambraces of Evil's Warding",
     "pages": [143], "kind": "armor", "magical": True,
     "aliases": ["vambraces"],
     "properties": [
         "rune-graven metal armbands; trace the runes and they flash blue, then ward "
         "until removed",
         "missiles fired by evil creatures attack at -4; misses are drawn to the "
         "vambraces and bounce (magical ammunition keeps its bonus but obeys)",
         "melee, auto-hitting, and area attacks are unaffected",
         "the chant: forged from spirits of Arcadia's fallen petitioners — and an evil "
         "wearer takes 2d8 every 10 rounds for the insult"],
     "origin": "Arcadia (by the chant)", "gloss": "dead heroes still catching arrows"},
    {"id": "item:ring-of-gehennan-fire-resistance",
     "name": "Ring of Gehennan Fire Resistance", "pages": [143],
     "kind": "wondrous", "magical": True,
     "properties": [
         "exemplar of the planar-protection trade: guards against the lava, magma, "
         "and heat OF GEHENNA — and nothing else's",
         "useless against the plane of Fire, dragon breath, or Muspelheim's volcanos",
         "single-plane focus makes it markedly cheaper than the multiuse article"],
     "origin": "Sigil bazaars", "works_on": "plane:gehenna",
     "gloss": "fire insurance, one furnace only"},
    {"id": "item:inner-planar-amulet", "name": "Inner-Planar Amulet", "pages": [143],
     "kind": "wondrous", "magical": True,
     # descriptive handle — the book names the CLASS ("items… usually an amulet…
     # useful only on a single plane"), not a proper item; the alias witnesses it
     "aliases": ["these amulets"],
     "properties": [
         "Sigil wizards infuse a single Inner Plane's essence at creation: one amulet "
         "carries that plane's breathing, protection, and movement needs together",
         "works only on its plane; burns out 6+1d4 days after activation",
         "the single-plane planar-protection trade's Inner-Planes face"],
     "origin": "Sigil", "gloss": "a week of survival on a chain"},
]


def attest_item_card(card, pages):
    pp = attest_name(card["name"], card.get("aliases", []), pages, set(card["pages"]))
    return {"pages": pp, "refused": not pp}

# ---------------------------------------------------------------- spells
WIZARD_PAGES = list(range(114, 127))    # printed 112-124
PRIEST_PAGES = list(range(127, 134))    # printed 125-131

# head: NAME-line(s) above "(School[, Elemental [X]][; Level N)" [Reversible]
# level admits I/l — the scan renders digit 1 as capital-I ("Level I" hid two
# priest spells, Protection from Prime P1 + Protection from Silver P1)
HEAD_RX = re.compile(
    r"\(\s*([A-Za-z/][A-Za-z/ ,'\-]*?)"            # school(s)
    r"(?:,\s*Elemental\s*\[([A-Za-z, ]+)\]\s*)?"   # optional elemental subtag
    r"[;:]\s*Level\s+([0-9Il])\s*\)"               # level (I/l = OCR'd 1)
    r"\s*(Reversible)?", re.IGNORECASE)

# the 2e school vocabulary — a head whose school-part shares no token with this
# closed set is a false positive (prose parenthetical), not a spell
SCHOOL_VOCAB = {"abjuration", "alteration", "conjuration", "summoning", "divination",
                "enchantment", "charm", "illusion", "phantasm", "invocation",
                "evocation", "necromancy", "elemental", "wild", "universal",
                "greater", "lesser", "geometry", "song", "shadow", "dimension",
                "metamagic"}


def _school_plausible(school_raw):
    toks = re.split(r"[/, ]+", school_raw.lower())
    return any(t in SCHOOL_VOCAB for t in toks if t)
FIELD_NAMES = ["Range", "Components", "Duration", "Casting Time",
               "Area of Effect", "Saving Throw", "Sphere", "Spheres"]
_FIELD_ALT = "|".join(re.escape(f) for f in FIELD_NAMES)
FIELD_RX = re.compile(
    rf"({_FIELD_ALT})\s*:\s*(.+?)(?=(?:{_FIELD_ALT})\s*:|$)", re.IGNORECASE | re.DOTALL)

ORIGIN_TAGS = {"HELLBOUND": "source:hellbound"}

# display-font section markers ("SECOND-LEVEL SPELLS" renders St:C9ND-Lt:Vt:L SPt:LLS)
SECTION_RX = re.compile(r"SP[Et:]LLS|L[Et:]V[Et:]L|FIRS|S[Et:]C|THIRD|F[O9(]UR|FIF|SIX", re.IGNORECASE)

# OCR name fixes, keyed by the RAW detected name, whitespace-normalized
# (every value hand-verified against the cited reflow page)
SPELL_NAME_FIXES = {
    "BREATIIE SMOKE, Du T; OR ASH": "Breathe Smoke, Dust, or Ash",   # pg116
    "AIRY EARTII": "Airy Earth",                                     # pg121
    "K.Now FACTION": "Know Faction",                                 # pg127
    "K.NOW FACTION": "Know Faction",
    "0RI TRIBULATION": "Tanar'ri Tribulation",      # pg120: TANAR / 0RI line-split
    "0F.MIPLANE SEED": "Demiplane Seed",            # pg126: DEMI → 0F.MI
    "BLESSED FORGETFULNE S": "Blessed Forgetfulness",                # pg128
    "ELEMENTAL BREACJI": "Elemental Breach",                         # pg133
    "SPI IERE OF SURVIVAL": "Sphere of Survival",                    # pg133
    "PROTECTION FROM PRIME to-FOOT RADIUS":
        "Protection from Prime, 10-foot Radius",                     # pg119 (wizard)
    "PROTECTION FROM PRIME 10-FOOT RADIU":
        "Protection from Prime, 10-foot Radius",                     # pg129 (priest)
}

# hand-verified statlines for reflow-scrambled bindings ("verified or absent"
# promotions). Each entry cites the PDF page a human read; binding was settled
# by block SEMANTICS (sphere names, area targets, family templates), recorded
# in the pour docket. Applied by finalize_spells with stats_cured=True.
SPELL_STAT_CURATIONS = {
    "gate-seal": {"page": 117, "stats": {
        "range": "Touch or special", "components": "V, S, M",
        "duration": "1 turn/level", "casting_time": "4",
        "area_of_effect": "1 gate or battlefield", "saving_throw": "None"},
        "why": "adjacent-head pair with Modron Mind; '1 gate' area names it"},
    "modron-mind": {"page": 117, "stats": {
        "range": "0", "components": "V, S, M", "duration": "1 turn/level",
        "casting_time": "3", "area_of_effect": "Caster", "saving_throw": "None"},
        "why": "the caster-only group; body is the caster's own transformation"},
    "breathe-earth": {"page": 119, "stats": {
        "range": "Touch", "components": "V, S, M",
        "duration": "1 hour/level + 1d4 hrs.", "casting_time": "5",
        "area_of_effect": "Creature touched", "saving_throw": "None"},
        "why": "Breathe-family template (cf. Breathe Smoke pg116: Touch/Creature touched/1 hr+1d4)"},
    "transmute-fire-to-smoke": {"page": 119, "stats": {
        "range": "10 yards/level", "components": "V, S, M",
        "duration": "1 turn + 1 rd./level", "casting_time": "3",
        "area_of_effect": "10-ft. cube/level or single creature", "saving_throw": "None"},
        "why": "volume-target group; mirrors Calm Wind's area transmutation template"},
    "airy-earth": {"page": 121, "stats": {
        "range": "0", "components": "M", "duration": "1 turn/level",
        "casting_time": "6", "area_of_effect": "10-ft. rad. sphere",
        "saving_throw": "None"},
        "why": "body: breathable radius around the caster; the other group is Acheron-cubes"},
    "cubehopper": {"page": 121, "stats": {
        "range": "0", "components": "V, S, M", "duration": "1 hour/level",
        "casting_time": "1 round", "area_of_effect": "2 cubes of Acheron",
        "saving_throw": "None"},
        "why": "'2 cubes of Acheron' can be no other spell"},
    "blessed-forgetfulness": {"page": 128, "stats": {
        "sphere": "Necromantic, Thought", "range": "Touch",
        "components": "V, S, M", "duration": "Permanent", "casting_time": "7",
        "area_of_effect": "1 creature", "saving_throw": "Negates"},
        "why": "sphere Necromantic/Thought = the mind-healing spell, not the earth ward"},
    "protection-from-earth": {"page": 128, "stats": {
        "sphere": "Elemental (Earth), Protection", "range": "Touch",
        "components": "V, S, M", "duration": "Special", "casting_time": "6",
        "area_of_effect": "1 creature", "saving_throw": "None"},
        "why": "sphere Elemental (Earth)/Protection; Duration Special = Protection-family template"},
    "touch-of-the-styx": {"page": 130, "stats": {
        "sphere": "Thought", "range": "Touch", "components": "Special",
        "duration": "Permanent", "casting_time": "7", "saving_throw": "Negates",
        "area_of_effect": "Creature touched"},
        "why": "completion: Components Special = body's 'must have touched the true waters of the Styx'"},
    "inverted-magic": {"page": 130, "stats": {
        "sphere": "Combat", "range": "Touch", "components": "V, S, M",
        "duration": "Instantaneous", "casting_time": "6", "saving_throw": "Negates",
        "area_of_effect": "1 creature"},
        "why": "the offensive-touch group; body confirms save attempt + 1-creature target"},
    "sever-the-silver-cord": {"page": 131, "stats": {
        "sphere": "Astral, Combat", "range": "10 yards/level", "components": "V, S",
        "duration": "Instantaneous", "casting_time": "8", "saving_throw": "Negates",
        "area_of_effect": "1 prime"},
        "why": "completion: '1 prime' area + save-vs-death body; V,S/8/Negates fragment is its tail"},
    "celestial-protection": {"page": 131, "stats": {
        "sphere": "Protection", "range": "Touch", "components": "V, S, M",
        "duration": "1 turn/level", "casting_time": "8", "saving_throw": "None",
        "area_of_effect": "1 creature"},
        "why": "beneficial ward = Save None; material = the holy-water anointing in the body"},
}

# a head whose NAME line the scan destroyed — poured to QUARANTINE by page,
# never guessed (the cage-head-lost law). Everything knowable rides along so a
# print-reading curation can promote it.
HEAD_LOST = [
    {"page": 132, "printed_page": 130, "klass": "priest", "level": 7,
     "school": "Invocation/Evocation", "sphere": "Sun",
     "stats": {"range": "0", "duration": "1 round/level", "area_of_effect": "Caster",
               "components": "V, S, M", "casting_time": "1 round",
               "saving_throw": "Negates"},
     "note": "name line OCR'd to 'l,' — 7th-level priest spell, Sphere Sun: bestows a "
             "powerful proxy's aura of awe (<6 HD creatures stop and face the caster; "
             "words act as suggestion, telepathically understood; save negates; >6 HD "
             "immune). Archon-developed on Mount Celestia."},
]


def load_component(build_root):
    d = Path(build_root) / COMPONENT / "reflow"
    return {int(p.stem.split("-")[1]): p.read_text(encoding="utf-8")
            for p in d.glob("page-*.txt")}


def _name_rx(name):
    """planes.py law: word-boundary; short names case-sensitive; multi-word
    names join whitespace-tolerantly so a line wrap still attests."""
    pat = r"\s+".join(re.escape(w) for w in name.split())
    if len(name) <= 4:
        return re.compile(rf"\b{pat}\b")
    return re.compile(rf"\b{pat}\b", re.IGNORECASE)


def attest_name(name, aliases, pages, page_whitelist=None):
    """Pages on which the name (or an alias) witnesses. Optionally restricted."""
    rxs = [_name_rx(name)] + [_name_rx(a) for a in aliases]
    hits = []
    for pg, txt in sorted(pages.items()):
        if page_whitelist and pg not in page_whitelist:
            continue
        if any(rx.search(txt) for rx in rxs):
            hits.append(pg)
    return hits


def attest_race_card(card, pages):
    """Race name must witness on the card's claimed pages; each variant head too.
    Returns {pages: [...], refused: bool, variants: {name: [pages]}}."""
    pp = attest_name(card["name"], [], pages, set(card["pages"]))
    vr = {}
    for v in card.get("variants", []):
        vr[v["name"]] = attest_name(v["name"], [], pages, set(v["pages"]))
    return {"pages": pp, "refused": not pp, "variants": vr}


def attest_kit_card(card, pages):
    pp = attest_name(card["name"], card.get("aliases", []), pages, set(card["pages"]))
    return {"pages": pp, "refused": not pp}


# ---------------------------------------------------------------- spell parser
def _clean_name(raw):
    """Raw caps head → clean Title Case name. Fix table first (whitespace-
    normalized key); then mechanical repairs for the rigid-format residue."""
    raw = re.sub(r"\s+", " ", raw.strip().rstrip("."))
    if raw in SPELL_NAME_FIXES:
        return SPELL_NAME_FIXES[raw]
    s = raw.replace("K.", "K")             # OCR splits 'K' as 'K.' mid-word
    # title-case words, keeping smalls lowercase ('of', 'the', 'to', 'or'...)
    smalls = {"of", "the", "to", "or", "and", "from", "a", "an", "in", "on"}
    words = []
    for i, w in enumerate(s.lower().split()):
        words.append(w if (w in smalls and i > 0) else w.capitalize())
    return " ".join(words)


def _name_plausible(name):
    """A spell name is words-with-letters, no field-glyph soup. Digits are
    allowed only in the 2e radius idiom ('..., 10-foot Radius')."""
    if not (3 <= len(name) <= 42):
        return False
    if re.search(r"[:;()]|t:|\$|♦", name):
        return False
    deradiused = re.sub(r"\d+[-' ]?(?:foot|ft\.?|yard)\s+Radius", "", name, flags=re.I)
    if re.search(r"[0-9]", deradiused):
        return False
    return bool(re.fullmatch(r"[A-Za-z' ,\-]+", deradiused.strip(" ,")) or not deradiused.strip(" ,"))


def _parse_school(school_raw, elem_raw):
    """Normalize case token-by-token: 'Enchantment/charm, evocation' →
    'Enchantment/Charm, Evocation'."""
    school = re.sub(r"\s+", " ", school_raw).strip().rstrip(",")
    school = re.sub(r"[A-Za-z]+", lambda m: m.group(0).capitalize(), school)
    elemental = [e.strip().title() for e in elem_raw.split(",")] if elem_raw else []
    return school, elemental


def _level_int(raw):
    return 1 if raw in ("I", "l") else int(raw)


def extract_spells(pages, page_list, klass):
    """Sweep `page_list` (one class's chapter run) for spell blocks.
    Returns (spells, rejects). Identity (name/school/level) binds by head
    adjacency — certain. Stat fields bind ONLY when exactly one field-group
    sits between this head and the next ('verified or absent'); otherwise
    stats_unbound=True and the curation table is the door back in."""
    spells, rejects = [], []
    for pg in page_list:
        txt = pages.get(pg)
        if not txt:
            continue
        lines = txt.splitlines()
        heads = []                                    # (line_idx, name_raw, school, elem, level, reversible)
        for i, ln in enumerate(lines):
            m = HEAD_RX.search(ln)
            if not m or not _school_plausible(m.group(1)):
                continue
            # assemble the name from preceding lines: skip blanks + origin tags,
            # collect caps-ish lines until a section marker / field line / prose
            name_parts, origin = [], None
            j = i - 1
            # the head line itself may carry a prefix (rare)
            prefix = ln[:m.start()].strip()
            if prefix:
                name_parts.append(prefix)
            while j >= 0 and len(name_parts) < 3:
                s = lines[j].strip()
                j -= 1
                if not s:
                    if name_parts:
                        break
                    continue
                if s.upper().rstrip(".") in ORIGIN_TAGS:
                    origin = ORIGIN_TAGS[s.upper().rstrip(".")]
                    continue
                if FIELD_RX.match(s) or SECTION_RX.search(s) and not name_parts:
                    if SECTION_RX.search(s) and _name_plausible(_clean_name(s)):
                        pass                          # a real name can trip SECTION_RX ('Spell...'); keep
                    else:
                        break
                letters = [c for c in s if c.isalpha()]
                if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.7:
                    break                             # prose — name lines are caps
                name_parts.append(s)
                if len(" ".join(name_parts)) > 34:
                    break
            name_raw = " ".join(reversed(name_parts)).strip()
            heads.append({"line": i, "name_raw": name_raw, "school_raw": m.group(1),
                          "elem_raw": m.group(2) or "", "level": _level_int(m.group(3)),
                          "reversible": bool(m.group(4)), "origin": origin})

        # bind stat fields: the gap between head k and head k+1
        for k, h in enumerate(heads):
            gap_start = h["line"] + 1
            gap_end = heads[k + 1]["line"] - 1 if k + 1 < len(heads) else len(lines) - 1
            gap = "\n".join(lines[gap_start:gap_end + 1])
            # an origin tag directly AFTER the head also counts
            after = next((s.strip() for s in lines[gap_start:gap_start + 3] if s.strip()), "")
            if after.upper().rstrip(".") in ORIGIN_TAGS:
                h["origin"] = h["origin"] or ORIGIN_TAGS[after.upper().rstrip(".")]
            # field groups: runs of consecutive field-bearing lines
            groups, cur = [], []
            for s in gap.splitlines():
                if FIELD_RX.search(s):
                    cur.append(s)
                elif cur:
                    groups.append("\n".join(cur)); cur = []
            if cur:
                groups.append("\n".join(cur))
            # merge groups separated only by blank/short lines into logical groups:
            # a single statblock reflows as 2 runs (col A then col B) WHEN both runs
            # carry DISJOINT field names — treat disjoint-adjacent runs as one block
            logical = []
            for g in groups:
                fields_g = {mm.group(1).title() for mm in FIELD_RX.finditer(g)}
                if logical:
                    prev_fields = {mm.group(1).title() for mm in FIELD_RX.finditer(logical[-1])}
                    if not (prev_fields & fields_g):
                        logical[-1] = logical[-1] + "\n" + g
                        continue
                logical.append(g)
            fields, unbound = {}, False
            if len(logical) == 1:
                blob = re.sub(r"\s*\n\s*", " ", logical[0])
                for mm in FIELD_RX.finditer(blob):
                    key = mm.group(1).title().replace("Spheres", "Sphere")
                    val = re.sub(r"\s+", " ", mm.group(2)).strip().rstrip(".")
                    fields.setdefault(key.lower().replace(" ", "_"), val)
            elif len(logical) > 1:
                unbound = True                        # ambiguous — verified or absent
            name = _clean_name(h["name_raw"])
            rec = {"name": name, "name_raw": h["name_raw"], "page": pg,
                   "printed_page": pg - PAGE_OFFSET, "klass": klass,
                   "school": None, "elemental": [], "level": h["level"],
                   "reversible": h["reversible"], "origin": h["origin"],
                   "stats": fields, "stats_unbound": unbound}
            rec["school"], rec["elemental"] = _parse_school(h["school_raw"], h["elem_raw"])
            if not _name_plausible(name):
                rejects.append(rec)
            else:
                spells.append(rec)
    return spells, rejects


def merge_spells(*spell_lists):
    """Same name across class lists = one spell, classes unioned, witnesses kept.
    2e prints class-specific variants of one spell (Protection from Prime is W2
    but P1; the 10-foot Radius is W4+P4 with different durations) — when versions
    differ, the by-class maps carry both and nothing is laundered."""
    import collections
    by_name = collections.OrderedDict()
    for lst in spell_lists:
        for s in lst:
            key = s["name"].lower()
            if key not in by_name:
                t = dict(s)
                t["classes"] = [s["klass"]]
                t["pages"] = [s["page"]]
                t["level_by_class"] = {s["klass"]: s["level"]}
                t["stats_by_class"] = {s["klass"]: s["stats"]} if s["stats"] else {}
                del t["klass"], t["page"]
                by_name[key] = t
            else:
                t = by_name[key]
                if s["klass"] not in t["classes"]:
                    t["classes"].append(s["klass"])
                t["pages"].append(s["page"])
                t["level_by_class"][s["klass"]] = s["level"]
                if s["stats"]:
                    t["stats_by_class"][s["klass"]] = s["stats"]
                    if not t["stats"]:
                        t["stats"], t["stats_unbound"] = s["stats"], s["stats_unbound"]
                t["origin"] = t["origin"] or s["origin"]
    # collapse by-class maps that agree everywhere
    for t in by_name.values():
        if len(set(t["level_by_class"].values())) == 1:
            t["level"] = next(iter(t["level_by_class"].values()))
            if len(t["level_by_class"]) == len(t["classes"]):
                t["level_by_class"] = {}
        sbc = t["stats_by_class"]
        if len(sbc) <= 1 or all(v == t["stats"] for v in sbc.values()):
            t["stats_by_class"] = {}
    return list(by_name.values())


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s


def finalize_spells(merged):
    """Apply the hand-verified stat curations (stats_cured + page witness ride
    along — never silent), and surface what stays unbound."""
    for t in merged:
        cur = SPELL_STAT_CURATIONS.get(slugify(t["name"]))
        if cur:
            base = dict(t["stats"]) if t["stats"] and not t["stats_unbound"] else {}
            base.update(cur["stats"])
            t["stats"] = base
            t["stats_unbound"] = False
            t["stats_cured"] = {"page": cur["page"], "why": cur["why"]}
    return merged


if __name__ == "__main__":
    import sys

    # --- cards well-formed -------------------------------------------------
    known_planes = {"plane:ysgard", "plane:limbo", "plane:mechanus",
                    "plane:the-abyss", "plane:the-outlands"}
    seen = set()
    for c in RACE_CARDS:
        assert c["id"].startswith("race:") and c["id"] not in seen, c["id"]
        seen.add(c["id"])
        assert c["pages"] and all(1 <= p <= 162 for p in c["pages"]), c["id"]
        assert c["native_to"] in (None,) or c["native_to"] in known_planes, c["id"]
        for v in c.get("variants", []):
            assert set(v["pages"]) <= set(c["pages"]), (c["id"], v["name"])
    assert len(RACE_CARDS) == 8                       # the book's "eight available races"
    for c in KIT_CARDS:
        assert c["id"].startswith("class:") and c["id"] not in seen, c["id"]
        seen.add(c["id"])
        assert c["parent_class"] in {i for i, _, _ in BASE_CLASSES}, c["id"]
        assert c["kind"] in ("planewalker", "location")
        assert c["located_in"] in (None,) or c["located_in"] in known_planes, c["id"]

    # --- item cards well-formed ----------------------------------------------
    item_planes = {"plane:gehenna", "plane:baator", "plane:mount-celestia",
                   "plane:the-outlands"}
    factions = {"faction:harmonium", "faction:mercykillers"}
    for c in ITEM_CARDS:
        assert c["id"].startswith("item:") and c["id"] not in seen, c["id"]
        seen.add(c["id"])
        assert c["pages"] and all(134 <= p <= 143 for p in c["pages"]), c["id"]
        assert isinstance(c["magical"], bool) and c["properties"], c["id"]
        assert c.get("used_by") in (None,) or c["used_by"] in factions, c["id"]
        assert c.get("works_on") in (None,) or c["works_on"] in item_planes, c["id"]
    assert len(ITEM_CARDS) == 38      # 12 tools-of-the-trade + 26 magical/protections

    # --- attestation refuses what the text lacks ----------------------------
    fake_pages = {72: "The AASIMAR are plane-touched.", 73: "Bariaur roam Ysgard."}
    rep = attest_race_card(RACE_CARDS[0], fake_pages)   # aasimar claims pp 72-73
    assert rep["pages"] == [72] and not rep["refused"]
    rep2 = attest_race_card(RACE_CARDS[3], fake_pages)  # githzerai claims p77 — absent
    assert rep2["refused"]
    rep3 = attest_item_card(ITEM_CARDS[0], {134: "tempered green steel of Avernus"})
    assert rep3["pages"] == [134] and not rep3["refused"]   # alias rescues
    rep4 = attest_item_card(ITEM_CARDS[0], {134: "ordinary iron only"})
    assert rep4["refused"]

    # --- head + name assembly ------------------------------------------------
    pages = {114: "\n".join([
        "PORTAL BEACON",
        "(Evocation/Invocation; Level 1)",
        "",
        "Range: 10 yards/level Components: V, S",
        "Duration: 1 turn/level Casting Time: 1",
        "Area of Effect: One portal Saving Throw: None",
        "",
        "This spell marks a portal.",
    ])}
    sp, rj = extract_spells(pages, [114], "wizard")
    assert len(sp) == 1 and not rj
    s = sp[0]
    assert s["name"] == "Portal Beacon" and s["level"] == 1
    assert s["school"] == "Evocation/Invocation"
    assert s["stats"]["range"] == "10 yards/level"
    assert s["stats"]["saving_throw"] == "None"
    assert not s["stats_unbound"]

    # --- elemental subtag + reversible + origin tag (after head) -------------
    pages = {116: "\n".join([
        "ACIDIC BLAST",
        "(Invocation/Evocation, Elemental [Water, Earth]; Level 3) Reversible",
        "",
        "HELLBOUND",
        "",
        "Range: Touch Components: V, S, M",
        "Duration: Special Casting Time: 6",
    ])}
    sp, _ = extract_spells(pages, [116], "wizard")
    assert sp[0]["elemental"] == ["Water", "Earth"]
    assert sp[0]["reversible"] and sp[0]["origin"] == "source:hellbound"

    # --- origin tag BETWEEN name and head (the RENEWED ABILITY layout) -------
    pages = {127: "\n".join([
        "RENEWED",
        "ABILITY",
        "HELLBOUND",
        "(Alteration; Level 2)",
        "",
        "Sphere: All Range: Touch",
        "Components: V, S Casting Time: 5",
    ])}
    sp, _ = extract_spells(pages, [127], "priest")
    assert sp[0]["name"] == "Renewed Ability" and sp[0]["origin"] == "source:hellbound"
    assert sp[0]["stats"]["sphere"] == "All"

    # --- adjacent heads + two stat groups = UNBOUND (verified or absent) -----
    pages = {117: "\n".join([
        "MODRON MIND",
        "(Alteration; Level 3)",
        "",
        "GATE SEAL",
        "(Abjuration; Level 3) Reversible",
        "",
        "Range: Touch or special Components: V, S, M",
        "Duration: 1 turn/level Casting Time: 4",
        "Area of Effect: 1 gate Saving Throw: None",
        "",
        "Range: 0 Components: V, S, M",
        "Duration: 1 turn/level Casting Time: 3",
        "Area of Effect: Caster Saving Throw: None",
        "",
        "Like the spell's namesake, the caster...",
    ])}
    sp, _ = extract_spells(pages, [117], "wizard")
    assert len(sp) == 2
    modron = next(x for x in sp if x["name"] == "Modron Mind")
    gate = next(x for x in sp if x["name"] == "Gate Seal")
    assert not modron["stats"] and not modron["stats_unbound"]   # nothing in ITS gap
    assert gate["stats_unbound"] and not gate["stats"]           # two groups — refused
    assert gate["reversible"]

    # --- column-split single statblock (disjoint runs merge to ONE group) ----
    pages = {128: "\n".join([
        "FOSTERED PROTECTION",
        "(Abjuration; Level 3)",
        "",
        "Sphere: Protection",
        "Range:Touch",
        "Duration: 1 turn/level",
        "Area of Effect: 1 creature",
        "",
        "Components: V, S, M",
        "Casting Time: 5",
        "Saving Throw: None",
        "",
        "Fostered protection can be cast only...",
    ])}
    sp, _ = extract_spells(pages, [128], "priest")
    f = sp[0]
    assert not f["stats_unbound"], f
    assert f["stats"]["components"] == "V, S, M" and f["stats"]["range"] == "Touch"

    # --- Level I (OCR'd digit 1) parses -----------------------------------------
    pages = {127: "\n".join([
        "PROTECTION",
        "FROM PRIME",
        "(Abjuration; Level I)",
        "",
        "Sphere: Protection Range:Touch",
        "Duration: 3 rounds/level Casting Time: 4",
        "Area of Effect: Creature touched Saving Throw: None",
    ])}
    sp, _ = extract_spells(pages, [127], "priest")
    assert sp[0]["level"] == 1 and sp[0]["name"] == "Protection from Prime"
    assert sp[0]["stats"]["duration"] == "3 rounds/level"

    # --- per-class divergence: levels AND stats both disclosed -------------------
    w2 = [{"name": "Protection from Prime", "name_raw": "X", "page": 114,
           "printed_page": 112, "klass": "wizard", "school": "Abjuration",
           "elemental": [], "level": 2, "reversible": False, "origin": None,
           "stats": {"duration": "1 turn/level"}, "stats_unbound": False}]
    p1 = [{"name": "Protection from Prime", "name_raw": "X", "page": 127,
           "printed_page": 125, "klass": "priest", "school": "Abjuration",
           "elemental": [], "level": 1, "reversible": False, "origin": None,
           "stats": {"duration": "3 rounds/level"}, "stats_unbound": False}]
    m = merge_spells(w2, p1)[0]
    assert m["level"] == 2 and m["level_by_class"] == {"wizard": 2, "priest": 1}
    assert m["stats_by_class"]["priest"]["duration"] == "3 rounds/level"

    # --- curation promotes an unbound spell, with witness -------------------------
    gs = [{"name": "Gate Seal", "name_raw": "GATE SEAL", "page": 117,
           "printed_page": 115, "klass": "wizard", "school": "Abjuration",
           "elemental": [], "level": 3, "reversible": True, "origin": None,
           "stats": {}, "stats_unbound": True}]
    f = finalize_spells(merge_spells(gs))[0]
    assert not f["stats_unbound"] and f["stats"]["area_of_effect"] == "1 gate or battlefield"
    assert f["stats_cured"]["page"] == 117

    # --- dual-class merge -----------------------------------------------------
    w = [{"name": "Know Faction", "name_raw": "KNOW FACTION", "page": 114,
          "printed_page": 112, "klass": "wizard", "school": "Divination",
          "elemental": [], "level": 1, "reversible": False, "origin": None,
          "stats": {"range": "60 ft"}, "stats_unbound": False}]
    p = [{"name": "Know Faction", "name_raw": "K.Now FACTION", "page": 127,
          "printed_page": 125, "klass": "priest", "school": "Divination",
          "elemental": [], "level": 1, "reversible": False, "origin": None,
          "stats": {}, "stats_unbound": False}]
    merged = merge_spells(w, p)
    assert len(merged) == 1 and merged[0]["classes"] == ["wizard", "priest"]
    assert merged[0]["pages"] == [114, 127]

    # --- name cleaning ---------------------------------------------------------
    assert _clean_name("BREATIIE SMOKE, Du T; OR ASH") == "Breathe Smoke, Dust, or Ash"
    assert _clean_name("UP THE ABYSSAL WALLS") == "Up the Abyssal Walls"
    assert _clean_name("VROCK'S SCREECH") == "Vrock's Screech"

    # --- false heads die at the school-vocab gate ------------------------------
    pages = {99: "PRETTY TEXT\n(Garbage Text; Level 3)\n\nRange: Touch"}
    sp, rj = extract_spells(pages, [99], "wizard")
    assert not sp and not rj                          # not even a reject — no head
    assert _school_plausible("Invocation/Evocation")
    assert _school_plausible("Abjuration, Elemental")
    assert not _school_plausible("Garbage Text")

    print("pwh.py self-test: all green")
    sys.exit(0)