<!-- markdownlint-disable -->
# Plan: OLTP + CDC + Lakehouse Redesign

**Date:** 2026-09-25 · **Status:** Approved · **Source:** [spec.md](spec.md)

Delivery: six sequential PRs to `main` (phases 0–5). Each PR leaves `make up` coherent up to its layer, carries its own tests, and updates the README "current phase" note. Branches are `feature/*` (and `docs/*` for phase 0) off `main`.

## Files to Change

### Phase 0 · `docs/oltp-cdc-lakehouse-design`
- **Add:** `docs/features/2026-09-25-oltp-cdc-lakehouse/{intent,spec,plan}.md`, `adr/0012-real-cdc-debezium-avro-registry.md` (supersedes 0010), `adr/0013-bronze-replay-log-chained-layers.md` (amends 0003), `adr/0014-silver-boundary-and-changes-tables.md` (amends 0009), `adr/0015-pii-hashed-at-bronze-edge.md`, `adr/0016-iceberg-maintenance-via-spark.md`.
- **Edit:**
  - `adr/0003`, `adr/0009`: add an "Amended by" note.
  - `adr/0010`: mark "Superseded by ADR-0012".
  - `adr/0008`: single ODCS standard.
  - `adr/0011`: Doris becomes the lakehouse query engine, with no OLTP federation.
  - `.github/PULL_REQUEST_TEMPLATE.md`: branches off `main`.
  - `README.md`, `README.pt-BR.md`: a "redesign in progress" banner and a link to intent.

### Phase 1 · `feature/oltp-app-and-cdc`
- **Delete:**
  - `services/db/migrations/V1__…`, `V2__…`, `V3__…`.
  - `services/flink-jobs/src/{raw_event_ingestion,silver_enrichment,session_aggregation,product_funnel,user_360,entity_sync,order_ingestion}.py`.
  - `services/flink-jobs/src/contracts/`, `services/flink-jobs/contracts/`, all of `contracts/**`.
  - `services/cube/model/cubes/*.yml`, `scripts/init-iceberg-tables.py`, `examples/queries/*.sql`.
  - `services/simulator/src/simulator/{entities,events}.py`.
- **Add:**
  - `services/db/migrations/V1__oltp_schema.sql` (9 tables, CHECKs, indexes, `PUBLICATION shop_pub`, replication role).
  - `infra/postgres/postgresql.conf` or compose `command:` flags (`wal_level=logical`, `max_replication_slots`, `max_wal_senders`, `max_slot_wal_keep_size=1GB`).
  - `infra/kafka-connect/Dockerfile` (Debezium 2.7.x + Confluent Avro converter jars), `infra/kafka-connect/shop-connector.json`, `infra/kafka-connect/register.sh`.
  - `infra/redpanda/create-topics.sh` (7-day retention, `clickstream.events` partitioned).
  - `services/simulator/src/simulator/{config.py,seed.py,db.py}`, `domain/{order_state.py,errors.py}`, `usecases/{customers,catalog,inventory,orders,payments,shipments}.py`, `workers/progress.py`, `traffic/sessions.py`, `producers/clickstream.py`, `schemas/clickstream_event.avsc`.
  - `tests/simulator/{conftest.py,test_order_state.py,test_usecases_orders.py,test_usecases_customers.py,test_workers.py,test_seed.py,test_clickstream.py}`.
- **Edit:**
  - `services/simulator/src/simulator/main.py` (becomes the app loop), `services/simulator/pyproject.toml` + `uv.lock` (`psycopg[binary]`, `confluent-kafka[avro]`; drop `kafka-python`).
  - `infra/compose/docker-compose.yml`: Postgres flags; expose the registry on `8081`, moving the Flink UI to `8082`; add `kafka-connect`, `connect-init`, `topics-init`; the simulator gets the Postgres DSN and depends on `db-migrate`; drop the JDBC env from `job-submitter`.
  - `infra/job-submitter/submit_jobs.py` (`JOBS = []` placeholder), `.env.example` (remove `SIMULATOR_*_TOPIC`; add `SCHEMA_REGISTRY_URL`, `TIME_SCALE`, `PII_HMAC_KEY`, the Debezium user), `Makefile` (`make connect-status`), `.github/workflows/ci.yml` (Postgres service for simulator tests), `tests/simulator/test_simulator.py` (removed/replaced).

