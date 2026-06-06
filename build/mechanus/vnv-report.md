# Mechanus V&V Report — 2026-06-05

**Scope:** comprehensive verification & validation of the Mechanus MCP server v0
(mechanical core, law tables, rulings ledger, Modron seam), executed over the **live
MCP stdio transport** as registered in `.mcp.json` — the exact path play will use.
**Method:** every probe's expected value stated *before* the call; ground truth = the
SRD PDFs on disk, the docket law (MECHANUS.md §5–6), and independent recomputation.
**Environment:** Win11, py launcher → Python 3.13.13, `law_version 018b2eed42e9afe7`.

**Verdict: PASS — 47/47 live probes behaved as predicted** (two of those predictions
were defects, F1/F2, found in pre-probe review, confirmed live, fixed, and pinned as
tests). Suite: **107 passed** post-fix. The in-process suite (104→107 tests incl. the
334-monster fleet audit) remains the regression net; this report covers the transport.

---

## Phase 1 — Surface conformance (10/10)

| probe | expected | actual |
|---|---|---|
| `law_info` | version `018b2eed42e9afe7`, every table cited | ✓ 9 tables, all `_source`d |
| `usage_stats` | persistent counter | ✓ counts from prior smoke present |
| 8 parked tools (`view`, `rule_search`, `rule_quote`, `delta`, `resolve`, `convert`, `apply_influence`, `answer_key`) | each refuses `NOT_POURED`, names Mimir's §9 steps 1–4 | ✓ all 8, full message |

## Phase 2 — Law tables vs print (12/12)

| probe | expected (page) | actual |
|---|---|---|
| DC ladder, 5e-2024 | 6 rungs 5–30, cite p.6 | ✓ |
| 'nearly impossible', 5e-2014 | 30, cite p.77 | ✓ |
| 'brutal' | error listing the ladder | ✓ |
| DC under view=2e | refusal: 2e is roll-under; dice → Modron | ✓ |
| Budget, 4×L1 low | **200** (SRD 5.2.1 p.202 Example 1) | ✓ 200 |
| Budget, 6×L15 high | **46,800** (p.203 Example 3) | ✓ 46,800 |
| Budget, 1×L20 high / boundary | 22,000 | ✓ |
| Budget, mixed [3,3,4,5] moderate | 1,575 | ✓ with per-character breakdown |
| Budget, view=5e-2014 | `LawUnavailable` naming SRD 5.1's lack of encounter math | ✓ |
| Budget, level 0 / difficulty 'brutal' | ValueErrors | ✓ both |
| `attribution` | verbatim legal-page blocks, correct per-view URLs | ✓ both blocks |

## Phase 3 — `is_lawful` battery (22/22)

**Entities (5):**
- vrock → lawful, view **inferred 5e-2014**, 11 pass/1 skip; PB 3, XP 2300, HP 104=⌊104.5⌋, saves, passive all `pass` ✓
- aboleth → lawful, view **inferred 5e-2024 from url**; expertise math (History 12=4+2·4, Perception 10=2+2·4) ✓
- lich (waivers on) → **lawful**, `waived: [skill_bonuses_math]`, p.325 witness in the docket ✓
- lich (waivers off) → **unlawful**, same check fails ✓
- spider → unlawful, `passive_perception_math expected 10 actual 12` — the upstream 5e-bits mis-key, still caught ✓

**Corruption battery (12/12 single-field corruptions, each tripping its named check):**
pb→`pb_matches_cr` (+F3 cascade, below) · xp→`xp_matches_cr` **soft, stays lawful** ·
hp→`hp_matches_roll` · ac 30→`ac_in_range` · speed 42→`speeds_multiple_of_5` ·
passive→`passive_perception_math` · save+1→`save_bonuses_math` · skill mod+3PB→
`skill_bonuses_math` (passive computed from the *stated* skill still passed — checks are
independent) · 'befuddled'→`conditions_known` · 'x-ray vision'→`senses_known` ·
STR 35→`abilities_present_in_range` · CR 0.3→`cr_valid` with dependent checks
**skipping gracefully**, no crash.

