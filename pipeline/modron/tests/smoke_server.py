"""Smoke test: drive the Modron MCP server over real stdio, end to end.

Spawns the EXACT configured process from .mcp.json (the py.exe launcher law —
CLAUDE.md MCP registration; bare `python` is the WindowsApps stub trap), with
ONE disclosed override: MODRON_LEDGER points at a temp db so smoke dice never
land in the real rolls.db. The overlay write-door is probed for REFUSAL only —
no real file mutates.

Not a pytest module (the suite stays fast/offline) — run from pipeline/modron:
    py -3.13 tests/smoke_server.py

Minted per correction-docket lane L4 item 11 (audit 2026-06-06): Modron was the
only sibling without a stdio smoke.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PKG_ROOT = Path(__file__).resolve().parent.parent          # pipeline/modron
REPO_ROOT = PKG_ROOT.parent.parent                          # C:/sandbox/Planescape
HANDBOOK = REPO_ROOT / "build" / "mimir" / "handbook.db"

BURAQ_FLAT = {
    "type": "creature", "name": "Buraq", "edition": "2e",
    "thac0": "13", "hit_dice": "7+7", "damage_attack": "1d4/1d4",
    "no_of_attacks": "2", "magic_resistance": "30%", "morale": "elite (14)",
    "armor_class": "2",
}


async def main() -> int:
    cfg = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    spawn = cfg["mcpServers"]["modron"]
    tmp = tempfile.mkdtemp(prefix="modron-smoke-")
    params = StdioServerParameters(
        command=spawn["command"],                  # the EXACT configured spawn
        args=spawn["args"],
        cwd=spawn.get("cwd", str(REPO_ROOT)),
        env={**os.environ, **spawn.get("env", {}),
             "MODRON_LEDGER": str(Path(tmp) / "rolls.db")},
    )
    failures = []

    def check(label: str, cond: bool, detail=""):
        print(("  PASS  " if cond else "  FAIL  ") + label
              + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(label)

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            check("17 tools listed", len(names) == 17, f"got {len(names)}: {sorted(names)}")

            async def call(tool, **args):
                r = await session.call_tool(tool, args)
                text = r.content[0].text
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"_text": text}      # refusal doors speak plain text

            # 2. parse round-trip, no dice fall
            p = await call("parse_expr", expr="4d6kh3+2")
            check("parse_expr normal form", p.get("normal_form") == "4d6kh3+2", p)

            # 3. dice_stats exact
            st = await call("dice_stats", expr="2d6")
            check("dice_stats 2d6 exact mean 7", st.get("method") == "exact"
                  and abs(st.get("mean", 0) - 7.0) < 1e-9, st)

            # 4. ephemeral roll (temp ledger)
            r = await call("roll", expr="2d6+3", view="2e")
            check("roll 2d6+3 ledgered", 5 <= r.get("total", 0) <= 15
                  and r.get("roll_id", "").startswith("rol:eph:"), r)

            # 5. 2e THAC0 check with derived hits_ac
            rc = await call("roll_check", kind="attack", view="2e",
                            params={"thac0": 13, "ac": 4})
            check("2e THAC0 attack derives hits_ac",
                  rc.get("outcome", {}).get("target") == 9
                  and "hits_ac" in rc.get("outcome", {}), rc)

            # 6. the audit's reaction matrix live (bands_by + disclosed default)
            rx = await call("roll_check", kind="reaction", view="2e",
                            params={"cha_mod": 0, "disposition": "hostile"})
            check("reaction disposition column live",
                  rx.get("outcome", {}).get("disposition") == "hostile"
                  and rx.get("outcome", {}).get("band") in
                  ("flight", "cautious", "threatening", "hostile"), rx)

            # 7. registry table roll (slags vortex)
            t = await call("roll_table", table="tbl:2e:sigil:slags-vortex-type")
            t_rolls = t.get("rolls") or [{}]
            check("slags vortex table rolls",
                  1 <= t_rolls[0].get("rolled", 0) <= 4
                  and t_rolls[0].get("result") is not None
                  and t.get("coverage", {}).get("verdict") == "ok", t)

            # 8. the L4 creature adapter live through the server door
            comp = await call("rollables", entity=BURAQ_FLAT, view="2e",
                              sweep_prose=False)
            keys = {s.get("key") for s in comp.get("specs", [])}
            check("MC flat creature compiles (audit fix live)",
                  {"attack", "hp", "morale", "magic_resistance"} <= keys, sorted(keys))

            # 9. handbook entity door (when poured)
            if HANDBOOK.exists():
                ak = await call("rollables", entity="npc:uncaged:a-kin", view="2e")
                check("handbook a-kin compiles >5 specs",
                      len(ak.get("specs", [])) > 5
                      and "handbook.db" in str(ak.get("source", "")), ak.get("source"))
            else:
                print("  SKIP  handbook a-kin (handbook.db not poured)")

            # 10-12. session ceremony: commit → roll → seal → reveal → verify
            ses = await call("session_open", label="smoke-night", view="2e",
                             seed_phrase="modron smoke")
            sid = ses.get("session_id", "")
            check("session commits before dice", bool(ses.get("seed_commitment"))
                  and "seed" not in {k.lower() for k in ses if "secret" in k.lower()}, ses)
            sr = await call("roll", expr="1d20", view="2e", session_id=sid)
            check("session roll draws counter 1",
                  sr.get("roll_id", "").endswith(":00001"), sr)
            closed = await call("session_close", session_id=sid)
            check("close withholds seed", "seed_revealed_hex" not in closed, closed)
            revealed = await call("session_close", session_id=sid, reveal=True)
            check("on-demand reveal publishes seed",
                  bool(revealed.get("seed_revealed_hex")), revealed)
            ver = await call("verify", session_id=sid)
            check("verify(session) PASS sweeps all rolls",
                  ver.get("verdict") == "PASS" and ver.get("rolls_checked") == 1, ver)

            # 13. fiat refusal without reason
            f_bad = await call("force", value=12, view="2e")
            check("force without reason refused",
                  "reason" in json.dumps(f_bad).lower()
                  and not f_bad.get("roll_id"), f_bad)

            # 14. honest fiat with reason
            f_ok = await call("force", value=12, reason="smoke: plot armor", view="2e")
            check("fiat ledgered as fiat", f_ok.get("method", "fiat") == "fiat"
                  and f_ok.get("roll_id", "").startswith("rol:fiat:"), f_ok)

            # 15. conventions disclose the poured-FG&G sources + the matrix
            conv = await call("conventions", view="2e")
            blob = json.dumps(conv)
            check("2e pack: FG&G poured + reaction matrix",
                  "poured: build/mechanus/fgg-text/" in blob and "bands_by" in blob)

            # 16. modifier registry serves the resolved FG&G cite
            mods = await call("modifiers", query="specialization", view="2e")
            rows = mods.get("modifiers", mods if isinstance(mods, list) else [])
            check("weapon-specialization cites FG&G p32",
                  any("FG&G p32" in json.dumps(m) for m in rows), rows)

            # 17. guarded write door refuses a bad op (no real file touched)
            bad = await call("define_modifier", spec={
                "id": "smoke-bad", "label": "bad", "effects": [{"op": "explode_total"}]})
            check("define_modifier bad op refused",
                  "unknown effect op" in json.dumps(bad), bad)

            # 18. usage counters live (shape-agnostic: sum every int in the tree)
            us = await call("usage_stats")

            def _ints(o):
                if isinstance(o, bool):
                    return 0
                if isinstance(o, int):
                    return o
                if isinstance(o, dict):
                    return sum(_ints(v) for v in o.values())
                if isinstance(o, list):
                    return sum(_ints(v) for v in o)
                return 0
            check("usage_stats counts this conversation", _ints(us) >= 10, us)

    print(("SMOKE PASS — " if not failures else "SMOKE FAIL — ")
          + f"{18 - len(failures)}/18 checks"
          + (f"; failures: {failures}" if failures else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(asyncio.run(main()))
