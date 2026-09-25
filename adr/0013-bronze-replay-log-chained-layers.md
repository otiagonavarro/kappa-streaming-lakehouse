<!-- markdownlint-disable -->
# ADR-0013 - Bronze as the lakehouse replay log, with chained medallion layers

- **Status:** Accepted (amends ADR-0003 and ADR-0009)
- **Data:** 2026-09-25
- **Feature:** [`docs/features/2026-09-25-oltp-cdc-lakehouse/`](../docs/features/2026-09-25-oltp-cdc-lakehouse/spec.md)

---

## Contexto

The medallion of ADR-0009 is nominal: every clickstream job reads the `raw-events` Kafka topic directly, silver does not read bronze, and silver and gold are written from Kafka by the same job. Reprocessing (ADR-0003) depends on replaying Redpanda from offset 0, which ties history to the broker's retention.

## Problema

What should bronze store for CDC, and should each layer read the previous layer or fan out from Kafka?

## Alternativas

Bronze content:

1. **Append-only changelog (chosen)** — one Iceberg table per source topic with the flattened Debezium envelope: `op`, `before_*`/`after_*`, `_source_lsn`, `_source_tx_id`, `_source_ts` and the Kafka partition/offset. Nothing is merged or dropped, so the full state history of every row is kept.
2. **Upserted mirror of the OLTP** — easier to query, but it loses history (e.g. how long an order stayed `paid` before `shipped`).

Topology:

1. **Chained (chosen)** — only bronze jobs read Redpanda; silver streams from bronze and gold streams from silver, using Iceberg streaming reads.
2. **Fan-out from Kafka (status quo)** — lowest latency, but layers guarantee nothing to each other and reprocessing depends on broker offsets.

## Decisão

Bronze is an append-only changelog and is the lakehouse's replay source. Layers are chained: Kafka → bronze → silver → gold. Redpanda keeps a short retention (7 days) and acts as a buffer, not as the system of record for history.

## Consequências

- The medallion becomes real: rebuilding silver or gold means re-reading the previous layer, not rewinding consumer offsets.
- This is Kappa applied to a lakehouse: there is still a single streaming code path (no batch layer), but the replayable log is bronze on Iceberg rather than only the broker. This amends the "replay Kafka from offset 0" reading of ADR-0003.
- **Latency:** Iceberg publishes data on commit, which happens on Flink checkpoints (30 s by default). End-to-end freshness at gold becomes tens of seconds to a few minutes instead of seconds. This is accepted; a dedicated low-latency hot path is out of scope.
- Iceberg streaming reads only consume append snapshots, which shapes the silver design (ADR-0014).
