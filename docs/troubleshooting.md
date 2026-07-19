<!-- markdownlint-disable -->
# Troubleshooting

| Symptom | Likely Cause | Fix |
| --- | --- | --- |
| `make check` reports a Flink job missing | `entity_sync`/`order_ingestion` are not wired into the submitter by design (see `rfcs/RFC-0010-roadmap.md`) — expected, not a bug. For one of the 5 active jobs: check `docker compose logs jobmanager` | See `docs/playbook.md#a-flink-job-is-not-running` |
| `docker compose up` fails on port conflict | Another process already bound to a port this stack needs (Kafka 9092, Flink 8081, Postgres 5432, Doris 9030, Cube.js 4000, etc.) | Stop the conflicting process or change the port mapping in `infra/compose/docker-compose.yml` |
| Services stuck `starting` and never healthy | Insufficient Docker memory allocation for Flink + Doris + Postgres + MinIO together | Increase Docker Desktop's memory limit, then `make down && make up` |
| Results look stale after changing job code | Flink jobs are long-running and don't auto-reload | `make reprocess` |
| `make demo-time-travel` fails | Script calls two helper scripts (`scripts/get-iceberg-metadata-path.py`, `scripts/count-iceberg-rows.py`) that don't exist in the repo — a known, tracked gap | See `rfcs/RFC-0010-roadmap.md`; not yet fixed |
| Doris queries hang or return nothing after a partial restart | Doris FE/BE's internal gossip protocol depends on static container IPs, which can desync after `docker compose down` without `-v` followed by `up` | `make down` (with `-v`) then `make up` for a clean restart |
| `pytest` fails with `ModuleNotFoundError: No module named 'simulator.events'` | Stale `__pycache__` or an `__init__.py` shadowing the real package (this exact bug was hit and fixed during the `bundle-structure-standard` retrofit) | `rm -rf tests/simulator/__pycache__ services/simulator/.pytest_cache` and retry |
| Simulator produces no events | `make sim-start` wasn't run, or the simulator container isn't healthy | `docker compose -f infra/compose/docker-compose.yml ps simulator`; `make sim-start` |
