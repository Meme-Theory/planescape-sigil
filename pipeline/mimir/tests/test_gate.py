"""V&V — the gate is a real judge (gate.py).

The gate's whole claim is "verified or absent": the Handbook contains only what passed.
A judge that admits everything is worthless, so these probes DOCTOR one field at a time and
assert the gate QUARANTINEs to the correct reason bucket — and, just as important, that a
LAWFUL block sails through (no crying wolf). This is the corruption-probe discipline the
siblings use (Modron's doctored statblocks, Mechanus's test_lawful).

Buckets: schema-fail (L1) · invariant-fail (L2) · conflict (L3) · low-confidence (θ).
"""
import pytest
import store as S
import gate as G


@pytest.fixture
def store(tmp_path):
    st = S.HandbookStore(tmp_path / "t.db")
    yield st
    st.close()


def mk_monster(**over):
    """A lawful 2e monster envelope (13/13 statblock fields, all values in range). Override a
    nested dict with sb=/d=, or a top-level key (name=, confidence=, see_also=)."""
    sb = {"ac": "5", "mv": "12", "hp": "40", "thac0": "13", "num_attacks": "1", "damage": "1d8",
          "special_attacks": "gaze", "special_defenses": "+1 or better weapon",
          "magic_resistance": "20%", "size": "M", "morale": "14", "intelligence": "high", "xp": "2000"}
    d = {"race": "arcanaloth", "alignment": "NE", "level_hd": "8"}
    v2 = {"name": "Testbeast", "statblock": sb, "descriptor": d, "sections": {}, "body": "prose",
          "pages": [10], "confidence": 0.9, "provenance": {"source_sha256": "abc"}, "see_also": []}
    if "sb" in over:
        sb.update(over.pop("sb"))
    if "d" in over:
        d.update(over.pop("d"))
    v2.update(over)
    return v2


def run(v2, store, cur=None):
    return G.gate(v2, store, "", cur or {})       # (decision, reason, env, docket)


# ---- the lawful case must ADMIT (no crying wolf) ----------------------------
def test_lawful_monster_admits_with_edges_and_docket(store):
    v2 = mk_monster(see_also=[{"name": "Shemeshka the Marauder", "page": 11}],
                    d={"faction": "Fated"})
    dec, reason, env, dk = run(v2, store)
    assert dec == "ADMIT", reason
    assert store.exists(env["id"])
    rels = {x["rel"] for x in store.neighbors(env["id"])}
    assert "member_of" in rels and "references" in rels      # edge synthesis fired
    assert dk["decision"] == "ADMIT" and dk["adjudicator"] == "auto"


# ---- L1 schema --------------------------------------------------------------
def test_l1_monster_below_floor_quarantines(store):
    v2 = mk_monster()
    v2["statblock"] = {"ac": "5", "mv": "12", "hp": "40", "thac0": "13", "damage": "1d8"}  # 5/13
    dec, reason, *_ = run(v2, store)
    assert (dec, reason) == ("QUARANTINE", "schema-fail")


def test_l1_humanoid_floor_is_lower(store):
    """A class-based humanoid legitimately lacks SA/SD/MR — floor is 7, not 10."""
    v2 = mk_monster(d={"char_class": "F8", "race": "human", "alignment": "NG"})
    v2["statblock"] = {"ac": "3", "mv": "12", "hp": "45", "thac0": "13",
                       "num_attacks": "2", "damage": "1d8", "morale": "14"}            # 7/13
    dec, reason, *_ = run(v2, store)
    assert dec == "ADMIT", reason


def test_l1_name_fragment_quarantines(store):
    dec, reason, *_ = run(mk_monster(name="AC 5; MV 12"), store)
    assert (dec, reason) == ("QUARANTINE", "schema-fail")


# ---- L2 invariants ----------------------------------------------------------
def test_l2_missing_confidence_quarantines(store):
    dec, reason, *_ = run(mk_monster(confidence=None), store)
    assert (dec, reason) == ("QUARANTINE", "invariant-fail")


