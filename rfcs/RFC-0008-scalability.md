<!-- markdownlint-disable -->
# RFC-0008 - Escalabilidade

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## Escalabilidade Horizontal

Not exercised in this demo — every service runs as a single container/node. Flink is configured with a single TaskManager (`taskmanager.numberOfTaskSlots: 16`, `taskmanager.memory.process.size: 4096m`), which provides task-level parallelism within one node but no horizontal TaskManager scaling. Kafka (Redpanda) runs as a single broker. Doris runs single-node FE+BE. In a real deployment, Flink would scale by adding TaskManagers, Redpanda/Kafka by adding brokers and partitions, and Doris by adding BE nodes.

## Escalabilidade Vertical

The current configuration (16 task slots, 4GB Flink process memory) is a demo-scale default, not a tuned production sizing. Vertical scaling (more CPU/memory per container) is the simplest lever available in the current single-node setup.

## Sharding

Not configured. Kafka topics (`raw-events`, `entity-updates`) run with whatever default partition count Redpanda assigns; no explicit partitioning strategy is set for throughput scaling.

## Particionamento

Iceberg tables are partitioned per their access pattern: `bronze.raw_events` by `event_date`, `silver.user_sessions` by `session_date`, product/category-oriented Gold tables by `category_id`, and `user_360`-adjacent tables by `registered_date` (exact partition columns per table are defined in each table's contract under `contracts/`).

## Cache

Doris acts as a query-federation and caching layer between Iceberg (cold, object-storage-backed) and PostgreSQL (hot, low-latency serving) — this is effectively the system's caching strategy: keep frequently-queried aggregates in Postgres, let Doris query Iceberg directly for anything not pre-aggregated.

## Replicação

None configured for any component — single-node MinIO, single-node PostgreSQL, single-node Redpanda broker, single-node Doris FE/BE. No replication factor is set on Kafka topics.

## Custos

Local-first design (MinIO instead of GCS by default) keeps this demo's cost at zero. `STORAGE_BACKEND=gcs` is documented and code-supported for switching to real cloud storage, but that path is untested (no evidence it has ever run against real GCS — tracked in `rfcs/RFC-0010-roadmap.md`).

## Planejamento de Capacidade

No capacity planning has been done — the deployment is fixed-size and sized for demo workloads (the simulator's synthetic event rate), not for a target production throughput.
