<!-- markdownlint-disable -->
# Runbook

Operational procedures for `kappa-streaming-lakehouse`. All commands assume you're in the bundle root.

## Starting the Stack

```bash
make up
# equivalent to:
# cp -n .env.example .env
# docker compose -f infra/compose/docker-compose.yml up -d
```

Wait ~2 minutes for all services to report healthy, then verify:

```bash
make check
```

## Stopping the Stack

```bash
make down
# docker compose -f infra/compose/docker-compose.yml down -v
```

`-v` removes volumes — this wipes MinIO/Postgres/Nessie state. Use `docker compose -f infra/compose/docker-compose.yml stop` instead if you want to keep data across a restart.

## Controlling the Simulator

```bash
make sim-start   # start event generation
make sim-stop    # stop event generation
```

## Viewing Logs

```bash
make logs                                             # all services, follow
docker compose -f infra/compose/docker-compose.yml logs -f <service>   # one service
```

## Reprocessing (Full History Replay)

```bash
make reprocess
```

Cancels all `RUNNING` Flink jobs, truncates the affected PostgreSQL tables, and resubmits all jobs from Kafka offset 0. See `rfcs/RFC-0009-failure-recovery.md` for details and `scripts/reprocess.sh` for the implementation.

## Demos

```bash
make demo-schema-evolution   # real Iceberg ADD COLUMN demo
make demo-time-travel        # currently broken — see rfcs/RFC-0010-roadmap.md
```

## Switching to GCS

Set `STORAGE_BACKEND=gcs` and the relevant GCS credentials in `.env` before `make up`. This path is documented and code-supported but **untested** — see `rfcs/RFC-0008-scalability.md` and `adr/0006-minio-over-gcs-for-local-dev.md`.

## Job Control

The Flink REST API (`localhost:8081`) is the control surface for jobs. `infra/job-submitter` submits the 5 active jobs on stack startup; to resubmit manually, see `infra/job-submitter/submit_jobs.py`.