def test_l2_provenance_check_fires_on_empty(store):
    """npc_envelope always synthesizes provenance, so we hit the check directly to prove it
    is a real hard gate (the guarantee is upstream, the check is the backstop)."""
    checks = list(G.l2_invariants({"provenance": {}, "confidence": 0.9}))
    prov = next(c for c in checks if c["name"] == "provenance_present")
    assert prov["sev"] == "hard" and prov["result"] == "fail"


# ---- L3 independent (derivable 2e math) -------------------------------------
def test_l3_ac_out_of_range_conflict(store):
    dec, reason, *_ = run(mk_monster(sb={"ac": "99"}), store)
    assert (dec, reason) == ("QUARANTINE", "conflict")


def test_l3_thac0_out_of_range_conflict(store):
    dec, reason, *_ = run(mk_monster(sb={"thac0": "50"}), store)
    assert (dec, reason) == ("QUARANTINE", "conflict")


def test_l3_hp_outside_hd_range_conflict(store):
    # HD 2 monster → hp ∈ [2,16]; 500 is impossible
    dec, reason, *_ = run(mk_monster(sb={"hp": "500"}, d={"level_hd": "2"}), store)
    assert (dec, reason) == ("QUARANTINE", "conflict")


def test_l3_hp_check_skipped_for_humanoids(store):
    """Class HP isn't d8-HD-bounded — the check must NOT fire (or it would false-quarantine
    every high-level human). HD 2, hp 60, but char_class set → admits."""
    v2 = mk_monster(sb={"hp": "60"}, d={"char_class": "F10", "level_hd": "2", "race": "human"})
    dec, reason, *_ = run(v2, store)
    assert dec == "ADMIT", reason


def test_l3_damage_not_dice_conflict(store):
    dec, reason, *_ = run(mk_monster(sb={"damage": "by weapon type"}), store)
    assert (dec, reason) == ("QUARANTINE", "conflict")


# ---- θ floor & curation override --------------------------------------------
def test_theta_below_floor_quarantines(store):
    dec, reason, *_ = run(mk_monster(confidence=0.69), store)
    assert (dec, reason) == ("QUARANTINE", "low-confidence")


def test_theta_at_floor_admits(store):
    dec, *_ = run(mk_monster(confidence=0.70), store)
    assert dec == "ADMIT"


def test_curation_overrides_theta(store):
    """A human/vision adjudication is itself a recorded witness — it overrides the auto-θ floor
    (VALIDATION §4 'curated values still pass the gate, but the override is SHA'd')."""
    eid = "npc:uncaged:testbeast"
    cur = {eid: {"set": {"fields.statblock.notes": "seen on the page render"},
                 "adjudication": {"by": "vision", "loc": "uncaged:p10"}}}
    dec, reason, env, dk = run(mk_monster(confidence=0.40), store, cur)
    assert dec == "ADMIT", reason
    assert dk["adjudicator"] == "human-vision"
    assert env["curated"]                                     # the override is recorded on the entity


# ---- id-collision (main()'s seen-set guard) ---------------------------------
def test_id_collision_quarantines_the_second(store):
    """Two entries sluggify to the same id → the second is held as id-collision, NEVER allowed
    to silently clobber the first (the 29→28 silent-loss bug, structurally prevented)."""
    seen, results = set(), []
    for v2 in (mk_monster(), mk_monster(sb={"hp": "41"})):     # same name → same id, different data
        eid = f"npc:uncaged:{S.slug(v2['name'])}"
        if eid in seen:
            env = G.npc_envelope(v2)
            dk = {"entity_id": eid, "decision": "QUARANTINE",
                  "checks": [{"layer": "L2", "name": "unique_id", "sev": "hard", "result": "fail"}]}
            store.quarantine(env, dk, "id-collision")
            results.append("id-collision")
        else:
            dec, _, env, _ = G.gate(v2, store, "", {})
            if dec == "ADMIT":
                seen.add(env["id"])
            results.append(dec)
    assert results == ["ADMIT", "id-collision"]
    held = store.conn.execute("SELECT reason FROM quarantine").fetchone()["reason"]
    assert held == "id-collision"


