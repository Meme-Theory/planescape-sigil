#!/usr/bin/env python3
"""Mimir MCP Server — query access to the Planescape Handbook (handbook.db).

The read face of Mimir (ARCHITECTURE.md). Every backend, Mechanus, Modron, and DM play call
THIS instead of re-parsing PDFs — "search the Handbook before you generate." It wraps the shared
`handbook_store` library read-only; the curatorial WRITE path (propose / adjudicate) stays behind
the gate (`gate.py`), never here. Modelled on the Ainulindale `knowledge-mcp` server.

Tools:
  search_handbook  — FTS5 ranked search across every dimension (npc/faction/location/source/…)
  get_entity       — full typed node by id or name (fields + provenance + confidence)
  trace_entity     — evidence chain: an entity + its whole edge neighbourhood (the soul tool)
  query_graph      — traverse edges from a node (member_of / located_in / references / part_of …)
  list_entities    — enumerate a dimension
  coverage         — admitted-vs-quarantined census, by dimension
  review_queue     — what the gate is holding, and why
"""
import warnings, os
warnings.filterwarnings("ignore")
os.environ["PYTHONWARNINGS"] = "ignore"

import asyncio, json, sys, logging
from pathlib import Path

import mcp.server.stdio
import mcp.types as types
from mcp.server import Server

SERVER_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SERVER_DIR))
import store as S                                       # the shared schema-as-library