### Phase 2 · `feature/bronze-layer`
- **Add:**
  - `services/flink-jobs/src/contracts.py` (ODCS loader + DDL builder), `udfs/pii.py` (`hmac_sha256`), `sql/bronze/{cdc.py,clickstream.py}`, `jobs/{bronze_cdc,bronze_clickstream}.py`.
  - `contracts/bronze/{cdc_customers,…,cdc_shipments,clickstream_events}.odcs.yaml` (10 files).
  - `tests/flink_jobs/{conftest.py,test_contracts_loader.py,test_bronze_sql.py,test_pii_udf.py}`, `tests/contracts/test_bronze_vs_avro.py`, `tests/contracts/fixtures/*.avsc`.
- **Edit:**
  - `services/flink-jobs/src/common.py` (keep `build_env`/`get_env`; move contract helpers out).
  - `infra/job-submitter/Dockerfile`: add `flink-sql-avro-confluent-registry-1.18.1`; drop the JDBC + Postgres jars; copy `contracts/` + `jobs/`.
  - `submit_jobs.py` (2 jobs), `services/flink-jobs/pyproject.toml` (add pytest extras), `.github/workflows/ci.yml` (real `test-flink-jobs` + contracts job).

### Phase 3 · `feature/silver-layer`
- **Add:**
  - `docs/features/2026-09-25-oltp-cdc-lakehouse/spike-doris-equality-deletes.md`.
  - `sql/silver/{changes.py,current_state.py,clickstream.py}`, `jobs/{silver_cdc,silver_clickstream}.py`.
  - `contracts/silver/*.odcs.yaml` (9 `_changes` + 9 current-state + `clickstream_events` + `clickstream_quarantine`).
  - `tests/flink_jobs/test_silver_changes.py`, `test_silver_current_state.py`, `test_silver_clickstream.py`.
- **Edit:** `submit_jobs.py` (4 jobs), `infra/compose/docker-compose.yml` (`table.exec.source.idle-timeout` in Flink properties).

### Phase 4 · `feature/gold-and-serving`
- **Add:**
  - `sql/gold/{dim_customer,dim_product,fct_orders,fct_order_items,fct_payments,sessions,funnel_1m,customer_360}.py`, `jobs/{gold_dimensions,gold_orders,gold_clickstream}.py`, `scripts/generate-dim-date.py`.
  - `contracts/gold/*.odcs.yaml` (9 files, including `dim_date`).
  - `services/cube/model/cubes/{orders,order_items,payments,sessions,funnel,customers}.yml`, `examples/queries/*.sql` (rewritten on gold).
  - `tests/flink_jobs/test_gold_{scd2,fct_orders,temporal_join,sessions,funnel}.py`.
- **Edit:** `infra/compose/docker-compose.yml` (`doris-init` drops the `postgres` catalog; the Cube DB name stays `lakehouse.gold`), `submit_jobs.py` (7 jobs).

### Phase 5 · `feature/ops-and-docs`
- **Add:** `infra/iceberg-maintenance/{Dockerfile,maintain.py}`, `.github/workflows/e2e.yml` (nightly + `workflow_dispatch`), `tests/e2e/test_gold_consistency.py`.
- **Edit:**
  - `infra/compose/docker-compose.yml` (maintenance service; `profiles` for `up-lite`), `Makefile` (`up-lite`, `reprocess`).
  - `scripts/{reprocess.sh,healthcheck.sh,time-travel-demo.sh,schema-evolution-demo.sh}`.
  - `rfcs/RFC-0000…0010` (the ones referencing old names), `docs/{flink-jobs,faq,playbook,tradeoffs,runbook,troubleshooting}.md`, `diagrams/*` (regenerated), `README.md`, `README.pt-BR.md` (12 GB requirement, architecture, remove banner).
  - `.github/workflows/ci.yml` (ruff blocking on `services/**/src`), `docs/compliance-gap-report.md`.

