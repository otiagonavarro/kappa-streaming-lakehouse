<!-- markdownlint-disable -->
# ADR-0003 - Kappa over Lambda architecture

- **Status:** Accepted — amended by ADR-0013 (2026-09-25)
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; originally narrated in `docs/trade-offs.md`)

---

## Contexto

E-commerce clickstream analytics needs both real-time freshness and correctness on reprocessing. The two dominant architectural patterns are Lambda (separate batch + streaming paths) and Kappa (streaming-only, replay for reprocessing).

## Problema

Which architecture should the pipeline use to serve both live dashboards and historical/reprocessed results?

## Alternativas

1. **Lambda architecture** — a fast streaming path for live results plus a slow batch path for accurate historical results, reconciled at query time. Pros: can use the best-fit engine per workload (e.g. Spark batch + Flink streaming). Cons: two codebases must produce identical results; when they diverge, there is no single source of truth; roughly doubles pipeline code and infrastructure.
2. **Kappa architecture (chosen)** — one streaming pipeline handles both live processing and historical reprocessing by replaying the Kafka log from offset 0. Pros: single codebase — if it works on live data, it works on replayed data; no batch/streaming divergence risk. Cons: reprocessing an entire history means replaying the whole log, which can be slower than a purpose-built batch job for very large histories; some computations (e.g. certain large-scale ML training joins) are still more naturally batch.

## Decisão

Kappa. Single streaming pipeline: `Kafka → Flink → Iceberg (lakehouse) + PostgreSQL (serving)`. Reprocessing replaces the batch layer entirely via Kafka replay (`make reprocess`).

| Criterion | Kappa (this project) | Lambda |
| --- | --- | --- |
| Codebases | One (streaming only) | Two (batch + streaming must agree) |
| Correctness risk | Low — one source of truth | High — batch/streaming divergence is a known failure mode |
| Reprocessing | Replay Kafka from offset 0 | Re-run batch job from cold storage |
| Latency | Stream-native, sub-second | Streaming is near-real-time; batch results lag hours |
| Complexity | Simpler operationally | Complex: maintain two pipelines, two schedulers |
| When Lambda wins | Never for new systems; only when batch logic is fundamentally irreducible (e.g. ML training at scale) | When the streaming engine cannot express certain aggregations efficiently |

## Consequências

- No batch/streaming divergence class of bugs — there is only one code path.
- Reprocessing cost scales with total log size, not with a batch job's incremental delta — acceptable at this bundle's data volumes, worth revisiting if adopted at much larger scale.
- Recommendation (unchanged from the original trade-off analysis): start with Kappa; add a batch path only if a specific computation cannot be expressed efficiently in a stream processor.

## Emenda (2026-09-25)

Amended by [ADR-0013](0013-bronze-replay-log-chained-layers.md). The single-streaming-path decision stands. What changes:

- **Replay source:** reprocessing now replays the **bronze** Iceberg changelog instead of Kafka from offset 0. Redpanda keeps a 7-day retention as a buffer.
- **Pipeline:** the pipeline is `Postgres (OLTP) → Debezium → Redpanda → Flink → Iceberg bronze → silver → gold → Doris/Cube`. PostgreSQL is no longer a serving sink; it is the application's source of truth ([ADR-0012](0012-real-cdc-debezium-avro-registry.md)).
- **Latency:** the "sub-second" figure in the table above no longer holds at gold. Chained layers commit on Flink checkpoints, so freshness is tens of seconds to minutes.