# ---- the Mechanus seam (L3 lawfulness delegated to the law engine) ----------
def test_l3_delegates_to_mechanus_with_law_version(store):
    """Wired seam: a lawful monster's docket carries Mechanus `law:*` checks and a stamped
    `law_version` — proof L3 ran her judge, not merely the local fallback. (Skips if the
    sibling isn't importable in this environment — the gate is allowed to degrade.)"""
    if G._mech_is_lawful is None:
        import pytest as _p
        _p.skip("mechanus not importable here")
    dec, _, env, dk = run(mk_monster(), store)
    assert dec == "ADMIT"
    assert [c for c in dk["checks"] if c["name"].startswith("law:")], "no law:* checks — seam not wired"
    assert dk["independent"].get("law_version"), "law_version not stamped on the docket"


def test_l3_hp_in_hd_range_comes_from_mechanus(store):
    """The HD math now rides on Mechanus: an impossible monster hp still QUARANTINEs to conflict,
    via her `law:hp_in_hd_range` rather than gate-local code."""
    if G._mech_is_lawful is None:
        import pytest as _p
        _p.skip("mechanus not importable here")
    dec, reason, _, dk = run(mk_monster(sb={"hp": "500"}, d={"level_hd": "2"}), store)
    assert (dec, reason) == ("QUARANTINE", "conflict")
    assert any(c["name"] == "law:hp_in_hd_range" and c["result"] == "fail" for c in dk["checks"])


def test_l3_falls_back_when_mechanus_absent(store, monkeypatch):
    """Graceful degradation: with Mechanus unavailable the gate still runs the local hp-in-HD
    check — impossible hp QUARANTINEs, a lawful block ADMITs. No crash, no hard dependency."""
    monkeypatch.setattr(G, "_mech_is_lawful", None)
    dec, reason, *_ = run(mk_monster(sb={"hp": "500"}, d={"level_hd": "2"}), store)
    assert (dec, reason) == ("QUARANTINE", "conflict")
    assert run(mk_monster(name="Fallbackbeast"), store)[0] == "ADMIT"


# ---- witnessed schema-waiver (Patch the razorvine: a thin-but-complete plant block) ---------
def _thin(**over):
    v2 = mk_monster(**over)
    v2["statblock"] = {"ac": "5", "mv": "0", "hp": "45", "thac0": "20", "damage": "1d3"}   # 5/13
    return v2


def test_witnessed_waiver_admits_thin_block(store):
    """A witnessed waiver downgrades a named hard-fail (a stationary plant's thin statblock) to
    'waived' — admitted, but DISCLOSED in the docket with its page witness, never silently passed."""
    eid = "npc:uncaged:testbeast"
    cur = {eid: {"waivers": [{"check": "statblock_fields", "witness": "uncaged:p78", "reason": "plant"}],
                 "adjudication": {"by": "vision"}}}
    dec, reason, env, dk = run(_thin(), store, cur)
    assert dec == "ADMIT", reason
    assert dk["adjudicator"] == "human-vision"
    waived = [c for c in dk["checks"] if c.get("result") == "waived"]
    assert waived and waived[0]["name"] == "statblock_fields"
    assert waived[0]["waiver"]["witness"] == "uncaged:p78"


def test_waiver_without_witness_is_ignored(store):
    """A waiver with no witness is a blindfold, not a waiver — the hard-fail still QUARANTINEs."""
    eid = "npc:uncaged:testbeast"
    cur = {eid: {"waivers": [{"check": "statblock_fields", "reason": "no witness"}],
                 "adjudication": {"by": "vision"}}}
    dec, reason, *_ = run(_thin(), store, cur)
    assert (dec, reason) == ("QUARANTINE", "schema-fail")


# ---- minor tier (the appendix's further smattering: descriptor-only, no statblock) -----------
def _minor(**over):
    v2 = {"name": "Leyruss Arn", "tier": "minor", "statblock": {},
          "descriptor": {"race": "tiefling", "alignment": "NE"}, "sections": {}, "body": "",
          "pages": [122], "confidence": 0.72, "provenance": {"source_sha256": "x"}, "see_also": []}
    if "d" in over:
        v2["descriptor"] = over.pop("d")
    v2.update(over)
    return v2


