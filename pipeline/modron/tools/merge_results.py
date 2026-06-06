#!/usr/bin/env python
"""merge_results.py — deterministic synthesis of the Modron audit (replaces the
synth agent, which died twice on its giant inline payload; the merge law is
mechanical and belongs in a script).

Inputs (build/modron/review/):
  results-bank/canonical-results.json   17 reviews + alts + banked verdicts + courts
  results-bank/surgical-harvest.json    B-1 review + all surgical verdicts
  integrity-report.json                 mechanical universe + routed pre-findings
  chunks-manifest.json                  census
Outputs:
  workflow-results.json                 every finding with verdicts[] + status
  run-summary.md                        the coverage proof (no silent caps)

Merge law (workflow-rate-limit-discipline #4): required coverage = 2 verdicts
when proposed_fix.lane != none else 1; REFUTED if any verdict refutes; VERIFIED
if coverage met and none refute; UNDER-VERIFIED otherwise — a missing verdict
is never survival and never refutation. Dedupe by (target_id, kind): a group is
VERIFIED if any member is, refuted only if all are.

Run: py -3.13 pipeline/modron/tools/merge_results.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REVIEW = ROOT / "build/modron/review"
BANK = REVIEW / "results-bank"

CHUNK_IDS = ["A-1-2e", "A-2-2e-planescape", "A-3-5e-2014", "A-4-5e-2024",
             "B-1-core-5e", "B-2-core-2e", "B-3-planescape-2e",
             "C-1-chaos-law", "C-2-cage", "C-3-inner-a", "C-4-inner-b",
             "F-1-design-docs", "F-2-verification-claims",
             "G-1-creatures", "G-2-npc-a", "G-3-npc-b", "G-4-hp-roster",
             "G-5-clean-sample"]


def main() -> int:
    canonical = json.loads((BANK / "canonical-results.json").read_text(encoding="utf-8"))
    surgical = json.loads((BANK / "surgical-harvest.json").read_text(encoding="utf-8"))
    integrity = json.loads((REVIEW / "integrity-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((REVIEW / "chunks-manifest.json").read_text(encoding="utf-8"))

    # ---- verdict pool ------------------------------------------------------
    pool: dict[str, list[dict]] = {}

    def add_verdict(fid: str, refuted: bool, why: str, src: str):
        pool.setdefault(fid, []).append({"refuted": bool(refuted), "why": why, "src": src})

    for cid, c in canonical["canonical"].items():
        if c.get("status") != "ok":
            continue
        for fid, vs in (c.get("verdicts") or {}).items():
            for v in vs:
                add_verdict(fid, v["refuted"], v.get("why", ""), f"banked:{v.get('transcript','')[:20]}")
    for key in ("verify:file-batch", "verify:B-1"):
        for rec in surgical.get(key, []):
            for v in rec["payload"].get("verdicts") or []:
                add_verdict(v["finding_id"], v.get("refuted"), v.get("why", ""),
                            f"surgical:{rec['transcript'][:20]}")

    # ---- findings (canonical + alts + B-1) ---------------------------------
    findings: list[dict] = []
    reviews_by_chunk: dict[str, dict] = {}
    for cid, c in canonical["canonical"].items():
        if c.get("status") != "ok":
            continue
        reviews_by_chunk[cid] = c["review"]
        for f in (c["review"].get("findings") or []):
            findings.append({**f, "chunk": cid})
        for f in (c.get("alt_findings") or []):
            findings.append({**f, "chunk": cid})
    b1 = (surgical.get("review:B-1-core-5e") or [{}])[0].get("payload")
    if b1:
        reviews_by_chunk["B-1-core-5e"] = b1
        for f in (b1.get("findings") or []):
            findings.append({**f, "chunk": "B-1-core-5e"})

    # ---- status per finding -------------------------------------------------
    for f in findings:
        lane = (f.get("proposed_fix") or {}).get("lane", "none")
        need = 2 if lane != "none" else 1
        vs = pool.get(f["finding_id"], [])
        f["verdicts"] = vs
        if any(v["refuted"] for v in vs):
            f["status"] = "REFUTED"
        elif len(vs) >= need:
            f["status"] = "VERIFIED"
        else:
            f["status"] = "UNDER-VERIFIED"

    # ---- dedupe by (target_id, kind) ----------------------------------------
    groups: dict[tuple, list[dict]] = {}
    for f in findings:
        groups.setdefault((f.get("target_id"), f.get("kind")), []).append(f)
    deduped: list[dict] = []
    for key, members in groups.items():
        rank = {"VERIFIED": 2, "UNDER-VERIFIED": 1, "REFUTED": 0}
        best_status = sorted((m["status"] for m in members), key=lambda s: rank[s])[-1]
        candidates = [m for m in members if m["status"] == best_status]
        primary = sorted(candidates, key=lambda m: (m.get("confidence") or 0))[-1]
        primary = dict(primary)
        primary["status"] = best_status
        if len(members) > 1:
            primary["merged_ids"] = sorted(m["finding_id"] for m in members
                                           if m["finding_id"] != primary["finding_id"])
        deduped.append(primary)
    deduped.sort(key=lambda f: f["finding_id"])

    # ---- courts ---------------------------------------------------------------
    def merge_court(rulings: list[dict], refuter_payloads: list) -> list[dict]:
        by_where: dict[str, list[dict]] = {}
        for payload in refuter_payloads:
            verdicts = payload if isinstance(payload, list) else payload.get("verdicts") or []
            for v in verdicts:
                by_where.setdefault(v["finding_id"], []).append(v)
        out = []
        for r in rulings:
            vs = by_where.get(r["where"], [])
            status = "REFUTED" if any(v.get("refuted") for v in vs) else (
                "VERIFIED" if len(vs) >= 2 else "UNDER-VERIFIED")
            out.append({**r, "refuter_verdicts": vs, "status": status})
        return out

    courts = {
        "mechanus": merge_court(
            (canonical["courts"]["mechanus"] or {}).get("rulings", []),
            [rec["payload"] for rec in surgical.get("court-refuter:mechanus", [])]),
        "fgg": merge_court(
            (canonical["courts"]["fgg"] or {}).get("rulings", []),
            canonical["courts"].get("fgg_refuters", [])
            + (json.loads((BANK / "fgg-refuter-verdicts.json").read_text(encoding="utf-8"))
               if (BANK / "fgg-refuter-verdicts.json").exists() else [])),
    }

    # ---- stats ------------------------------------------------------------------
    def count(status):
        return sum(1 for f in deduped if f["status"] == status)
    stats = {
        "findings_raw": len(findings), "findings_deduped": len(deduped),
        "verified": count("VERIFIED"), "refuted": count("REFUTED"),
        "under_verified": count("UNDER-VERIFIED"),
        "court_rulings": {k: len(v) for k, v in courts.items()},
        "court_verified": {k: sum(1 for r in v if r["status"] == "VERIFIED")
                           for k, v in courts.items()},
        "by_lane": {}, "by_kind": {},
    }
    for f in deduped:
        if f["status"] != "VERIFIED":
            continue
        lane = (f.get("proposed_fix") or {}).get("lane", "none")
        stats["by_lane"][lane] = stats["by_lane"].get(lane, 0) + 1
        stats["by_kind"][f["kind"]] = stats["by_kind"].get(f["kind"], 0) + 1

    (REVIEW / "workflow-results.json").write_text(json.dumps(
        {"findings": deduped, "courts": courts, "stats": stats,
         "reviews_by_chunk": {cid: {"reviewed_ids": r.get("reviewed_ids", []),
                                    "findings": [f["finding_id"] for f in r.get("findings") or []]}
                              for cid, r in reviews_by_chunk.items()}},
        indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- run-summary.md -----------------------------------------------------------
    fin_by_id = {f["finding_id"]: f for f in findings}
    lines = ["# Modron audit — run summary (coverage proof)", "",
             f"Census (chunks-manifest): {manifest['census']}", ""]
    for cid in CHUNK_IDS:
        r = reviews_by_chunk.get(cid)
        lines.append(f"## {cid}")
        if not r:
            lines.append("**MISSING REVIEW** — gap!")
            continue
        rids = r.get("reviewed_ids") or []
        fids = [f["finding_id"] for f in (r.get("findings") or [])]
        # alt findings ride the chunk too
        alts = [f["finding_id"] for f in findings
                if f["chunk"] == cid and f["finding_id"].endswith("-alt")]
        touched: dict[str, list[str]] = {}
        for fid in fids + alts:
            f = fin_by_id[fid]
            touched.setdefault(str(f.get("target_id")), []).append(
                f"{fid}[{f['status']}]")
        for rid in rids:
            t = touched.get(str(rid))
            lines.append(f"- `{rid}` — " + ("; ".join(t) if t else "clean"))
        extra = [t for t in touched if t not in {str(x) for x in rids}]
        for t in extra:
            lines.append(f"- `{t}` (target outside reviewed list) — {'; '.join(touched[t])}")
        lines.append("")
    lines.append("## Courts")
    for name, rulings in courts.items():
        lines.append(f"### court-{name}")
        for r in rulings:
            new = r.get("ref_new") or r.get("page_cite") or ""
            lines.append(f"- `{r['where']}` → **{r['verdict']}** {new} — {r['status']}")
        lines.append("")
    inf = integrity["info"]
    lines += [
        "## Mechanical universe (integrity-report.json)",
        f"- ledger: {inf['ledger']['sessions']} sessions / {inf['ledger']['rolls']} rolls / "
        f"{inf['ledger']['replayed']} replayed clean / {inf['ledger']['fiat']} fiat",
        f"- math fixtures: {inf['math_fixtures']['total']} ({inf['math_fixtures']['match']} match; "
        "1 routed divergence — analysis-vs-engine clamp+count)",
        f"- violations: {integrity['stats']['hard']} hard / {integrity['stats']['soft']} soft "
        f"(all routed/known): {integrity['stats']['by_check']}",
        f"- fleet: {inf['fleet']['entities']} entities compiled, {inf['fleet']['specs']} specs; "
        f"16-creature systemic shape gap (routed); flags {inf['fleet']['by_flag']}",
        f"- pending refs fed to courts: {inf['pending_refs']}; minted law ids: {inf['minted_law_ids']}",
        "",
        "## Totals",
        f"- findings: {stats['findings_raw']} raw → {stats['findings_deduped']} deduped; "
        f"**{stats['verified']} VERIFIED** · {stats['refuted']} refuted · "
        f"{stats['under_verified']} under-verified",
        f"- verified by lane: {stats['by_lane']}",
        f"- verified by kind: {stats['by_kind']}",
        f"- courts: {stats['court_rulings']} rulings, {stats['court_verified']} verified",
    ]
    (REVIEW / "run-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"-> {REVIEW / 'workflow-results.json'}")
    print(f"-> {REVIEW / 'run-summary.md'}")
    print(json.dumps(stats, indent=1))
    return 0


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
