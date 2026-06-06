<!-- ENTITY CARD — the concatenable dramatis unit (card_version 1; MODRON §12 Q5
     ruling 2026-06-05: encounters assemble by concatenating cards).
     One entity, the full stat chain in one block:
       WHAT        (Mimir)    — served values + provenance, pinned by admission_sha
       WHAT SYSTEM (Mechanus) — the governing law + target numbers, witnessed
       HOW         (Modron)   — compiled roll specs + every flag, adjudicated
     A card is self-contained: drop it into encounter.md §3 unchanged; its
     run-sheet row concatenates into the §9 sheet. Pin admission_sha so a
     re-pour can't silently shift the card under the encounter.
     INLINE combatants (a retinue named only in an admitted envelope's prose):
     cite the parent envelope + field path + the prose flag's adjudication, and
     witness every derived mechanic from a quotable law lane (e.g. FG&G page
     tables) — provenance flows through the parent. -->

### <Name> — <one-line role in this scene>
- id: `<type:source:slug>` · admission_sha: `<full sha, exactly as served>` · conf: `0.NN` · loc: `<product>:p<NN>`
- role: <antagonist | wildcard | prize | bystander> · disposition: <posture / what turns it>
- law: <governing mechanics with witnesses — THAC0 bracket / save targets / DCs
  (page-cited or tool-cited) · rulings in scope (docket ids) · cross-view
  borrowings declared>
- rollables digest (source `handbook.db:<id>`): <the keys that matter at the table>
- flags: <each lawfulness_flag / requires_confirmation / suspect / UNCURED +
  adjudication (confirmed | cured at gate | struck) — or "none">
- run-sheet row:
  `| <name> | <#> | <AC> | <hp> | <THAC0/bonus> | <atk> | <damage> | <MR> | <morale> | <saves> |`