**2e + shapes (5):** Otyugh bare-2e all-pass (morale "champion (14)"→14, MR "None"→0) ·
A'kin `12+24` plus-bump → THAC0 7, hp 92∈[36,120] · THAC0 mismatch → **soft only,
lawful stays true** · `1/2` HD → F1 confirmed live (below) · garbage entity → clean
adapter refusal naming the four shapes.

## Phase 4 — Ledger docket law + the Modron seam (16/16)

The reciprocity contract, executed for real:

1. `session_open` → commitment **`cf12f7fb…`** published before any die fell
2. `roll 1d20` on the committed stream → **13**, `rol:mechanus-vnv-…:00001`
3. `record_ruling rul:vnv:loot-recipient:001` **citing that roll_id** → sha `4e001d29…`, ts, law_version stamped
4. **Dup-content rejected by sha even under a fresh ruling_id** ✓
5. Docket-law battery — 6/6 violations rejected with exact messages: no-why-on-rejected ("loser preservation"), two ADOPTED, zero ADOPTED, scope 'party', confidence 1.5, rolls=[42] ("dockets cite dice, never contain them")
6. `overrule` → `:002` (compensation ruling); **history preserved**; `ruling_chain` walks `[:001, :002]` from the old id ✓
7. Double-overrule of `:001` → rejected, "chain from the head" ✓
8. `precedents("portal compass", scope)` → FTS hit resolving to **the head** (`:002`) only; unrelated topic → `[]` ✓
9. `house_rules` scoped: present in `table:vnv`, absent in `campaign:elsewhere` ✓
10. `modron verify(roll_id)` → **PASS** (faces/total/sha re-derived) ✓
11. `session_close` → seed revealed; **commitment independently recomputed: `sha256(seed) == cf12f7fb…` VERIFIED** ✓

## Phase 5 — Cross-witness + regression

- **Sibling witness agreement:** Modron `dice_stats(11d10+44)` (exact convolution) →
  mean **104.5**; Mechanus `hp_matches_roll` (closed-form N·(S+1)/2+K) → **104.5**.
  Independent implementations, identical law. ✓
- **Regression:** pytest **107 passed** (incl. the pinned 334-monster fleet audit:
  326 lawful / 3 waivered print-deviations / 5 upstream bugs / 4 halved-XP softs).

## Findings

| id | severity | finding | disposition |
|---|---|---|---|
| **F1** | defect | fractional HD (`1/2` — real 2e monsters) hard-failed both 2e checks as "unparseable", though the <1 bracket existed for them | **FIXED**: `parse_hd_2e` handles `N/M`; HP range floors/ceils with the 2e min-1-hp clamp; pinned (`test_f1_…`) |
| **F2** | defect | `1-1` HD scored THAC0 19; canonical row is "1-1 *or less*: 20" (the kobold row) | **FIXED**: minus-HD demotes at the 1 boundary; pinned (`test_f2_…`) |
| **F3** | design note | corrupting PB also fails save/skill math — checks trust the *stated* PB, so a wrong PB un-derives the whole block | **INTENDED**, now pinned as deliberate (`test_f3_…`) |

*F1/F2 are in the package now; the running server picks them up on next `/mcp` reconnect
(stdio server loads code at spawn). `law_version` is unchanged — data files untouched;
recorded dockets stay pinned to `018b2eed42e9afe7`.*

## Residual risks (named, not hidden)

- **5e-2024 witness thinness:** 5e-bits `2024/` has 3 monsters, no Spells/Rules — 2024
  lawfulness is validated on shape, not fleet-audited. Re-audit when upstream lands or
  when the 5.2.1 pour (§9 step 2) gives us our own set.
- **2e checks are bracket-level:** FG&G harvest outliers (HD 13→8, HD 20→5) are recorded
  in `thac0_2e.json` evidence, severity soft by design — 2e prints deviate by author intent.
- **Parked tools** are contract-tested (refusal shape) but their real behavior is
  unbuilt until Mimir pours; nothing here validates future `view()` semantics.
- V&V wrote two real rulings + one house rule under `table:vnv` scope in the production
  ledger — harmless, scoped, and themselves evidence; delete via supersede if unwanted.

— *Mechanus V&V, executed by the Mechanus session; every number above is reproducible
from the transcript, the suite, or the ledger.*
