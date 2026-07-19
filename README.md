<!-- markdownlint-disable -->
<div align="center">
  <img src="./assets/logo.svg" alt="navarro" width="200" />
    <h1>Kappa Streaming Lakehouse</h1>
    <h2>Real-time Data Lake with Flink, Iceberg, Nessie, Doris & Cube.js</h2>

  🇺🇸 **English** | 🇧🇷 [Português](./README.pt-BR.md)
</div>

## The Problem

E-commerce platforms generate massive volumes of clickstream events every second — page views, add-to-cart actions, purchases. Product and marketing teams need real-time answers: which products convert, how users move through funnels, which sessions are still active.

Traditional data architectures force a trade-off:

- **Batch-first (data warehouse)** — Results are accurate but stale. Dashboards lag hours behind reality, and decisions are made on yesterday's data.
- **Lambda architecture** — Runs a fast streaming path alongside a slow batch path. Two codebases must produce identical results, creating the classic dual-maintenance problem: when they diverge, which one is correct?

Neither option gives you both real-time freshness and correctness without doubling complexity.

## The Solution

A **Kappa architecture** where a single streaming pipeline handles both live processing and historical reprocessing. Every event flows through one path, landing in a **bronze/silver/gold medallion lakehouse** with a federated semantic layer on top:

> **Kafka → Flink → Iceberg (bronze/silver/gold) + PostgreSQL (serving) → Doris + Cube.js (federation/BI)**

There is no batch layer. When you need to recompute history, you replay the Kafka log from the beginning — the same code, the same pipeline, just from offset 0.

## Why This Architecture Works

| Problem | How Kappa + Lakehouse solves it |
|---------|--------------------------------|
| Batch/streaming code divergence | One codebase — if it works on live data, it works on replayed data |
| Dashboard latency (hours → seconds) | Flink processes event-by-event; results land in PostgreSQL in sub-second time |
| Reprocessing without a batch layer | Kafka is the immutable source of truth — replay from offset 0 replaces batch entirely |
| Data lake lacks ACID / time travel | Iceberg brings ACID transactions, schema evolution, and time travel to object storage |
| Dashboard reads too slow on data lake | PostgreSQL upserts deliver sub-10ms queries for serving dashboards |
| Schema changes break consumers | Nessie provides git-like branching for safe schema evolution on the catalog |
| "Which system has this data?" | Doris federates Iceberg + PostgreSQL; Cube.js exposes one semantic API over both |

---

## Diagrams

Deeper diagrams — components, boundaries, the bootstrap/reprocess runbook, a federated-query sequence, medallion lineage, and the session state machine — live as self-contained, theme-aware HTML in [`diagrams/`](diagrams/) (dark/light toggle, PNG/SVG export built in). PNG snapshots:

### Architecture

<img src="diagrams/architecture.png" alt="Kappa Streaming Lakehouse architecture diagram: components, storage, and boundaries" width="100%">

Components, storage, and security/region boundaries for the full stack, from the event simulator through Doris + Cube.js. [Interactive version](diagrams/architecture.html).

### Workflow

<img src="diagrams/workflow.png" alt="Stack bootstrap and reprocessing runbook workflow diagram" width="100%">

The `make up` bootstrap sequence (Compose → Flyway → Flink → job submission, with Doris/Cube.js federation booting in parallel) and the `make reprocess` exception path. [Interactive version](diagrams/workflow.html).

### Sequence

<img src="diagrams/sequence.png" alt="Cube.js federated query sequence diagram with Doris cache-miss fallback" width="100%">

A Cube.js query on a pre-aggregation cache miss, falling back to a Doris federated read across the Iceberg and PostgreSQL catalogs in one session. [Interactive version](diagrams/sequence.html).

### Data Flow

<img src="diagrams/dataflow.png" alt="Bronze to silver to gold data flow and lineage diagram" width="100%">

Bronze → silver → gold lineage, `user_id` sensitivity boundaries, and downstream consumers. [Interactive version](diagrams/dataflow.html).

### Lifecycle

<img src="diagrams/lifecycle.png" alt="User session lifecycle state machine diagram" width="100%">

