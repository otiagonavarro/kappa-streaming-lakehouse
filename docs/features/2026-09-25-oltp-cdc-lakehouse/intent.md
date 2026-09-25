<!-- markdownlint-disable -->
# Intent: OLTP + CDC + Lakehouse Redesign

**Date:** 2026-09-25 · **Status:** Approved · **Owner:** Tiago Navarro

## Problem Statement

The project claims a Kappa streaming lakehouse over a realistic e-commerce domain, but the current implementation does not hold up under technical review:

- **The domain is not a real application.** Entities (`users`, `products`, `categories`, `orders`, `order_items`) have no lifecycle: every order is born `completed`, has exactly one item, and never changes. There are no payments, shipments, or inventory. The simulator invents rows directly instead of behaving like an application.
- **CDC is simulated, and the data flow is inverted.** The simulator publishes a fake CDC stream to a single wide-schema `entity-updates` topic (ADR-0010). Flink then *writes* into PostgreSQL. Postgres is a sink/serving store, not the source of truth, and there is no WAL-based capture.
- **The medallion is only nominal.** Every clickstream job reads directly from the `raw-events` Kafka topic. Silver does not read bronze, and silver and gold are both written from Kafka by the same job. Entity tables live in a `kappa.*` namespace outside bronze/silver/gold, with no contracts.
- **Business logic sits in silver.** Sessionization (`silver.user_sessions`, a 30-minute business rule) is classified as silver.
- **Entity jobs never run.** `entity_sync.py` and `order_ingestion.py` are not in the job-submitter list (`infra/job-submitter/submit_jobs.py:18`), so entities never reach the lakehouse on `make up`.
- **The BI layer can query OLTP.** Doris federates a `postgres` JDBC catalog, so analytical queries can hit the transactional store.
- **Two contract standards and two loaders coexist** (ODCS v3 and Data Contract Specification 1.1), and flink-jobs has zero automated tests.

## Why Now

The gaps above were surfaced in a design review on 2026-09-25. They undermine the project's core claims (real CDC, Kappa replay, medallion layering), which are the point of the portfolio. No external deadline was stated (see Open Questions).

## Proposed Outcome

A lakehouse fed by **real WAL-based CDC** from an **OLTP application with lifecycle-bearing entities**, and a **medallion where each layer feeds the next**. Done means all of the following hold on a fresh `make up` (≥12 GB RAM):

1. **OLTP source of truth.** Postgres holds only the application schema: `customers`, `addresses`, `categories`, `products`, `inventory`, `orders` (state machine `created → paid → shipped → delivered`, plus `cancelled`/`refunded`), `order_items`, `payments`, `shipments`. The simulator acts as the application through transactional domain use cases, is restart-safe (state in Postgres), uses a configurable `TIME_SCALE`, and seeds its own data through the same use cases.
2. **Real CDC.** Debezium (Kafka Connect, `pgoutput`, `wal_level=logical`) publishes one topic per table to Redpanda as Avro, registered in the Redpanda Schema Registry. Clickstream (`page_view`, `add_to_cart`, `remove_from_cart`, `begin_checkout`) is produced directly to Redpanda, also as Avro, and is correlated to orders via `session_id`.
3. **Chained medallion.** Kafka → bronze → silver → gold, with each layer reading the previous one via Iceberg streaming reads.
   - **Bronze:** an append-only changelog, which becomes the lakehouse replay source. PII is HMAC-hashed at this edge.
   - **Silver:** source-aligned (typing, dedup, applying the changelog, quarantine), with no business rules. Each entity has an append-only `_changes` table (streamed by gold) and a current-state upsert table (for ad hoc queries).
   - **Gold:** holds all business modeling: `dim_customer`/`dim_product` (SCD2), `fct_orders` (accumulating snapshot), `fct_order_items`, `fct_payments`, `sessions` (with anonymous→customer stitching), `funnel_1m` (closing on real orders), and `customer_360`.
