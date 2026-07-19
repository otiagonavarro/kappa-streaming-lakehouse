<!-- markdownlint-disable -->
# Trade-offs

Cross-cutting summary of the trade-offs accepted by this bundle's architecture. Each decision's full alternatives/consequences analysis lives in its ADR — this table is the synthesized view across all of them, per `openspec/specs/bundle-structure-standard/spec.md#cross-cutting-trade-off-summary` (portfolio root).

| Decision | What we gained | What we gave up | Related ADR |
| --- | --- | --- | --- |
| Kappa over Lambda architecture | Single codebase — no batch/streaming divergence risk | A purpose-built batch engine for very-large-scale historical recompute | [ADR-0003](../adr/0003-kappa-over-lambda.md) |
| Iceberg over Delta Lake / Hudi | Engine-agnostic lakehouse, mature Flink connector, native GCS support | Delta Lake's broader third-party ecosystem tooling | [ADR-0004](../adr/0004-iceberg-over-delta-hudi.md) |
| Flink over Spark Structured Streaming | Native session windows, exactly-once state, low-latency event-at-a-time processing | Spark's larger community and tooling ecosystem | [ADR-0005](../adr/0005-flink-over-spark-structured-streaming.md) |
| MinIO over GCS (local default) | Zero-cost, zero-credential, five-minute local runnability | An untested `STORAGE_BACKEND=gcs` code path — real but unverified | [ADR-0006](../adr/0006-minio-over-gcs-for-local-dev.md) |
| Nessie REST catalog over JDBC catalog | Git-like branching/tagging, production-representative catalog patterns | One more service to operate | [ADR-0007](../adr/0007-nessie-rest-catalog-over-jdbc-catalog.md) |
| ODCS contract drives job DDL at runtime | Schema changes happen in one place; DDL can't silently drift from the contract | The contract file itself becomes a reviewed, code-equivalent dependency | [ADR-0008](../adr/0008-odcs-contract-driven-job-ddl.md) |
| Bronze/Silver/Gold medallion with per-layer contracts | Explicit validation/enrichment boundary, clear per-layer ownership | More tables, more contracts, more jobs to keep consistent | [ADR-0009](../adr/0009-medallion-architecture-with-contracts.md) |
| Single wide-schema `entity-updates` topic | One consumer/deserializer path across five entity types | Weaker per-entity typing; sparse/nullable messages | [ADR-0010](../adr/0010-wide-schema-cdc-topic.md) |
| Doris + Cube.js federation | One semantic layer/API across Iceberg + PostgreSQL, consistent metric definitions | Two more services to operate; IP-pinned internal networking | [ADR-0011](../adr/0011-doris-cubejs-federation.md) |

## Recommendation Summary

Start with Kappa unless you hit a computation that genuinely cannot be expressed efficiently in a stream processor. Favor engine-agnostic, contract-driven storage (Iceberg + versioned contracts) over hardcoded schemas — the ODCS/data-contract investment paid for itself the moment the medallion layers were introduced without breaking the raw-ingestion job. The federation layer (Doris + Cube.js) is worth its operational cost specifically because it removes "which system has this data" as a question analysts need to answer themselves.
