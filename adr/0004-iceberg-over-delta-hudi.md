<!-- markdownlint-disable -->
# ADR-0004 - Apache Iceberg over Delta Lake / Apache Hudi

- **Status:** Accepted
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; originally narrated in `docs/trade-offs.md`)

---

## Contexto

The lakehouse table format needs to support ACID transactions, schema evolution, and time travel on top of object storage, integrated with Flink for writes and Doris for federated reads.

## Problema

Which open table format should back the lakehouse: Apache Iceberg, Delta Lake, or Apache Hudi?

## Alternativas

1. **Delta Lake** — mature ecosystem, strong Spark integration. Cons at the time of this decision: Flink connector was less mature than Iceberg's; historically more tied to the Spark/Databricks ecosystem.
2. **Apache Hudi** — strong upsert/CDC-oriented use cases. Cons: more operational complexity for this bundle's append-heavy, less upsert-heavy workload.
3. **Apache Iceberg (chosen)** — engine-agnostic (not tied to any single compute engine), native support for GCS-compatible object storage, and the most mature Flink connector of the three at decision time.

## Decisão

Apache Iceberg, with Project Nessie as the REST catalog (see ADR-0007) and MinIO/GCS as the object store (see ADR-0006).

| Criterion | Iceberg (this project) | Delta Lake | Hudi |
| --- | --- | --- | --- |
| Flink connector maturity | Best — native FlinkSink, exactly-once | Needs Delta Standalone; community-maintained connector | Gaps in Flink 1.18 (no Merge-on-Read with Flink) |
| Engine agnostic | Yes — Spark, Trino, DuckDB, Athena all work natively | Primarily Spark-first | Primarily Spark-first |
| GCS support | Native via `gcs-connector-hadoop` | Supported | Supported |
| Schema evolution | ADD/DROP/RENAME without rewrite | ADD only (without rewrite) | ADD/DROP with rewrite risk |
| Time travel | Full snapshot history | Log-based (vacuum deletes history) | Timeline-based |
| Catalog ecosystem | REST (Nessie), Hive, JDBC | Unity, Hive | Hive only (primarily) |
| When to choose Delta instead | Heavy Databricks shop; Unity Catalog required | — | — |
| When to choose Hudi instead | Need upserts at very high write frequency (Hudi Merge-on-Read) | — | — |

## Consequências

- Full ACID guarantees, additive schema evolution (`ALTER TABLE ADD COLUMN`, demonstrated in `scripts/schema-evolution-demo.sh`), and time-travel queries (`scripts/time-travel-demo.sh`, currently broken — see `rfcs/RFC-0010-roadmap.md`) come "for free" from the table format.
- Engine independence means Doris can federate Iceberg tables without depending on Spark/Databricks-specific integration.
- Narrower ecosystem tooling compared to Delta Lake's broader third-party tool support — accepted as a reasonable trade given the Flink-centric pipeline.