def test_minor_tier_admits_on_complete_descriptor(store):
    """No statblock, but a complete descriptor (race+alignment) + clean name → ADMIT at the
    extractor's lower confidence. Turns a named-but-mentioned cutter into a real node."""
    dec, reason, env, dk = run(_minor(), store)
    assert dec == "ADMIT", reason
    assert env["fields"]["tier"] == "minor"
    assert any(c["name"] == "minor_descriptor" and c["result"] == "pass" for c in dk["checks"])
    assert not any(c["name"] == "statblock_fields" for c in dk["checks"])   # full-tier check skipped


def test_minor_tier_incomplete_descriptor_quarantines(store):
    """A minor whose descriptor didn't fully parse (no alignment) is too uncertain — schema-fail."""
    dec, reason, *_ = run(_minor(d={"race": "tiefling"}, confidence=0.6), store)
    assert (dec, reason) == ("QUARANTINE", "schema-fail")


# ---- subject dimension (cross-book plot pivots) + plothook tagger -----------------------------
def _seed(store, eid, typ, name, fields=None):
    """Admit a bare entity through the gate's write path (test fixture helper)."""
    env = {"type": typ, "id": eid, "name": name, "edition": "2e", "fields": fields or {},
           "content": name, "provenance": {"value_sources": [{"src": "test"}], "method": "seed"},
           "confidence": 1.0, "curated": {}, "source_sha": None}
    store.admit(env, {"decision": "ADMIT", "adjudicator": "test", "checks": [],
                      "independent": {"channel": "test", "confirmations": 1}, "confidence_final": 1.0})


def test_subject_staging_lane_is_empty_all_folded(store):
    # all three cross-book pivots folded into their home dims; the staging lane is empty but stays open.
    assert G.SUBJECTS == []
    assert G.pour_subjects(store) == 0
    assert any(d["id"] == "deity:aoskar" for d in G.DEITIES)        # Aoskar → deity
    assert G.LADY["id"] == "sigil:the-lady-of-pain"                 # the Lady → sigil
    assert any(e["id"] == "event:the-blood-war" for e in G.EVENTS)  # the Blood War → event


def test_pivot_aliases_are_specific_not_generic():
    """Integrity: the Athar's 'fraudulent god' slur names ANY power, and 'dead god' names many — neither
    may be an Aoskar alias, or oblique matching would mis-bridge. Aoskar's portfolio epithet IS present."""
    aoskar = next(d for d in G.DEITIES if d["id"] == "deity:aoskar")["aliases"]
    al = [a.lower() for a in aoskar]
    assert "fraudulent god" not in al and "dead god" not in al
    assert any("portals" in a for a in al)
    bw = next(e for e in G.EVENTS if e["id"] == "event:the-blood-war")["aliases"]   # blood-war folded to event
    assert all("war" in a.lower() for a in bw)                # war-specific aliases only


def test_pour_deities_folds_aoskar_with_concerns(store):
    # the fold: Aoskar is a `deity` carrying its aliases + the Dead Gods Plot (concerns), NOT a subject.
    _seed(store, "hook:uncaged:dead-gods", "hook", "The Dead Gods Plot", {"grain": "plot"})
    assert G.pour_deities(store) == 1
    d = store.get("deity:aoskar")
    assert d and any("portals" in a for a in d["fields"]["aliases"])
    assert not store.exists("subject:aoskar")                 # folded out of the staging dim
    out = [(e["rel"], e["node"]) for e in store.neighbors("hook:uncaged:dead-gods")]
    assert ("concerns", "deity:aoskar") in out


def test_pour_sigil_folds_lady_and_enriches_hub(store):
    # the Lady absorbs subject:the-lady-of-pain → a `sigil` being; location:sigil is ruled_by her.
    _seed(store, "location:sigil", "location", "Sigil")
    _seed(store, "location:sigil:lady-s-ward", "location", "Lady's Ward")
    _seed(store, "faction:athar", "faction", "Athar")
    lady, wards, seats = G.pour_sigil(store)
    assert store.exists("sigil:the-lady-of-pain") and not store.exists("subject:the-lady-of-pain")
    out = {(e["rel"], e["node"]) for e in store.neighbors("location:sigil")}
    assert ("ruled_by", "sigil:the-lady-of-pain") in out
    assert ("has_ward", "location:sigil:lady-s-ward") in out and wards == 1
    assert ("seats", "faction:athar") in out and seats == 1


