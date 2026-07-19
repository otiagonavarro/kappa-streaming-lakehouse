<!-- markdownlint-disable -->
# Compliance Gap Report: `bundle-structure-standard` / `portfolio-conventions`

Produced for `openspec/changes/adopt-architecture-bundles-framework` task group 3. Assesses `kappa-streaming-lakehouse` — the only bundle that predates the standard — against `openspec/specs/{bundle-structure-standard,portfolio-conventions}/spec.md` (portfolio root repo).

> **Update (2026-07-19):** the table below is a point-in-time snapshot from the initial assessment. It is kept unedited as the historical record. The gaps it lists were subsequently closed by the full retrofit authorized in `adr/0002-full-retrofit-authorized.md` — `rfcs/`, `adr/`, `LICENSE`, `infra/{terraform,docker,compose}/`, `services/`, top-level `tests/`, `docs/tradeoffs.md`, and CI now all exist. Remaining known gaps (unwired Flink jobs, broken time-travel demo, no DLQ, untested GCS path, no enforced coverage gate, `feat/*` branch-naming exception) are tracked in `rfcs/RFC-0010-roadmap.md`, not silently closed here.

## Legend

✅ Present and compliant · ⚠️ Present but partial/misplaced · ❌ Missing

## `bundle-structure-standard`

| Requirement | Status | Notes |
| --- | --- | --- |
| Bundle directory layout | ⚠️ | Has `docs/`, `assets/`. Missing `rfcs/`, `adr/`, `diagrams/`, `examples/`, `services/`, top-level `tests/`, `LICENSE`. Has `infra/docker-compose.yml`, not the required `infra/{terraform,docker,compose}/` split — no Terraform or standalone Dockerfiles currently exist to justify the subdivision. Domain code lives in bundle-specific top-level dirs (`flink-jobs/`, `simulator/`, `cube/`, `db/`) rather than under `services/`. |
| Mandatory RFC set | ❌ | No `rfcs/` directory. Problem framing and architecture live in `README.md` ("The Problem", "The Solution", "Architecture" sections) instead of numbered RFCs. No domain model, data model, API/contracts, security, scalability, or roadmap RFC exists as a standalone document. |
| RFC content minimums | ❌ | N/A until `rfcs/` exists — see above. |
| ADR usage | ❌ | No `adr/` directory. Significant decisions (Kappa vs. Lambda, Nessie catalog, Doris + Cube.js federation, medallion contracts) are narrated in `docs/trade-offs.md` and commit messages, but not recorded as individual ADRs with alternatives/decision/consequences. |
| Diagrams as versioned artifacts | ⚠️ | Architecture diagram exists as an embedded Mermaid `flowchart` in `README.md` — compliant in spirit, but not under a dedicated `diagrams/` directory as the requirement expects. |
| Operational documentation | ⚠️ | Has `docs/flink-jobs.md` and operational scripts (`scripts/healthcheck.sh`, `scripts/reprocess.sh`, `scripts/schema-evolution-demo.sh`, `scripts/time-travel-demo.sh`) but no dedicated runbook, playbook, troubleshooting guide, or FAQ document. |
| Executable and testable implementation | ⚠️ | Runs via `infra/docker-compose.yml` (not the required `infra/compose/docker-compose.yml` path) and has a `Makefile`. Automated tests exist only under `simulator/tests/`, not a top-level `tests/`. |
| Optional supplementary materials | ✅ | No loose attachments at bundle root; what exists lives under `docs/`. |
| Cross-cutting trade-off summary | ⚠️ | `docs/trade-offs.md` already does almost exactly this — five detailed trade-off comparisons — but is named `trade-offs.md` (not `tradeoffs.md`) and predates `adr/`, so it can't yet link back to ADRs. Closest-to-compliant item in the whole bundle. |
| Bundle completion acceptance criteria | ❌ | Blocked on the RFC set and ADRs above; problem, architecture, implementation, and tests are otherwise in reasonable shape. |

## `portfolio-conventions`

| Requirement | Status | Notes |
| --- | --- | --- |
| Commit message convention | ✅ | `git log` shows consistent `feat:`, `fix:`, `docs:` prefixes — already Conventional Commits. |
| Branching model | ⚠️ | Branches follow `feature/*`→`feat/*` (non-standard prefix: `feat/` not `feature/`), `fix/*`, `docs/*` naming and merge to `main` via PR. No `develop` branch — feature branches merge directly to `main`. Prefix and missing `develop` are both deviations from the spec's literal `feature/*` naming and two-tier branching. |
| Versioning and licensing | ❌ | No `LICENSE` file in the bundle, and the portfolio root `LICENSE` doesn't exist yet either (portfolio-level gap, tracked as task 4.2). No version tags found. |
| Quality gates | ⚠️ | `flink-jobs/pyproject.toml` and `simulator/pyproject.toml` exist (dependency + likely lint/format config), but no `.github/` CI workflow was found, and no documented minimum coverage threshold. |
| README as entry point | ✅ | `README.md` (and `README.pt-BR.md`) already covers what/problem/how-to-run/architecture/technologies — the strongest-compliing document in the bundle, and a reasonable model for the README template. |
| Existing bundle compliance tracking | ✅ | This report is that documented gap assessment. |

## Summary

`kappa-streaming-lakehouse` is functionally solid (working pipeline, thorough README, real trade-off analysis, clean commit history) but structurally predates the standard: it has no `rfcs/`, `adr/`, or `LICENSE`, and its existing `docs/trade-offs.md` and `infra/docker-compose.yml` are one rename/move away from compliance rather than needing to be rebuilt. The retrofit decision (full / partial / grandfathered) is recorded in `adr/0001-architecture-bundles-framework-compliance.md`.
