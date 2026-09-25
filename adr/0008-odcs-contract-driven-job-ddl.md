<!-- markdownlint-disable -->
# ADR-0008 - ODCS data contract drives Flink job DDL at runtime

- **Status:** Accepted — amended 2026-09-25
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; see commit `02fc9ed`)

---

## Contexto

The `raw_event_ingestion` Flink job needs a Kafka source table DDL and an Iceberg sink table DDL. These DDLs must stay consistent with the actual event schema, or the job breaks silently or loudly depending on where the mismatch surfaces.

## Problema

Should the Kafka source / Iceberg sink DDL for `raw_event_ingestion` be hardcoded in the job's source code, or derived from an external, versioned contract?

## Alternativas

1. **Hardcoded DDL in job source code** — simplest to read for a single job. Cons: couples schema changes to code changes; the contract (if one exists elsewhere, e.g. for consumers) can silently drift from what the job actually does.
2. **Contract-driven DDL (chosen)** — `services/flink-jobs/contracts/raw_events.contract.yaml` (an ODCS-format contract) is loaded at runtime by `services/flink-jobs/src/common.py`'s `load_contract`, and `kafka_source_ddl_from_contract` / `iceberg_sink_ddl_from_contract` build the actual Flink SQL DDL from it. The contract *is* the schema source of truth, not documentation describing a separately-maintained schema.

## Decisão

Contract-driven DDL via the ODCS contract file, genuinely executed at job startup — not merely referenced in documentation.

## Consequências

- Schema changes happen in one place (the contract file); the job's DDL cannot silently drift from what the contract says, because the DDL *is generated from* the contract.
- The contract file becomes a dependency that must be kept in sync and reviewed with the same care as code — a change to `raw_events.contract.yaml` is functionally a code change, even though it's YAML.
- No automated compatibility check exists yet between contract versions (tracked in `rfcs/RFC-0010-roadmap.md`) — a breaking contract change today would only surface at job runtime, not at review time.

## Emenda (2026-09-25)

The contract-driven DDL decision stands and now applies to **every** lakehouse table. What changes (see [`docs/features/2026-09-25-oltp-cdc-lakehouse/spec.md`](../docs/features/2026-09-25-oltp-cdc-lakehouse/spec.md)):

- **Single standard:** ODCS v3 is the only contract standard. The Data Contract Specification 1.1 files under `contracts/` are replaced by ODCS files in one tree, `contracts/{bronze,silver,gold}/<table>.odcs.yaml`, read by one loader. `services/flink-jobs/contracts/` and `contracts/loader.py` are removed.
- **Bronze:** the Schema Registry is the schema source of truth, because the schema originates in Postgres and arrives through Debezium ([ADR-0012](0012-real-cdc-debezium-avro-registry.md)). The bronze contract declares topic, subject and expected columns, and a CI test checks it against the Avro schema. This closes the "no automated compatibility check" gap above at the log edge.
- **Silver and gold:** the ODCS contract generates the Iceberg DDL, as before.
- **Quality rules** (`notNull`, `unique`, enumerations) are declared in contracts and enforced in CI; runtime enforcement in Flink stays on the roadmap.
