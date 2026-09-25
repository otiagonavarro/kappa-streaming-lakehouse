<!-- markdownlint-disable -->
# ADR-0012 - Real WAL-based CDC with Debezium, Avro and the Redpanda Schema Registry

- **Status:** Accepted (supersedes ADR-0010)
- **Data:** 2026-09-25
- **Feature:** [`docs/features/2026-09-25-oltp-cdc-lakehouse/`](../docs/features/2026-09-25-oltp-cdc-lakehouse/spec.md)

---

## Contexto

The simulator publishes a hand-built "CDC" stream to a single wide-schema `entity-updates` topic (ADR-0010), and Flink writes those entities *into* PostgreSQL. Postgres is a sink, not a source of truth, and no change is ever captured from a database log. A portfolio that claims CDC has to capture changes from a real transactional store.

## Problema

How should changes in the OLTP application database reach the streaming log, and in what serialization format?

## Alternativas

1. **Debezium Postgres connector on Kafka Connect (chosen)** — reads the WAL through the native `pgoutput` plugin and a replication slot, and publishes one topic per table. It is the de facto standard, with initial snapshot, heartbeat and outbox support. Cons: one more JVM container (~0.5–1 GB RAM).
2. **Redpanda Connect `postgres_cdc` input** — lightweight and "all Redpanda". Cons: the input is enterprise-licensed (license key or trial), so the stack would not be freely runnable by anyone who clones the repo.
3. **Flink CDC (`postgres-cdc`) reading the WAL directly** — one less component. Cons: the log never lands in Redpanda, so there is no replayable log shared by consumers, which contradicts the Kappa principle (ADR-0003).

Serialization format:

1. **Avro + Schema Registry (chosen)** — compact, strongly typed (`NUMERIC` stays a decimal), and schema evolution is visible end to end (`ALTER TABLE` → new registry version → lakehouse).
2. **JSON without schemas** — readable in the console, but types are not guaranteed (decimals become strings/base64) and evolution is implicit.
3. **JSON with embedded schema** — every message carries its full schema: all the size cost, none of the registry's benefits.

## Decisão

- PostgreSQL runs with `wal_level=logical`, a dedicated replication user, a `PUBLICATION` restricted to the 9 application tables, and `REPLICA IDENTITY DEFAULT` on every table.
- Debezium 2.7.x (pinned) on Kafka Connect publishes one topic per table (`shop.public.<table>`), keyed by primary key, serialized as Avro and registered in Redpanda's built-in Schema Registry (`TopicNameStrategy`).
- The clickstream, produced directly by the application, also uses Avro in the same registry.
- Topic retention is 7 days: the long-term replay source becomes the bronze layer (ADR-0013).

## Consequências

- One topic and one schema per entity replace the sparse wide schema of ADR-0010. Consumers get strong typing per entity instead of branching on a discriminator.
- **Licensing:** Debezium 2.x no longer ships the Confluent Avro converter, and it is required because both Redpanda's registry and Flink's `avro-confluent` format speak the Confluent wire/API. The converter is under the **Confluent Community License**: free and keyless, but source-available rather than OSI. The owner accepted it on 2026-09-25, and the project constraint is "free and runnable by anyone, no license keys".
- `REPLICA IDENTITY DEFAULT` means `UPDATE`/`DELETE` events carry only the primary key in `before`. Every downstream computation uses `after` plus the LSN ordering, so the full before-image is not needed, and the WAL stays small.
- The replication slot retains WAL while Connect is down; `max_slot_wal_keep_size` bounds it, and slot monitoring goes into the runbook.
- Kafka Connect adds roughly 1 GB to the local stack; the documented minimum becomes 12 GB RAM.
