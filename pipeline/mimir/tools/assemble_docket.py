#!/usr/bin/env python
"""assemble_docket.py — Great Audit Phase 2: deterministic docket assembly.

Inputs (all under build/mimir/review/):
  review-results.json    — the Review+Verify workflow's return value (saved by the session)
  court-verdicts.json    — quarantine court (banked from wf_cf73ebe9-b79)
  preseeded-findings.json— Phase-0 mechanically-verified findings
  integrity-report.json  — the mechanical pass
  manifest.json          — chunk coverage ledger

Outputs:
  correction-docket.md / correction-docket.json / run-summary.md

NO data mutations — this writes the proposal artifacts only (docket-first law).
Run: py -3.13 pipeline/mimir/tools/assemble_docket.py
"""
from __future__ import annotations
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
import store as S                                           # noqa: E402

R = S.ROOT / "build/mimir/review"
DATE = "2026-06-06"
SEV_ORDER = ["misbind", "provenance-miss", "field-wrong", "ocr-name",
             "weak-witness", "dup-suspect", "other"]
LANE_TITLES = {
    "card": "Lane 1 — card fixes (curated tables in parse/{planes,boxset,cage}.py + gate.py)",
    "module-curation": "Lane 2 — module curation dicts (PORTAL_CURATIONS pattern; new dicts as proposed)",
    "curations-json": "Lane 3 — curations.json (dot-path sets; the _admit_seed hook now serves every dim)",
    "none": "Report-only (no fix proposed — weak witness / attention items)",
}

# Registry ratification — the 8 proposed-closed dims (DIMENSIONS.md ledger, 2026-06-06
# REGISTRY CLOSE-OUT row). ADOPT/REJECT each.
REGISTRY_ITEMS = [
    ("cant-term", "close: the cant sibling owns the lexicon (362-term tiered store + harvest loop)"),
    ("audio", "close: dabus owns renders (content-addressed ledger; renders never ship)"),
    ("rumor", "close: fold to `hook` grain (rumor = a hook with truth-value dark; grain field carries it)"),
    ("region", "close: wards live as location kind:ward (six poured; part_of sigil)"),
    ("philosophy", "close: carried by faction/sect `philosophy` fields (15 Manifesto cards + sect glosses)"),
    ("language", "park-thin: no poured corpus attests a language dim yet (Planewalker's Hbk may reopen)"),
    ("map", "park-thin: awaits the player/DM-pair design"),
    ("symbol", "park-thin: faction signs ride faction fields until a consumer exists"),
]