def test_pour_plothooks_bridges_owner_to_deity_pivot(store, monkeypatch):
    """End-to-end (synthetic scope): a tagged seed → grain='seed' hook involving owner+pivot, mints the
    owner→pivot edge, and nests part_of the curated plot — now anchoring the FOLDED deity:aoskar."""
    _seed(store, "npc:uncaged:wooly-cupgrass", "npc", "Wooly Cupgrass")
    _seed(store, "hook:uncaged:dead-gods", "hook", "The Dead Gods Plot", {"grain": "plot"})
    G.pour_deities(store)                                     # admits deity:aoskar (+ concerns edge)
    body = "Cupgrass's next goal is to find the blood of the god of portals, a rumored gate key."
    monkeypatch.setattr(G, "_uncaged_scopes", lambda st: [
        {"text": body, "owner": "npc:uncaged:wooly-cupgrass", "owner_type": "npc",
         "page": 23, "book": "uncaged", "subject_known": 1.0}])
    monkeypatch.setattr(G, "_manifesto_scopes", lambda st, idx: [])
    adm, queued, npart, ncross = G.pour_plothooks(store)
    assert adm >= 1
    seeks = [e["node"] for e in store.neighbors("npc:uncaged:wooly-cupgrass", rel="seeks")]
    assert "deity:aoskar" in seeks                            # the pivot edge re-formed on the deity
    seedhooks = [h for h in store.list("hook", limit=99) if h["fields"].get("grain") == "seed"]
    out = {(e["rel"], e["node"]) for e in store.neighbors(seedhooks[0]["id"])}
    assert ("involves", "deity:aoskar") in out
    assert ("part_of", "hook:uncaged:dead-gods") in out      # seed nests under the curated plot


def test_manifesto_restricted_to_pivot_anchors(store, monkeypatch):
    """A field-structured book's faction geography is already poured — so a Manifesto scope must yield
    ONLY pivot-anchored seeds (its HQ/ally co-occurrences are dropped as structured data)."""
    _seed(store, "faction:doomguard", "faction", "Doomguard")
    _seed(store, "location:sigil:armory", "location", "The Armory")       # the Doomguard's HQ
    _seed(store, "hook:uncaged:blood-war", "hook", "The Blood War Plot", {"grain": "plot"})
    G.pour_events(store)                                      # event:the-blood-war (the folded pivot)
    # one sentence names both the HQ (structured) and the Blood War (a pivot MacGuffin, now an event)
    text = "The Doomguard secretly wants to intensify the Blood War from the Armory."
    monkeypatch.setattr(G, "_uncaged_scopes", lambda st: [])
    monkeypatch.setattr(G, "_manifesto_scopes", lambda st, idx: [
        {"text": text, "owner": "faction:doomguard", "owner_type": "faction",
         "page": 70, "book": "manifesto", "subject_known": 0.8}])
    G.pour_plothooks(store)
    seeds = [h for h in store.list("hook", limit=99) if h["fields"].get("grain") == "seed"]
    objs = {h["fields"]["object"] for h in seeds}
    assert "event:the-blood-war" in objs                      # the MacGuffin survives (now an event)
    assert "location:sigil:armory" not in objs                # the HQ (structured data) is dropped


