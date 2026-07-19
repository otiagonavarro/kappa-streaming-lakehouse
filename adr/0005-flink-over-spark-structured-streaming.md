<!-- markdownlint-disable -->
# ADR-0005 - Apache Flink over Spark Structured Streaming

- **Status:** Accepted
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; originally narrated in `docs/trade-offs.md`)

---

## Contexto

The pipeline needs a stream-processing engine that can do stateful, low-latency, session-windowed processing with exactly-once guarantees, and that integrates well with Iceberg for lakehouse writes.

## Problema

Which stream processing engine: Apache Flink or Spark Structured Streaming?

## Alternativas

1. **Spark Structured Streaming** — larger community, broader tooling/ecosystem than Flink. Cons at decision time: micro-batch execution model rather than native event-at-a-time streaming, which is a weaker fit for native session-gap windowing and sub-second latency targets.
2. **Apache Flink (chosen)** — native event-at-a-time streaming, native session windows (used directly for the 30-minute session-gap rule), exactly-once state via checkpointing, and stateful processing as a first-class model.

## Decisão

Apache Flink (PyFlink 1.18.1), with `EXACTLY_ONCE` checkpointing (30s interval) and native session windows for session/funnel aggregation.

| Criterion | Flink (PyFlink) | Spark Structured Streaming |
| --- | --- | --- |
| Latency | True streaming (event-by-event or micro-batch) | Micro-batch only (100ms-1s minimum) |
| Session windows | Native first-class support | Requires custom state management |
| Stateful processing | First-class (`ValueState`, `MapState`, RocksDB backend) | Limited; requires `flatMapGroupsWithState` |
| Exactly-once | Native end-to-end | Requires careful sink configuration |
| Python maturity | Good (PyFlink 1.18 covers DataStream + Table API) | Better — PySpark is more complete |
| Learning curve | Higher | Lower (SQL is familiar) |
| Kubernetes / cloud | Flink on K8s (Flink Operator) is production-grade | Databricks, EMR — managed |
| When Spark wins instead | Purely batch workloads; heavy ML/data-science integration; team already knows PySpark | — |

## Consequências

- Session-gap windowing (`silver_enrichment`/`session_aggregation`) and product-funnel windowing (`product_funnel`) map directly onto Flink's native windowing APIs, without approximating them on top of micro-batches.
- Sub-second-to-seconds latency from event to PostgreSQL upsert, consistent with the freshness goals in `rfcs/RFC-0001-problem.md`.
- Smaller community/tooling ecosystem than Spark's — accepted given the fit for this workload's latency and windowing requirements.
