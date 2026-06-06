#!/usr/bin/env python3
"""dabus end-to-end MCP stdio smoke — spawns the server via the EXACT spawn
configured in .mcp.json (family law: never smoke-test through a different
interpreter than the one that will serve).

    py -3.13 pipeline/dabus/smoke_server.py            # from repo root

Probes: handshake, tools/list, list_voices, voice_info(grace), speak (render),
speak again (MUST cache-hit), find_renders, render_info, stack_status,
usage_stats. The speak probes load the model — first run takes ~1-2 min.
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
SMOKE_LINE = "Aye, the dabus speaks. Mark the irony well."

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""),
          flush=True)


def main() -> int:
    cfg = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    entry = cfg["mcpServers"].get("dabus")
    check("dabus registered in .mcp.json", entry is not None)
    if not entry:
        return 1
    cmd = [entry["command"], *entry["args"]]
    check("configured interpreter exists", Path(entry["command"]).exists(),
          entry["command"])

    proc = subprocess.Popen(cmd, cwd=entry.get("cwd", str(REPO)),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            encoding="utf-8")

    # reader thread: readline() can't be timeboxed, a queue can (smoke #1
    # wedged exactly here when the server's first model load hung)
    import queue
    lines: "queue.Queue[str | None]" = queue.Queue()

    def _pump() -> None:
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)  # EOF sentinel

    threading.Thread(target=_pump, daemon=True).start()

    def send(msg: dict) -> None:
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def recv(want_id: int, timeout: float = 30.0) -> dict | None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = lines.get(timeout=min(1.0, max(0.05, deadline - time.time())))
            except queue.Empty:
                continue
            if line is None:
                return None  # server EOF
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                check("stdout is protocol-clean", False, f"junk line: {line[:80]!r}")
                continue
            if msg.get("id") == want_id:
                return msg
        check(f"response to id {want_id} within {timeout:.0f}s", False, "TIMEOUT")
        return None

    def call(rid: int, tool: str, args: dict, timeout: float = 30.0) -> dict | None:
        send({"jsonrpc": "2.0", "id": rid, "method": "tools/call",
              "params": {"name": tool, "arguments": args}})
        resp = recv(rid, timeout)
        if not resp or "result" not in resp:
            return None
        try:
            return json.loads(resp["result"]["content"][0]["text"])
        except (KeyError, IndexError, json.JSONDecodeError):
            return {"_raw": resp["result"]}

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "dabus-smoke", "version": "0"}}})
        init = recv(1, 60)
        check("initialize handshake", bool(init and "result" in init),
              (init or {}).get("result", {}).get("serverInfo", {}).get("name", ""))
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tl = recv(2, 30)
        tools = {t["name"] for t in (tl or {}).get("result", {}).get("tools", [])}
        check("tools/list serves 11 tools", len(tools) == 11, str(sorted(tools)))

        lv = call(3, "list_voices", {})
        packed = {p["voice"] for p in (lv or {}).get("packs", [])
                  if p.get("status") == "PACKED"}
        check("list_voices: grace+annah PACKED", {"grace", "annah"} <= packed,
              str(sorted(packed)))

        vi = call(4, "voice_info", {"voice": "annah"})
        ok = bool(vi) and "main" in (vi.get("registers") or {})
        pitch = ((vi or {}).get("registers", {}).get("main") or {}).get("pitch")
        check("voice_info: annah main register + pitch join", ok and bool(pitch),
              f"tail Δ {pitch.get('tail_minus_median') if pitch else '?'}")

        t0 = time.time()
        sp1 = call(5, "speak", {"voice": "annah", "text": SMOKE_LINE}, timeout=300)
        ok1 = bool(sp1) and sp1.get("cached") is False and \
            Path(sp1.get("file", "")).exists()
        check("speak: fresh render on disk", ok1,
              f"{sp1.get('duration_s')}s audio in {time.time()-t0:.0f}s"
            if ok1 else json.dumps(sp1)[:200])

        sp2 = call(6, "speak", {"voice": "annah", "text": SMOKE_LINE}, timeout=60)
        check("speak again: smart provision (cached)",
              bool(sp2) and sp2.get("cached") is True and
              sp2.get("render_id") == (sp1 or {}).get("render_id"),
              (sp2 or {}).get("render_id", "?"))

        fr = call(7, "find_renders", {"query": "irony"})
        check("find_renders: FTS finds the line",
              bool(fr) and fr.get("count", 0) >= 1)

        ri = call(8, "render_info", {"ref": (sp1 or {}).get("render_id", "")})
        check("render_info: provenance row", bool(ri) and ri.get("file_exists")
              and ri.get("hits", 0) >= 1 and ri.get("lane"))

        # ---- the Mimir seam: perform a handbook line by dialog id ----
        import sqlite3
        hb = REPO / "build" / "mimir" / "handbook.db"
        did = None
        if hb.exists():
            conn = sqlite3.connect(f"file:{hb}?mode=ro", uri=True)
            row = conn.execute(
                "SELECT id FROM entities WHERE type='dialog' AND id LIKE "
                "'dialog:uncaged:%' LIMIT 1").fetchone()
            conn.close()
            did = row[0] if row else None
        if did:
            sd = call(11, "speak_dialog", {"ref": did}, timeout=300)
            line = (sd or {}).get("lines", [{}])[0]
            ok = bool(line.get("file")) and Path(line.get("file", "")).exists() \
                and line.get("source_ref") == did \
                and (line.get("mimir") or {}).get("page") is not None
            check("speak_dialog: handbook line performed, join-key + page witness",
                  ok, f"{did} -> {Path(line.get('file', '?')).name}")
            ji = call(12, "render_info", {"ref": did})
            check("render_info answers to the dialog id (join-key lookup)",
                  bool(ji) and ji.get("source_ref") == did and ji.get("file_exists"))
        else:
            check("speak_dialog: handbook line performed, join-key + page witness",
                  False, "no dialog nodes in handbook.db — pour first")

        st = call(9, "stack_status", {})
        check("stack_status: GPU + model loaded",
              bool(st) and "9070" in str(st.get("gpu", ""))
              and st.get("model", {}).get("loaded") is True,
              str(st.get("gpu")))

        us = call(10, "usage_stats", {})
        check("usage_stats counts the probes",
              bool(us) and us.get("total_calls", 0) >= 8)
    finally:
        proc.terminate()

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
