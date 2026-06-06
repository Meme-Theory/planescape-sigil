#!/usr/bin/env python3
"""cant end-to-end MCP stdio smoke — spawns the server via the EXACT spawn
configured in .mcp.json (family law: never smoke-test through a different
interpreter than the one that will serve).

    py -3.13 pipeline/cant/smoke_server.py             # from repo root

Probes: handshake, tools/list (5), cant_info (engine v + store state),
transmute (3 candidates + suggestions + determinism), model door shut without
a key, decode (gloss + loose flag), suggest_terms, examples register filter.
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent

checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, ok, detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""),
          flush=True)


def main() -> int:
    cfg = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))
    entry = cfg["mcpServers"].get("cant")
    check("cant registered in .mcp.json", entry is not None)
    if not entry:
        return 1
    cmd = [entry["command"], *entry["args"]]
    check("configured interpreter exists", Path(entry["command"]).exists(), entry["command"])

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)          # the model-door probe needs a shut door
    env.pop("CANT_API_KEY", None)
    proc = subprocess.Popen(cmd, cwd=entry.get("cwd", str(REPO)),
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True,
                            encoding="utf-8", env=env)

    import queue
    lines: "queue.Queue[str | None]" = queue.Queue()

    def _pump() -> None:
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

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
                return None
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
                         "clientInfo": {"name": "cant-smoke", "version": "0"}}})
        init = recv(1, 60)
        check("initialize handshake", bool(init and "result" in init),
              (init or {}).get("result", {}).get("serverInfo", {}).get("name", ""))
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tl = recv(2, 30)
        tools = {t["name"] for t in (tl or {}).get("result", {}).get("tools", [])}
        check("tools/list serves 6 tools",
              tools == {"transmute", "voiceover", "decode", "suggest_terms",
                        "examples", "cant_info"},
              str(sorted(tools)))

        info = call(3, "cant_info", {})
        ok = bool(info) and info.get("engine_version") == "2" \
            and info.get("lexicon", {}).get("terms", 0) > 300
        check("cant_info: engine v2, lexicon >300 terms", ok,
              f"{info.get('lexicon', {}).get('terms')} terms, "
              f"store {info.get('compiled', {}).get('state')}" if info else "no payload")

        t1 = call(4, "transmute",
                  {"text": "Hello! The police arrested the thief who stole my money.",
                   "density": "street", "attitude": "hostile"})
        cands = (t1 or {}).get("candidates", [])
        street = next((c for c in cands if c["density"] == "street"), {})
        s_text = street.get("text", "")
        ok = len(cands) == 3 and any(w in s_text for w in ("jink", "gelt")) \
            and "Hardheads" in s_text and "knicked" in s_text and t1.get("suggestions")
        check("transmute: 3 candidates, cant landed, palette served", ok, s_text[:90])

        t2 = call(5, "transmute",
                  {"text": "Hello! The police arrested the thief who stole my money.",
                   "density": "street", "attitude": "hostile"})
        check("transmute: deterministic (same ask, same answer)",
              bool(t2) and t2.get("candidates") == t1.get("candidates"))

        t3 = call(6, "transmute", {"text": "Tell me the truth.", "method": "model"})
        door = (t3 or {}).get("model_door", {})
        check("model door shut without key (honest refusal)",
              t3 is not None and t3.get("method") == "rule" and "refused" in door,
              door.get("refused", "")[:60])

        d = call(7, "decode", {"text": "Pike it, berk — no jink, no chant."})
        hits = {h["term"]: h for h in (d or {}).get("hits", [])}
        check("decode: berk/jink strict, bare 'chant' loose-flagged",
              {"berk", "jink", "the chant", "pike it"} <= set(hits)
              and not hits["berk"]["loose"] and hits["the chant"]["loose"],
              (d or {}).get("glossed", "")[:90])

        s = call(8, "suggest_terms", {"query": "money", "tier": "core"})
        check("suggest_terms: money → jink (core)",
              "jink" in [t["term"] for t in (s or {}).get("terms", [])])

        ex = call(9, "examples", {"register": "stern", "limit": 4})
        lns = (ex or {}).get("lines", [])
        check("examples: stern register filter holds",
              bool(lns) and all(l["register"] == "stern" for l in lns),
              f"{len(lns)} lines")

        err = call(10, "transmute", {"text": "x", "density": "soaked"})
        check("bad density refused with ERROR", err is None or "_raw" in err)

        # ---- dabus handoff (D11): adaptive — provisioned packs or honest withholding
        vo = call(14, "voiceover", {"text": "Be careful — someone betrayed us.",
                                    "npc": "npc:uncaged:a-kin", "register": "stern"})
        spk = (vo or {}).get("speakable")
        if spk:
            check("voiceover: npc cast → dabus-ready speak payload",
                  spk.get("tool") == "speak" and spk["args"]["voice"]
                  and spk["args"]["text"].startswith("["),
                  f"{spk['args']['voice']}: {spk['args']['text'][:60]}")
        else:
            check("voiceover: speakable withheld HONESTLY (why present)",
                  bool((vo or {}).get("casting", {}).get("why")),
                  str((vo or {}).get("casting", {}).get("why"))[:70])
        vo2 = call(15, "voiceover", {"text": "Hello.", "npc": "npc:nowhere:uncast"})
        check("voiceover: uncast npc refuses speakable, line still serves",
              vo2 is not None and vo2.get("speakable") is None and vo2.get("line"),
              str(vo2.get("casting", {}).get("why"))[:60] if vo2 else "")

        # ---- semantic lane (D9): adaptive — BOTH states are lawful, probe whichever holds
        sem = (info or {}).get("semantic", {})
        if sem.get("enabled"):
            check("semantic lane enabled (vectors == lexicon terms)",
                  sem.get("vectors") == info["lexicon"]["terms"],
                  f"{sem.get('vectors')} vectors, model {sem.get('model_sha')}")
            sg = call(11, "suggest_terms", {"query": "bribe"})
            top = ((sg or {}).get("terms") or [{}])[0]
            check("semantic: 'bribe' → garnish (cosine > 0.5)",
                  top.get("term") == "garnish" and top.get("match", {}).get("semantic", 0) > 0.5,
                  f"semantic {top.get('match', {}).get('semantic')}")
            tc = call(12, "transmute", {"text": "I'll pay you well for that gemstone."})
            cons = [c["term"] for c in (tc or {}).get("concepts", [])]
            check("semantic: concepts catch what regex missed (gemstone→sparkle)",
                  "sparkle" in cons, str(cons))
            neg = call(13, "transmute", {"text": "The weather is pleasant today."})
            check("semantic: negative control stays silent (θ holds)",
                  (neg or {}).get("concepts") == [])
        else:
            check("semantic lane disabled HONESTLY (why present)",
                  bool(sem.get("why")), str(sem.get("why"))[:70])

    finally:
        proc.terminate()

    passed = sum(1 for _, ok, _ in checks if ok)
    print(f"\ncant smoke: {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
