# Round: PWH equipment — item 106→143

**Date:** 2026-06-06 · **Commit:** c19a10c · **Store:** 891→928 entities, 1,988→2,028 edges

## What landed
- 38 ITEM_CARDS in parse/pwh.py + item lane in pour_pwh: 12 tools-of-the-trade
  (Baatorian green steel w/ armor+weapon tables — CELL-level verified-or-absent,
  illegible weights stay absent; bariaur gear ×5; modron gear ×3; celestial
  etheroscope; sickle; scythe) + 26 magical/protections (scythe/sickle family,
  planar wards/mancatcher/trap, fiend globe, grue bottle, shifters' manacles,
  seeker stones, transient sword, vambraces, Gehennan ring + Inner-Planar
  amulet — the latter a DISCLOSED descriptive handle, the book names the class
  not a proper item).
- 38/38 attested; 7 shredded heads recovered by the page's own OCR forms
  (8ARIAUR, BomED BREATII, CLOTIIJNG, CHAI s OF LIGHT, body-witness for the
  protection scroll, leader-name for Gnome's Home pattern).
- **Dual-source merge PROVED:** item:planar-wards — The Grixitt's Uncaged
  wields + PWH's mechanics card on ONE node. The marquee join.
- used_by edges: planar mancatcher→harmonium, shifters' manacles→mercykillers
  (used_by registered in REL_CATALOG).
- The 4 item-embedded d100 tables (fiend globe / grue bottle / breathing
  potion / protection scroll) = TABLE substance → handoff D13. The printed-136
  what-to-look-for survey = existing core/ToM items, cross-refs, never minted.

## Rail
suite 104 ✓ · integrity 0 hard · pin+verify RECONSTITUTED · ledgers.
