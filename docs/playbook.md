<!-- markdownlint-disable -->
# Playbook

What to do when specific things go wrong. See `docs/troubleshooting.md` for quick symptom→fix lookups; this playbook covers the deeper incident types.

## A Flink job is not RUNNING

**Symptoms:** `make check` reports fewer than 5 RUNNING jobs; Flink Web UI (`:8081`) shows a job in `FAILED` or `CANCELED` state.

**Diagnosis:**
1. Check the JobManager/TaskManager logs: `docker compose -f infra/compose/docker-compose.yml logs -f jobmanager taskmanager`.
2. Check whether `entity_sync` or `order_ingestion` are the "missing" jobs — those two exist in source but are **not** submitted by `infra/job-submitter` by design (see `rfcs/RFC-0010-roadmap.md`). Their absence from the RUNNING list is expected, not a failure.
3. For one of the 5 jobs that should be running, check the ODCS contract (`services/flink-jobs/contracts/raw_events.contract.yaml`) for a recent change — since job DDL is generated from it at runtime (ADR-0008), a malformed contract will fail the job at startup.

**Resolution:** fix the underlying cause (contract, dependency availability), then resubmit via `infra/job-submitter/submit_jobs.py` or `make reprocess` if a full replay is warranted.

## Downstream results look stale or wrong after a code change

**Symptoms:** `gold.*` tables or PostgreSQL serving tables reflect pre-change logic.

**Diagnosis:** Flink jobs are long-running; a code change to a job doesn't take effect until the job is resubmitted.

**Resolution:** `make reprocess` — cancels all jobs, truncates affected Postgres tables, resubmits from Kafka offset 0. This is the standard "fix and recompute" cycle in a Kappa architecture — see `rfcs/RFC-0009-failure-recovery.md`.

## Doris query returns nothing / times out

**Symptoms:** queries against Doris (`:9030`) via Cube.js or directly fail or hang.

**Diagnosis:** Doris FE/BE containers pin static IPs for internal gossip (see `rfcs/RFC-0006-security.md` and `adr/0011-doris-cubejs-federation.md`); if Docker reassigns those IPs (e.g. after a partial `docker compose down`/`up` without `-v`), Doris's internal cluster state can desync.

**Resolution:** `make down` (with `-v`) followed by `make up` for a clean restart. This wipes state, so only use it if a partial-restart desync is suspected.

## A dependent service never becomes healthy

**Symptoms:** `docker compose ps` shows a service stuck in `starting`/unhealthy, and everything depending on it (via `depends_on: condition: service_healthy`) never starts.

**Diagnosis:** check that service's own logs first. Common causes: port already in use on the host, insufficient Docker memory allocation (Flink + Doris + Postgres + MinIO together need real headroom), or a `.env` value that doesn't match what a healthcheck expects.

**Resolution:** free the port / increase Docker's memory allocation / fix the `.env` value, then `make down && make up`.
