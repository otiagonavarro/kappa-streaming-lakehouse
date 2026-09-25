<!-- markdownlint-disable -->
# ADR-0016 - Scheduled Iceberg table maintenance via Spark procedures

- **Status:** Accepted
- **Data:** 2026-09-25
- **Feature:** [`docs/features/2026-09-25-oltp-cdc-lakehouse/`](../docs/features/2026-09-25-oltp-cdc-lakehouse/spec.md)

---

## Contexto

Roughly 39 Iceberg tables receive a commit on every Flink checkpoint (30 s), which is ~2,880 snapshots and many small files per table per day. Silver current-state and gold tables also accumulate equality-delete files, which make reads in Doris progressively slower. Without maintenance, a long-running `make up` degrades visibly and MinIO grows without bound.

## Problema

How, and with which engine, should Iceberg tables be compacted and their snapshots expired?

## Alternativas

1. **Spark procedures (chosen)** — the official Iceberg procedures (`rewrite_data_files`, `rewrite_position_delete_files`, `expire_snapshots`, `remove_orphan_files`), with the most complete support, including compaction that applies equality deletes. Cons: a Spark image in the stack, run as a short-lived maintenance container.
2. **Flink actions (`RewriteDataFilesAction`)** — no new engine. Cons: more limited; compaction does not handle equality deletes well, and snapshot expiry needs the Java API.

## Decisão

An `iceberg-maintenance` container (Spark 3.5 + `iceberg-spark-runtime-3.5_2.12:1.6.1` + Nessie) loops every 15 minutes over every table: `rewrite_data_files` (target 128 MB, `partial-progress.enabled`), `rewrite_position_delete_files`, `expire_snapshots` older than 24 h, and `remove_orphan_files` older than 24 h.

## Consequências

- This does not contradict ADR-0005: Flink remains the only processing engine. Spark is used only for table maintenance, where Iceberg's own tooling is Spark-first.
- **Time travel is limited to 24 h.** Long-term history lives in the append-only bronze, not in snapshots; the time-travel demo states this.
- Iceberg's optimistic concurrency means a rewrite that conflicts with a concurrent Flink commit fails validation and is retried next cycle; Flink commits are never blocked.
- The container is excluded from `make up-lite`.
