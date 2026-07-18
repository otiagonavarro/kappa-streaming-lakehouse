<!-- markdownlint-disable -->
# Architecture Trade-offs

Honest comparisons of every major technology choice in this project.

---

## 1. Kappa vs Lambda Architecture

| Criterion | Kappa (this project) | Lambda |
|-----------|---------------------|--------|
| Codebases | **One** (streaming only) | Two (batch + streaming must agree) |
| Correctness risk | Low — one source of truth | High — batch/streaming divergence is a known failure mode |
| Reprocessing | Replay Kafka from offset 0 | Re-run batch job from cold storage |
| Latency | Stream-native, sub-second | Streaming is near-real-time; batch results lag hours |
| Complexity | Simpler operationally | Complex: maintain two pipelines, two schedulers |
| When Lambda wins | Never for new systems; only when batch logic is fundamentally irreducible (e.g., ML training at scale) | When streaming engine cannot express certain aggregations efficiently |

**Recommendation:** Start with Kappa. Add a batch path only if you hit a specific computation that cannot be expressed efficiently in a stream processor (rare with Flink's Table API).

---

## 2. Apache Iceberg vs Delta Lake vs Apache Hudi

| Criterion | Iceberg (this project) | Delta Lake | Hudi |
|-----------|----------------------|-----------|------|
| Flink connector maturity | **Best** — native FlinkSink, exactly-once | Needs Delta Standalone; connector is community-maintained | Gaps in Flink 1.18 (no MOR with Flink) |
| Engine agnostic | Yes — Spark, Trino, DuckDB, Athena all work natively | Primarily Spark-first | Primarily Spark-first |
| GCS support | **Native** via `gcs-connector-hadoop` | Supported | Supported |
| Schema evolution | ADD/DROP/RENAME without rewrite | ADD only (without rewrite) | ADD/DROP with rewrite risk |
| Time travel | Full snapshot history | Log-based (vacuum deletes history) | Timeline-based |
| Catalog ecosystem | REST (Nessie), Hive, JDBC | Unity, Hive | Hive only (primarily) |
| When to choose Delta | Heavy Databricks shop; Unity Catalog required | — | — |
| When to choose Hudi | Need upserts at very high write frequency (HoodieMergeOnRead) | — | — |

**Recommendation:** Iceberg is the open standard for multi-engine, cloud-native data lakes. Choose Delta only if locked into Databricks. Hudi only if your write workload is dominated by upserts at millions/sec.

---

## 3. Apache Flink vs Spark Structured Streaming

| Criterion | Flink (PyFlink) | Spark Structured Streaming |
|-----------|----------------|--------------------------|
| Latency | True streaming (event-by-event or micro-batch) | Micro-batch only (100ms–1s minimum) |
| Session windows | **Native** first-class support | Requires custom state management |
| Stateful processing | First-class (`ValueState`, `MapState`, RocksDB backend) | Limited; requires `flatMapGroupsWithState` |
| Exactly-once | Native end-to-end | Requires careful sink configuration |
| Python maturity | Good (PyFlink 1.18 covers DataStream + Table API) | **Better** — PySpark is more complete |
| Learning curve | Higher | Lower (SQL is familiar) |
| Kubernetes / cloud | Flink on K8s (Flink Operator) is production-grade | Databricks, EMR — managed |
| When Spark wins | Purely batch workloads; heavy ML/data science integration; team knows PySpark | — |

**Recommendation:** Flink for stream-first architectures. Spark when the team is Python/ML-heavy and latency > 1s is acceptable.

---

## 4. MinIO vs Google Cloud Storage (GCS)

| Criterion | MinIO (local dev) | GCS |
|-----------|------------------|-----|
| Cost | Free (local Docker) | Pay-per-GB stored + egress |
| Setup | `docker compose up` | GCP project, bucket, IAM, SA key |
| S3 API compatibility | **Full** — Iceberg sees it as S3 | Requires `gcs-connector-hadoop` |
| Consistency | Strong (single node) | Strong (Google's multi-region) |
| Scale | Single-node toy | Unlimited, globally replicated |
| When to use GCS | Never for local dev | Production; `STORAGE_BACKEND=gcs` activates it in this project |

**Recommendation:** MinIO for zero-cost local development (default in this project). Flip `STORAGE_BACKEND=gcs` when deploying to GCP. No code changes required — only env vars.

---

## 5. Nessie REST Catalog vs JDBC Catalog

| Criterion | Nessie (this project) | JDBC (Postgres-backed) |
|-----------|----------------------|----------------------|
| Catalog branching | **Yes** — git-like branches/tags | No |
| Schema drift protection | Branch → merge workflow | Manual |
| Operational complexity | One extra Docker service | Zero extra service |
| Production use | Dremio cloud, Project Nessie OSS | Common in self-hosted setups |
| Multi-engine | Any Iceberg client | Any Iceberg client |

**Recommendation:** Nessie in this project because it demonstrates production patterns and catalog branching is a key Iceberg feature. JDBC catalog is simpler and perfectly valid for single-engine setups.

---

## Summary Decision Matrix

| Decision | Choice | Key reason |
|----------|--------|-----------|
| Architecture | Kappa | Single pipeline, Kafka replay = no batch layer needed |
| Table format | Iceberg | Best Flink connector + engine-agnostic |
| Catalog | Nessie | Git-style branching, production-grade REST API |
| Stream processor | PyFlink | Native session windows, exactly-once, Python |
| Serving layer | PostgreSQL | Sub-10ms latency for dashboard reads |
| Local storage | MinIO | Zero-cost GCS proxy |
