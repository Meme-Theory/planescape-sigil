# Planescape DM Project — Content Corpus

Everything in this folder was gathered from **legitimately free sources**: Creative
Commons / OGL rules text, fan-made content distributed free by its authors, and
CC-BY-SA wiki text. **No pirated scans of official TSR/WotC products live here.**
Official books you own go in `official/` — the pipelines will ingest whatever you
drop there. See `official/CATALOG.md` for the full product line and where to buy.

## Layout & Provenance

| Folder | What | Source | License / status |
|---|---|---|---|
| `official/` | **USER DROP FOLDER** — your purchased PDFs | you | your copies |
| `srd/srd-5.1/` | D&D 5.1 SRD (PDF + full markdown repo) | media.wizards.com, github OldManUmby/DND.SRD.Wiki | CC-BY-4.0 |
| `srd/srd-5.2/` | D&D 5.2.1 SRD (2024 rules) | media.dndbeyond.com | CC-BY-4.0 |
| `srd/json-data/5e-database/` | SRD as structured JSON API data | github 5e-bits/5e-database | MIT/CC-BY |
| `srd/json-data/open5e-api/` | Open5e data: SRD + Kobold Press OGL monsters etc. | github open5e/open5e-api | OGL/CC mix, per-source |
| `retroclones/for-gold-and-glory/` | **AD&D 2e retroclone** (382p) — our 2e mechanics reference | free PDF by Justen Brown | OGL, free |
| `retroclones/osric/` | AD&D 1e retroclone (OSRIC 2.2) | archive.org (free-distribution license) | OGL/OSRIC license |
| `retroclones/basic-fantasy/` | Basic Fantasy RPG r107 | archive.org | open, free distribution |
| `fan/planewalker-public-files/` | **THE PLANEWALKER ARCHIVE** (662MB): PSCS 3.0/3.5 + 4e draft, Adventure Hook Junction, Sigil NPC/venue/gods lists, SIGIS zines, Ortho setting, WotC PLANESCAPE-L mailing-list archive, pronunciation WAVs | archive.org `planewalker-public-files` | fan content, freely distributed |
| `fan/planewalker-pscs/` | Planar Mage (Mage: the Ascension × Planescape conversion) | planewalker.com | fan content |
| `fan/mimir-netbooks/` | mimir.net netbook PDFs: PSCS chapters 1–9, 2e netbooks (Bariaur, Doomguard, Beastlands, Elemental…), Monstrous Compendium netbooks, **Factol's Manifesto 5e conversion** | mimir.net (site live & active 2026) | fan content |
| `fan/mimir/` | Full mimir.net corpus: ~1,835 posts + pages as WordPress JSON (factions, planar races, cant, essays) + extra linked files | mimir.net wp-json API | fan content (Jon Winter-Holt et al.) |
| `fan/fanzines/` | The Bone-Box Rattler #1 (PDF + OCR text) | archive.org | fanzine |
| `fan/5etools-homebrew/` | Fan 5e JSON: PS:T bestiary, Carceri adventure, Dante's Inferno bestiary, Far Realm features | github TheGiddyLimit/homebrew | fan content |
| `fan/github-repos/` | city-of-doors (interactive Sigil map + tiles), sigil-map Foundry module, BG3 Planescape mod, **Planescape MUD world/area files**, campaign-notes repos | github, per-repo | per-repo |
| `fan/web-supplements/` | 1d4chan Planescape (via 1d6chan), Planar DM resources page, acaeum index | various | CC-BY-SA / reference |
| `wikis/wikipedia/` | 52 articles: setting, boxed sets, every module, races, planes | en.wikipedia Special:Export | CC-BY-SA 4.0 |
| `wikis/fandom-planescape/` | planescape.fandom.com full export (~800 pages) | MediaWiki API | CC-BY-SA |
| `wikis/fandom-torment/` | torment.fandom.com full export (~1,450 pages — PS:T + Tides) | MediaWiki API | CC-BY-SA |
| `wikis/forgotten-realms-wiki/` | FR wiki planar categories (544 pages: planes, Sigil, archdevils, demon lords, modrons, gith…) | MediaWiki API | CC-BY-SA |
| `wikis/timaresh/` | Timaresh Planescape wiki (~700 pages) | rilmani.org/w/api.php | CC-BY-NC-SA |
| `wikis/planar-legends-mud/` | Planar Legends (Planescape MUD) wiki (~700 articles) | wiki.planarlegends.com | fan content |
| `_meta/` | Fetch/export scripts (re-runnable), search indexes, link lists | this project | — |

## Formats on hand (pipeline targets)

- **MediaWiki XML** (`<page><revision><text>` wikitext) — all of `wikis/`
- **WordPress REST JSON** (`content.rendered` HTML) — `fan/mimir/`
- **5etools JSON** (statblock schema) — `fan/5etools-homebrew/`
- **Open5e / 5e-database JSON** (clean SRD schema) — `srd/json-data/`
- **Markdown** — `srd/srd-5.1/markdown/`
- **PDF** (born-digital, text-extractable) — netbooks, PSCS, SRDs, retroclones
- **MUD area files** — `fan/github-repos/planescape-mud__planescape_world/`
- **Mailing-list mbox/digests** — `fan/planewalker-public-files/extracted/WizardsEmailListArchives/planescape-l/`

## Regenerating / extending

All fetchers live in `_meta/*.sh`. Notable: `wiki_export_fixed.sh` (CRLF-safe
MediaWiki bulk export — native Windows jq emits `\r\n`, always `tr -d '\r'`),
`mimir_pull.sh`, `mimir_files.sh`, `frwiki_export.sh`. Git Bash gotcha: `/tmp`
doesn't resolve for native exes — use `_meta/tmp/`.

## Known gaps (deliberate)

- Official TSR/WotC PDFs: **buy-and-drop**, see `official/CATALOG.md`
- DMs Guild free/PWYW titles: checkout-gated, listed in CATALOG instead
- PS:T game text (`dialog.tlk`): copyrighted game data — convert from your GOG copy if owned
- Audio/video (podcasts, actual plays): indexed in `_meta/archive-org-search.json`, not mirrored
