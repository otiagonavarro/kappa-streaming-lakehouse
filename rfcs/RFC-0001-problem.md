<!-- markdownlint-disable -->
# RFC-0001 - Problema

- **Status:** Accepted
- **Autor:** Tiago Ribeiro Navarro de Andrade
- **Criado em:** 2026-07-19
- **Última atualização:** 2026-07-19
- **Versão:** 1.0

---

## Contexto

E-commerce platforms generate massive volumes of clickstream events every second — page views, add-to-cart actions, purchases. Product and marketing teams need real-time answers: which products convert, how users move through funnels, which sessions are still active.

## Problema

Traditional data architectures force a trade-off between freshness and correctness:

- **Batch-first (data warehouse)** — results are accurate but stale; dashboards lag hours behind reality.
- **Lambda architecture** — runs a fast streaming path alongside a slow batch path. Two codebases must produce identical results, creating the classic dual-maintenance problem: when they diverge, which one is correct?

## Quem Sofre com Ele

Product and marketing teams who need same-session decisions (e.g. "is this promotion converting right now?"), and the data engineers maintaining two parallel codebases (streaming + batch) that are expected to agree.

## Impacto

Stale dashboards lead to decisions made on yesterday's data. Lambda's dual-codebase maintenance burden creates a recurring class of bugs: streaming and batch results silently diverging, with no single source of truth to arbitrate which is "correct."

## Como É Resolvido Hoje

Most teams pick one side of the trade-off: accept staleness (pure batch) or accept dual-maintenance risk and cost (Lambda). A smaller set adopt "streaming-first" tools but still bolt on a separate batch/backfill mechanism for reprocessing, which is Lambda in disguise.

## Limitações

- Batch-first: cannot serve real-time use cases at all.
- Lambda: doubles pipeline code, doubles infrastructure, and requires an explicit reconciliation strategy for when the two paths disagree — reconciliation logic that itself needs testing and maintenance.

## Objetivos da Solução

A single streaming pipeline (Kappa architecture) that handles both live processing and historical reprocessing through the same code path: `Kafka → Flink → Iceberg (lakehouse) + PostgreSQL (serving)`. There is no batch layer. Recomputing history means replaying the Kafka log from the beginning — the same code, the same pipeline, from offset 0 (`make reprocess`, see `scripts/reprocess.sh`).