## Work Order

1. **Phase 0:** write the ADRs from spec → update the superseded/amended ADRs → PR template → README banner → PR.
2. **Phase 1** (TDD on the domain):
   1. `V1__oltp_schema.sql` plus the Postgres logical-replication config. Verify with `make up` + `psql` (`SHOW wal_level`, `\dRp+`).
   2. `domain/order_state.py`, test-first (pure).
   3. Use cases, test-first against real Postgres: customers → catalog/inventory → orders (place/cancel with inventory) → payments → shipments → `forget_customer`.
   4. `workers/progress.py` with `TIME_SCALE`, plus the restart test.
   5. `seed.py` (idempotent), then the `traffic/sessions.py` + Avro producer (`clickstream_event.avsc`).
   6. `main.py` loop; delete the legacy simulator modules and tests.
   7. Kafka Connect image + connector JSON + registration init; topic init; expose the registry.
   8. Delete the legacy Flink jobs, contracts, cubes, and migrations; empty `JOBS`; fix CI.
   9. Manual verification in the Redpanda Console, then the PR.
3. **Phase 2:**
   1. ODCS loader + tests.
   2. HMAC UDF + tests.
   3. Bronze contracts (generated from the registered Avro schemas and committed as fixtures).
   4. Bronze SQL + batch tests.
   5. Jobs + Dockerfile jars.
   6. Verify: bronze row counts grow, and `SELECT … WHERE after_email LIKE '%@%'` returns 0.
   7. PR.
4. **Phase 3:**
   1. **Spike first:** create a tiny Iceberg upsert table via Flink and read it from Doris 4.1.3. Record the result and pick the fallback if needed.
   2. Silver contracts → SQL functions + batch tests (dedup, out-of-order c/u/d, `r`+`c`, quarantine) → jobs.
   3. Verify `_changes` vs. current state in Doris.
   4. PR.
5. **Phase 4:**
   1. `dim_date` script.
   2. SQL + batch tests in this order: `fct_orders` → `fct_payments` → `dim_product` SCD2 → `fct_order_items` temporal join → `dim_customer` SCD2 → `sessions` → `funnel_1m` → `customer_360`.
   3. Jobs.
   4. Doris catalog removal.
   5. Cubes + example queries.
   6. PR.
6. **Phase 5:**
   1. Maintenance container, verified with snapshot counts before and after.
   2. `up-lite` profile.
   3. Reprocess from bronze (cancel silver/gold jobs → drop silver/gold tables → resubmit reading bronze from the first snapshot).
   4. Demos.
   5. Docs, RFCs, and diagrams.
   6. E2E workflow.
   7. Ruff blocking.
   8. PR.

## Tests Required