logging.basicConfig(level=logging.INFO, filename=str(SERVER_DIR / "mimir_mcp.log"),
                    filemode="w", format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mimir")
server = Server("mimir")


def _store():
    if not S.DEFAULT_DB.exists():
        raise FileNotFoundError(f"handbook.db not found at {S.DEFAULT_DB} — run gate.py to pour it first.")
    return S.HandbookStore(S.DEFAULT_DB, readonly=True)


def _txt(s):
    return [types.TextContent(type="text", text=s)]


# --------------------------------------------------------------------------- tools
@server.list_tools()
async def handle_list_tools():
    ENT = "Entity type: npc | faction | location | source (more as dimensions pour)."
    return [
        types.Tool(name="search_handbook", description=(
            "FTS5 ranked search across ALL Handbook dimensions. Use this BEFORE generating "
            "anything to see what the Cage already knows."),
            inputSchema={"type": "object", "properties": {
                "query": {"type": "string", "description": "Search terms (FTS5: AND/OR/NOT, \"phrases\")"},
                "type": {"type": "string", "description": "Optional dimension filter. " + ENT},
                "edition": {"type": "string", "description": "Optional edition filter, e.g. '2e'"},
                "limit": {"type": "integer", "default": 20}}, "required": ["query"]}),
        types.Tool(name="get_entity", description=(
            "Full typed node by id ('npc:uncaged:a-kin') or by name ('A\\'kin') — fields, "
            "provenance, confidence, curation."),
            inputSchema={"type": "object", "properties": {
                "id_or_name": {"type": "string"},
                "type": {"type": "string", "description": "Optional dimension hint for name lookup. " + ENT}},
                "required": ["id_or_name"]}),
        types.Tool(name="trace_entity", description=(
            "Evidence chain for a name/concept: the entity plus its whole edge neighbourhood — "
            "who it references, who references it, where it sits, what it's a member of."),
            inputSchema={"type": "object", "properties": {
                "name": {"type": "string"}, "limit": {"type": "integer", "default": 12}},
                "required": ["name"]}),
        types.Tool(name="query_graph", description=(
            "Traverse edges from a node. rel filters the relation (member_of, located_in, "
            "references, part_of, attested_in); direction 'out' (default) or 'in'."),
            inputSchema={"type": "object", "properties": {
                "node": {"type": "string", "description": "Entity id or name"},
                "rel": {"type": "string"}, "direction": {"type": "string", "enum": ["out", "in"], "default": "out"}},
                "required": ["node"]}),
        types.Tool(name="list_entities", description="Enumerate a dimension. " + ENT,
            inputSchema={"type": "object", "properties": {
                "type": {"type": "string"}, "limit": {"type": "integer", "default": 60}}, "required": ["type"]}),
        types.Tool(name="coverage", description="Admitted-vs-quarantined census by dimension; edge count.",
            inputSchema={"type": "object", "properties": {}}),
        types.Tool(name="review_queue", description="What the gate is holding in quarantine, and why.",
            inputSchema={"type": "object", "properties": {"limit": {"type": "integer", "default": 40}}}),
    ]


@server.call_tool()
async def handle_call_tool(name, arguments):
    args = arguments or {}
    handlers = {"search_handbook": _search, "get_entity": _get, "trace_entity": _trace,
                "query_graph": _graph, "list_entities": _list, "coverage": _coverage,
                "review_queue": _review}
    if name not in handlers:
        return _txt(f"Unknown tool: {name}")
    st = None
    try:                                                  # one connection per call, closed in finally —
        st = _store()                                     # a leaked readonly handle keeps the DB file
        return handlers[name](st, args)                   # locked on Windows and blocks the gate's re-pour
    except Exception as e:
        logger.exception("tool %s failed", name)
        return _txt(f"Error: {e}")
    finally:
        if st is not None:
            st.close()


def _resolve(st, ref):
    """An id (has ':') resolves directly; a name resolves via FTS to the best entity id."""
    if ":" in ref and st.get(ref):
        return ref
    hits = st.search(ref, limit=1)
    return hits[0]["entity_id"] if hits else None


def _search(st, args):
    rows = st.search(args["query"], type=args.get("type"), edition=args.get("edition"),
                     limit=args.get("limit", 20))
    if not rows:
        return _txt(f"No results for {args['query']!r}.")
    out, by = [f"## search: {args['query']!r} — {len(rows)} hits"], {}
    for r in rows:
        by.setdefault(r["type"], []).append(r)
    for t, rs in by.items():
        out.append(f"\n### {t} ({len(rs)})")
        for r in rs:
            out.append(f"- **{r['name'] or r['entity_id']}**  `{r['entity_id']}`")
    return _txt("\n".join(out))


def _get(st, args):
    eid = _resolve(st, args["id_or_name"])
    e = st.get(eid) if eid else None
    if not e:
        return _txt(f"No entity matching {args['id_or_name']!r}.")
    e.pop("content", None)
    return _txt(f"## {e['name']}  `{e['id']}`  ({e.get('edition')}, conf {e.get('confidence')})\n```json\n"
                + json.dumps({k: v for k, v in e.items() if k != "id"}, indent=1, ensure_ascii=False) + "\n```")


def _trace(st, args):
    eid = _resolve(st, args["name"])
    if not eid:
        return _txt(f"No trace for {args['name']!r}.")
    e = st.get(eid)
    lim = args.get("limit", 12)
    lines = [f"## evidence chain: {e['name']}  `{eid}`  ({e.get('edition')})"]
    d = e.get("fields", {}).get("descriptor") or {}
    if d:
        lines.append(f"*{d.get('race') or '?'}* · {d.get('faction') or '—'} · {d.get('alignment') or '?'}")
    out = st.neighbors(eid, direction="out")
    inb = st.neighbors(eid, direction="in")
    for label, edges in (("→ outbound", out), ("← inbound", inb)):
        if not edges:
            continue
        lines.append(f"\n**{label}** ({len(edges)})")
        grp = {}
        for x in edges[:200]:
            grp.setdefault(x["rel"], []).append(x["node"].split(":")[-1])
        for rel, nodes in grp.items():
            lines.append(f"- `{rel}`: {', '.join(nodes[:lim])}" + (" …" if len(nodes) > lim else ""))
    return _txt("\n".join(lines))


def _graph(st, args):
    eid = _resolve(st, args["node"])
    if not eid:
        return _txt(f"No node matching {args['node']!r}.")
    ns = st.neighbors(eid, rel=args.get("rel"), direction=args.get("direction", "out"))
    if not ns:
        return _txt(f"No {args.get('direction','out')} edges from `{eid}`"
                    + (f" with rel={args['rel']!r}" if args.get("rel") else "") + ".")
    lines = [f"## {args.get('direction','out')} edges from `{eid}` ({len(ns)})"]
    for x in ns:
        lines.append(f"- `{x['rel']}`{(' ['+x['role']+']') if x.get('role') else ''} → {x['node']}")
    return _txt("\n".join(lines))


def _list(st, args):
    rows = st.list(args["type"], limit=args.get("limit", 60))
    if not rows:
        return _txt(f"No entities of type {args['type']!r}.")
    lines = [f"## {args['type']} — {len(rows)}"]
    for r in rows:
        lines.append(f"- **{r['name']}**  `{r['id']}`  (conf {r.get('confidence')})")
    return _txt("\n".join(lines))


def _coverage(st, args):
    c = st.coverage()
    return _txt("## Handbook coverage\n```json\n" + json.dumps(c, indent=1) + "\n```")


def _review(st, args):
    rows = st.conn.execute("SELECT id, type, name, reason FROM quarantine LIMIT ?",
                           (args.get("limit", 40),)).fetchall()
    if not rows:
        return _txt("Quarantine is empty — nothing held.")
    lines = [f"## review queue — {len(rows)} held"]
    for r in rows:
        lines.append(f"- [{r['reason']}] **{r['name']}** `{r['id']}`")
    return _txt("\n".join(lines))


async def main():
    async with mcp.server.stdio.stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