The session state machine — event ingestion, validation, the 30-minute gap watch, and terminal outcomes. [Interactive version](diagrams/lifecycle.html).

---

## Quickstart

**Requirements:** Docker ≥ 24, Docker Compose ≥ 2.20, 8 GB RAM, 4 CPUs

```bash
git clone https://github.com/otiagonavarro/kappa-streaming-lakehouse kappa-streaming-lakehouse
cd kappa-streaming-lakehouse

# 1. Start the full stack (MinIO by default, no GCS credentials needed)
make up

# 2. Wait ~2 minutes for all services to become healthy, then check
make check

# 3. Query the serving layer
psql postgresql://kappa:kappa@localhost:5432/kappa -f examples/queries/top_converting_products.sql
```

Open the Flink Web UI at **<http://localhost:8081>** to see running jobs and DAGs.  
Open the MinIO console at **<http://localhost:9001>** (minioadmin / minioadmin) to browse Iceberg data files.  
Open the Cube.js Playground at **<http://localhost:4000>** to explore the semantic layer and run sample queries.  
Query Doris directly with `mysql -h127.0.0.1 -P9030 -uroot`. Two catalogs are pre-registered: `lakehouse` (Iceberg tables via Nessie, e.g. `lakehouse.gold.session_metrics`) and `postgres` (the JDBC-federated serving layer, e.g. `postgres.public.session_metrics`, `postgres.public.users`) — both queryable in the same session, including joins across them.

---

## Data Model

### Kafka Topics

**`raw-events`** — clickstream events, consumed by three jobs (`raw_event_ingestion`, `silver_enrichment`, `product_funnel`):

```json
{
  "event_id":   "uuid-v4",
  "event_type": "page_view | add_to_cart | purchase",
  "user_id":    "U1234",
  "session_id": "uuid-v4",
  "product_id": "P123",
  "timestamp":  "2024-03-15T10:22:31.456789+00:00",
  "metadata":   { "page": "/products/P123", "referrer": "https://..." }
}
```

