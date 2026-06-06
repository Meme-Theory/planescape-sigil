"""Smoke test: drive the Mechanus MCP server over real stdio, end to end.

Not a pytest module (the suite stays fast/offline) — run directly:
    python tests/smoke_server.py
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PKG_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


async def main() -> int:
    tmp = tempfile.mkdtemp(prefix="mechanus-smoke-")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mechanus.server"],
        cwd=str(PKG_ROOT),
        env={**os.environ, "MECHANUS_RULINGS_DB": str(Path(tmp) / "rulings.db"),
             "PYTHONPATH": str(PKG_ROOT)},
    )
    failures = []

    def check(label: str, cond: bool, detail=""):
        print(("  PASS  " if cond else "  FAIL  ") + label + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(label)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            check("20 tools listed", len(names) == 20, f"got {len(names)}: {sorted(names)}")

            async def call(tool, **args):
                r = await session.call_tool(tool, args)
                return json.loads(r.content[0].text)

            d = await call("dc_suggest", difficulty="medium", view="5e-2024")
            check("dc_suggest medium=15, cited", d.get("dc") == 15 and "p.6" in d.get("source", ""), d)

            b = await call("encounter_budget", party_levels=[1, 1, 1, 1], difficulty="low")
            check("budget example 1 = 200", b.get("budget") == 200, b)

            b14 = await call("encounter_budget", party_levels=[5], difficulty="low", view="5e-2014")
            check("2014 budget refuses with reason", b14.get("kind") == "LawUnavailable"
                  and "SRD 5.1" in b14.get("error", ""), b14)

            vrock = json.loads((FIXTURES / "monsters_2014.json").read_text(encoding="utf-8"))["monsters"]["vrock"]
            v = await call("is_lawful", entity=vrock)
            check("vrock lawful over stdio", v.get("lawful") is True, v.get("summary"))

            lich = json.loads((FIXTURES / "monsters_2014.json").read_text(encoding="utf-8"))["monsters"]["lich"]
            v = await call("is_lawful", entity=lich)
            check("lich waived via known_waivers", v.get("lawful") is True
                  and v["summary"]["waived"] == ["skill_bonuses_math"], v.get("summary"))

            v = await call("is_lawful", entity=lich, apply_known_waivers=False)
            check("lich fails without waivers", v.get("lawful") is False, v.get("summary"))

            att = await call("attribution")
            check("attribution carries both blocks",
                  "5e-2014" in att.get("attribution", {}) and "5e-2024" in att.get("attribution", {}))

            parked = await call("view", name="vrock")
            check("parked tool returns NOT_POURED", "NOT_POURED" in parked.get("error", ""), parked)

            pl = await call("planar_law")
            check("planar_law index lists 7 families",
                  len(pl.get("families", {})) == 7 and len(pl.get("law_version", "")) == 16, pl)

            pl = await call("planar_law", law_id="law:plane-environment:the-gray-waste:wasting-sickness")
            check("planar_law resolves the Wasting with witness",
                  "10%" in pl.get("row", {}).get("rule", "")
                  and pl["row"]["witness"][0]["component"] == "planes-of-conflict-2615-02-liber-malevolentiae", pl)

            pl = await call("planar_law", plane="plane:limbo")
            ids = {r["law_id"] for r in pl.get("rows", [])}
            check("planar_law plane lookup finds Limbo's law",
                  {"law:planar-conditions:limbo", "law:planar-keys:limbo",
                   "law:plane-environment:limbo:miniflux"} <= ids, sorted(ids))

            pl = await call("planar_law", plane="plane:the-outlands")
            check("planar_law refuses honestly off-corpus (M7 parked named)",
                  "M7 parked" in pl.get("error", ""), pl)

            docket = {
                "ruling_id": "rul:smoke:test:001", "question": "Does the smoke test pass?",
                "view": "5e-2014", "scope": "table:smoke",
                "ladder_path": ["house:none", "raw:none", "interp"],
                "candidates": [{"position": "yes", "fate": "ADOPTED"},
                               {"position": "no", "fate": "rejected", "why": "it passed"}],
                "confidence": 1.0, "adjudicator": "workflow:smoke",
                "rolls": ["roll:smoke:000001"],
            }
            rec = await call("record_ruling", docket=docket)
            check("ruling recorded with sha+ts", bool(rec.get("sha")) and bool(rec.get("ts")), rec)

            dup = await call("record_ruling", docket={**docket, "ruling_id": "rul:smoke:test:002"})
            check("dup content rejected by sha", dup.get("kind") == "DocketError", dup)

            pre = await call("precedents", topic="smoke")
            check("precedents finds the ruling", len(pre) == 1 and pre[0]["ruling_id"] == "rul:smoke:test:001", pre)

            over = await call("overrule", ruling_id="rul:smoke:test:001",
                              docket={**docket, "ruling_id": "rul:smoke:test:003", "confidence": 0.5})
            check("overrule chains", over.get("supersedes") == "rul:smoke:test:001", over)

            chain = await call("ruling_chain", ruling_id="rul:smoke:test:001")
            check("chain walks both ways",
                  chain.get("chain") == ["rul:smoke:test:001", "rul:smoke:test:003"], chain)

            info = await call("law_info")
            check("law_info cites every table", len(info.get("tables", {})) >= 7
                  and len(info.get("law_version", "")) == 16, info)

            stats = await call("usage_stats")
            check("usage counter counts", stats.get("dc_suggest", 0) >= 1, stats)

    print(f"\n{'SMOKE CLEAN' if not failures else 'SMOKE FAILED'} — {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