def test_pour_events_folds_blood_war_and_ties_upheaval(store):
    """The LAST fold: the Blood War is an `event` (subject gone, concerns re-pointed); the Great Upheaval
    is the cross-dimension capstone — deity + sigil participated_in it, and it occurred_at the temple."""
    _seed(store, "hook:uncaged:blood-war", "hook", "The Blood War Plot", {"grain": "plot"})
    _seed(store, "deity:aoskar", "deity", "Aoskar")
    _seed(store, "sigil:the-lady-of-pain", "sigil", "The Lady of Pain")
    _seed(store, "location:sigil:the-shattered-temple", "location", "The Shattered Temple")
    assert G.pour_events(store) == 2
    assert not store.exists("subject:the-blood-war")          # folded out of the staging dim
    bw_in = {(e["rel"], e["node"]) for e in store.neighbors("event:the-blood-war", direction="in")}
    assert ("concerns", "hook:uncaged:blood-war") in bw_in    # the curated plot re-pointed to the event
    up_in = {(e["rel"], e["node"]) for e in store.neighbors("event:the-great-upheaval", direction="in")}
    assert ("participated_in", "sigil:the-lady-of-pain") in up_in
    assert ("participated_in", "deity:aoskar") in up_in       # the capstone ties deity + sigil
    up_out = {(e["rel"], e["node"]) for e in store.neighbors("event:the-great-upheaval")}
    assert ("occurred_at", "location:sigil:the-shattered-temple") in up_out


# ---- dialog dimension (the NPC voice vector) -------------------------------------------------
def test_pour_dialog_binds_spoken_by_with_register(store):
    """A speaker's lines become `dialog` nodes bound via `spoken_by`, register read from the verb."""
    _seed(store, "npc:uncaged:a-kin", "npc", "A'kin")
    node = {"name": "A'kin", "pages": [12], "sections": {},
            "body": 'A\'kin beams, "Come in, come in! I won\'t bite." Later he says, "It is yours, friend."'}
    adm, queued = G.pour_dialog(store, nodes=[node])
    assert adm >= 1
    dlg = store.list("dialog", limit=99)
    assert dlg and all(d["fields"]["owner"] == "npc:uncaged:a-kin" for d in dlg)
    out = {(e["rel"], e["node"]) for e in store.neighbors(dlg[0]["id"])}
    assert ("spoken_by", "npc:uncaged:a-kin") in out          # the line binds to its speaker
    assert any(d["fields"]["register"] == "amused" for d in dlg)   # 'beams' → render-ready register
    # ids are content-addressed (owner+text) → STABLE across re-pours (the Dabus render join-key)
    import hashlib
    for d in dlg:
        h = hashlib.sha256(f"{d['fields']['owner']}|{d['fields']['text']}".encode()).hexdigest()[:12]
        assert d["id"] == f"dialog:uncaged:{h}"


# ---- the universal curation rail (_admit_seed hook — Great Audit Phase 0) -------------------
def test_admit_seed_applies_curation_to_seeded_dim(store, monkeypatch):
    """A curations.json entry keyed by a SEEDED id (non-npc dim) applies at pour time:
    dot-path sets land, the curated stamp carries the adjudication, the docket says
    human-vision. This is the lane-3 rail generalized beyond the npc gate path."""
    monkeypatch.setattr(G, "_CURATIONS", {
        "faction:fated": {"set": {"fields.home_plane": "Ysgard (curated)"},
                          "adjudication": "test ruling 2026-06-06"}})
    v2 = mk_monster(d={"faction": "Fated"})
    G.pour_factions(store, [v2])
    n = store.get("faction:fated")
    assert n["fields"]["home_plane"] == "Ysgard (curated)"          # dot-path set landed
    assert n["curated"]["fields.home_plane"]["adjudication"] == "test ruling 2026-06-06"
    dk = store.conn.execute("SELECT docket FROM dockets WHERE entity_id='faction:fated'").fetchone()
    import json as _j
    assert _j.loads(dk["docket"])["adjudicator"] == "human-vision"  # disclosed, never silent


def test_admit_seed_without_curation_unchanged(store, monkeypatch):
    """Control: no curation for the id → auto docket, empty curated (no false stamps)."""
    monkeypatch.setattr(G, "_CURATIONS", {"faction:somebody-else": {"set": {"fields.x": 1}}})
    v2 = mk_monster(d={"faction": "Fated"})
    G.pour_factions(store, [v2])
    n = store.get("faction:fated")
    assert not n["curated"]
    assert "x" not in n["fields"]
