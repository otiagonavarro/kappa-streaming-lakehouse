<!-- markdownlint-disable -->
# RFC-0010 - Roadmap

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## v0.1 — v0.4 (Shipped)

- v0.1 — Core Kafka → Flink → Iceberg pipeline (`raw_event_ingestion`).
- v0.2 — PostgreSQL serving layer, session aggregation, product funnel (`session_aggregation`, `product_funnel`).
- v0.3 — Bronze/Silver/Gold medallion architecture with Data Contract Specification contracts; e-commerce entity model (star schema) via the `entity-updates` topic.
- v0.4 — Apache Doris + Cube.js federation as the semantic/BI layer.

## v1.0 — `bundle-structure-standard` Compliance (In Progress)

- `rfcs/`, `adr/`, `LICENSE`, `infra/{terraform,docker,compose}/`, `services/`, top-level `tests/`, `docs/tradeoffs.md`, and basic CI — this retrofit.

## Known Gaps (Not Yet Scheduled)

Recorded here rather than silently left undocumented — each is a real, verified gap found during the `bundle-structure-standard` retrofit:

- **Two orphaned Flink jobs** — `entity_sync.py` and `order_ingestion.py` exist in `services/flink-jobs/src/` but are not included in `infra/job-submitter/submit_jobs.py`'s `JOBS` list, so they never run. Either finish wiring them in or remove them.
- **Broken time-travel demo** — `scripts/time-travel-demo.sh` calls `scripts/get-iceberg-metadata-path.py` and `scripts/count-iceberg-rows.py`, neither of which exists in the repository. The demo currently fails.
- **No dead-letter queue** — malformed events are silently dropped during Silver validation instead of being routed to a DLQ topic (`rfcs/RFC-0009-failure-recovery.md`).
- **Untested GCS path** — `STORAGE_BACKEND=gcs` is documented and code-supported but has no evidence of ever having run against real GCS.
- **No CI-enforced coverage gate** — CI (`.github/workflows/ci.yml`) reports simulator test coverage but does not yet fail below `CONTRIBUTING.md`'s 70% floor, since no coverage baseline had been measured before this retrofit. `services/flink-jobs` has zero automated tests.
- **No contract compatibility checks** — nothing automatically verifies backward compatibility between versions of the ODCS/Data Contract Specification contract files.
- **Branch-naming exception** — uses `feat/*` (not `feature/*`) and merges directly to `main` with no `develop` branch, both deviations from `portfolio-conventions`. Documented as an accepted exception (`adr/0002-full-retrofit-authorized.md`) rather than retroactively rewritten, since renaming branches would rewrite shared history across 8+ already-merged PRs.
- **No production security posture** — by design for now; see `rfcs/RFC-0006-security.md`. Revisiting this is a prerequisite for any deployment beyond local Docker Compose, not a "nice to have."

## Melhorias Futuras

- Real metrics/tracing/dashboards (`rfcs/RFC-0007-observability.md` gap).
- Horizontal scaling exercise: multiple Flink TaskManagers, multiple Kafka partitions/brokers, multiple Doris BE nodes (`rfcs/RFC-0008-scalability.md`).
- Incremental (rather than batch-recomputed) `user_360`.

## Refatorações

- Reconcile the two coexisting contract standards (ODCS for `raw_events`, Data Contract Specification 1.1.0 for the medallion layers) — either standardize on one, or explicitly document why both are appropriate for their respective use cases.
