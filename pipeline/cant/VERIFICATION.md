# cant — V&V report (live-wire ceremony)

**Date:** 2026-06-06 · **Engine:** v1 · **Lexicon:** 362 terms (118 core / 244 ext)
· **Rewrites:** 20 templates / 128 subs / 3 seasonings · **Vectors:** 362×384,
MiniLM-L6-v2 (model sha `6fd5d72fe458…`, PROVENANCE-pinned) · **Store at close:**
COMPILED (built 2026-06-06, 100 dialog lines, 422 prose entities, 83 terms attested)

Designed-then-executed, four layers. **Layer B ran through the LIVE session MCP
connection** (the real client wire, not a test subprocess) — the same transport
the table will use. Verdict: **all probes PASS · 0 engine defects** · 2 doc-drift
corrections (counts in CANT.md §2, fixed this pass).

The handbook **poured twice during the ceremony** (Meme's In-the-Cage session,
prose 390→396→422). Unplanned, and the best witness the freshness law could ask
for: every tool's store note flipped STALE within one call of each pour, named
the fix, and recovered on re-harvest — no reconnect at any point.

## Layer A — offline foundations

| probe | verdict |
|---|---|
| A1 `cant/gears.py` self-test (matcher law: word/inflect/phrase-boundary/none+loose/hyphen/curly/variants/candidates/snippet) | PASS |
| A2 `cant/embed.py` self-test (shape, L2 norm, ranking sanity bribe~garnish 0.569 ≫ weather 0.043, byte-determinism) | PASS |
| A3 pytest pack — **33 passed** (incl. 2 guards ADDED this ceremony: A5 backref-vs-capture-group audit over every rewrite `out`; A6 sidecar integrity — shape/alignment/norms/lexicon-sha/model-sha-vs-PROVENANCE) | PASS |
| A4 `smoke_server.py` through the EXACT `.mcp.json` spawn — **16/16** | PASS |

## Layer B — live wire (session MCP, 15 probe families)

| probe | verdict | witness |
|---|---|---|
| B1 `cant_info` shape + truth | PASS | caught a REAL stale (pour had landed); counts/tiers/sources/thresholds correct |
| B2 `transmute` contract | PASS | 3 candidates, auditable `applied` trace, attested palette, store note, lane notes |
| B3 determinism | PASS | repeat call → byte-identical candidates incl. traces |
| B4 density ladder | PASS | `never→when the Lady speaks` fired ONLY at heavy; min_density disclosed; its grammar-warning note rode along |
| B5 attitude poles | PASS | hostile→berk, friendly→cutter, neutral→none (no 2nd person) |
| B6 single-address law (D1 regression input) | PASS | one address, no `{addr}` remnants |
| B7 register bias | PASS | register=stern → all corpus exemplars stern |
| B8 negative control | PASS | weather: 0 applied / 0 suggestions / 0 concepts, input untouched at all densities |
| B9 `decode` | PASS | 9 hits; strict vs loose split exact (`dark?`, `greens?` flagged; `a body` phrase-matched; inflection `greens`→green) |
| B10 `suggest_terms` matrix | PASS | blend visible (oasis lex 1 + cos 0.571; bub semantic-only 0.449); tier+cat → exactly jink; `semantic=false` → lexical-only, bub gone |
| B11 `examples` + **cross-MCP provenance** | PASS | speaker/term/register filters exact; served `dialog:uncaged:b30b04e4ccc4` re-fetched from LIVE Mimir — text/register/owner/page match; id stable across the day's re-pour |
| B12 refusal lane | PASS | whitespace transmute / empty decode / whitespace suggest → structured ERROR ×3 |
| B13 model door | PASS | method=model, no key → honest refusal + how_to_enable + rule candidates standing, method stayed `rule` |
| B14 unicode transport | PASS | curly quotes/em-dash/ellipsis in and out unmangled; template matched inside “…” |
| B15 usage telemetry | PASS | counters 36→69 across ceremony, per-tool deltas consistent, last_called moves |

## Layer C — freshness drills (the growth loop, live)

| drill | verdict | witness |
|---|---|---|
| C1 STALE detect→fix→recover | PASS ×2 | both NATURAL (real pours landed mid-ceremony); detector tripped on next call, re-harvest flipped COMPILED **without reconnect** (mtime-fresh law on the wire) |
| C2 vectors-absence degrade + recover | PASS | `mv vectors.npz` aside SUCCEEDED against the running server (**no held handle** — the Windows lock law witnessed); live call → `semantic.enabled:false` + why + fix, lexical results still served; restore → cosine 0.5849 back, no reconnect |
| C3 rewrites live-reload | PASS | drill rule planted via edit → fired on next live call (trace carried its REMOVE-note) → reverted → gone; zero reconnects |

## Layer D — robustness

| probe | verdict | witness |
|---|---|---|
| D1 latency | PASS | transmute 4.8 ms/call mean, suggest_terms 3.2 ms (semantic encode included; single-thread ORT) |
| D2 long input | PASS | 6,150 chars → 98 ms, 6 rules applied, content checks hold |
| D3 adversarial input | PASS | regex metachars (`\1 [or] {else} ^and$ (?:guards)`) pass through untouched — no re.error, input `\1` never expands (expand applies to rule outs only); subs still land around them |

## Defects

**Engine: none found.** The ceremony's only corrections were documentation
drift (CANT.md §2 counts: subs 121→128, tiers 117/245→118/244 — fixed) and two
NEW standing guards added to the pytest pack (A5 backrefs, A6 sidecar
integrity), now part of every future run.

Prior defects D1–D4 (double-address, suggest leak, snippet degenerate, decode
phrase recall — CANT.md §7) remain pinned and passing.

## Repro

```bash
py -3.13 pipeline/cant/cant/gears.py          # A1
py -3.13 pipeline/cant/cant/embed.py          # A2
cd pipeline/cant && py -3.13 -m pytest tests/ -q     # A3 (33)
py -3.13 pipeline/cant/smoke_server.py        # A4 (16) — from repo root
# Layer B/C: live tools through a connected client; drills per this report
```
