<!-- markdownlint-disable -->
# ADR-0002 - Full retrofit authorized, superseding ADR-0001

- **Status:** Accepted
- **Data:** 2026-07-19

---

## Contexto

ADR-0001 decided on a partial retrofit for `kappa-streaming-lakehouse`'s compliance with `bundle-structure-standard`/`portfolio-conventions`: only low-risk additive items (this ADR's predecessor, the gap report, a `LICENSE` copy) would happen immediately, and the expensive items (the full 11-document RFC set, retroactive ADRs, `infra/` restructuring, `tests/` consolidation, CI) were deferred to a dedicated follow-up change, per this change's own non-goal of not rewriting or migrating `kappa-streaming-lakehouse`'s content.

The portfolio owner (project maintainer) subsequently reviewed the gap report directly and explicitly requested the full retrofit now, in this same session, rather than deferring it — overriding both the original non-goal and ADR-0001's alternative-3 decision.

## Problema

ADR-0001 is no longer an accurate record of what will happen. Does it get edited in place, or superseded?

## Alternativas

1. **Edit ADR-0001 in place** — Simpler, one file. Rejected: ADRs are meant to be an append-only decision log; editing a decision after the fact erases the record of what was actually decided and why at the time, which is the entire point of keeping ADRs.
2. **Supersede with a new ADR** — Mark ADR-0001 `Superseded by ADR-0002`, leave its original content untouched as a historical record, and record the new decision (full retrofit, authorized directly by the maintainer) here. Chosen: preserves the audit trail — a reader can see the standard's own compliance decision was itself revised once, and why.

## Decisão

Proceed with the full retrofit (ADR-0001's rejected "Alternative 1"), now explicitly authorized:
- Restructure `infra/` (`infra/compose/docker-compose.yml`, `infra/terraform/`, `infra/docker/`) and consolidate `tests/`.
- Rename and reshape `docs/trade-offs.md` → `docs/tradeoffs.md` into the required table format, linked to the new ADRs below.
- Write the full `rfcs/` set (`RFC-0000` … `RFC-0010`) with real content drawn from the existing README, `docs/flink-jobs.md`, and the codebase (`contracts/`, `cube/model/`, `db/migrations/`, `flink-jobs/`, `simulator/`).
- Backfill ADRs for the major decisions already made and previously only narrated in `docs/trade-offs.md` and commit history (Kappa vs. Lambda, catalog choice, Doris + Cube.js federation, medallion/ODCS contracts, and others surfaced during the retrofit).
- Add basic CI (lint + test) and a documented minimum coverage threshold, per `CONTRIBUTING.md`'s 70% baseline.
- Branch-naming (`feat/*` vs. `feature/*`, no `develop` branch) is a policy/process decision, not a file-content one — recorded as a documented exception rather than rewritten, since renaming branches retroactively would rewrite shared history across 8+ already-merged PRs.

## Consequências

- `kappa-streaming-lakehouse` becomes the collection's first fully (or near-fully) compliant reference bundle, replacing `templates/bundle/` as the concrete example once complete.
- Risk of rushed or synthesized RFC/ADR content is mitigated by grounding every document in facts extracted directly from the existing README, docs, and source code — not invented from scratch.
- The `feat/*` branch-prefix and missing-`develop` deviations remain open exceptions, documented here rather than silently fixed, since fixing them retroactively is out of scope for a content/structure retrofit.
