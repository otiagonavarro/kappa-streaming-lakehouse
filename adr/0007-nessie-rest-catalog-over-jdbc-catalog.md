<!-- markdownlint-disable -->
# ADR-0007 - Project Nessie REST catalog over JDBC catalog

- **Status:** Accepted
- **Data:** 2026-07-19 (retroactive — decision predates this ADR; originally narrated in `docs/trade-offs.md`; the codebase went through both states, see Contexto)

---

## Contexto

Iceberg requires a catalog to track table metadata pointers. Two realistic options were exercised in this bundle's history: a simple JDBC catalog (backed by PostgreSQL) and Project Nessie's REST catalog. Commit history shows the project actually switched to a JDBC-style catalog at one point and then reverted back to Nessie (commit `3381a6c`, "revert catalog to Nessie, add Doris + Cube.js lakehouse federation") — this ADR documents the Nessie-over-JDBC decision as it stands today; ADR-0011 covers the Doris + Cube.js addition made in that same commit.

## Problema

Which Iceberg catalog implementation should the lakehouse use?

## Alternativas

1. **JDBC catalog (backed by PostgreSQL)** — simpler, one fewer service to run. Cons: no git-like branching/tagging of table state, and doesn't demonstrate the catalog patterns a reader studying this architecture would likely encounter in production (Nessie, AWS Glue, Unity Catalog, etc. all offer richer catalog semantics than plain JDBC).
2. **Project Nessie REST catalog (chosen)** — git-like branching and tagging for the entire catalog, a closer match to production-grade catalog patterns, and a genuinely educational thing to demonstrate in an architecture-bundles context. Cons: one more service to run and operate.

## Decisão

Project Nessie REST catalog, reverted back to after a period on a JDBC-style catalog.

| Criterion | Nessie (this project) | JDBC (Postgres-backed) |
| --- | --- | --- |
| Catalog branching | Yes — git-like branches/tags | No |
| Schema drift protection | Branch → merge workflow | Manual |
| Operational complexity | One extra Docker service | Zero extra service |
| Production use | Dremio cloud, Project Nessie OSS | Common in self-hosted setups |
| Multi-engine | Any Iceberg client | Any Iceberg client |

## Consequências

- Demonstrates catalog branching/tagging patterns relevant to production lakehouse deployments, aligned with this bundle's educational goal.
- Adds one more moving part to the local stack (the Nessie service itself), traded off against the demonstrative value.
- The catalog switch (JDBC → Nessie → back) is a real example of architecture evolving through use — worth keeping visible in the commit history rather than squashed away, as a demonstration that "how it evolves" (per `Architecture-Bundles-Framework.md`'s philosophy) is itself part of the case study.