**`entity-updates`** — a single wide-schema CDC topic carrying users, products, categories, and orders ([ADR-0010](adr/0010-wide-schema-cdc-topic.md)). `entity_sync.py` and `order_ingestion.py` consume it into dimension/fact tables in both Iceberg and PostgreSQL, but — see [Known Gaps](#known-gaps) — neither job is wired into the default `job-submitter` run yet.

### Iceberg Tables (medallion architecture, Nessie catalog)

| Layer | Table | Partitioned by | Contract |
|-------|-------|-----------------|----------|
| Bronze | `bronze.raw_events` | `event_date` | [contracts/bronze/raw_events.yaml](contracts/bronze/raw_events.yaml) |
| Silver | `silver.validated_events` | `event_date` | [contracts/silver/validated_events.yaml](contracts/silver/validated_events.yaml) |
| Silver | `silver.user_sessions` | `session_date` | [contracts/silver/user_sessions.yaml](contracts/silver/user_sessions.yaml) |
| Gold | `gold.session_metrics` | `session_date` | [contracts/gold/session_metrics.yaml](contracts/gold/session_metrics.yaml) |
| Gold | `gold.product_funnel_1m` | — | [contracts/gold/product_funnel_1m.yaml](contracts/gold/product_funnel_1m.yaml) |
| Gold | `gold.user_360` | — | [contracts/gold/user_360.yaml](contracts/gold/user_360.yaml) |

### PostgreSQL Serving Tables

| Table | Key | Updated by | Migration |
|-------|-----|-----------|-----------|
| `session_metrics` | `session_id` (upsert) | `session_aggregation.py` | `V1__create_session_metrics.sql` |
| `product_funnel_1m` | `(product_id, window_start)` | `product_funnel.py` | `V2__create_product_funnel_1m.sql` |
| `categories`, `users`, `products`, `orders`, `order_items` | entity/order PKs | `entity_sync.py`, `order_ingestion.py` (not wired — see [Known Gaps](#known-gaps)) | `V3__create_ecommerce_entities.sql` |

---

## Data Contracts

Two data contract formats coexist today (reconciling them is tracked in [RFC-0010](rfcs/RFC-0010-roadmap.md)):

1. **Medallion contracts** ([Data Contract Specification](https://datacontract.com/) 1.1.0) at [`contracts/{bronze,silver,gold}/`](contracts) — one YAML per table, declaring schema, types, quality rules (`notNull`, `uniqueness`, `enumeration`, `freshness`), partitioning, and SLAs. `services/flink-jobs/src/contracts/loader.py` loads them at runtime (`ddl_columns`, `partition_spec`), and every medallion job builds its `CREATE TABLE` DDL from the contract instead of hardcoding it.
2. **Legacy [ODCS](https://bitol-io.github.io/open-data-contract-standard/)** (Open Data Contract Standard) contract at [`services/flink-jobs/contracts/raw_events.contract.yaml`](services/flink-jobs/contracts/raw_events.contract.yaml) — the original contract format, predating the medallion contracts and now superseded in practice by `contracts/bronze/raw_events.yaml`.

Either way, changing a table's schema, types, or partition key only requires editing the matching YAML — not the job code.

---

## Trade-offs

> Full analysis: [docs/tradeoffs.md](docs/tradeoffs.md)

| Concern | Choice | Why |
|---------|--------|-----|
| Architecture | Kappa | Single pipeline; reprocessing via Kafka replay |
| Table format | Iceberg | Best Flink connector, engine-agnostic, GCS native |
| Catalog | Nessie | Git-style branching, production-grade REST API |
| Streaming engine | PyFlink | Python-native, full DataStream + Table API |
| Serving layer | PostgreSQL | Sub-10ms latency for dashboard queries |
| Local dev | MinIO | Zero-cost GCS proxy, `STORAGE_BACKEND=gcs` to switch |
| Data contracts | Bronze/Silver/Gold + per-layer YAML | Explicit validation/enrichment boundary; DDL can't drift from the contract |
| CDC topic | Single wide-schema `entity-updates` | One consumer path across five entity types, at the cost of weaker per-entity typing |
| BI / semantic layer | Doris + Cube.js federation | One API across Iceberg + PostgreSQL, consistent metric definitions |

---

## Reprocessing

The defining property of Kappa: drop all derived state and re-derive it from the Kafka log.

```bash
make reprocess
```

This will:

1. Cancel all running Flink jobs
2. Truncate the PostgreSQL serving tables (`session_metrics`, `product_funnel_1m`, `users`, `products`, `categories`, `orders`, `order_items`)
3. Drop the Iceberg tables across the bronze → silver → gold layers
4. Restart all jobs with `--from-beginning` (Kafka consumer group reset to offset 0)

After reprocessing completes, row counts will be identical to the original run.

---

## GCS Cloud Mode

1. Create a GCS bucket and a service account with `roles/storage.admin`
2. Download the SA key JSON to `./secrets/gcp-sa.json`
3. Edit `.env`:

   ```
   STORAGE_BACKEND=gcs
   GCS_BUCKET=my-kappa-lake
   GCS_PROJECT_ID=my-project
   ```

4. Run `make up` — Flink will write Iceberg files directly to GCS

---

## Version Matrix

| Component | Version |
|-----------|---------|
| Apache Flink (PyFlink) | 1.18.1 |
| Apache Iceberg | 1.5.2 (flink-runtime-1.18) |
| Project Nessie | 0.108.2 |
| Apache Doris | 4.1.3 |
| Cube.js | latest |
| Redpanda (Kafka-compatible) | 23.3.6 |
| PostgreSQL | 15.6 |
| Python | 3.11 |
| MinIO | RELEASE.2024-03-15 |
| Flyway | 10.10.0 |

---

## Documentation

| Where | What |
|-------|------|
| [`rfcs/`](rfcs) | RFC-0000..RFC-0010 — problem framing, architecture, domain/data model, API, security, observability, scalability, failure recovery, roadmap |
| [`adr/`](adr) | ADR-0001..ADR-0011 — individual architectural decisions (Kappa vs. Lambda, Iceberg vs. Delta/Hudi, Flink vs. Spark, Nessie, contract-driven DDL, medallion contracts, wide-schema CDC topic, Doris + Cube.js federation) |
| [`docs/tradeoffs.md`](docs/tradeoffs.md) | Cross-cutting trade-off summary linking back to each ADR |
| [`docs/runbook.md`](docs/runbook.md), [`docs/playbook.md`](docs/playbook.md), [`docs/troubleshooting.md`](docs/troubleshooting.md), [`docs/faq.md`](docs/faq.md) | Operational docs |
| [`docs/flink-jobs.md`](docs/flink-jobs.md) | Per-job DAG reference for the PyFlink pipeline |
| [`docs/compliance-gap-report.md`](docs/compliance-gap-report.md) | Point-in-time structural retrofit assessment |

### Known Gaps

Tracked in full in [`rfcs/RFC-0010-roadmap.md`](rfcs/RFC-0010-roadmap.md). The ones most relevant before you run this locally:

- **`entity_sync.py` and `order_ingestion.py` are not wired into `job-submitter`** — the dimension/fact tables they populate (`users`, `products`, `categories`, `orders`, `order_items` in both Iceberg and Postgres) exist in schema/contract form but stay empty until those two jobs are added to `infra/job-submitter/submit_jobs.py`'s `JOBS` list.
- `scripts/time-travel-demo.sh` currently fails — it calls two helper scripts that don't exist yet.
- No dead-letter queue: `silver_enrichment` drops malformed events instead of routing them for inspection.
- `STORAGE_BACKEND=gcs` is implemented but has never been run against real GCS.

---

## Project Structure

```
kappa-streaming-lakehouse/
├── .github/workflows/        # CI (lint + test)
├── rfcs/                     # RFC-0000..RFC-0010, the design record
├── adr/                      # Architecture decision records (0001-0011)
├── diagrams/                 # Architecture/workflow/sequence/dataflow/lifecycle diagrams (JSON + HTML + PNG)
├── docs/                     # Trade-offs, runbook, playbook, troubleshooting, FAQ, Flink jobs reference
├── contracts/                # Medallion data contracts (Data Contract Specification 1.1.0)
│   ├── bronze/                  # raw_events.yaml
│   ├── silver/                  # validated_events.yaml, user_sessions.yaml
│   └── gold/                    # session_metrics.yaml, product_funnel_1m.yaml, user_360.yaml
├── examples/
│   └── queries/               # Example analytical SQL
├── services/
│   ├── flink-jobs/
│   │   ├── contracts/           # Legacy ODCS contract (raw_events.contract.yaml)
│   │   └── src/                 # PyFlink streaming jobs
│   │       ├── common.py          # Shared env config + catalog setup
│   │       ├── contracts/loader.py  # Loads contracts/{bronze,silver,gold}/*.yaml
│   │       ├── raw_event_ingestion.py  # Kafka → bronze.raw_events
│   │       ├── silver_enrichment.py    # bronze → silver.validated_events
│   │       ├── session_aggregation.py  # silver.user_sessions + gold.session_metrics
│   │       ├── product_funnel.py       # Kafka → gold.product_funnel_1m
│   │       ├── user_360.py             # gold.session_metrics → gold.user_360
│   │       ├── entity_sync.py          # entity-updates → dims (not wired)
│   │       └── order_ingestion.py      # entity-updates → facts (not wired)
│   ├── simulator/             # Python event simulator
│   │   └── src/simulator/
│   │       ├── events.py        # Event generators (page_view, add_to_cart, purchase)
│   │       ├── entities.py      # Entity/CDC generators
│   │       └── main.py          # Click CLI
│   ├── cube/model/cubes/      # Cube.js semantic layer models
│   └── db/migrations/         # Flyway SQL migrations (V1-V3)
├── infra/
│   ├── compose/
│   │   └── docker-compose.yml
│   ├── job-submitter/         # Submits the 5 wired PyFlink jobs
│   ├── terraform/             # (empty — no IaC yet)
│   └── docker/                # (empty — no standalone Dockerfiles yet)
├── tests/
│   └── simulator/             # Simulator unit tests
├── scripts/                   # Demo + ops scripts
└── LICENSE
```
