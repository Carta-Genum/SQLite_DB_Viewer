# 2026-03-06: GCP Cloud Run + GCS for cloud deployment

> Migrated from legacy `docs/decisions.md` by the 2026-06-10 legacy-memory
> deprecation chore. Format mapped: Context -> Why, Decision -> What was
> decided, Alternatives -> Alternatives considered, Outcome -> Consequences.

**Status**: ACCEPTED
**Owner**: Daniel Zucha
**ADR source**: `docs/decisions.md` (pre-migration) heading `### 2026-03-06: GCP Cloud Run + GCS for cloud deployment`

## What was decided

Use GCP Cloud Run (Job for scraper, Service for viewer) with GCS as the shared storage layer. Region europe-west4, public viewer, scale-to-zero.

## Why

Need weekly automated scraping with team-wide access to the latest spatial transcriptomics database. Minimal maintenance, low cost.

## Evidence

- Original ADR: `docs/decisions.md` heading `### 2026-03-06: GCP Cloud Run + GCS for cloud deployment` (file removed in this PR; see git history pre-`chore/migrate-legacy-memory`).
- Source registry: previously `S3` in `knowledge/sources/source_registry.md` (retired in this PR).

## Alternatives considered

- Persistent VM (e.g. GCE with Docker Compose): simpler but always-on cost (~$15-30/mo), requires OS patching
- Cloud Functions: not suited for long-running scraper (30+ min), no container support for the viewer
- Firebase Hosting + Cloud Functions: viewer is dynamic (SQLite queries), not a good fit for static hosting

## Consequences

Estimated $2-7/mo. Viewer scales to zero when idle. Scraper runs only when scheduled. GCS versioning provides rollback.

## Cross-references

- [Source Registry](../sources/source_registry.md)
- [Index](../index.md)
- Supersedes / superseded by: see git history of `docs/decisions.md` for
  chronological context.

**Last updated**: 2026-06-11