4. **Analytics isolated from OLTP.** Doris reads only the Iceberg lakehouse, and Cube serves gold.
5. **Single contract standard.** ODCS v3 contracts for every lakehouse table. The Schema Registry is the source of truth for bronze, validated by CI. Contracts generate the silver and gold DDL.
6. **Operable.** 7 Flink jobs (one per layer/domain, via `StatementSet`). A scheduled Iceberg maintenance job (compaction, delete-file rewrite, 24h snapshot expiry, orphan cleanup).
7. **Tested.** Domain tests against real Postgres, Flink SQL logic tested in local batch mode, and contract tests, all per PR. A nightly/manual E2E. Ruff is blocking on new code.
8. **Documented.** ADRs updated or superseded (0003, 0008, 0009, 0010, 0011, plus new ADRs for CDC and PII-at-edge), diagrams, README (EN/PT), and runbook reflect the new architecture.

## Affected Users / Systems

- **Services:** `services/simulator` (rewritten as an application), `services/db/migrations` (reset to a single OLTP `V1`), `services/flink-jobs` (all jobs replaced by 7 layered jobs), `services/cube` (cubes rewritten for the new gold).
- **Infra:** `infra/compose` (Postgres logical replication, Kafka Connect/Debezium, Schema Registry exposure, Iceberg maintenance container, Doris `postgres` catalog removed), `infra/job-submitter`.
- **Contracts:** `contracts/` and `services/flink-jobs/contracts/` (consolidated into ODCS).
- **Docs:** ADRs, RFCs, `docs/`, `diagrams/`, READMEs, `examples/queries/`, and demo scripts (`time-travel-demo.sh`, `schema-evolution-demo.sh`).
- **CI:** `.github/workflows/ci.yml`.
- **Consumers:** analysts/BI via Doris and Cube (the gold schema changes completely). There are no external downstream consumers, and the repo has no `docs/service-graph.mmd`.

## Constraints

- **Runs locally via `docker compose`** with a documented minimum of 12 GB RAM. The TaskManager stays at 4 GB. The first fallback is a `make up-lite` profile without Doris/Cube.
- **Free and runnable by anyone:** no license keys or paid tiers (this is why Redpanda Connect `postgres_cdc` was rejected). Free source-available licenses are acceptable (e.g. the Confluent Community License for the Avro converter, accepted 2026-09-25).
- **Iceberg stays the only table format** (ADR-0004); no Paimon.
- **Streaming end to end.** Gold is not computed in batch. The latency of the chained layers (checkpoint/commit of tens of seconds to minutes, plus Doris metadata refresh) is accepted.
- **No backward compatibility required.** There is no production data, so migrations are reset and an old `postgres-data` volume requires `make down -v`.
- **Delivery in sequential PRs to `main`** (phases 0–5). `main` may have an empty lakehouse between phases 1 and 4, and the README must state the current phase.
- **LGPD:** sensitive customer data must never land in the lakehouse in clear text.
- **Postgres tables use `REPLICA IDENTITY DEFAULT`.**
- **Redpanda topics:** 7-day retention. Iceberg time travel is limited to 24h.

## Out of Scope

- An HTTP API for the application (the domain use cases stay embeddable for a future API).
- Sellers/marketplace, coupons, persisted carts, and reviews.
- Retroactive historical data generation.
- Runtime data-quality enforcement in Flink (CI only for now).
- Crypto-shredding / KMS-based PII erasure.
- A read replica for Postgres.
- A dedicated low-latency "hot path" from Kafka to Doris.
- Cloud deployment (Terraform/GCS).

## Open Questions

- **Driver and deadline:** is there an external driver or target date (interview, publication, TCC presentation) that should shape phase priority?
- **Doris 4.x and Iceberg equality deletes:** confirm that Doris reads gold and silver upsert tables with equality deletes correctly. Validate early in phase 3/4.
- **Flink Iceberg streaming read of `_changes` tables:** confirm the watermark/ordering strategy by `_source_lsn` across partitions for SCD2 and the accumulating snapshot.
- **Maintenance vs. streaming writers:** confirm that Spark compaction runs safely alongside Flink commits (commit conflicts/retries) on the same tables.
- **Debezium initial snapshot vs. application seed ordering** on first boot, and replication slot cleanup on `make down`.
- **HMAC secret management** for local dev (`.env`) and its rotation implications for joins on hashed keys.
