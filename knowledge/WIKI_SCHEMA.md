# WIKI_SCHEMA.md — SQLite_DB_Viewer Wiki Schema

> Per-project schema. Shared structure lives in `~/.claude/rules/llm-wiki.md`.

## Project flavor

**Flavor**: tooling

**Wiki purpose**: organize architecture, modules, integrations, and
decisions for the SQLite database viewer dashboard. See project `CLAUDE.md`
for stack and current phase.

## Entity types in use

- `entities/components/` — UI modules, query helpers.
- `entities/integrations/` — SQLite source, hosting.
- `entities/data_formats/` — table schemas the viewer expects.
- `entities/runbooks/` — local run, deploy.
- `decisions/` — ADRs.

## Project-specific page fields

TODO.

## Project-specific evidence tags

- `[ADR:NNN]`, `[PR:NNN]`, `[Issue:NNN]`, `[Commit:<sha7>]`.
