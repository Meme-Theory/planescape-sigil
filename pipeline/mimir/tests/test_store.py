"""V&V — the store contract (store.py).

The store is the shared schema-library: Mimir writes through it, the siblings read it.
These probes pin the LAW the store claims to enforce — gate-only writes, edge dedup,
content-address idempotence, curation preservation, FTS resync — independently of any
particular pour. tmp_path gives every test a fresh DB; nothing here touches the live one.
"""
import pytest
import store as S

DK = {"checks": [], "independent": {}}            # a minimal docket (gate builds the real one)


@pytest.fixture
def store(tmp_path):
    st = S.HandbookStore(tmp_path / "t.db")
    yield st
    st.close()


def ent(eid="npc:t", curated=None, content="c", name="T", typ="npc"):
    return {"type": typ, "id": eid, "name": name, "content": content, "curated": curated or {}}


# ---- gate-only write law ----------------------------------------------------
def test_admit_requires_type_and_id(store):
    with pytest.raises(ValueError):
        store.admit({"id": "x"}, DK)              # no type
    with pytest.raises(ValueError):
        store.admit({"type": "npc"}, DK)          # no id


def test_readonly_guard_blocks_every_write(tmp_path):
    p = tmp_path / "t.db"
    S.HandbookStore(p).close()                    # create the file first
    ro = S.HandbookStore(p, readonly=True)
    with pytest.raises(PermissionError):
        ro.admit(ent(), DK)
    with pytest.raises(PermissionError):
        ro.quarantine(ent("npc:bad"), DK, "schema-fail")
    with pytest.raises(PermissionError):
        ro.add_edge("references", "a", "b")
    ro.close()


# ---- edge dedup (D1 regression) ---------------------------------------------
def test_edge_dedup_null_role(store):
    """The majority case: role=NULL. SQL treats every NULL as DISTINCT, so a bare
    UNIQUE(...role) constraint silently fails to dedup. add_edge must still collapse
    identical NULL-role edges (the see_also-listed-twice / re-synthesis case)."""
    store.add_edge("references", "npc:a", "npc:b")
    store.add_edge("references", "npc:a", "npc:b")
    n = store.conn.execute(
        "SELECT COUNT(*) FROM edges WHERE rel='references' AND src_id='npc:a' AND tgt_id='npc:b'"
    ).fetchone()[0]
    assert n == 1, f"NULL-role edge duplicated ({n} rows) — dedup contract broken"


def test_edge_role_is_significant(store):
    """Different roles on the same (rel,src,tgt) are genuinely distinct edges (PRIMARY vs
    DERIVED taxonomy membership) — dedup must NOT collapse those."""
    store.add_edge("member_of", "npc:a", "faction:f", role="PRIMARY")
    store.add_edge("member_of", "npc:a", "faction:f", role="PRIMARY")   # dup → collapse
    store.add_edge("member_of", "npc:a", "faction:f", role="DERIVED")   # distinct → keep
    n = store.conn.execute("SELECT COUNT(*) FROM edges WHERE rel='member_of'").fetchone()[0]
    assert n == 2


# ---- content-address idempotence --------------------------------------------
def test_admission_sha_deterministic_and_content_sensitive():
    e = {"id": "npc:t", "fields": {"a": 1}, "content": "hi"}
    d = {"checks": [{"x": 1}], "independent": {"y": 2}}
    assert S.admission_sha(e, d) == S.admission_sha(e, d)             # re-gate reproduces
    assert S.admission_sha(e, d) != S.admission_sha({**e, "fields": {"a": 2}}, d)  # change invalidates


# ---- curation preservation across rebuild -----------------------------------
def test_curation_carried_forward_unless_overridden(store):
    store.admit(ent(curated={"fields.x": 1}), DK)
    store.admit(ent(curated={}), DK)                                  # re-pour, no override
    assert store.get("npc:t")["curated"] == {"fields.x": 1}, "prior curation lost on rebuild"
    store.admit(ent(curated={"fields.x": 2}), DK)                     # explicit override
    assert store.get("npc:t")["curated"]["fields.x"] == 2


# ---- FTS stays in sync ------------------------------------------------------
def test_fts_resync_on_readmit(store):
    store.admit(ent(content="arcanaloth fiend of the lower planes"), DK)
    assert any(r["entity_id"] == "npc:t" for r in store.search("arcanaloth"))
    store.admit(ent(content="celestial deva of the upper planes"), DK)
    assert not store.search("arcanaloth"), "stale FTS row survived re-admit"
    assert any(r["entity_id"] == "npc:t" for r in store.search("deva"))


# ---- quarantine is a separate store -----------------------------------------
def test_quarantine_never_enters_entities(store):
    store.quarantine(ent("npc:bad", name="Bad"), DK, "schema-fail")
    assert not store.exists("npc:bad")
    cov = store.coverage()
    assert cov["quarantined_total"] == 1 and cov["admitted_total"] == 0


# ---- require_resolve refuses dangling edges ---------------------------------
def test_require_resolve_refuses_unadmitted_endpoint(store):
    store.admit(ent("npc:real"), DK)
    assert store.add_edge("references", "npc:real", "npc:ghost", require_resolve=True) is False
    assert store.add_edge("references", "npc:real", "npc:real", require_resolve=True) is True
