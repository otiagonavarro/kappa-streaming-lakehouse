<!-- markdownlint-disable -->
# RFC-0000 - Project Charter

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## Nome

Kappa Streaming Lakehouse

## Visão

Demonstrate, end-to-end and runnable, that a single streaming pipeline (Kappa architecture) can serve both real-time dashboards and historical reprocessing for an e-commerce clickstream, without a parallel batch pipeline — eliminating the batch/streaming divergence problem that Lambda architectures accept as a cost of doing business.

## Objetivos

- Ingest synthetic e-commerce clickstream events (`page_view`, `add_to_cart`, `purchase`) through Kafka (Redpanda) and process them exactly-once with Apache Flink.
- Land the same stream in an Iceberg lakehouse (via Nessie catalog, on MinIO/GCS object storage) for historical/analytical queries, and in PostgreSQL for sub-10ms serving queries — from one codebase, not two.
- Federate the lakehouse and the serving layer through Apache Doris, exposed to BI tooling through a Cube.js semantic layer.
- Demonstrate real Kappa-architecture capabilities live: full-history replay from Kafka offset 0, Iceberg schema evolution without file rewrites, and Iceberg time-travel queries.
- Model a realistic e-commerce domain (users, products, categories, orders, order items) via a wide-schema CDC-style `entity-updates` topic, not just raw clickstream.

## Não Objetivos

- Not a production-grade platform: default credentials, no TLS, no auth, no RBAC are all explicit, documented choices (see `rfcs/RFC-0006-security.md`) — the goal is architectural demonstration, not deployment-readiness.
- Not a general-purpose streaming framework — it's one opinionated, working instance of a Kappa architecture, not something meant to be imported as a library.
- Not attempting full feature parity with any single vendor's managed streaming/lakehouse platform.
- Not horizontally scaled in this demo — single-node Flink TaskManager, single-node Doris FE/BE, single-node Postgres. Scaling strategy is documented (`rfcs/RFC-0008-scalability.md`) but not exercised here.

## Escopo

In scope: event simulation, stream ingestion, stream processing (5 active Flink jobs), lakehouse storage, serving-layer storage, federated query layer, semantic layer, replay/reprocessing tooling, schema-evolution and time-travel demos.

Out of scope (tracked as roadmap gaps, `rfcs/RFC-0010-roadmap.md`): production security hardening, horizontal scaling, CI-enforced coverage gates, the two unwired Flink jobs (`entity_sync`, `order_ingestion`), and the currently-broken `time-travel-demo.sh` script.

## Glossário

- **Kappa architecture** — a streaming-only architecture where historical reprocessing replays the same stream pipeline from the beginning of the log, instead of running a separate batch pipeline (as in Lambda architecture).
- **Medallion architecture** — layered data quality tiers: Bronze (raw), Silver (validated/enriched), Gold (aggregated for consumption).
- **ODCS** — Open Data Contract Standard; used here to drive the raw-event Flink job's Kafka source and Iceberg sink DDL directly from a contract file at runtime.
- **Entity-updates topic** — a single Kafka topic carrying wide, nullable-schema CDC-style updates for every dimension/fact entity (`user`, `product`, `category`, `order`, `order_item`).

## Stakeholders

- **Primary:** the `architecture-bundles` collection's readers — engineers and architects studying Kappa/lakehouse patterns.
- **Maintainer:** Tiago Ribeiro Navarro de Andrade.

## Roadmap Inicial

See `rfcs/RFC-0010-roadmap.md` for the full, current roadmap. Initial milestones: v0.1 (Kafka→Flink→Iceberg core pipeline), v0.2 (PostgreSQL serving + session/funnel aggregation), v0.3 (medallion contracts + e-commerce entity model), v0.4 (Doris + Cube.js federation) — all four already shipped as of this charter. v1.0 (full `bundle-structure-standard` compliance, this retrofit) is in progress.

## Referências

- `README.md` — architecture overview, quickstart, technology rationale.
- `docs/flink-jobs.md` — per-job Flink implementation details.
- `openspec/specs/bundle-structure-standard/spec.md`, `openspec/specs/portfolio-conventions/spec.md` (portfolio root) — the governance standard this charter brings the bundle into compliance with.
