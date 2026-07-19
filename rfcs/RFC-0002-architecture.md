<!-- markdownlint-disable -->
# RFC-0002 - Arquitetura

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## Context Diagram

```mermaid
flowchart LR
    User["Product / Marketing / Analyst"] -->|queries| CUBE["Cube.js Semantic Layer"]
    CUBE --> DORIS["Apache Doris (federation)"]
    DORIS --> ICEBERG["Iceberg Lakehouse"]
    DORIS --> PG["PostgreSQL Serving"]
    SIM["Event Simulator"] -->|clickstream + entity updates| KAFKA["Kafka (Redpanda)"]
    KAFKA --> FLINK["Apache Flink"]
    FLINK --> ICEBERG
    FLINK --> PG
```

## Container Diagram

```mermaid
flowchart LR
    SIM["Event Simulator\n(Python + Faker, services/simulator)"]
    KAFKA["Kafka\n(Redpanda)"]
    FLINK["Apache Flink\n(PyFlink 1.18, services/flink-jobs)"]
    NESSIE["Nessie Catalog\n(REST)"]
    MINIO["MinIO / GCS\n(object storage)"]
    ICEBERG["Iceberg Tables"]
    DORIS["Apache Doris\n(FE + BE, federation)"]
    CUBE["Cube.js\n(semantic layer, services/cube)"]
    PG["PostgreSQL\n(serving layer, services/db)"]

    SIM -->|"page_view / add_to_cart / purchase"| KAFKA
    SIM -->|"user / product / category / order / order_item"| KAFKA
    KAFKA -->|raw-events, entity-updates| FLINK
    FLINK -->|"exactly-once, contract-driven DDL"| ICEBERG
    FLINK -->|upsert| PG
    ICEBERG --- NESSIE
    ICEBERG --- MINIO
    DORIS -->|Iceberg via Nessie REST catalog| ICEBERG
    DORIS -->|JDBC| PG
    CUBE -->|MySQL protocol| DORIS
```

## Component Diagram

```mermaid
flowchart TD
    subgraph "services/flink-jobs (5 active jobs)"
        J1[raw_event_ingestion]
        J2[silver_enrichment]
        J3[session_aggregation]
        J4[product_funnel]
        J5[user_360]
    end
    subgraph "services/flink-jobs (exist, not wired into submitter)"
        J6[entity_sync]
        J7[order_ingestion]
    end
    KAFKA[Kafka] --> J1
    J1 --> BRONZE[bronze.raw_events]
    BRONZE --> J2
    J2 --> SILVER["silver.validated_events\nsilver.user_sessions"]
    SILVER --> J3
    SILVER --> J4
    J3 --> GOLD1[gold.session_metrics]
    J4 --> GOLD2[gold.product_funnel_1m]
    GOLD1 --> J5
    J5 --> GOLD3[gold.user_360]
```

## Fluxos

**Fluxo de dados:** `simulator → Kafka (raw-events, entity-updates) → Flink jobs → Iceberg (bronze/silver/gold) + PostgreSQL (upserted serving tables) → Doris (federated query) → Cube.js (semantic API) → BI/analyst`.

**Fluxo de execução:** `make up` starts all services via `infra/compose/docker-compose.yml`; `infra/job-submitter` submits the 5 active jobs to the Flink JobManager on startup; the simulator (`services/simulator`) continuously produces synthetic events; jobs run continuously with `EXACTLY_ONCE` checkpointing every 30s.

## Tecnologias

Redpanda (Kafka-API), PyFlink 1.18.1, Project Nessie (REST catalog), MinIO (S3-compatible, GCS-swappable via `STORAGE_BACKEND`), Apache Iceberg, Apache Doris (FE+BE), Cube.js, PostgreSQL 15.6 (migrated via Flyway). Rationale for each major choice is in the corresponding ADR — see `adr/0003-*.md` through `adr/0011-*.md`.

## Dependências

Docker Compose orchestrates all services with healthcheck-gated startup order (`depends_on: condition: service_healthy`). `infra/job-submitter` depends on the Flink JobManager and Kafka being healthy before submitting jobs. Doris depends on static container IPs for its own internal gossip protocol (not a security measure — see `rfcs/RFC-0006-security.md`).

## Interfaces

- **Kafka topics:** `raw-events` (clickstream), `entity-updates` (wide-schema CDC for dimension/fact entities) — see `rfcs/RFC-0005-api.md`.
- **Flink REST API** (`:8081`) — job control, used by `infra/job-submitter`, `scripts/healthcheck.sh`, `scripts/reprocess.sh`.
- **Doris MySQL protocol** (`:9030`) — federated SQL surface for Cube.js and direct analyst queries (`examples/queries/*.sql`).
- **Cube.js API** (`:4000`) — REST/SQL semantic API + Playground.
- **Nessie REST API** — Iceberg catalog operations, also used for schema-evolution and time-travel demos.
