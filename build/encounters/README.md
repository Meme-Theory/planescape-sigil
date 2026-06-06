# build/encounters/ — encounter artifacts

One directory per encounter: `<slug>/encounter.md` (the design artifact) +
`<slug>/runs/<session_id>.md` (one record per run, never overwritten).

- **Requirements:** `.claude/rules/encounters.md` (R1–R8 — the artifact law)
- **Formats:** `.claude/templates/encounter.md`, `encounter-run.md`
- **Direction:** `/encounter-plan` and `/encounter-run` skills
  (`.claude/skills/`), or the `encounter-director` agent for design/dry-runs

Skills are direction, rules are requirements, templates are formats.
Nothing here is hand-written from scratch; everything traces — entities to
`admission_sha`s, quotes to (product, page), rolls to a committed session,
rulings to dockets. Lineage: cross-validation.md §4, skill candidate #5.
