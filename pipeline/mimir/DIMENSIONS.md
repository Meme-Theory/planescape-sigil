# Mimir — Dimension Registry

The canonical catalog of every **dimension** (entity type) the Handbook models. Grounded
in the source's *own* ontology: the dimension list below is cross-validated against the
wiki category taxonomy (timaresh + fandom + planar-legends) and mimir.net's section/category
structure — not invented. Volume hints are observed counts from those sources.

> Design law (from the Ainulindale lens): **fixed envelope, open fields, generic edges,
> uniform FTS.** Adding a dimension never migrates the store — it registers a plugin.

---

## 0. The envelope (every entity, every dimension)

```jsonc
{
  "type": "npc",                  // dimension id (this registry)
  "id": "npc:uncaged:akin",       // stable, edition+source namespaced
  "name": "A'kin",
  "edition": "2e",                // EVERY entity is edition-tagged (multi-edition is the point)
  "fields": { ... },              // OPEN per-dimension schema (defined below)
  "content": "...",               // flat text projection → uniform FTS5
  "provenance": {                 // the ARBITRATION RECORD (our upgrade over the lens)
    "value_sources": [ {"src":"official-2e","loc":"uncaged:p10:bbox","sha":"…"},
                       {"src":"timaresh","loc":"A'kin"} ],
    "method": "cross-source-consensus", "agreement": 1.0
  },
  "confidence": 0.96,             // explicit validator score (the lens lacked this)
  "curated": { ... },             // human/agent edits — PRESERVED across every rebuild
  "attested_in": ["source:uncaged", "wiki:timaresh:A'kin"]
}
```

**Cross-cutting fields on all dimensions:** `edition`, `provenance`, `confidence`,
`curated`, `attested_in`. The `edition` field + the `same_as`/`converts_to` edges are how
the 2e→5e uplift and the "answer-key" arbitration work.

---

## 1. BEINGS  *(wiki: Inhabitants 46, Character Profiles 265, Monster 23; mimir: Cutters 145, Bestiary 129, Planar Races 45)*

### dim:npc — a named individual
- **attested:** Uncaged, Factol's Manifesto, every adventure; wiki Character_Profiles; mimir Cutters
- **fields:** `descriptor{plane,sex,race,class,level_hd,faction,alignment}`, `statblock{ac,mv[],hp,thac0,num_attacks,damage,sa,sd,sw,mr,size,morale,int,xp,notes,spells,spell_like}`, `sections{personality,role_playing,combat,location,special_equipment,…}`, `body`, `aliases`
- **edges:** descriptor.faction→`member_of` · descriptor.race→`is_a`(creature/race) · sections.location→`located_in` · see_also→`references` · descriptor.deity→`worships`

### dim:dialog — a bound NPC utterance (the **voice vector**)  *(`parse/dialog.py`)*
- **why:** a character's spoken lines, bound to the speaker, **register-tagged so they render** in the
  voice stack (`tools/voices/grace.toml`'s `[main]`/`[grave]`/`[amused]`/`[stern]` axis). `trace_entity(npc)`
  shows their whole voice; the synth pulls it via `spoken_by`. Sources: the module's direct speech + the
  Uncaged epigraph quotes ("either in the module, or in the quotes").
- **fields:** `text`, `register`(main|grave|amused|stern), `verb`(the speech verb it was read from),
  `owner`(npc), `attribution`(named-subject|entry-subject+verb|first-person), `page`
- **edges:** utterance→`spoken_by`(npc). *(addressee→`spoken_to` when an addressee is named — future.)*
- **tagging:** a quoted span is bound iff it's SPEECH (not an emphasis-label) attributed to THIS NPC (a
  foreign named speaker un-binds it); register = the speech verb; `confidence = attribution × cleanliness`,
  with cleanliness penalising OCR **column-bleed** (narration / word-fusion / brackets / mid-quote colons
  leaking into the span). Auto-admit ≥ θ=0.6, else → review (`low-confidence-dialog`).
- **Dabus seam (the consumer):** the `dabus` voice MCP (tools session) builds/requests/lists/finds dialog
  WAVs. It reads this dimension via `store.py` **readonly** (the sibling-lib pattern, no MCP-over-MCP):
  `neighbors(npc,'spoken_by','in')` → ids, `get(id)` → `text`+`register`. **The id is content-addressed
  `sha256(owner|text)`** so a rendered WAV stays joined to its line across re-pours (sequential ids would
  renumber). The `register` vocabulary IS grace.toml's axis; Dabus owns the (speaker→voice-set) and
  (voice,register)→ref-clip mappings. Mimir owns the text, never depends on F5-TTS.
- **boundary:** pathological-OCR entries (Seamus/Qaida) leave residual column-bleed that review catches —
  documented, not silently admitted. *(Future: page-grade gating from `quality.json` for a systematic floor.)*

### dim:creature — a generic monster / stat-bearing type
- **attested:** Monstrous Compendium appendices, Planes of X Monstrous Supplements; wiki Monster/Inhabitants; mimir Bestiary
- **fields:** `statblock`, `ecology{habitat_plane,diet,society}`, `variants[]`, `climbing` (CR/HD), `tactics`
- **edges:** habitat_plane→`inhabits` · is_a→creature-taxon · variant→`variant_of`

