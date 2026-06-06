---
name: cant
description: Transmute plain English into Sigil street cant (or decode cant back) via the cant MCP — sentence in, suggested results out, then table-polish; --speak renders it aloud through dabus. Use when the DM wants a line "in cant", an NPC to talk like a Cager, a cant line SPOKEN in a voice, cant text glossed, or cant vocabulary for a concept. Args: "<text>" [light|street|heavy] [friendly|neutral|hostile] [main|amused|stern|grave] [decode] [--speak [voice|npc:<id>]].
---

# /cant — the table veneer over the cant MCP

The ENGINE is the cant MCP (`pipeline/cant/CANT.md`); this skill is direction
for using it at the table. The engine suggests; you polish; the DM decides.

## Direction

1. **Engine first, always.** `transmute(text, density, attitude, register)`
   — never invent cant from memory without the palette in front of you.
   Input IS cant already (or the DM says "decode")? → `decode(text)` instead.
2. **Present tight:** the requested-density candidate on top, the other two
   as alternates, then (only if useful) 2-3 palette picks with their lexicon
   defs. With attestations, cite them short — `(A'kin, Uncaged p9)`.
3. **You MAY polish fluency** — reorder clauses, fix grammar the rule
   composer bent — but every cant TERM must come from the engine's palette,
   lexicon, or corpus exemplars. An invented term is provenance fraud;
   if the palette is thin, say so and call `suggest_terms` for more.
4. **Corpus outranks invention:** when `corpus_examples` serves an attested
   line in the right register, steal its rhythm and say where it came from.
5. **Knobs** (from args or ask only if the DM's intent is unclear):
   density light/street/heavy · attitude friendly/neutral/hostile (cutter vs
   berk) · register main/amused/stern/grave (the dialog dimension's axis).
6. **NPC voice:** for "make X say it", `mimir trace_entity(X)` → their
   dialog lines + registers, then bias word choice toward terms X actually
   uses (`examples(speaker=X)` shows them). The engine's persona param is
   queued (CANT.md §9 Q3) — until then, this skill IS the persona layer.
7. **--speak (the dabus handoff, D11):** call `voiceover` instead of
   `transmute` — voice= a pack name, or npc= a Mimir id (cast via dabus's
   speakers.toml; an UNCAST npc refuses — offer the DM the cast line to add,
   never guess). Then fire `speakable.args` at dabus `speak` VERBATIM — the
   payload is the contract; editing it between the two calls breaks the
   replay law (same English ⇒ same WAV). Report render_id + file + duration.
   If the DM wants a different take of the SAME line: dabus
   `force_render=true`, not a re-transmute.
8. **Store notes are law:** `STALE` → offer `py -3.13 pipeline/cant/harvest.py`
   after the session; `LEXICON-ONLY` → corpus examples are unavailable, say so.
9. **Lane law:** no store writes, no rulings, no dice. If the DM wants a new
   term ADDED, that's a curation edit to `pipeline/cant/data/lexicon.json`
   (with a source) + a harvest re-run — offer it, don't sneak it.

## Output shape

> **street:** Pike it, berk — the Hardheads scragged him at the gate.
> *alt (light):* … · *alt (heavy):* …
> *palette:* scragged = arrested (core, attested ×3) · …
> *(exemplar: "A body does not jink the dead-book today, yes?" — Xideous, Uncaged p115)*

Decode mode: glossed text first, then the hits table; `?`-flagged hits are
common-English collisions — read them in context before trusting.
