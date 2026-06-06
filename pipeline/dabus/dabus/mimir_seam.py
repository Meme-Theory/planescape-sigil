"""The Mimir seam — dialog nodes read the sibling way.

store.py is the shared schema-library: loaded via importlib (module name
'mimir_store' to dodge our own store.py), opened READONLY, and — per Mimir
V&V D3 / the Windows lock gotcha — opened and CLOSED per call so dabus never
holds handbook.db hostage during a re-pour. No MCP-over-MCP, ever.

Contract (Mimir design session, 2026-06-05 — accepted in DABUS.md §9):
dialog node = {id (content-addressed, stable across re-pours → the WAV
join-key), fields.text (gen_text), fields.register (the mood axis dabus
already speaks), fields.owner (speaker entity), fields.page (witness)}.
dabus owns (speaker → voice) and (voice, register) → ref-clip mapping.
"""

import importlib.util
from pathlib import Path

from . import REPO

_MIMIR_STORE_PATH = REPO / "pipeline" / "mimir" / "store.py"


class SeamError(ValueError):
    """Refusal-grade: missing node, wrong type, absent handbook."""


_mod = None


def _store_module():
    global _mod
    if _mod is None:
        if not _MIMIR_STORE_PATH.exists():
            raise SeamError(f"Mimir store lib not found at {_MIMIR_STORE_PATH}")
        spec = importlib.util.spec_from_file_location("mimir_store", _MIMIR_STORE_PATH)
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
    return _mod


def _open():
    mod = _store_module()
    db = Path(mod.DEFAULT_DB)
    if not db.exists():
        raise SeamError(f"handbook.db not poured yet at {db}")
    return mod.HandbookStore(db, readonly=True)


def _normalize(env: dict) -> dict:
    """Envelope -> the dabus-facing dialog dict. Pure; unit-tested."""
    if not env:
        raise SeamError("no such entity in the handbook")
    if env.get("type") != "dialog":
        raise SeamError(f"{env.get('id')} is type {env.get('type')!r}, not dialog")
    f = env.get("fields") or {}
    if not f.get("text"):
        raise SeamError(f"{env.get('id')} has no fields.text — nothing to speak")
    if not f.get("owner"):
        raise SeamError(f"{env.get('id')} has no fields.owner — no speaker to cast")
    return {
        "dialog_id": env["id"],
        "text": f["text"],
        "register": f.get("register") or "main",
        "register_defaulted": "register" not in f,
        "verb": f.get("verb"),
        "owner": f["owner"],
        "page": f.get("page"),
        "attribution": f.get("attribution"),
        "source_sha": env.get("source_sha"),
        "confidence": env.get("confidence"),
    }


def dialog_node(dialog_id: str) -> dict:
    st = _open()
    try:
        return _normalize(st.get(dialog_id))
    finally:
        st.conn.close()


def npc_dialog(npc_id: str) -> list[dict]:
    """Every dialog node spoken_by an NPC, page-ordered (stable batches)."""
    st = _open()
    try:
        npc = st.get(npc_id)
        if not npc:
            raise SeamError(f"no such entity {npc_id!r} in the handbook")
        ids = [e["node"] for e in st.neighbors(npc_id, rel="spoken_by",
                                               direction="in")]
        nodes = [_normalize(st.get(i)) for i in ids]
        nodes.sort(key=lambda n: (n["page"] if n["page"] is not None else 10**6,
                                  n["dialog_id"]))
        return nodes
    finally:
        st.conn.close()
