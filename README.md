<!-- markdownlint-disable -->
<div align="center">
  <img src="./assets/logo.svg" alt="navarro" width="200" />
    <h1>Kappa Streaming Lakehouse</h1>
    <h2>Real-time Data Lake with Flink, Iceberg, Nessie & PostgreSQL</h2>

  🇺🇸 **English** | 🇧🇷 [Português](./README.pt-BR.md)
</div>

## The Problem

E-commerce platforms generate massive volumes of clickstream events every second — page views, add-to-cart actions, purchases. Product and marketing teams need real-time answers: which products convert, how users move through funnels, which sessions are still active.

Traditional data architectures force a trade-off:

- **Batch-first (data warehouse)** — Results are accurate but stale. Dashboards lag hours behind reality, and decisions are made on yesterday's data.
- **Lambda architecture** — Runs a fast streaming path alongside a slow batch path. Two codebases must produce identical results, creating the classic dual-maintenance problem: when they diverge, which one is correct?

Neither option gives you both real-time freshness and correctness without doubling complexity.

## The Solution

A **Kappa architecture** where a single streaming pipeline handles both live processing and historical reprocessing. Every event flows through one path:

> **Kafka → Flink → Iceberg (lakehouse) + PostgreSQL (serving)**

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

---

## Architecture

```mermaid
flowchart LR
    SIM["🐍 Event Simulator\n(Python + Faker)"]
    KAFKA["📨 Kafka\n(Redpanda)"]
    FLINK["⚡ Apache Flink\n(PyFlink 1.18)"]
    NESSIE["🗂 Nessie Catalog\n(REST)"]
    ICEBERG["🧊 Iceberg Tables\n(GCS / MinIO)"]
    PG["🐘 PostgreSQL\n(Serving layer)"]
    BI["📊 Analytics\n(DuckDB / psql)"]

    SIM -->|"page_view\nadd_to_cart\npurchase"| KAFKA
    KAFKA -->|raw-events| FLINK
    FLINK -->|"raw_event_ingestion\n(exactly-once)"| ICEBERG
    FLINK -->|"session_aggregation\n(upsert)"| PG
    FLINK -->|"product_funnel\n(1-min windows)"| PG
    NESSIE -.->|"catalog metadata"| ICEBERG
    ICEBERG -->|"time-travel\nDuckDB queries"| BI
    PG -->|"low-latency\nanalytical queries"| BI
```

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
psql postgresql://kappa:kappa@localhost:5432/kappa -f queries/top_converting_products.sql
```

Open the Flink Web UI at **<http://localhost:8081>** to see running jobs and DAGs.  
Open the MinIO console at **<http://localhost:9001>** (minioadmin / minioadmin) to browse Iceberg data files.

---

## Data Model

### Kafka Topic: `raw-events`

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

### Iceberg Tables (Nessie catalog → `kappa` namespace)

| Table | Partitioned by | Purpose |
|-------|---------------|---------|
| `kappa.raw_events` | `event_date` (daily) | Immutable event archive, time-travel |
| `kappa.session_metrics` | `session_date` (daily) | Per-session aggregates |

### PostgreSQL Serving Tables

| Table | Key | Updated by |
|-------|-----|-----------|
| `session_metrics` | `session_id` (upsert) | `session_aggregation.py` |
| `product_funnel_1m` | `(product_id, window_start)` | `product_funnel.py` |

---

## Data Contracts

The `raw_event_ingestion` job is driven by an [ODCS](https://bitol-io.github.io/open-data-contract-standard/) (Open Data Contract Standard) YAML contract at [`flink-jobs/contracts/raw_events.contract.yaml`](flink-jobs/contracts/raw_events.contract.yaml), instead of hardcoded SQL DDL.

The contract is the single point of contact between the `raw-events` Kafka topic and the `kappa.raw_events` Iceberg table — it declares:

- **`servers`** — the Kafka source (topic, format, connector options) and the Iceberg sink (catalog, database, table properties)
- **`schema`** — column names, types, nullability, and the partition key
- **`customProperties`** — job-level config (checkpointing mode, checkpoint interval)

`flink-jobs/src/common.py` loads the contract at runtime (`load_contract`) and builds the Kafka source DDL and Iceberg sink DDL from it (`kafka_source_ddl_from_contract`, `iceberg_sink_ddl_from_contract`) — changing the topic, table schema, or storage properties only requires editing the YAML, not the job code.

---

## Trade-offs

> Full analysis: [docs/trade-offs.md](docs/trade-offs.md)

| Concern | Choice | Why |
|---------|--------|-----|
| Architecture | Kappa | Single pipeline; reprocessing via Kafka replay |
| Table format | Iceberg | Best Flink connector, engine-agnostic, GCS native |
| Catalog | Nessie | Git-like branching, production-grade REST API |
| Streaming engine | PyFlink | Python-native, full DataStream + Table API |
| Serving layer | PostgreSQL | Sub-10ms latency for dashboard queries |
| Local dev | MinIO | Zero-cost GCS proxy, `STORAGE_BACKEND=gcs` to switch |

---

## Reprocessing

The defining property of Kappa: drop all derived state and re-derive it from the Kafka log.

```bash
make reprocess
```

This will:

1. Cancel all running Flink jobs
2. Truncate `session_metrics` and `product_funnel_1m` in PostgreSQL
3. Truncate Iceberg tables
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
| Project Nessie | 0.76.6 |
| Redpanda (Kafka-compatible) | 23.3.6 |
| PostgreSQL | 15.6 |
| Python | 3.11 |
| MinIO | RELEASE.2024-03-15 |
| Flyway | 10.10.0 |

---

## Project Structure

```
kappa-streaming-lakehouse/
├── flink-jobs/
│   ├── contracts/           # ODCS data contracts (YAML)
│   │   └── raw_events.contract.yaml
│   └── src/                 # PyFlink streaming jobs
│       ├── common.py        # Shared env config + catalog setup + contract loader
│       ├── raw_event_ingestion.py
│       ├── session_aggregation.py
│       └── product_funnel.py
├── simulator/              # Python event simulator
│   └── src/simulator/
│       ├── events.py       # Event generators (page_view, add_to_cart, purchase)
│       └── main.py         # Click CLI
├── db/migrations/          # Flyway SQL migrations
├── infra/                  # Docker Compose + job submitter
│   ├── docker-compose.yml
│   └── job-submitter/
├── queries/                # Example analytical SQL
├── scripts/                # Demo + ops scripts
└── docs/                   # Architecture docs
```
