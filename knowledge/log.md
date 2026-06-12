# Wiki Log

Append-only. One entry per INGEST / QUERY / LINT operation. See
`~/.claude/rules/llm-wiki.md` for the entry format.

<!-- Example entries (delete this block once the first real entry lands):

## [YYYY-MM-DD] ingest | Author 2024 -- Title
- source: docs/papers/author_2024.pdf
- pages touched: literature/author_2024.md (new), entities/genes/CXCL9.md, hypotheses/H1_b2m_high_immune_hot.md
- notes: confirms IFNg-driven CXCL9 induction; cited in H1 Evidence FOR.

## [YYYY-MM-DD] query | Does CXCL9 expression differ between islet types?
- pages consulted: entities/genes/CXCL9.md, hypotheses/H1_b2m_high_immune_hot.md
- new pages: none

## [YYYY-MM-DD] lint
- contradictions: none
- stale claims: H3_bystander_activation.md cites V04 but V05 superseded
- orphan pages: entities/cell_types/nk_cells.md not in index
- missing cross-refs: literature/zhang_2008.md not linked from H3

-->

## [2026-06-11] lint
- contradictions: none
- stale claims: none
- orphan pages: none (scaffold only)
- missing cross-refs: none
- notes: first lint after wiki scaffold creation; no content pages yet.

## [2026-06-12] ingest | Migrate 1 ADR from legacy docs/decisions.md
- source: `docs/decisions.md` (pre-migration; deleted in this PR)
- pages touched: `decisions/2026-03-06_gcp-cloud-run-gcs-for-cloud-deployment.md` (new); `index.md` populated.
- notes: Per cross-project legacy-memory deprecation spec. No `docs/journal_archive.md` to migrate (project never had one).

## [2026-06-12] lint | Pre-PR lint pass for legacy-memory deprecation
- contradictions: none
- stale claims: none
- orphan pages: none
- missing cross-refs: none
