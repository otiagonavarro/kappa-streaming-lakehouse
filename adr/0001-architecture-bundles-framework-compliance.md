<!-- markdownlint-disable -->
# ADR-0001 - Architecture Bundles Framework compliance strategy

- **Status:** Superseded by ADR-0002
- **Data:** 2026-07-19

---

## Contexto

The `architecture-bundles` portfolio adopted a governance standard (`openspec/changes/adopt-architecture-bundles-framework`, specs `bundle-structure-standard` and `portfolio-conventions`) defining the required directory layout, RFC/ADR set, and conventions every bundle must follow. `kappa-streaming-lakehouse` was built before this standard existed and was assessed against it in `docs/compliance-gap-report.md`. That report found the bundle functionally solid — working pipeline, thorough bilingual README, real trade-off analysis in `docs/trade-offs.md`, Conventional Commits already in use — but structurally non-compliant: no `rfcs/`, no `adr/` (until this file), no `LICENSE`, no top-level `tests/`, and an `infra/docker-compose.yml` instead of `infra/compose/docker-compose.yml`.

## Problema

Should `kappa-streaming-lakehouse` be fully retrofitted to the new standard immediately, partially retrofitted, or grandfathered in as-is with a documented exception?

## Alternativas

1. **Full retrofit now** — Write the entire mandatory RFC set (11 documents), migrate `docs/trade-offs.md` into individual ADRs plus a `docs/tradeoffs.md` summary, restructure `infra/`, add a top-level `tests/`, and add `LICENSE`. Pros: fully compliant immediately, becomes the collection's reference example. Cons: large scope, directly contradicts this change's own non-goal ("Rewriting or migrating `kappa-streaming-lakehouse`'s content in this change — only assessing and recording the gap"), and risks rushed, low-quality RFCs written after the fact rather than as design tools.
2. **Grandfather as-is, no changes** — Accept the gap report as the permanent record and make no further changes. Pros: zero effort, zero risk of breaking a working bundle. Cons: the bundle never converges with the standard, and low-risk, high-value fixes (adding a `LICENSE`, renaming an already-matching trade-offs doc) are left undone for no reason.
3. **Partial retrofit, prioritized by cost/value, executed as follow-up changes** — Do the low-risk additive items opportunistically (this ADR, a `LICENSE` copy once the portfolio root one exists, renaming `docs/trade-offs.md` → `docs/tradeoffs.md`), defer the expensive one (writing the full 11-document RFC set and backfilling ADRs for past decisions) to a dedicated follow-up change scoped and reviewed on its own. Pros: respects this change's non-goal, makes visible progress without a risky big-bang rewrite, keeps the gap report actionable instead of static. Cons: bundle stays partially non-compliant for a while; requires tracking follow-up work explicitly so it isn't forgotten.

## Decisão

**Alternative 3: partial retrofit.** Immediate scope (this ADR plus adjacent low-risk work, tracked in this change's own `tasks.md`):
- Add this ADR (`adr/0001-*.md`) — bootstraps the `adr/` directory itself.
- Add `docs/compliance-gap-report.md` (already done).
- `LICENSE` copy is added once the portfolio root `LICENSE` is published (task 4.2) — sequenced, not skipped.

Deferred to a dedicated follow-up change (not this one, per its non-goal):
- Writing the full `rfcs/` set (`RFC-0000` … `RFC-0010`), backfilling problem/architecture/domain/data-model/API/security/observability/scalability/failure-recovery content from what already exists in `README.md`, `docs/flink-jobs.md`, and `docs/trade-offs.md`.
- Renaming `docs/trade-offs.md` → `docs/tradeoffs.md` and reshaping it into the required table format once `adr/` has enough entries to link to.
- Adding a top-level `tests/` (or documenting `simulator/tests/` as the bundle's test location if consolidation isn't worth it).
- Restructuring `infra/docker-compose.yml` → `infra/compose/docker-compose.yml` (plus `infra/terraform/`, `infra/docker/` if/when Terraform or standalone Dockerfiles are introduced).
- Deciding whether to keep the `feat/*` branch prefix (already established across 8+ merged PRs) as a bundle-level exception, or rename to `feature/*` to match `portfolio-conventions` literally, and whether to introduce a `develop` branch or formally except direct-to-`main` merging.
- Adding CI (lint/format/test) under `.github/workflows/` and a documented minimum coverage threshold.

## Consequências

- `kappa-streaming-lakehouse` remains a documented partial exception rather than a silent gap — anyone auditing the collection can see exactly what's missing and why via `docs/compliance-gap-report.md` and this ADR.
- The bundle is not blocked or destabilized by this change; no existing content is moved, renamed, or deleted here.
- A follow-up change is required to close the remaining gaps (full RFC set, ADR backfill, `infra/` restructure, `tests/` consolidation, branch-naming exception decision, CI). Until that change lands, `kappa-streaming-lakehouse` should not be cited as the collection's fully-compliant reference example — `templates/bundle/` (from this change) is the reference until then.
