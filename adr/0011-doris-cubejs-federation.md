<!-- markdownlint-disable -->
# ADR-0011 - Apache Doris + Cube.js as the federated query/semantic layer

- **Status:** Accepted
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; see commit `3381a6c`, same commit as the Nessie catalog revert in ADR-0007)

---

## Contexto

Analysts and BI tools need to query across both the Iceberg lakehouse (cold, historical, object-storage-backed) and the PostgreSQL serving layer (hot, low-latency aggregates) without knowing which system holds which data, and ideally through a stable semantic API rather than raw SQL against two different engines.

## Problema

How should queries be federated across Iceberg and PostgreSQL, and exposed to BI/analyst tooling?

## Alternativas

1. **Query each store directly** — analysts hit Iceberg (via some query engine) for historical data and PostgreSQL directly for serving-layer data, with no unification. Cons: analysts need to know which system holds which data; no single semantic layer; no consistent metric definitions (e.g. conversion rate) across sources.
2. **Apache Doris + Cube.js (chosen)** — Doris federates two catalogs (`lakehouse`, Iceberg via the Nessie REST catalog; `postgres`, via JDBC) into one queryable SQL engine (MySQL wire protocol, `:9030`). Cube.js sits on top as a semantic layer, defining reusable metrics (e.g. `conversion_rate = converted_sessions / NULLIF(count, 0)` across the three cubes: `session_metrics`, `product_funnel_1m`, `user_360`) and exposing a REST/SQL API + Playground (`:4000`).

## Decisão

Apache Doris for federation, Cube.js for the semantic/API layer on top of it. Introduced in the same commit as the Nessie catalog revert (ADR-0007) — a single architectural change that both fixed the catalog choice and added the federation/semantic layer.

## Consequências

- Analysts and BI tools query one system (Cube.js) with consistent metric definitions, without needing to know whether the underlying data lives in Iceberg or PostgreSQL.
- Two more services to operate (Doris FE+BE, Cube.js) — a real increase in operational surface, traded off against the value of a unified semantic layer.
- Doris's own internal gossip protocol currently depends on static container IPs (see `rfcs/RFC-0006-security.md`) — a networking convenience, not a security measure, and worth not confusing the two.