### dim:race — a playable / cultural species  *(taxon-bearing)*
- **attested:** Planewalker's Handbook (planar races + kits), The Inner Planes; mimir Planar Races (deeply subdivided)
- **fields:** `ability_mods`, `traits[]`, `society`, `origin_plane`, `playable`(bool), `subtype`
- **taxon:** outsider-type → family (eladrin/guardinal/archon/tanar'ri/baatezu/yugoloth/rilmani/aeon/psychopomp/modron…) → member
- **edges:** origin_plane→`native_to` · family→`is_a`(role: member)
- **POURED 2026-06-06 (PWH round): the book's "eight available races"** — aasimar · bariaur ·
  genasi (4 elemental variants as attested sub-records) · githzerai · planar half-elf ·
  planar human · rogue modron · tiefling. Curated cards (`parse/pwh.py RACE_CARDS`,
  paraphrased mechanics + page witnesses), name-attested per card page; variants attest
  individually or stay off the node. `native_to` minted only where the target plane node
  stands (bariaur→ysgard, githzerai→limbo, rogue-modron→mechanus); collective origins
  ("the Upper Planes") stay fields. Outsider taxon still awaits the MC appendices.

### dim:deity — a power / divine entity  *(wiki Powers 281; mimir Powers 226 — HIGH VOLUME)*
- **attested:** On Hallowed Ground, deities index; wiki Powers/Divine realms; mimir Powers/Pantheons
- **fields:** `portfolio`, `status`(alive/dead), `alignment`, `rank`(greater/intermediate/lesser/demi), `domains[]`, `symbol`, `realm`, `pantheon`, `proxies[]`, `aliases`, `gloss`
- **edges:** realm→`dwells_in`(plane/layer) · pantheon→`is_a` · proxies→`served_by` · worshippers→inverse `worships` · plot→`concerns`
- **POURED 2026-06-05 (corpus-attested):** `deity:aoskar` only — the lone power named in the poured books
  (Uncaged + Manifesto). **Aoskar ABSORBED `subject:aoskar`** (the fold): the deity node carries the
  portfolio epithets as `aliases` + the Dead Gods Plot (`concerns`), and the plothook tagger now anchors
  hooks on it (Cupgrass `seeks` deity:aoskar). Fills out when On Hallowed Ground / the deity-naming books
  pour (Poseidon/Arawn et al. live in those, un-poured today). `pour_deities` (`DEITIES` table).
- **GROWN 2026-06-06 (realms round): 46 powers** — every attested realm-holder enters as a deity stub
  (`pour_realms`): Moradin, Yondalla, Set, Odin, Loki, Hecate, Hades, Arawn (he poured after all — the
  malevolentiae attests him), Kiaransalee, the Queen of Air and Darkness… **`kind` is typed honestly:**
  `power` · `pantheon-group` (the Titans, the Vanir) · **`abyssal lord (quasi-power)`** (Graz'zt,
  Demogorgon, Zuggtmoy, Kostchtchie, Pazrael — realm-holders, not true powers). Each carries
  `fields.realms[]` + `home_plane` + box provenance with power-witness pages. On Hallowed Ground
  remains the portfolio/rank filler.

### dim:proxy — a deity's mortal/planar agent
- **fields:** `patron_deity`, `powers[]`, `npc_ref` · **edges:** patron→`serves`

---

## 2. SOCIAL  *(wiki Faction 43, Sect 22; mimir Factions 23 / Sects 34 / Philosophies 34 / Coteries 34 / Organisations 11 / Hierarchies 10)*

### dim:faction — one of the 15 (and the Ascendant/historical ones)
- **attested:** Factol's Manifesto, core box; wiki Faction/Ascendant Faction; mimir Factions
- **fields:** `philosophy`, `tenets[]`, `hq{location}`, `factol`, `sign`, `abilities[]`, `recruitment`, `status`(active/dissolved-post-Faction-War)
- **edges:** hq→`headquartered_in` · factol→`led_by`(npc) · allies→`allied_with` · enemies→`opposed_to` · members→inverse `member_of` · tenet→`espouses`(belief)

### dim:sect — a minor belief group (non-faction)
### dim:philosophy / belief — a tenet / philosophical position
- **fields:** `statement`, `held_by[]`(faction/sect), `implication` · **edges:** held_by→`espoused_by`
### dim:organization — guilds, coteries, crews, hierarchies (taxon: fiendish/celestial ranks)
- **fields:** `kind`, `members[]`, `purpose`, `hierarchy[]` · **edges:** member→`member_of` · rank→`outranks`

---

## 3. PLACES  *(wiki Locations 200+, Planes 78, Layers 46, Gate-towns 11; mimir Places 489 / Layers 85 / Planes 30)*

### dim:cosmology — a model of the multiverse  *(taxon root)*
- **attested:** Manual of the Planes editions; wiki Great Wheel / World Tree / World Axis planes
- **fields:** `model`(great-wheel|world-tree|world-axis|world-axis-4e), `edition`, `structure`
- **note:** the SAME plane sits differently per model → cosmology is a top taxon; planes link to it per edition.
- **POURED 2026-06-06 (In the Cage):** 2 grouping nodes — `cosmology:the-great-ring` (10 witness pages)
  + `cosmology:the-inner-planes`. Outer planes `part_of` the Ring (the Outlands sits INSIDE, no edge);
  inner/paraelemental `part_of` the Inner Planes; `location:sigil` is `hub_of` the Ring. The Wayfarer's
  ring-not-gate-towns portal claim resolves to the Ring node when the prose names no single plane.

### dim:plane — an Outer/Inner/Transitive plane  *(taxon-bearing)*
- **attested:** Planes of Chaos/Law/Conflict, Inner Planes, A Guide to the Astral/Ethereal
- **fields:** `category`(outer|inner|transitive|prime|demiplane), `alignment`, `planar_traits{magic,gravity,morale,time,…}`, `denizens[]`, `ruler`, `gate_town`
- **edges:** layers→`has_layer` · cosmology→`part_of`(per edition) · gate_town→`gated_by` · ruler→`ruled_by` · planar_trait→`exhibits`(rule)
- **POURED 2026-06-06 (In the Cage):** **24 planes** via the curated GAZETTEER + attestation sweep —
  a node ships ONLY with page witnesses (`fields.pages`); bytopia is registered but unattested → absent.
  16 outer + transitive (Astral/Ethereal/Prime) + inner (4 elemental + para-ooze). `parse/cage.py GAZ`
  is the recognizer; the planes' deep fields await Planes of Law/Chaos/Conflict pours.
- **ENRICHED 2026-06-06 (the three Planes boxes — Law 2607 / Chaos 2603 / Conflict 2615):** all
  **16 Great-Ring planes** (minus the Outlands — the Player's Primer isn't in corpus) carry their
  **attested layer structure** (`fields.layers` in box order, `layer_note` for Mechanus/Limbo/Abyss),
  gate_town, and dual/triple-source provenance. `parse/planes.py PLANE_CARDS` = curated cards,
  **text-validated**: `attest_card` searches the box's own reflow for every claimed name; a
  zero-witness claim is REFUSED. This round: **56/56 layer claims attested, 0 refused.**
  Bytopia entered the store here (its first witness is its own booklet).

### dim:layer — a sub-plane  *(Abyss layers, Baator's nine, etc.)*
- **fields:** `parent_plane`, `ordinal`, `ruler`, `features[]` · **edges:** parent→`layer_of` · ruler→`ruled_by`
- **POURED 2026-06-06:** 4 attested — Amun-Thys `layer_of` Arborea, Durao `layer_of` the Abyss, Avernus
  `layer_of` Baator, the Viper Wastes (parent NOT attested in this book — fields say so, no edge: honest).
- **GROWN 2026-06-06 (Planes boxes): 56 layers** with ordinals + page witnesses — Baator's nine
  (the box spells it **Cania**), Celestia's seven, Carceri's six, Acheron/Gehenna/Elysium/Pandemonium's
  four each, the triads, Bytopia's two, the Abyss's mapped first (**"the Plain of Infinite Portals"** —
  "Pazunia" never appears in the 2e box, so that name is an alias only). **Identity merge:** Planes of
  Chaos's *Pelion* = In the Cage's *Amun-Thys* → ONE node (`layer:amun-thys`, renamed Pelion, aliases
  kept) so the Ditch portal keeps pointing at the same identity. Mechanus + Limbo claim NO layers
  (`layer_note` says why) — verified-or-absent applies to negatives too.

### dim:location — a discrete site (kip, tavern, fortress, landmark)  *(highest volume)*
- **attested:** In the Cage, Uncaged, every adventure; wiki Locations in X; mimir Places
- **fields:** `region`(ward/layer/plane), `kind`, `occupants[]`, `description`, `portals[]`
- **edges:** region→`located_in` · occupants→inverse `located_in` · portals→`has_portal`
- **POURED 2026-06-06 (3rd book): 90 nodes.** In the Cage's six ward tours: **21 establishments MERGED**
  into existing Uncaged nodes (dual-source provenance, content appended `[In the Cage pNN]`) + **30 new**
  (incl. 8 `tier:minor` Lower-Ward pubs from the catchall). Roster law = the contents page (same as
  Uncaged); 10 entries whose heads the grade-C scan shredded are QUARANTINED by name with reasons
  (`cage-head-lost`) — the v1b re-OCR pass is their upgrade path, never a guess.

### dim:region — a ward, district, or named area  *(Sigil's wards; plane regions)*
- **fields:** `parent`(sigil/plane), `sites[]`, `factions_present[]` · **edges:** parent→`part_of`

### dim:settlement — a burg / town / city
### dim:gate-town — one of the 16 Outlands rim towns
- **attested:** A Player's Primer to the Outlands; wiki Gate-towns
- **fields:** `aligned_plane`, `features`, `slide_risk` · **edges:** aligned_plane→`gates_to`
- **POURED 2026-06-06:** 5 attested by In the Cage (Automata, Hopeless, Ribcage, Rigus, Torch — the
  Ditch map-key names them) — `gate_to` their plane + `located_in` plane:the-outlands. The other 11
  registered in the gazetteer, unattested, absent. *(Poured edge name is `gate_to`.)*
- **BACKFILLED 2026-06-06 (Planes boxes): +7** — Excelsior, Xaos, Sylvania, Bedlam, Plague-Mort,
  Faunel, Tradegate (each witnessed in its plane's own booklet). **12 of 16 stand;** Fortitude,
  Ecstasy, Curst, Glorium stay absent until the Player's Primer (or another witness) pours.
### dim:realm — a deity's planar domain  *(wiki Divine realms 30)* → `realm_of`(deity), `located_in`(layer)
- **POURED 2026-06-06:** 1 — the Dwarven Mountain `located_in` plane:the-outlands (p8: foundry portals).
- **GROWN 2026-06-06 (realms round): 48 realms** via `REALM_CARDS` (`parse/planes.py`) — curated from
  the boxes' own realm sections (Law/Conflict carry literal `POWER.` stat lines; the Chaos Travelogue
  heads each realm with its name), **text-validated**: realm name AND power name must both witness, or
  the card declares power=None WITH a note (Stillsong's "great mystery"; the Spawning Stone's slaad
  lords). 47/48 attested; **Blood Tor refused** (name survives only as the shredded header `BL OOIJ
  ToR`) → quarantined `realm-unattested` for v1b. Names follow the text: **Cavern of Azuth** (not
  "Azuth's Cavern"), **The Slime Pits** (Shedaklah OCR-shredded, rides as alias). `located_in` binds
  the layer when the card is confident + the node exists, else the plane.
### dim:sigil — THE hub (singleton meta-location)  *(wiki/mimir Sigil 17/92)* → wards, the Lady, factions, portals
- **POURED 2026-06-05:** the hub PLACE stays `location:sigil`, now enriched — `ruled_by` → the Lady,
  `has_ward` → the six wards, `seats` → every faction. **The Lady of Pain is a `sigil`-type being**
  (`sigil:the-lady-of-pain`) that ABSORBED `subject:the-lady-of-pain` (the fold): sui generis (no statblock,
  no power), carrying her aliases + the cross-book pivot edges (Shemeshka `opposes` her in Uncaged, the
  Fated `seeks` to evade her Maze in the Manifesto — one node spanning both books). `pour_sigil`.

---

## 4. CONNECTIONS  *(wiki Planar pathways 12, Locations on the River Styx 17)*

### dim:portal — a doorway between places
- **attested:** In the Cage, Uncaged, Sigil sourcebooks
- **fields:** `from_location`, `to_destination`, `key{item,condition}`, `permanence`, `properties`
- **edges:** from→`portal_in` · to→`leads_to` · key→`keyed_to`(item)
- **POURED 2026-06-06 (In the Cage): 27 portal nodes** from the mechanical sweep
  (`parse/cage.py sweep_portals`): sentence→clause TRIGGER×DESTINATION grammar, gazetteer dests,
  owned regime (an establishment's entry binds its portals) + front-matter regime (nearest in-clause
  src mention), negation guard ("not to the gate-towns…" pours nothing), layer-suppresses-parent
  dedup. **Poured edge names: `opens_from`(→location, role sigil-side) + `connects_to`(→place,
  role far-side)** — supersede the registry's draft portal_in/leads_to. Every node carries
  `fields.witness` (the sentence), `form[]` (permanent|temporary|shifting|one-way), pages.
  θ=0.55; 11 candidates queued `portal-review` (unbound src or <θ) — review promotes, never silence.
  Marquee finds: the nic'Epona's three gem-portals, the Bottle & Jug arch-cluster (×5), the Hive's
  wandering Limbo shack, the one-way ooze puddles, Jeremo's secret Ysgard door (CURATED re-bind —
  reflow scrambled it into the Prison's span; `PORTAL_CURATIONS`, witnessed).

### dim:pathway — a planar conduit (River Styx, Infinite Staircase, World Tree branches, color pools, conduits)
- **fields:** `kind`, `connects[]`(planes), `method`, `hazards[]` · **edges:** connects→`connects`
- **POURED 2026-06-06:** 2 attestation-stubs (the River Styx, the River Oceanus — In the Cage names
  both as portal destinations); `connects[]` edges await the planes books.

---

## 5. RULES & MECHANICS  *(wiki Spells 617!, Psionics 14; mimir Crunch 15, Hazards 12, Energons 12)*

### dim:spell — a spell  *(HIGHEST single category — 617)*
- **attested:** Planewalker's Handbook, SRD 5.1/5.2, every class source
- **fields:** `level`, `school`, `classes[]`, `components`, `range`, `duration`, `effect`, `planar_keyed`(bool), `reversible`
- **edges:** classes→`castable_by` · planar→`keyed_to`(plane) · same spell across editions→`same_as`
- **POURED 2026-06-06 (PWH round): 57 spells** from Magic on the Planes (printed 112-131),
  parsed (`parse/pwh.py extract_spells`): rigid head = NAME + `(School[, Elemental [X]]; Level N)`
  gated by the closed 2e school vocabulary; `Level I` OCR mapped to 1 (it hid two priest
  spells). **Stat binding is verified-or-absent:** the two-column reflow scrambles adjacent-head
  statlines, so fields bind only when exactly one group sits in the head's gap; 12
  reflow-scrambled spells promoted via `SPELL_STAT_CURATIONS` (hand-read, page-witnessed,
  semantics-bound — sphere names / area targets / family templates), stamped `stats_cured`.
  Dual-class spells merge by name with `level_by_class`/`stats_by_class` disclosed when the
  print differs (Protection from Prime is W2/P1). 8 spells carry the book's own HELLBOUND
  origin tag → `attested_in role=first-printed-in` edges. 1 head-lost quarantine
  (`pwh-spell-head-lost`, printed p130 — promotion needs a print reading). Mechanics TEXT
  stays un-poured (M6 lane); statline attributes ride the node like creature statblocks.

### dim:rule — a mechanical rule / subsystem
- **fields:** `category`(planar-effect|faction-ability|combat|travel|morale), `text`, `applies_to[]`, `edition`
- **edges:** applies_to→`governs` (plane/faction/race)

### dim:planar-trait — a property modifying a plane (the planar-properties system)
- **fields:** `trait_type`(magic|gravity|time|morale|elemental|alignment), `plane`, `effect`, `severity`
- **edges:** plane→`exhibited_by`

### dim:item — equipment / magic item / artifact
- **fields:** `kind`, `properties[]`, `attunement`, `value`, `charges`, `edition`
- **edges:** wielder→inverse `wields` · key-for→`unlocks`(portal)

### dim:class — a class or 2e kit (planar kits)
- **fields:** `edition`, `abilities[]`, `requirements`, `is_kit`(bool), `parent_class`
- **POURED 2026-06-06 (PWH round): 11** — 4 base-class stubs (fighter/wizard/priest/rogue,
  `is_kit: false`; the spine `castable_by` and `kit_of` point at) + 7 kits as curated cards
  (`parse/pwh.py KIT_CARDS`): 4 planewalker kits + 3 location kits (abyssal warrior ·
  floating sorcerer · hinterland bandit — grade-C p100 recovered by OCR-form alias, the
  Blood Tor law). Location kits edge `located_in` where the plane stands (abyss, outlands).
  Proficiency MECHANICS are M12 in the handoff; kit requirement fields name them.
### dim:psionic — a psionic power / wild talent
- **RE-PARKED 2026-06-06 (registry correction):** the close-out expected psionics to pour
  with the Planewalker's Handbook — **the book has no psionics section** (three scattered
  asides: printed pp. 8, 92, 141; "psionicists are basically wizards, as far as most
  planewalkers are concerned"). No identities to pour, none invented. The dim waits for a
  psionics-bearing book (The Will and the Way / Dark Sun line — not in the corpus).
### dim:hazard — an environmental danger (razorvine, plane-specific perils)  *(mimir Hazards 12)*
### dim:table — a random/reference table (encounter, planar-effect, slide)  *(mimir Encounter Lists 21)*
- **fields:** `dice`, `entries[{roll,result}]`, `context` · **edges:** result→`references`

---

## 6. LANGUAGE & CULTURE  *(mimir Chant 16, Languages 11; the cant glossary in Planewalker's Handbook)*

### dim:cant-term — a piece of the Planar Cant lexicon
- **attested:** Planewalker's Handbook glossary, mimir Chant; *the language backend's core*
- **fields:** `term`, `definition`, `part_of_speech`, `register`(common|faction|low), `example`, `synonyms[]`, `etymology`
- **edges:** faction-jargon→`used_by` · synonyms→`synonym_of`

### dim:language — a tongue (not the cant — e.g., Abyssal, the Dabus rebus-speech)
### dim:saying — a proverb / idiom ("The Lady's mercy", "Sodding berk")
- **fields:** `text`, `meaning`, `context` · **edges:** →`references`(faction/place)

---

## 7. NARRATIVE & PLAY  *(wiki Timeline 141, Adventures 13; mimir Poetry 52 / Stories 20 / Essays 13 / Histories 7)*

### dim:adventure — a published module
- **fields:** `code`(TSR#), `level_range`, `synopsis`, `acts[]`, `npcs[]`, `locations[]`, `hooks[]`
- **edges:** npcs→`features` · locations→`set_in` · code→`is_a`(source)

### dim:hook — an adventure seed  *(Adventure Hook Junction; Uncaged "Ties That Bind")*
- **two grains, one type** (like npc full/minor): `grain:plot` = a named arc (hand-curated — the
  Blood War Plot, the Dead Gods Plot…); `grain:seed` = a fine-grained, **mechanically-tagged** hook
  (one cutter's goal/scheme/feud/quest). Seeds nest under arcs via `part_of`.
- **fields:** `grain`, `premise`, `flavor`(goal|scheme|conflict|quest), `owner`(npc/faction),
  `object`, `trigger`, `stakes`, `pages`
- **edges:** owner→`involves`(role *subject*) · object→`involves`(role *object*) · seed→`part_of`(plot) ·
  when the object is a `subject`, owner→`seeks`/`schemes_around`/`opposes`/`hires`(subject) — the pivot graph
- **tagger:** `parse/hooks.py` — see *Mechanical hook tagging* below (the "how").

### dim:subject — a cross-book PLOT PIVOT (a MacGuffin: a dead power, a ruler, a war)  *(provisional)*
- **why its own type:** hooks in different books pivot on the same thing — Aoskar, the Lady of Pain,
  the Blood War. A subject node **carrying aliases** lets oblique references resolve ("god of portals"
  → Aoskar) and makes the pivot graph-walkable: `trace_entity("The Lady of Pain")` shows the Uncaged
  hooks (Shemeshka opposes, Djhek'nlarr hires) AND the Manifesto ones (Sign-of-One opposes, Fated
  seeks) in one neighbourhood. **The subject node IS the cross-book bridge** — no special edge needed.
- **fields:** `kind`(dead-power|power|conflict|…), `gloss`, `aliases[]`
- **edges:** plot→`concerns`(subject) · owner→`seeks`/`opposes`/`schemes_around`/`hires`(subject)
- **provisional / reconciliation:** `subject` is the plot-anchor *role*, not an ontology. When the home
  dimensions pour (Aoskar → `dim:deity`, the Blood War → `dim:event`, the Lady → the `dim:sigil`
  singleton), each subject reconciles into its node via `same_as`/`aspect_of`, keeping the aliases +
  pivot edges. Aliases are pivot-SPECIFIC (Aoskar's portfolio epithet), never a generic slur — "fraudulent
  god" names *any* power and is refused. **Resolved (Meme, 2026-06-05):** subjects FOLD into their home
  dims at pour-time — `subject` is a staging role, not permanent.

### dim:event — a historical / setting event (Faction War, Great Modron March, Blood War battles)
- **fields:** `kind`, `era`, `when`, `participants[]`, `gloss`, `aliases` · **edges:** participants→`participated_in` · →`occurred_at`(location) · date→`occurred_on`(timeline) · plot→`concerns`
- **POURED 2026-06-05 (corpus-attested):** `event:the-blood-war` (the eternal fiend war) — **absorbed
  `subject:the-blood-war`, the LAST fold**: aliases + the Blood War Plot (`concerns`); the Doomguard's
  Manifesto hook re-anchored on it (`seeks`). And **`event:the-great-upheaval`** (~630y ago) — the founding
  event of the modern Cage: the Lady destroyed Aoskar, razed his Great Temple of Doors (now the Shattered
  Temple), forbade worship, chartered the factions. **The cross-dimension capstone:** `deity:aoskar` +
  `sigil:the-lady-of-pain` `participated_in` it, and it `occurred_at` `location:sigil:the-shattered-temple`
  — one event node ties three dimensions. `pour_events` (`EVENTS` table). With this, the `subject` staging
  lane is **empty** (all three pivots folded into deity/sigil/event).

### dim:timeline — a chronology anchor  *(wiki Timeline 141)*  → ordered `before`/`after` edges
### dim:fiction — in-world creative text (poem, story, essay, SIGIS zine, epigraph, handout)
- **fields:** `form`(poem|story|essay|letter|ad), `author`(in-world), `text`, `themes[]`
- **edges:** author→`authored_by` · about→`references`
### dim:rumor — a piece of chant with a truth-value  *(true/false/uncertain — DM dark)*
- **fields:** `content`, `truth`, `spreads_in` · **edges:** about→`references`

### Mechanical hook tagging  *(`parse/hooks.py` — the "how", proven on Uncaged + Manifesto)*

A `grain:seed` hook is identified WITHOUT hand-transcription by three signals — **TRIGGER × ANCHOR ×
PROXIMITY**:
- **TRIGGER** — an intent verb in four flavors, with priors (most-specific wins): `scheme` .85
  (secretly/plots/usurp/betray) > `quest` .80 (hires/pays/bounty/reward) > `conflict` .75
  (enemy/feud/revenge/opposes) > `goal` .70 (wants to/seeks/next goal/'d love to).
- **ANCHOR** — ≥1 admitted entity (or subject *alias*) named in the trigger's sentence (±1).
- **PROXIMITY** — same sentence (×1.0) vs ±1 sentence (×0.8).

`confidence = base[flavor] × anchor_specificity × proximity × subject_known`, ×0.5 if the trigger is
polysemous (rival/reward), ×1.15 if the object is a `subject` (the MacGuffin bonus). Auto-admit ≥
**θ=0.55**, else → the review queue (`quarantine` bucket `low-confidence-hook`). The subject is FREE on
the prose side: it's the entry's NPC, known from the roster boundary.

**Two regimes — match the method to the book's shape (the central finding):**
- **prose-embedded** (Uncaged): hooks live in entry bodies; subject = the entry's NPC (exact). Tag all
  anchors. → **41 seeds.**
- **field-structured** (Manifesto): the faction cards' geography/allies/enemies are ALREADY poured as
  fields + `allied_with`/`opposed_to` edges, so prose-tagging there mostly RE-surfaces structured data
  ("Athar schemes around its own HQ"). **Restrict to `subject` anchors** → only the narrative MacGuffins
  the cards omit, which are exactly the cross-book bridges. → **3 seeds** (Doomguard→Blood War,
  Fated→the Lady, Sign-of-One→the Lady).

**Failure modes guarded (the assay caught each — `tools/hook_probe.py`):** list-density fan-out (>3
distinct anchors near one trigger = a relationship LIST already held as `PLOT_EDGES` → drop the
sentence, kills the "Zadara schemes around [a dozen names]" blow-up); alias double-count (collapse to
one per id); struct-field re-tag (`Enemies:` lines routed out); polysemy (rival-as-compare,
reward-as-adjective); setting-scale anchors (Sigil/the Cage → ×0.4). Self-tested in
`hooks.py.__main__`; gate-pinned in `tests/test_hooks.py` + `tests/test_gate.py` (48 green).

---

## 8. META & REFERENCE  *(wiki Sourcebooks 38, Imagemaps 19, Audio 26; mimir Music 40, Collections 41)*

### dim:source — a product (book/box/zine/article) as a first-class node
- **fields:** `title`, `code`, `edition`, `year`, `kind`(boxed-set|accessory|adventure|netbook|wiki|article), `license`
- **edges:** every entity→`attested_in`(source) — makes provenance traversable
### dim:map — an illustration / map / imagemap
- **fields:** `depicts`, `kind`(map|portrait|diagram), `page`, `file` · **edges:** depicts→`depicts`
### dim:symbol — a faction sign / divine symbol / heraldry
### dim:audio — a soundtrack cue / pronunciation / actual-play  *(mimir Music 40)*

---

## Cross-cutting: edge-type catalog

Relations are **generic rows** `(rel, src_type, src_id, tgt_type, tgt_id, edition, provenance, confidence)`.
Adding a relation kind = a new `rel` string, never a schema change.

`member_of · led_by · headquartered_in · espouses · allied_with · opposed_to · is_a · variant_of ·
located_in · part_of · has_layer · layer_of · ruled_by · has_ward · seats · gated_by · gates_to · has_portal · leads_to ·
portal_in · keyed_to · connects · inhabits · native_to · dwells_in · worships · served_by · realm_of ·
governs · exhibits · castable_by · wields · unlocks · features · set_in · involves · driven_by ·
concerns · seeks · schemes_around · hires · participated_in · occurred_on · occurred_at · authored_by · spoken_by ·
references · attested_in · depicts · used_by · synonym_of ·
opens_from(portal, sigil-side) · connects_to(portal, far-side) · gate_to(gate-town→plane) · hub_of(Sigil→Ring) ·
same_as(cross-edition) · converts_to(uplift) · supersedes(errata)`

## Cross-cutting: taxon (hierarchy) catalog

Hierarchies use `taxon(id,name,tier,parent_id,kind)` + `is_a`/`part_of` membership edges with `role`:
- **cosmology** → plane → layer → region → location → site
- **creature** → outsider-type → family (eladrin/guardinal/tanar'ri/baatezu/yugoloth/rilmani/aeon/…) → species → variant
- **organization** → faction|sect|coterie → rank → member
- **pantheon** → deity → proxy

## Cross-cutting: identity, aspect & the edition view  *(refined with `MECHANUS.md` §2)*

Edition is **a view over the same data**, not merely a tag. Three primitives — and the
**envelope does not change** to get them:

- **identity** — a thin, edition-less node `{type, identity_id, name, aliases[]}`: *A'kin*,
  *the vrock*, *Fireball*, *initiative*. **Mimir stores it** (gate-admitted) — it's where
  cross-edition curation lives. Synthesized from `same_as` clusters.
- **manifestation** — the standard envelope entity above, edition-tagged, gate-admitted.
  Links to its identity via an `aspect_of` edge (new `rel` string = data, not schema).
- **view** — a *pure function* `view(identity, edition, conversion_law_version) → manifestation`,
  **owned by Mechanus**, content-addressed. Ladder: NATIVE → ADMITTED(derived, gated) →
  DERIVED(live, flagged + docket) → SCAFFOLD. Mimir keeps the *records*; Mechanus runs the *function*.

`edition` is the **ruleset axis only** — `{1e, 2e, 5e-2014, 5e-2024, 3.5e?, 4e?}` — and is
**distinct from `license`** (a `dim:source` field: SRD-5.1 ≅ 5e-2014, SRD-5.2.1 ≅ 5e-2024,
For Gold & Glory ≅ quotable-2e, official-scan ≅ local-only). `srd` is **dropped** from the
edition enum — it's a license, not a ruleset (per REVIEW-5E §E). PAitM is the conversion
**answer key**. Cosmology stays its own taxon (Great Wheel / World Tree / World Axis),
edition-attached, never baked into `plane`.

---

## Registration recipe (add a dimension in 4 steps — no migration)

1. **Register** the `type` id here + in the code registry (alias map).
2. **Write** its `extract_<type>()` (the only bespoke code — emits envelopes).
3. **Declare** its `fields` schema + dedup/merge key + the validators that gate it.
4. **Declare** its edge-synthesis rules (which fields imply which edges).

Envelope, FTS, graph, MCP tools, curation-preservation, and the validator framework all keep working.

## 5E cross-check — RESOLVED  *(verdicts in `REVIEW-5E.md`, grounded in 54 PAitM statblocks)*

> **Canonical deltas from the review:** `dim:background` + `dim:feat` confirmed (Tier 2);
> `subclass` stays a `class` field (zero in PAitM — don't pre-build). 5e statblock sub-schema
> confirmed (edition-keyed `5e-2014`: cr/pb/abilities/saves/skills/senses/resist/immune/
> condition-immune/traits/actions/bonus/reactions/lair; AC **ascending**; Challenge line
> carries XP **and** PB inline; Lair-without-Legendary is valid). Field adds: `spell`
> (`concentration` is a *duration prefix*, not a flag; keep material text), `item`
> (`{kind,rarity,attunement,attunement_req}` — the mimir is officially a Wondrous Item),
> `condition` promoted (closed 2014 set).
>
> **Six I missed (the point of the second opinion):** (1) **faction-agent creatures** —
> 16/54 statblocks → add `member_of`/`affiliated_with`(faction) edge-synthesis to
> **`creature`**, not just `npc` **[→ Tier 1]**; (2) **planar-influence** — `dim:rule
> kind=planar-influence` + edge `influences`(plane→rule→creature), prime uplift-diff target;
> (3) **mimir-note / read-aloud** — 76+ attributed quotes + 101 read-aloud boxes →
> `dim:fiction.form += {mimir-note, read-aloud}` + `authored_by` in-world speakers — *the MCP
> is named Mimir; this is its **voice bank*** [high leverage for the cant backend]; (4) **map
> pairs** — `dim:location.fields += map_ref{map,marker}`, `dim:map.fields += {player_version,
> grid,scale}` + `variant_of`(DM↔player, 10 pairs), `dim:map.kind += handout`; (5) encounter/
> CR tables fit `dim:table`/`dim:hook` (gate-town `slide_risk` ✓ live in 5e); (6) **free L3
> witness** — 48 tooltip captures render the same statblocks via a *different* DDB pipeline →
> dual-rendering diff, zero-cost & independent (→ `VALIDATION.md`).

*Original cross-check below — kept for the reasoning trail (now answered above).*

This registry was derived from 2E source + the wikis. Before we pour the store, the 5E
ingest session confirms/extends the items below. The architecture *absorbs most* 5E
difference via the open `fields` envelope + `edition` tag + edition-keyed validators —
so the sharp question is narrow: **does any 5E thing need a NEW DIMENSION or a NEW
top-level FIELD slot we don't already have?**

**A. Almost-certain gap — 5E statblock schema (field, not dimension).** `npc`/`creature`
already exist, but their `statblock` is 2E-shaped (AC descending, THAC0, HD, morale). 5E
needs an edition-keyed sub-schema + its own validators: `cr`, `proficiency_bonus`, ability
scores STR..CHA (+mods), `saving_throws`, `skills`, `senses`(darkvision/passive Perception),
`damage_resistances/immunities/vulnerabilities`, `condition_immunities`, `languages`,
`traits[]`, `actions[]`, `bonus_actions[]`, `reactions[]`, `legendary_actions[]`,
`lair_actions[]`, `spellcasting`. AC is *ascending* (validator ranges differ). → confirm.

**B. Candidate NEW dimensions (2E had no clean equivalent):**
- `background` — **strong candidate**; 5E Planescape leans on faction-as-background
  (PAitM). 2E "kits" (mapped to `class`) are not the same shape. Fields: `feature`,
  `proficiencies`, `equipment`, `characteristics{trait/ideal/bond/flaw tables}`. → confirm.
- `feat` — 5E first-class option (prereqs, ASI-replacement); we only have it as a thin
  `class`-adjacent note. → confirm whether it earns its own dimension.
- `subclass` — 5E class archetypes (features-by-level). Field on `class` or its own dim? → confirm.

**C. Edition-keyed field additions to existing dimensions:**
- `spell`: `casting_time`, `ritual`(bool), `concentration`(bool), `components{v,s,m}`,
  `at_higher_levels`, per-class spell lists — 2E lacks these.
- `item`: `rarity`(common…artifact), `attunement_req` — 5E's core item axes.
- `condition`: 5E formalizes a closed condition set — promote from long-tail to tracked.

**D. 5E-only mechanics to slot as `rule`/adventure-field (probably NOT new dimensions):**
the 5E condition system; **Turn of Fortune's Wheel** incarnation/Fortune's-deck mechanic;
sidekick rules; milestone/encounter-block adventure structure.

**E. Edition granularity — sharpen the `edition` enum.** Distinguish **`5e-2014`**
(PAitM 2023, SRD 5.1) from **`5e-2024`** (SRD 5.2.1) — backgrounds, "species" vs "race",
weapon mastery, and statblock conventions differ between them, and we hold *both* SRDs.
The uplift must name its target ruleset. → confirm which 5E PAitM uses (expected 5e-2014).

> Reviewer: anything here you'd add/cut/reshape, and—critically—anything 5E-native that
> isn't on this list at all? That last question is the whole reason for the second opinion.

## Priority (by observed volume + project leverage)

**Tier 1 (build first):** npc, faction, plane, location, portal, spell, deity, cant-term, source.
**Tier 2:** creature, race, layer, gate-town, region, hook, subject*, dialog, event, rule, item, pathway.
**Tier 3 (long tail):** philosophy, sect, organization, planar-trait, class, psionic, hazard, table,
language, saying, adventure, timeline, fiction, rumor, map, symbol, audio, proxy, realm, cosmology.

*`subject` is a provisional plot-anchor role (see §7), reconciling into deity/event/sigil at pour-time.

---

## Decisions ledger

| date | decision | rationale |
|---|---|---|
| 2026-06-05 | **`dim:hook` gains a `grain` field** {plot\|seed} — NOT a new `plothook` type | One query surface; mechanically-tagged seeds nest `part_of` the curated arcs. Mirrors the npc full/minor tier. *(Fork ruling, Meme.)* |
| 2026-06-05 | **Cross-book pivots promoted to `dim:subject` nodes with aliases** — NOT a curated string-list | Oblique refs resolve via alias ("god of portals"→Aoskar); the pivot is graph-walkable; the subject node *is* the cross-book bridge. Provisional — reconciles into deity/event/sigil. *(Fork ruling, Meme.)* |
| 2026-06-05 | **Field-structured books restrict hook-tagging to `subject` anchors** | A faction card's geography/allies are already poured as fields+edges; prose-tagging them double-counts. Only the MacGuffins the cards omit are new — and those are the cross-book bridges. *(V&V finding — the Manifesto assay.)* |
| 2026-06-05 | **`subject` pivots FOLD into deity/event/sigil at pour-time** (resolves the §7 open Q) | `subject` is a staging role only; when the home dims pour, each reconciles via `same_as`/`aspect_of`, keeping aliases + pivot edges. *(Meme.)* |
| 2026-06-05 | **`dim:dialog` is a dimension + `spoken_by` edge** (not an npc field) | Bound speech stays queryable/traceable/render-ready; register read from the speech verb (the grace.toml axis); the voice stack pulls a character's lines via the edge. `tools/` stays out-of-band. *(Fork ruling, Meme.)* |
| 2026-06-05 | **`dialog` ids are content-addressed `sha256(owner\|text)`** | Stable across re-pours so the Dabus voice MCP's rendered WAVs stay joined to their line; sequential ids renumber on every re-extract. Dabus reads dialog via `store.py` readonly. |
| 2026-06-05 | **FOLD executed: Aoskar `subject`→`deity:aoskar`; the Lady `subject`→`sigil:the-lady-of-pain`** | First run of the staging-fold ruling. The home-dim node absorbs the pivot's aliases + edges; the plothook tagger re-anchored the hooks automatically via `PIVOT_TYPES`=(subject,deity,sigil). `location:sigil` enriched (ruled_by/has_ward×6/seats×17). The Blood War stays a `subject` until `event` pours (last). |
| 2026-06-05 | **`event` poured + the LAST fold: the Blood War `subject`→`event:the-blood-war`** (staging lane now EMPTY) | Completes the staging-fold cycle — all three pivots home (`PIVOT_TYPES`+=event). `event:the-great-upheaval` is the cross-dimension capstone: `deity:aoskar` + `sigil:the-lady-of-pain` `participated_in` it, `occurred_at` the Shattered Temple — one event ties three dims. |
| 2026-06-05 | **Hook θ=0.55** (below the npc θ=0.70) + list-density cap (>3 anchors/trigger) | Adventure seeds are softer than facts and carry a visible confidence + flavor; the cap kills the back-matter relationship-LIST fan-out already held as `PLOT_EDGES`. |
| 2026-06-06 | **In the Cage pours by ROSTER LAW** (contents page = entry boundaries) + a smallcaps OCR decoder + fallback boundaries + a named `EXPECTED_ABSENT` table | Same law as Uncaged's roster split. The display face is hostile (T→`+`, O→`©/0/9/e`, M→`ITI/III/ffl/m`, LL→`tt`, &→`8t/ft/Et`) — `parse/cage.py decode_heading` is heading-only, prose never enters it. An UNFOUND roster row still emits a page-end boundary (neighbors never absorb its pages) and quarantines BY NAME with the reason — 10 of 61 heads died in the grade-C scan; v1b re-OCR is their path in. "Verified or absent." |
| 2026-06-06 | **Places pour = curated GAZETTEER × attestation sweep** — a node ships only with page witnesses | The gazetteer (`cage.py GAZ`: 16 outer + transitive + inner planes, layers, realms, 16 gate-towns, pathways, 2 cosmology groupings) is the RECOGNIZER; the book's text is the WITNESS. 38 attested poured (24 planes, 5 gate-towns, 4 layers, 2 pathways, 1 realm, 2 cosmology); bytopia + 11 gate-towns registered-but-unattested stay absent. Structural edges (`layer_of`/`gate_to`/`located_in`/`part_of`-ring/`hub_of`) pour only between attested nodes. |
| 2026-06-06 | **`dim:portal` pours via the mechanical sweep, θ=0.55, witness-sentence mandatory; poured edges `opens_from`/`connects_to`** | TRIGGER×DESTINATION over sentence→clause windows; owned regime (entry binds) vs front-matter regime (nearest in-clause src); negation guard; layer-over-parent dedup. Map-key labels ARE attestations (the cartographer's curation) — their soup-witnesses disclose themselves. Unbound/<θ candidates queue `portal-review` (11) — review promotes, the pour never guesses. |
| 2026-06-06 | **`PORTAL_CURATIONS` — witnessed sweep re-binds** (the "fix a berk once" law extended to bindings) | Reflow occasionally scrambles a paragraph into the NEXT entry's span (Jeremo's Ysgard portal landed in the Prison's). When the witness sentence itself names the true owner, a curated `(src,dest)→src` re-bind applies at pour time, stamped `method: portal-sweep+curation`. |
| 2026-06-06 | **Portal review queue ADJUDICATED — 6 promote / 5 reject, none dropped** (`PORTAL_ADJUDICATIONS`, Meme) | Promote = the human override of the θ floor (gym's turquoise arch at 0.50; the Mortuary nexus whose comma-list broke clause pairing) or a **city-level class-portal binding** (`opens_from` location:sigil with `fields.src_class` disclosed — butcher shops/public baths/foundries/hidden air-supply). Reject = recorded why under `portal-rejected` (illustrative shifting-pattern examples, a crime-category hypothetical, the defunct rumor-grade Baator arch). 33 portals stand; the queue is empty. |
| 2026-06-06 | **Planes boxes pour by CURATED CARDS, text-validated** (`parse/planes.py`): a claim pours only with witnesses from the box's own reflow; zero-witness claims REFUSED + reported | The cards carry the box's OWN spellings (Cania; Olympus/Ossa/Pelion; "the Plain of Infinite Portals" — Pazunia is post-2e). 56/56 layers attested, 0 refused; 16 planes enriched; +7 gate-towns. **Identity law applied:** Pelion absorbs `layer:amun-thys` (one layer, two books, one node — portals keep their target). |
| 2026-06-06 | **Realms + per-plane alignment/traits DEFERRED** from the planes round | The mechanical "realm of X" sweep returns OCR fragments ("Olym", "Arvan") — pouring it would be guess-laundering. Realms need the Travelogue's structured per-layer lists as a curated+witnessed pass; alignment strings likewise enter only with page witnesses. `dim:realm` stays at 1 (the Dwarven Mountain) meanwhile. |
| 2026-06-06 | **Realms round EXECUTED — `REALM_CARDS`, double-witnessed** (realm name AND power name must both attest; power=None requires a note) | The deferral resolved the right way: the Law/Conflict books carry literal `POWER.` stat lines (the mechanical anchor the realm-of sweep lacked), the Chaos Travelogue heads realms by name. 47/48 poured + 45 deity stubs (kind: power / pantheon-group / abyssal-lord-quasi-power); Blood Tor refused→quarantined (`realm-unattested`). Poured names follow the TEXT (Cavern of Azuth; The Slime Pits w/ shedaklah alias). Alignment/traits still deferred. |
| 2026-06-06 | **Rule/effect substance HANDED OFF — Mimir keeps who/what/where/when; Mechanus gets what GOVERNS; Modron gets what the dice APPLY** (Meme's lane ruling; `build/family/rule-effect-handoff.md`) | `dim:rule` + `dim:planar-trait` become POINTER dims (node = name + witness + Mechanus `law_id`, joined by `exhibits`); `dim:table` substance → Modron rollables (Mimir holds identity + `used_at`); `dim:hazard` splits (existence/where = Mimir, law = Mechanus M7, dice = Modron D7); `dim:spell`/`dim:psionic` keep identity + who/where only (mechanics = Mechanus M6). The handoff lists M1-M8 / D1-D9 with page witnesses; numbered Qs to both siblings; Mimir mints pointer edges only after their ids exist. |
| 2026-06-06 | **Seven-dim round EXECUTED: proxy 4 · sect 6 · settlement 11 · saying 31 · adventure 31 · creature 16 · timeline +4 events** (`parse/boxset.py` + `parse/monstrous.py`; pours `pour_boxset`/`pour_creatures`/`pour_timeline`) | Mechanical where the books anchor (named `proxy of` bindings mint deity stubs; `SYNOPSIS:`-carded adventures; attribution-dashed sayings θ=0.6 with prose-attribution + letter-space guards; the MC parser handles THREE reflow formats — inline, label/value alternation w/ wrapped labels, split-column run-zip — plus a type-signature correction pass); curated-and-attested where they don't (sect/settlement cards). Creatures: 16 clean admit, 9 QUARANTINE by name (`mc-parse`, reasons recorded — v1b re-OCR path); name fragments skipped as page-spillover. Timeline: 4 phrase-witnessed Blood War chronology events (`before` chain, `part_of` event:the-blood-war, source:hellbound minted). |
| 2026-06-06 | **REGISTRY CLOSE-OUT — all 43 dims now poured (26), handoff-pending (4), book-pending (4), or proposed-closed (8)** | Poured 26 (+`subject` lane). **Handoff-pending:** rule · planar-trait · table · hazard (pointer-dims; await Mechanus/Modron ids per the lane ruling). **Book-pending:** spell · race · class · psionic (identities pour with the Planewalker's Handbook). **PROPOSED-CLOSED (Meme to ratify):** cant-term → cant sibling owns the lexicon · audio → dabus owns renders · rumor → fold to `hook` grain · region → wards live as location kind:ward · philosophy → carried by faction/sect fields · language/map/symbol → parked-thin (map awaits the player/DM-pair design). The mass spot-check workflow has its full target list. |
| 2026-06-06 | **GREAT AUDIT APPLIED — 824 entities reviewed, docket adopted verbatim, ONE re-pour** (Meme: "Misbinds are expected - Implement the correction docket; good audit") | All 314 confirmed findings + 35 court promotes landed: `cage.ENTRY_CURATIONS` (14 witnessed anchor-spans; all 10 head-lost entries RECOVERED, queue drained), `HOOK_ADJUDICATIONS` (stable book×object×flavor×page keys — seed ids renumber), `monstrous.CREATURE_CURATIONS` (22; renames re-slug ids; 6 recoveries admit), `DIALOG_ADJUDICATIONS` (28 reject + 1 rebind + 14 vision-over-θ promotes), `ITEM_CURATIONS` (7 drops, 4 de-fusions), 18 card fixes (Goldfire, Windwrath, Noctos removed, Blood Tor attests, gate_town verified-or-absent), curations.json 3→130 via the universal `_admit_seed` rail. **REGISTRY RATIFIED (same ruling): all 8 proposed-closed dims CLOSED** — cant-term→cant · audio→dabus · rumor→hook grain · region→ward locations · philosophy→faction/sect fields · language/map/symbol parked-thin. End state: **814 entities · 1,817 edges · 91 quarantined (6 adjudicated buckets)** · suite 104 · integrity 0 hard. V&V round 5 in VERIFICATION.md; docket + run records in `build/mimir/review/`. |
| 2026-06-06 | **PWH ROUND EXECUTED — the player bible (2620) pours race 8 · class 11 · spell 57 (+1 head-lost q) · faction 3rd-witness ×15; psionic RE-PARKED (wrong book)** (`parse/pwh.py` + `pour_pwh`; 891 entities · 1,988 edges) | Registry close-out's book-pending lane: races + kits = curated cards, name-attested per page (genasi's 4 variants attest individually; hinterland bandit recovered via OCR-form alias). Spells = parsed identities (school-vocab-gated heads; `Level I`→1 recovered 2 priest spells) + **verified-or-absent stat binding** — the 2-column reflow scrambles adjacent-head statlines, so ambiguous gaps bind NOTHING and 12 hand-read `SPELL_STAT_CURATIONS` promote with page witnesses + semantic whys; per-class divergence ships as `level_by_class`/`stats_by_class` (Protection from Prime W2/P1), never averaged. 8 HELLBOUND origin tags → `first-printed-in` edges; printed-p130's name-shredded L7 priest spell QUARANTINED with everything knowable (never guessed). **Psionic correction:** PWH has no psionics section — re-parked with the wrong-book note, waits for a psionics-bearing source. Sibling offers M9-M13/D10-D12 + the queued equipment item round live in `build/family/rule-effect-handoff.md` §PWH. |
| 2026-06-06 | **PWH EQUIPMENT ROUND EXECUTED — item 106→143: 38 cards poured (12 tools-of-the-trade + 26 magical/protections), 38/38 attested** (`pwh.ITEM_CARDS` + the item lane in `pour_pwh`; 928 entities · 2,028 edges) | The marquee dim's first GENERIC stock (no wielder, no `wields`): green steel (armor+weapons tables, cell-level verified-or-absent — illegible weights stay absent), bariaur gear ×5, modron gear ×3, etheroscope, sickle/scythe, 26 magical items incl. the scythe/sickle family, planar wards/mancatcher/trap, shifters' manacles, planar protections. **Dual-source merge proved:** `item:planar-wards` — The Grixitt's Uncaged gear gained its PWH rulebook card (one node, both books, `wields` + `attested_in`). Faction bindings as `used_by` edges (mancatcher→harmonium, manacles→mercykillers; rel registered in the integrity catalog). The 4 item-embedded d100 tables stay TABLE substance → handoff D13 (Modron mints, Mimir points `used_at` after). Printed-136's what-to-look-for survey = existing core/ToM items, cross-refs only, never minted. 7 shredded heads recovered by page's-own-form aliases (8ARIAUR, BomED BREATII, CLOTIIJNG…). Inner-Planar Amulet is a DISCLOSED descriptive handle (the book names the class, not a proper item). |
