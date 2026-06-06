"""cage_probe.py — assay In the Cage extraction against the REAL reflow (not a pour).

Reports: offset calibration vote, roster segmentation coverage (found/missing + match
scores + body sizes), portal-sweep candidates (≥θ vs queued), and Places attestation
counts. Run me before touching gate.py; tune cage.py until this reads clean.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "pipeline/parse"))
import cage as C

REFLOW = ROOT / "build/in-the-cage-a-guide-to-sigil/ddps-inthecage/reflow"


def main():
    pages = C.load_pages(REFLOW)
    off, votes = C.calibrate_offset(pages)
    print(f"offset: +{off}   votes={votes}")

    entries, missing = C.segment(pages, offset=off)
    minors, mmissing = C.segment_minors(pages)
    C.trim_entries(pages, entries, minors)
    entries = entries + minors
    unexplained = [m for m in missing if m not in C.EXPECTED_ABSENT
                   and dict((r[0], r[4]) for r in C.ROSTER).get(m) == "site"]
    sites = [e for e in entries if e["rtype"] in ("site", "minor")]
    print(f"\nsegmented {len(entries)}/{len(C.ROSTER) + len(C.MINORS)} rows "
          f"({len(sites)} sites+minors)")
    print(f"expected-absent: {sorted(m for m in missing if m in C.EXPECTED_ABSENT)}")
    print(f"UNEXPLAINED missing sites: {unexplained or '—'}   minor-missing: {mmissing or '—'}")
    for e in entries:
        flag = "" if len(e["body"]) > 200 else "   << thin"
        print(f"  p{e['page']:>3} → pg{e['scan_page']:>3}  {e['score']:.2f}  "
              f"{e['rtype']:<8} {e['name'][:42]:<44} {len(e['body']):>6}ch{flag}")

    # the sweep: owned regime over site/feature/chapter bodies; src binds for sites only
    pool = {}
    for e in sites:
        nm = e["name"].lower()
        pool[nm] = f"location:sigil:{nm}"            # probe-grade ids; gate resolves properly
        if not nm.startswith("the "):
            pool["the " + nm] = pool[nm]
    for w in ("lady's ward", "lower ward", "clerk's ward", "market ward",
              "guildhall ward", "hive ward"):
        pool[w] = f"location:sigil:{w}"
        pool["the " + w] = pool[w]
    pool["the hive"] = pool["hive ward"]

    cands = []
    for e in entries:
        if e["name"] == "Index":            # alphabetical adjacency = fake portals
            continue
        owned = e["rtype"] == "site"
        cands += C.sweep_portals(
            e["body"], page=e["page"],
            src_id=pool.get(e["name"].lower()) if owned else None,
            src_name=e["name"] if owned else None,
            src_pool=None if owned else pool)
    admit = [c for c in cands if c["confidence"] >= C.THETA_PORTAL and c["src"]]
    queued = [c for c in cands if c not in admit]
    print(f"\nportal candidates: {len(cands)}   ≥θ+src: {len(admit)}   queued: {len(queued)}")
    seen = set()
    for c in sorted(admit, key=lambda c: -c["confidence"]):
        k = (c["src"], c["dest"])
        if k in seen:
            continue
        seen.add(k)
        print(f"  {c['confidence']:.2f}  {str(c['form'] or '-'):<10} "
              f"{(c['src_name'] or '?')[:28]:<30} → {c['dest_name'][:34]:<36} p{c['page']}")
    print("\n  -- queued (no src or <θ), distinct dests --")
    qseen = set()
    for c in queued:
        k = (c["src_name"], c["dest"])
        if k in qseen:
            continue
        qseen.add(k)
        print(f"  {c['confidence']:.2f}  src={str(c['src_name'])[:24]:<26} "
              f"→ {c['dest_name'][:34]:<36} p{c['page']}  «{c['sentence'][:60]}»")

    wit = C.attest_places(pages, offset=off)
    print(f"\nPlaces attested: {len(wit)}")
    for gid, pp in sorted(wit.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"  {gid:<32} {len(pp):>3} pages   e.g. {pp[:8]}")


if __name__ == "__main__":
    main()
