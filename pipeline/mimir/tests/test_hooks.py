"""V&V — the mechanical plot-hook tagger (pipeline/parse/hooks.py).

A hook is TRIGGER x ANCHOR x PROXIMITY. These probes pin each signal AND each failure mode the
Uncaged+Manifesto assay surfaced: the list-density fan-out, alias double-counting, struct-field
re-tagging, polysemy misfires, and setting-scale over-matching. A tagger that fires on everything
is as worthless as a gate that admits everything.
"""
import hooks as H


def idx():
    return H.build_index([
        ("subject:aoskar", "subject", "Aoskar", ["god of portals", "dead god of portals"]),
        ("faction:society-of-sensation", "faction", "Society of Sensation", ["Sensates"]),
        ("faction:harmonium", "faction", "Harmonium", ["Hardheads"]),
        ("faction:dustmen", "faction", "Dustmen", []),
        ("location:sigil", "location", "Sigil", []),
    ])


# ---- TRIGGER x ANCHOR x PROXIMITY: the positive case --------------------------------------
def test_prose_goal_hook_with_exact_subject():
    body = ("Wooly Cupgrass tinkers in his lab. The bariaur's next goal is to find the blood of "
            "the dead god Aoskar, a rumored gate key.")
    seeds = H.tag_text(body, idx(), owner_id="npc:cupgrass", owner_type="npc", page=23, book="uncaged")
    aoskar = [s for s in seeds if s["object_id"] == "subject:aoskar"]
    assert len(aoskar) == 1 and aoskar[0]["flavor"] == "goal"      # exactly one (alias dupes collapse)
    assert aoskar[0]["owner"] == "npc:cupgrass"


def test_oblique_alias_resolves_subject():
    # the NAME 'Aoskar' never appears — only the portfolio epithet, an alias. This is the whole
    # reason subjects are nodes: oblique cross-book references resolve.
    rite = "The Signers secretly plot to restore the god of portals. Sigil would tremble."
    seeds = H.tag_text(rite, idx(), owner_id="faction:sign-of-one", book="manifesto", subject_known=0.7)
    assert any(s["object_id"] == "subject:aoskar" for s in seeds)


def test_flavor_priority_scheme_beats_goal():
    s = H.tag_text("The Harmonium secretly plot and want to expand against the Dustmen.", idx(),
                   owner_id="x")[0]
    assert s["flavor"] == "scheme"                                 # most-specific flavor wins


# ---- failure modes the assay caught -------------------------------------------------------
def test_list_density_drops_the_whole_sentence():
    # one trigger near >MAX_ANCHORS distinct ids is a relationship-LIST (already structured as
    # PLOT_EDGES), not a hook — the "Zadara schemes around [a dozen names]" fan-out.
    crowd = ("Zadara secretly schemes with the Sensates, the Harmonium, the Dustmen, and the "
             "god of portals all at once.")
    assert H.tag_text(crowd, idx(), owner_id="npc:zadara") == []


def test_struct_field_line_routed_out():
    # 'Enemies: ...' is a Manifesto card field, already poured as opposed_to edges.
    assert H.tag_text("Enemies: Harmonium, Dustmen", idx(), owner_id="faction:athar") == []


def test_self_anchor_skipped():
    assert H.tag_text("The Dustmen want to grow the Dustmen.", idx(), owner_id="faction:dustmen") == []


def test_ambiguous_trigger_is_penalized():
    # 'rewarding life' must not score as a real quest hook (reward-the-adjective, not reward-the-bounty)
    seeds = H.tag_text("She had a rewarding life among the Sensates.", idx(), owner_id="x")
    assert all(s["flavor"] != "quest" for s in seeds)


def test_setting_scale_anchor_is_low_confidence():
    # 'Sigil' matches nearly everything -> heavy specificity penalty keeps it below a real hook.
    big = H.tag_text("The cutter wants to rule Sigil.", idx(), owner_id="x")
    specific = H.tag_text("The cutter wants to rule the Harmonium.", idx(), owner_id="x")
    assert big and specific
    assert big[0]["confidence"] < specific[0]["confidence"]


# ---- the scoring contract -----------------------------------------------------------------
def test_score_orders_by_specificity_and_proximity():
    hi = H.score("scheme", 1.0, 1.0, 1.0, False)     # specific, in-sentence, known subject
    lo = H.score("goal", 0.4, 0.8, 0.7, True)        # setting-scale, ±1, inferred, ambiguous
    assert hi > lo and lo < H.score("goal", 1.0, 1.0, 1.0, False)
