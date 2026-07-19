<!-- markdownlint-disable -->
# RFC-0009 - Falhas e Recuperação

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## Banco Indisponível

No documented or automated failover for PostgreSQL, MinIO, or Nessie single-node failure. If any of these go down, dependent Flink jobs/consumers will fail their health checks and the pipeline stalls until the service is restored — there is no graceful degradation path.

## Filas Congestionadas

No backpressure-specific handling beyond what Flink and Kafka provide by default (Flink's own backpressure signaling, visible in its Web UI). No documented behavior for sustained consumer lag.

## Consumer Parado

Not explicitly handled — `scripts/healthcheck.sh` can detect that fewer than the expected number of Flink jobs are `RUNNING`, but there is no automated restart/alerting on top of that detection.

## Mensagens Duplicadas

`EXACTLY_ONCE` Flink checkpointing (30-second interval, checkpoints in `s3://flink-checkpoints/`) is the primary idempotency mechanism for the streaming path. PostgreSQL sinks use upserts (not plain inserts) as an additional safeguard against duplicate writes on job restart.

## Replay

The core Kappa-architecture capability, and genuinely implemented: `make reprocess` → `scripts/reprocess.sh` cancels all `RUNNING` Flink jobs via the REST API (`PATCH`), truncates the relevant PostgreSQL tables (`CASCADE`), and re-submits all jobs with `--from-beginning` (Kafka offset 0). This is the mechanism that eliminates the need for a separate batch/reprocessing pipeline.

## Backpressure

Relies on Flink's built-in backpressure propagation; no custom backpressure handling is implemented on top of it.

## Retry

No explicit application-level retry policy is implemented beyond what the underlying clients (Kafka consumer/producer, JDBC sink) do by default.

## DLQ

Not implemented. Malformed events during Silver validation are silently dropped (`json.ignore-parse-errors=true` in the Flink SQL config) rather than routed to a dead-letter topic — a real gap, tracked in `rfcs/RFC-0010-roadmap.md`, not something to gloss over.

## Circuit Breaker

Not implemented anywhere in the pipeline.

## Failover

No automated failover for any component. Recovery from a component failure today means manually restarting the affected container(s) via `docker compose`.

## Demonstrated Recovery Capabilities

Two specific Iceberg-native capabilities are demonstrated by dedicated scripts, and are worth calling out because they're real and working:

- **Schema evolution** (`scripts/schema-evolution-demo.sh`) — performs a real Iceberg `ALTER TABLE ADD COLUMN` and verifies that pre-existing rows return `NULL` for the new column without any file rewrite, demonstrating Iceberg's schema-evolution guarantee.
- **Time travel** (`scripts/time-travel-demo.sh`) — **currently broken**. It captures an Iceberg snapshot ID, ingests more data, and attempts a DuckDB time-travel query, but it calls two helper scripts (`scripts/get-iceberg-metadata-path.py`, `scripts/count-iceberg-rows.py`) that do not exist in the repository. This is a real, verified gap — flagged here and in `rfcs/RFC-0010-roadmap.md` rather than silently documented as working.
