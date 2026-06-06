#!/usr/bin/env python
"""harvest_workflow.py — bank completed agent outputs from the modron-audit
workflow transcripts (all runs of wf_2f0ec1f6-078), per the
workflow-rate-limit-discipline memory: bank partials, then run a SURGICAL
fresh workflow over only the dead work.

Reads each agent-*.jsonl, classifies the agent from its first user prompt,
extracts the LAST StructuredOutput tool_use payload (the validated return).
Writes build/modron/review/results-bank/harvest.json + a coverage report.

Run: py -3.13 pipeline/modron/tools/harvest_workflow.py <transcript-dir>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BANK = ROOT / "build/modron/review/results-bank"

CHUNK_IDS = ["A-1-2e", "A-2-2e-planescape", "A-3-5e-2014", "A-4-5e-2024",
             "B-1-core-5e", "B-2-core-2e", "B-3-planescape-2e",
             "C-1-chaos-law", "C-2-cage", "C-3-inner-a", "C-4-inner-b",
             "F-1-design-docs", "F-2-verification-claims",
             "G-1-creatures", "G-2-npc-a", "G-3-npc-b", "G-4-hp-roster",
             "G-5-clean-sample"]


def classify(prompt: str) -> str:
    if "confirm" in prompt and "stats.hard" in prompt:
        return "gate"
    for cid in CHUNK_IDS:
        if f"/chunks/{cid}.json" in prompt:
            return f"review:{cid}"
    if "adversarial-verify" in prompt:
        m = re.search(r'"finding_id":\s*"([A-Z]-\d[^"]*?)-\d+', prompt)
        return f"verify:{m.group(1) if m else 'unknown'}"
    if "resolution court" in prompt and "Mechanus law refs" in prompt:
        return "court-mechanus"
    if "resolution court" in prompt and ("FG&G" in prompt or "FG&amp;G" in prompt):
        return "court-fgg"
    if "audit mechanus court" in prompt:
        return "court-refuter:mechanus"
    if "audit fgg court" in prompt:
        return "court-refuter:fgg"
    if "synthesizer" in prompt:
        return "synth"
    if "completeness critic" in prompt:
        return "critic"
    return "unknown"


def harvest_file(path: Path) -> tuple[str, dict | None, str]:
    """(label, payload|None, first_prompt_snippet)"""
    label, payload, first_prompt = "unknown", None, ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = d.get("type")
            msg = d.get("message") or {}
            if t == "user" and not first_prompt:
                content = msg.get("content")
                if isinstance(content, str):
                    first_prompt = content
                elif isinstance(content, list):
                    first_prompt = " ".join(c.get("text", "") for c in content
                                            if isinstance(c, dict) and c.get("type") == "text")
                label = classify(first_prompt)
            if t == "assistant":
                for c in msg.get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use" \
                            and c.get("name") == "StructuredOutput":
                        payload = c.get("input")
    return label, payload, first_prompt[:200]


def main() -> int:
    tdir = Path(sys.argv[1])
    bank: dict[str, list] = {}
    for path in sorted(tdir.glob("agent-*.jsonl")):
        label, payload, _snip = harvest_file(path)
        if payload is None:
            continue
        bank.setdefault(label, []).append(
            {"transcript": path.name, "payload": payload})

    BANK.mkdir(parents=True, exist_ok=True)
    out = BANK / "harvest.json"
    out.write_text(json.dumps(bank, indent=1, ensure_ascii=False), encoding="utf-8")

    # coverage report
    print(f"banked -> {out}")
    reviews_done = sorted(k.split(":", 1)[1] for k in bank if k.startswith("review:"))
    missing = [c for c in CHUNK_IDS if c not in reviews_done]
    print(f"reviews banked ({len(reviews_done)}): {reviews_done}")
    print(f"reviews MISSING ({len(missing)}): {missing}")
    n_findings = 0
    for k in bank:
        if k.startswith("review:"):
            for rec in bank[k]:
                n_findings += len(rec["payload"].get("findings") or [])
    print(f"findings banked: {n_findings}")
    for k in ("gate", "court-mechanus", "court-fgg", "court-refuter:mechanus",
              "court-refuter:fgg", "synth", "critic"):
        print(f"{k:24} {len(bank.get(k, []))}")
    verify_keys = sorted(k for k in bank if k.startswith("verify:"))
    print(f"verify banks: {len(verify_keys)} -> {verify_keys}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