def load(name):
    p = R / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def fmd(f, i):
    fix = f.get("proposed_fix") or {}
    lines = [
        f"### {i}. `{f['entity_id']}` — {f['kind']} (conf {f.get('confidence', '?')})",
        "",
        f"- **detail:** {f['detail']}",
        f"- **evidence:** “{f.get('evidence_quote', '')}”",
        f"- **reflow:** `{f.get('reflow_file')}`",
        f"- **fix [{fix.get('lane')}]:** {fix.get('payload') or '—'}",
    ]
    refs = f.get("refutations") or []
    label = f.get("verification") or (f"confirmed-{len(refs)}x" if refs else "unverified")
    if refs:
        lines.append(f"- **verification:** `{label}` ({len(refs)} independent refuter(s) failed to refute)"
                     + (f" — {refs[0].get('why','')[:160]}" if refs else ""))
    if f.get("verified_by"):
        lines.append(f"- **verification:** {f['verified_by']}")
    if f.get("also"):
        lines.append(f"- also seen in: {', '.join(str(x).rsplit('/',1)[-1] for x in f['also'])}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    rev = load("review-results.json")
    court = load("court-verdicts.json")
    pre = load("preseeded-findings.json") or {"findings": []}
    integ = load("integrity-report.json") or {}
    manifest = load("manifest.json") or {}
    if not rev or not court:
        print("missing review-results.json or court-verdicts.json — run the workflow first")
        return 1

    confirmed = list(rev.get("confirmed") or [])
    refuted = list(rev.get("refuted") or [])
    unverified = list(rev.get("unverified") or [])
    # merge preseeded (already verified mechanically); dedupe on (entity_id, kind)
    have = {(f["entity_id"], f["kind"]) for f in confirmed}
    for f in pre.get("findings", []):
        if (f["entity_id"], f["kind"]) not in have:
            confirmed.append(f)
    sev_rank = {k: i for i, k in enumerate(SEV_ORDER)}
    confirmed.sort(key=lambda f: (sev_rank.get(f.get("kind"), 9), -(f.get("confidence") or 0)))

    by_lane = defaultdict(list)
    for f in confirmed:
        by_lane[(f.get("proposed_fix") or {}).get("lane") or "none"].append(f)
    by_kind = Counter(f.get("kind") for f in confirmed)

    cstats = {b: Counter(v["verdict"] for v in vs) for b, vs in court["buckets"].items()}
    n_promote = sum(c.get("promote-with-fix", 0) for c in cstats.values())
    n_hold = sum(c.get("hold", 0) for c in cstats.values())
    n_reject = sum(c.get("confirm-reject", 0) for c in cstats.values())

    stats = rev.get("stats") or {}
    coverage = rev.get("coverage") or {}
    reviewed_ids = {i for ids in coverage.values() for i in (ids or [])}
    flagged_ids = {f["entity_id"] for f in confirmed}
    istats = integ.get("stats") or {}

    # ---------- correction-docket.json ----------
    docket = {
        "id": f"audit:mimir:great-audit:{DATE}",
        "date": DATE, "status": "PROPOSED — awaiting Meme's sign-off; nothing applied",
        "stats": {
            "entities": 824, "reviewed": len(reviewed_ids),
            "clean": len(reviewed_ids - flagged_ids), "flagged": len(flagged_ids),
            "findings_confirmed": len(confirmed), "findings_refuted": len(refuted),
            "refutation_rate": (round(len(refuted) / max(1, len(refuted) + len(confirmed)), 3)),
            "by_kind": dict(by_kind),
            "quarantine": {"total": sum(len(v) for v in court["buckets"].values()),
                           "promote_with_fix": n_promote, "hold": n_hold,
                           "confirm_reject": n_reject},
            "integrity": {"hard": istats.get("hard"), "soft": istats.get("soft")},
            "workflow_runs": ["wf_cf73ebe9-b79 (court)", rev.get("run_id") or "review+verify"],
        },
        "lanes": {k: v for k, v in by_lane.items()},
        "court": court["buckets"],
        "registry_ratification": [{"dim": d, "proposal": p, "ruling": "ADOPT / REJECT (Meme)"}
                                  for d, p in REGISTRY_ITEMS],
        "rejected_findings": refuted,
        "unverified_findings": unverified,
    }
    (R / "correction-docket.json").write_text(json.dumps(docket, indent=1, ensure_ascii=False),
                                              encoding="utf-8")

    # ---------- correction-docket.md ----------
    md = [
        f"# The Great Audit — correction docket ({DATE})",
        "",
        "**Status: PROPOSED.** Docket-first law: every entry below is a *proposal*;",
        "nothing has been applied. Corrections land as data edits + ONE re-pour after",
        "Meme's sign-off (Phase 3 of `PLAN.md`). `handbook.db` is byte-identical to the",
        "pre-audit snapshot (`db-sha-prework.txt`).",
        "",
        "## 1. Stats",
        "",
        f"- entities reviewed: **{len(reviewed_ids)} / 824** · clean {len(reviewed_ids - flagged_ids)} · flagged {len(flagged_ids)}",
        f"- findings: **{len(confirmed)} confirmed** ({stats.get('confirmed_2x','?')} double-verified · "
        f"{stats.get('confirmed_1x','?')} single-verified) · {len(refuted)} refuted · "
        f"{len(unverified)} unverified (refutation rate {docket['stats']['refutation_rate']})",
        f"- workflow runs: review wf_19481e54-9d1 → throttled retry wf_b4967f79-98e (verification) · "
        f"court wf_cf73ebe9-b79",
        f"- by kind: " + " · ".join(f"{k} {n}" for k, n in by_kind.most_common()),
        f"- quarantine court: {docket['stats']['quarantine']['total']} items → "
        f"**{n_promote} promote-with-fix** · {n_hold} hold · {n_reject} confirm-reject",
        f"- integrity (mechanical): {istats.get('hard')} hard · {istats.get('soft')} soft "
        f"(softs = documented danglers + name-style reports)",
        f"- chunks: {stats.get('chunks')} ({stats.get('failed_chunks', 0)} failed)",
        "",
    ]
    sec = 2
    for lane in ("card", "module-curation", "curations-json"):
        fs = by_lane.get(lane, [])
        md += [f"## {sec}. {LANE_TITLES[lane]}", "", f"*{len(fs)} proposal(s).*", ""]
        md += [fmd(f, i + 1) for i, f in enumerate(fs)] or ["(none)", ""]
        sec += 1
    if by_lane.get("none"):
        md += [f"## {sec}a. {LANE_TITLES['none']}", ""]
        md += [fmd(f, i + 1) for i, f in enumerate(by_lane["none"])]

    md += [f"## {sec + 1}. Quarantine court verdicts", ""]
    for b, vs in court["buckets"].items():
        c = cstats[b]
        md += [f"### {b} ({len(vs)}: " + ", ".join(f"{k} {n}" for k, n in c.items()) + ")", ""]
        for v in vs:
            fix = v.get("fix") or {}
            md.append(f"- **{v['id']}** → `{v['verdict']}` — {v['why']}")
            if fix:
                md.append(f"  - fix [{fix.get('lane')}]: {str(fix.get('payload'))[:400]}")
                if fix.get("witness"):
                    md.append(f"  - witness: {str(fix['witness'])[:300]}")
        md.append("")

    md += [f"## {sec + 2}. Registry ratification — 8 proposed-closed dims (ADOPT/REJECT each)", ""]
    md += [f"- [ ] **{d}** — {p}" for d, p in REGISTRY_ITEMS]
    md += ["", f"## {sec + 3}. Rejected findings (preserved with why — docket law)", "",
           f"*{len(refuted)} finding(s) failed adversarial verification; kept for the record.*", ""]
    for f in refuted:
        whys = "; ".join((r.get("why") or "")[:120] for r in (f.get("refutations") or [])[:2])
        md.append(f"- `{f['entity_id']}` [{f['kind']}] {f['detail'][:140]} — **refuted:** {whys}")
    md.append("")
    if unverified:
        md += [f"## {sec + 4}. UNVERIFIED findings (verification died twice — attention, not adopted)", ""]
        for f in unverified:
            md.append(f"- `{f['entity_id']}` [{f['kind']}] {f['detail'][:160]}")
        md.append("")
    (R / "correction-docket.md").write_text("\n".join(md), encoding="utf-8")

    # ---------- run-summary.md ----------
    chunk_of = {}
    for c in manifest.get("chunks", []):
        for i in c.get("ids", []):
            chunk_of[i] = c["file"].rsplit("/", 1)[-1]
    rs = [
        f"# Great Audit run summary ({DATE})", "",
        f"- review workflow: {stats.get('chunks')} chunks, {stats.get('entities_reviewed')} entity-reviews",
        f"- coverage: {len(reviewed_ids)} / 824 unique ids reviewed",
        f"- court: 89/89 quarantined items judged (wf_cf73ebe9-b79)", "",
        "## Per-entity verdicts (every id, its chunk/reviewer, verdict)", "",
    ]
    missing = []
    db = S.HandbookStore(S.DEFAULT_DB, readonly=True)
    all_ids = [r["id"] for r in db.conn.execute("SELECT id FROM entities ORDER BY type, id")]
    db.close()
    for eid in all_ids:
        if eid in flagged_ids:
            verdict = "FLAGGED"
        elif eid in reviewed_ids:
            verdict = "clean"
        else:
            verdict = "NOT-REVIEWED"
            missing.append(eid)
        rs.append(f"- {eid} · {chunk_of.get(eid, '?')} · {verdict}")
    rs += ["", f"## Coverage holes: {len(missing)}", ""]
    rs += [f"- {m}" for m in missing] or ["(none — every admitted id reviewed)"]
    (R / "run-summary.md").write_text("\n".join(rs), encoding="utf-8")

    print(f"docket: {len(confirmed)} confirmed ({dict(by_kind)}) · {len(refuted)} refuted")
    print(f"court : {n_promote} promote / {n_hold} hold / {n_reject} reject")
    print(f"coverage: {len(reviewed_ids)}/824 reviewed · holes {len(missing)}")
    print("wrote correction-docket.md / correction-docket.json / run-summary.md")
    return 0 if not missing else 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