| Phase | Tests |
|---|---|
| 1 | State machine: all valid/invalid transitions. `place_order`: inventory decrement, rollback on stockout, 1–5 items, `total = Σ line_total`. `cancel_order` restocks; `refund_order` doesn't. `fail_payment` → retry → `pay_order`. Workers: `SKIP LOCKED` no double transition across two connections; resume after restart. `forget_customer` nulls PII + `status='deleted'`. Seed idempotent on a non-empty DB. Clickstream: Avro round-trip, anonymous→customer stitching within a session, `begin_checkout → place_order` shares `session_id`. |
| 2 | ODCS loader → DDL (columns, types, partitions, PK). HMAC deterministic, key-dependent, and null-safe. Bronze SQL flattens the envelope, preserves `op`/LSN, and hashes every PII column (a test asserts that every column tagged `pii` in the contract is hashed). Contract ↔ Avro fixture equivalence for all 10. |
| 3 | `_changes`: dedup `(pk, lsn)` and `r`+`c` collapse. Current state: the out-of-order input `u(lsn 3), c(lsn 1), d(lsn 5)` yields deleted with lsn 5; a late `u(lsn 4)` after `d(lsn 5)` doesn't resurrect. Clickstream: each quarantine reason, plus a valid event with a null `customer_id` accepted. |
| 4 | `fct_orders`: out-of-order status changes produce correct stage timestamps and durations; the cancelled path. SCD2: 3 versions → the first two closed with the correct `valid_to` and one current, under shuffled input; `dim_customer` versioned by an address change. Temporal join picks the price valid at order time. Sessions: 30 min gap split, stitching. Funnel: `abandoned = checkouts − orders`. |
| 5 | E2E: after 10 min of `make up`, every gold table is non-empty, `fct_orders` has `delivered` rows, `funnel orders ≤ checkouts`, and no clear-text email appears in any lakehouse table. |

## Risks & Mitigations

GitNexus is not indexed for this repo, so `impact()` could not run. The upstream analysis was done with `git grep` over every legacy name: 58 files reference them, all inside this repo, with no external consumers. No HIGH/CRITICAL external blast radius was found. The internal blast radius is total by design (phase 1 removes the legacy code).

| Risk | Severity | Mitigation |
|---|---|---|
| Doris 4.1.3 cannot read Iceberg equality deletes (silver current state / gold) | **HIGH** | Spike at the start of phase 3, before building silver. Fallbacks: (a) aggressive maintenance compaction applying deletes, or (b) expose current state to Doris as a Top-1 view over `_changes`. |
| PyFlink Python UDF (HMAC) throughput/latency, plus the Python worker memory in the 4 GB TaskManager | MEDIUM | Scale is small (≈10 eps). Measure in phase 2. Fallback: a Java UDF jar or `SHA256(CONCAT(key, value))` documented as a salted hash. |
| Unbounded Flink state for SCD2 self-join / `fct_orders` GROUP BY / temporal join grows over long runs | MEDIUM | Acceptable at portfolio scale. Use the RocksDB state backend in phase 4 if the heap grows. Document the TTL as a production consideration. |
| Iceberg streaming source + 30 s checkpoints: end-to-end gold latency of minutes may look "broken" in demos | MEDIUM | Document the expected latency in README/runbook. Tune `monitor-interval=10s`; checkpoint interval via env. |
| Debezium WAL retention grows if Connect is down (disk fills in the Postgres volume) | MEDIUM | `max_slot_wal_keep_size=1GB`; runbook slot monitoring; `make down` drops the volume. |
| Confluent Avro converter / Debezium 2.7 / Redpanda v23.3 registry compatibility | MEDIUM | Validated in phase 1 step 7 before any lakehouse work. Pin all versions. |
| Port clash: Redpanda registry `8081` vs. the Flink UI `8081` | LOW | Move the Flink UI host port to `8082` in phase 1; update docs/scripts that curl `:8081`. |
| `main` has an empty lakehouse between phases 1–4 | LOW (accepted) | README banner states the current phase. |
| Spark maintenance commit conflicts with Flink commits | LOW | Optimistic concurrency, `partial-progress`, retry next cycle. |
| Memory > 12 GB with Connect + Spark maintenance | MEDIUM | Maintenance runs as a short-lived container (not concurrent with peak); `make up-lite`; measure with `docker stats` in phase 5 and adjust the documented minimum. |

## Rollback Plan

- Each phase is one PR, and a phase is reverted with `git revert -m 1 <merge-sha>`.
- **Phase 1** is the only destructive PR (it deletes the legacy pipeline). Reverting it restores the old pipeline, followed by `make down -v && make up` because the Postgres schema and volume differ.
- Phases 2–5 are additive on top of phase 1. Reverting one leaves the earlier layers running; to drop its Iceberg tables, run `make down -v`.
- There is no production data, so no data migration or backfill is needed on rollback.
