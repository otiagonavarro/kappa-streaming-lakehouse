<!-- markdownlint-disable -->
# RFC-0007 - Observabilidade

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## Logs

No log aggregation. `docker compose logs [service]` is the only access path to service logs; nothing is shipped anywhere or retained beyond container lifetime.

## Métricas

No metrics are exported or scraped. Flink exposes its own internal metrics (visible in its Web UI at `:8081`), but nothing collects or persists them beyond that UI.

## Tracing

None. No distributed tracing is wired up across the pipeline.

## Dashboards

The only "dashboard" is Flink's built-in Web UI (`:8081`) for job status/backpressure/checkpoints — not a custom-built observability dashboard. Cube.js Playground (`:4000`) can be used ad hoc to explore query results, but it's a query tool, not a monitoring dashboard.

## Alertas

None configured.

## SLI

No SLIs are formally tracked. The closest proxy is `scripts/healthcheck.sh`'s 9 checks (see below), which are pass/fail, not measured-over-time indicators.

## SLO

None defined. The medallion contracts (`contracts/bronze/raw_events.contract.yaml`) state an SLA of 99.9% availability / 5-minute freshness for `bronze.raw_events`, but this is a contract-stated target, not an enforced or measured SLO in the running system.

## Error Budget

Not tracked — there is no SLO to budget against.

## What Actually Exists

The real observability surface in this bundle is narrower than the sections above suggest, and it's worth being explicit about what does work:

- **`scripts/healthcheck.sh`** — 9 checks: Kafka topic existence, Flink reachability, at least one RUNNING Flink job, Nessie reachability, and 5 PostgreSQL table non-empty checks. This is the closest thing to a real health/readiness surface and is used both standalone and as a dependency gate for other scripts.
- **Docker Compose healthchecks** — defined per-service (broker, minio, nessie, postgres, jobmanager, doris-fe) and used for `depends_on: condition: service_healthy` startup sequencing — an internal orchestration mechanism, not an exposed monitoring surface.

Adding real metrics/tracing/dashboards is tracked as a roadmap item (`rfcs/RFC-0010-roadmap.md`), not claimed as already done.
