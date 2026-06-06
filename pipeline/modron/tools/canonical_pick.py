#!/usr/bin/env python
"""canonical_pick.py — collapse the harvest bank to ONE canonical review per
chunk, attach only verify verdicts that UNAMBIGUOUSLY pair with it (same-run
by transcript mtime), compute the refuter deficit per finding (2 for
data-changing, 1 for observations; a dead refuter is NOT a refutation —
workflow-rate-limit-discipline #4), and write per-batch verify work files
for the surgical workflow.

Outputs under build/modron/review/results-bank/:
  canonical-results.json    one review per chunk + paired verdicts + courts
  verify-batches/batch-NN.json   findings still owed refuter coverage
Run: py -3.13 pipeline/modron/tools/canonical_pick.py <transcript-dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BANK = ROOT / "build/modron/review/results-bank"
BATCHES = BANK / "verify-batches"
RUN2_CUTOFF = "2026-06-06T10:30"   # run1 died 10:18-10:19; run2 spans 10:31+

CHUNK_IDS = ["A-1-2e", "A-2-2e-planescape", "A-3-5e-2014", "A-4-5e-2024",
             "B-1-core-5e", "B-2-core-2e", "B-3-planescape-2e",
             "C-1-chaos-law", "C-2-cage", "C-3-inner-a", "C-4-inner-b",
             "F-1-design-docs", "F-2-verification-claims",
             "G-1-creatures", "G-2-npc-a", "G-3-npc-b", "G-4-hp-roster",
             "G-5-clean-sample"]


def main() -> int:
    tdir = Path(sys.argv[1])
    bank = json.loads((BANK / "harvest.json").read_text(encoding="utf-8"))
    mtime = {p.name: p.stat().st_mtime for p in tdir.glob("agent-*.jsonl")}

    import datetime
    def is_run2(transcript: str) -> bool:
        t = mtime.get(transcript, 0)
        return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%dT%H:%M") >= RUN2_CUTOFF

    # verify verdicts grouped per finding_id, tagged by run
    verdicts_by_run: dict[bool, dict[str, list[dict]]] = {True: {}, False: {}}
    for k, recs in bank.items():
        if not k.startswith("verify:"):
            continue
        for r in recs:
            run2 = is_run2(r["transcript"])
            for v in r["payload"].get("verdicts") or []:
                verdicts_by_run[run2].setdefault(v["finding_id"], []).append(
                    {"refuted": bool(v.get("refuted")), "why": v.get("why", ""),
                     "transcript": r["transcript"]})

    canonical: dict[str, dict] = {}
    for cid in CHUNK_IDS:
        recs = bank.get(f"review:{cid}", [])
        # drop degenerates (reviewed nothing AND found nothing)
        live = [r for r in recs
                if (r["payload"].get("reviewed_ids") or r["payload"].get("findings"))]
        if not live:
            canonical[cid] = {"status": "MISSING"}
            continue
        # prefer the run that also has banked verdicts for this chunk's ids
        def verdict_run_for(rec):
            run2 = is_run2(rec["transcript"])
            fids = {f["finding_id"] for f in rec["payload"].get("findings") or []}
            covered = sum(1 for f in fids if f in verdicts_by_run[run2])
            return covered
        live.sort(key=lambda r: (verdict_run_for(r),
                                 len(r["payload"].get("reviewed_ids") or []),
                                 len(r["payload"].get("findings") or []),
                                 mtime.get(r["transcript"], 0)))
        chosen = live[-1]
        run2 = is_run2(chosen["transcript"])
        payload = chosen["payload"]
        findings = payload.get("findings") or []
        out_verdicts = {}
        for f in findings:
            fid = f["finding_id"]
            vs = verdicts_by_run[run2].get(fid, [])
            out_verdicts[fid] = vs
        # rescue NOVEL findings from dropped duplicate reviews (two independent
        # reviewers disagreed — the refuters adjudicate): only (target_id, kind)
        # pairs the chosen payload does NOT already carry; rekeyed -alt; zero
        # verdicts by construction so they all land in the deficit.
        seen_keys = {(f.get("target_id"), f.get("kind")) for f in findings}
        alt = []
        for rec in live[:-1]:
            for f in rec["payload"].get("findings") or []:
                key = (f.get("target_id"), f.get("kind"))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                alt.append({**f, "finding_id": f["finding_id"] + "-alt",
                            "from_dropped_review": rec["transcript"]})
        canonical[cid] = {"status": "ok", "transcript": chosen["transcript"],
                          "run2": run2, "review": payload,
                          "alt_findings": alt, "verdicts": out_verdicts}

    courts = {
        "mechanus": (bank.get("court-mechanus") or [{}])[-1].get("payload"),
        "fgg": (bank.get("court-fgg") or [{}])[-1].get("payload"),
        "fgg_refuters": [r["payload"] for r in bank.get("court-refuter:fgg", [])],
        "mechanus_refuters": [r["payload"] for r in bank.get("court-refuter:mechanus", [])],
    }

    # deficits: findings owed refuter coverage
    deficit: list[dict] = []
    stats = {"findings": 0, "fully_covered": 0, "deficit": 0, "refuted_already": 0}
    for cid, c in canonical.items():
        if c.get("status") != "ok":
            continue
        for f in (c["review"].get("findings") or []) + (c.get("alt_findings") or []):
            stats["findings"] += 1
            lane = (f.get("proposed_fix") or {}).get("lane", "none")
            need = 2 if lane != "none" else 1
            have = c["verdicts"].get(f["finding_id"], [])
            if any(v["refuted"] for v in have):
                stats["refuted_already"] += 1     # one real refutation kills it
                continue
            if len(have) >= need:
                stats["fully_covered"] += 1
                continue
            stats["deficit"] += 1
            deficit.append({"chunk": cid, "owed": need - len(have), **f})

    BATCHES.mkdir(parents=True, exist_ok=True)
    for old in BATCHES.glob("batch-*.json"):
        old.unlink()
    batch_files = []
    for i in range(0, len(deficit), 6):
        bf = BATCHES / f"batch-{i // 6:02d}.json"
        bf.write_text(json.dumps(deficit[i:i + 6], indent=1, ensure_ascii=False),
                      encoding="utf-8")
        batch_files.append(bf.as_posix())

    out = BANK / "canonical-results.json"
    out.write_text(json.dumps({"canonical": canonical, "courts": courts,
                               "stats": stats, "verify_batches": batch_files},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"canonical -> {out}")
    for cid in CHUNK_IDS:
        c = canonical[cid]
        if c.get("status") != "ok":
            print(f"  {cid:26} MISSING (surgical review needed)")
            continue
        n = len(c["review"].get("findings") or [])
        cov = sum(1 for f in (c["review"].get("findings") or [])
                  if len(c["verdicts"].get(f["finding_id"], [])) >= 1)
        print(f"  {cid:26} run2={c['run2']} findings={n:3} with-verdicts={cov}")
    print(f"stats: {stats}")
    print(f"verify batches: {len(batch_files)} x <=6 findings")
    print(f"courts: mechanus={'ok' if courts['mechanus'] else 'MISSING'} "
          f"fgg={'ok' if courts['fgg'] else 'MISSING'} "
          f"fgg_refuters={len(courts['fgg_refuters'])} "
          f"mechanus_refuters={len(courts['mechanus_refuters'])}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
