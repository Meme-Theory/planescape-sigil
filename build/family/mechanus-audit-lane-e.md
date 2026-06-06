# Lane E handoff — Mechanus audit sibling proposals (2026-06-06)

From the Mechanus correction docket (`build/mechanus/review/correction-docket.{md,json}`,
applied 2026-06-06, `law_version 0d05d408b20e7314`). Sibling etiquette held: the
Mechanus session edited none of the sibling files.

## CONVERGENCE NOTE — most of this lane was already done

The Modron session's own audit round 2 (same day, its `court-mechanus`) independently
applied **9 of the 11 proposals before this handoff landed** — and chose the *same
re-bind targets* the Mechanus seam court verified:

- modifiers/planescape-2e.json: the 3 wildcard refs → `law:planar-conditions:general:school-alteration-legend`;
  the 2 wind-madness refs → `law:plane-environment:pandemonium:wind-madness` ✓
- conventions/2e-planescape.json: limbo wildcard → `law:planar-conditions:limbo`
  (sub-ids per `_id_scheme`); wind-madness + wasting → the minted ids
  (`…the-gray-waste:wasting-sickness`) ✓ — plus refs this docket never asked for
  (miniflux, styx-memory, the everymans-madness mint)
- rollables/planescape-2e.json line 47: pending-mint annotation upgraded ✓

Two independent audits, same verdicts, zero coordination — the id scheme did its job.
All their cited refs verified resolvable via `tables.planar_law()` on
`law_version 0d05d408b20e7314`.

## REMAINING — 2 items

### To the Modron session — conventions/2e-planescape.json line 85 (wasting_contraction notes)

The trailing sentence still reads:
> "Hope-drain carries no stated dice in the witness — prose color, Mimir's lane."

Proposed replacement:
> "Hope-drain is separately minted law (law:plane-environment:the-gray-waste:hope-drain
> — weekly save vs. spell); its progression check kind is a D5 follow-up, not this kind."

Why: the witness DOES state a weekly save vs. spell, and Mechanus minted the row
(resolves today). Whether to add a `hope_drain` check kind is your design call — this
only stops the notes from denying dice the witness states and from assigning the law
to Mimir. (Confirmed by the audit's refute panel, conf 0.85.)

### To the Mimir session — pipeline/mimir/REVIEW-5E.md §A line 38

Amend `conditions ∈ the 2014 14-set` → `conditions ∈ the 2014 15-set (incl. exhaustion)`.
Witnesses: SRD 5.1 Appendix PH-A pp.358-359 lists 15 condition headings (Exhaustion
among them); 5e-bits v5.9.0 2014 Conditions.json has 15 entries; the shipped
`mechanus/data/law/conditions.json` implementing the §A check carries 15. If
"14 + exhaustion-as-special" was the intent, say so explicitly — as written the count
contradicts the implemented closed set. No law-data change; `law_version` untouched.
