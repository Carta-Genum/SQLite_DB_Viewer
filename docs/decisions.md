# Architectural Decision Record

### 2026-03-06: GCP Cloud Run + GCS for cloud deployment
**Context**: Need weekly automated scraping with team-wide access to the latest spatial transcriptomics database. Minimal maintenance, low cost.
**Decision**: Use GCP Cloud Run (Job for scraper, Service for viewer) with GCS as the shared storage layer. Region europe-west4, public viewer, scale-to-zero.
**Alternatives**:
- Persistent VM (e.g. GCE with Docker Compose): simpler but always-on cost (~$15-30/mo), requires OS patching
- Cloud Functions: not suited for long-running scraper (30+ min), no container support for the viewer
- Firebase Hosting + Cloud Functions: viewer is dynamic (SQLite queries), not a good fit for static hosting
**Outcome**: Estimated $2-7/mo. Viewer scales to zero when idle. Scraper runs only when scheduled. GCS versioning provides rollback.
